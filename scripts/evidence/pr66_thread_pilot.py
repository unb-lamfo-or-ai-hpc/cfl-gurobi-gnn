"""Freeze and execute a small shared-node CPU screen, never a GPU/NPAD job.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from collect_class_statistics import LICENSE, original_model
from collect_computational_ledger import canonical, digest, identity, write_json

CAPS = [1, 2, 4, 8, 16]
BASE_CONFIG = Path(__file__).resolve().parents[2] / (
    "configs/experiments/pr66_thread_screen_v1.json"
)


def strict_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("nonfinite_json")

    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("unsafe_or_oversized_json")
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=invalid,
    )


def roles_from_plan(value):
    roles = {}
    for record in value["records"]:
        parent = identity(
            record.get("parent_instance_id", record.get("source_instance_id"))
        )
        role = record.get("role")
        if not parent or role not in {"train", "validation", "test"}:
            raise ValueError("invalid_role_record")
        if parent in roles and roles[parent] != role:
            raise ValueError("conflicting_parent_roles")
        roles[parent] = role
    return roles


def draw_pair(roles, exclusions):
    """Uniform draw from sorted fitting pools, not from favorable solve outcomes."""
    rng = random.Random(42)
    pools, selected = {}, {}
    for difficulty in ("easy", "medium"):
        pool = sorted(
            parent
            for parent, role in roles.items()
            if role == "train"
            and parent.startswith(f"CFL_{difficulty}_instance_")
            and parent not in exclusions
        )
        if not pool:
            raise ValueError("empty_eligible_fitting_pool")
        pools[difficulty] = pool
        selected[difficulty] = rng.choice(pool)
    return pools, selected


def freeze(raw_root, role_plan, expected_role_sha, output):
    raw_root = Path(raw_root).resolve(strict=True)
    role_plan = Path(role_plan)
    if digest(role_plan) != expected_role_sha:
        raise ValueError("role_plan_hash_mismatch")
    config = strict_json(BASE_CONFIG)
    roles = roles_from_plan(strict_json(role_plan))
    if digest(role_plan) != expected_role_sha:
        raise ValueError("role_plan_changed")
    pools, selected = draw_pair(roles, config["frozen_optimization_test_parent_ids"])
    models = []
    for difficulty, parent in selected.items():
        path, status = original_model(
            raw_root, difficulty, int(parent.rsplit("_", 1)[1])
        )
        if status != "source_discovered":
            raise ValueError(status)
        models.append(
            {
                "source_instance_id": parent,
                "difficulty": difficulty,
                "role": "train",
                "relative_path": path.relative_to(raw_root).as_posix(),
                "original_lp_sha256": digest(path),
            }
        )
    receipt = {
        "schema_version": 1,
        "config": config,
        "config_sha256": digest(BASE_CONFIG),
        "role_plan_sha256": expected_role_sha,
        "eligible_pools": pools,
        "sampling": "python_random_Random42_choice_sorted_train_pools_easy_then_medium",
        "python_version": sys.version.split()[0],
        "models": models,
        "worker_sha256": digest(Path(__file__)),
        "optimization_runs": 0,
        "scientific_reporting_eligible": False,
    }
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(raw_root):
        raise ValueError("fresh_output_outside_raw_required")
    output.mkdir(parents=True)
    write_json(output / "pilot_plan.json", receipt)
    (output / "pilot_plan.sha256").write_text(
        digest(output / "pilot_plan.json") + "\n", encoding="ascii"
    )
    return receipt


def physical_mask(allowed, topology, required=16):
    """Accept exactly sixteen allocated physical cores; use one sibling each."""
    cores = {}
    for cpu in sorted(allowed):
        package, core = topology(cpu)
        cores.setdefault((package, core), cpu)
    if len(cores) != required:
        raise ValueError("affinity_does_not_cover_exactly_16_physical_cores")
    return sorted(cores.values())


def qualify_affinity():
    if (
        sys.platform != "linux"
        or os.environ.get("SLURM_CPUS_PER_TASK") != "16"
        or not os.environ.get("SLURM_JOB_ID", "").isdigit()
    ):
        raise ValueError("linux_slurm_16_core_allocation_required")

    def topology(cpu):
        root = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        return tuple(
            int((root / name).read_text())
            for name in ("physical_package_id", "core_id")
        )

    observed = sorted(os.sched_getaffinity(0))
    selected = physical_mask(observed, topology)
    os.sched_setaffinity(0, selected)
    if sorted(os.sched_getaffinity(0)) != selected:
        raise ValueError("affinity_binding_failed")
    return {
        "observed_cpu_ids": observed,
        "bound_cpu_ids": selected,
        "physical_cores": 16,
    }


def verified_plan(directory, expected_sha):
    directory = Path(directory)
    path = directory / "pilot_plan.json"
    if digest(path) != expected_sha:
        raise ValueError("pilot_plan_hash_mismatch")
    plan = strict_json(path)
    if (
        plan["config"] != strict_json(BASE_CONFIG)
        or plan["config_sha256"] != digest(BASE_CONFIG)
        or plan["worker_sha256"] != digest(Path(__file__))
    ):
        raise ValueError("configuration_or_worker_changed_after_freeze")
    pools, selected = draw_pair(
        {
            parent: "train"
            for pool in plan["eligible_pools"].values()
            for parent in pool
        },
        plan["config"]["frozen_optimization_test_parent_ids"],
    )
    if pools != plan["eligible_pools"] or len(plan["models"]) != 2:
        raise ValueError("invalid_frozen_cohort")
    if {m["difficulty"]: m["source_instance_id"] for m in plan["models"]} != selected:
        raise ValueError("drawn_pair_changed")
    return plan


def termination(status, gap, sol_count, target):
    if not sol_count:
        return "no_incumbent"
    if status == 2 and gap == 0:
        return "zero_reported_gap_at_solver_tolerances"
    if gap is not None and gap <= target:
        return "gap_target_reached"
    return {9: "time_limit", 17: "memory_limit"}.get(status, "other_solver_termination")


def finite(value):
    return float(value) if math.isfinite(value) else None


def attempt(plan_dir, expected_sha, raw_root, threads, difficulty):
    """One fresh process, model and environment; no checkpoint or warm start."""
    plan = verified_plan(plan_dir, expected_sha)
    if threads not in CAPS or difficulty not in {"easy", "medium"}:
        raise ValueError("attempt_not_in_frozen_matrix")
    affinity = qualify_affinity()
    if (
        os.environ.get("GRB_LICENSE_FILE", LICENSE) != LICENSE
        or not Path(LICENSE).is_file()
    ):
        raise ValueError("canonical_license_required")
    if any(
        os.environ.get(k) for k in ("GRB_WLSACCESSID", "GRB_WLSSECRET", "GRB_LICENSEID")
    ):
        raise ValueError("external_license_credentials_refused")
    os.environ["GRB_LICENSE_FILE"] = LICENSE
    import resource

    import gurobipy as gp

    config = plan["config"]
    if list(gp.gurobi.version()) != config["gurobi_version"]:
        raise ValueError("gurobi_version_changed")
    row = next(m for m in plan["models"] if m["difficulty"] == difficulty)
    path, status = original_model(
        Path(raw_root).resolve(strict=True),
        difficulty,
        int(row["source_instance_id"].rsplit("_", 1)[1]),
    )
    if status != "source_discovered" or digest(path) != row["original_lp_sha256"]:
        raise ValueError("frozen_original_model_changed")
    output = Path(plan_dir) / f"{difficulty}-threads{threads}"
    output.mkdir(exist_ok=False)
    parameters = {
        **config["fixed_parameters"],
        "Threads": threads,
        "Seed": 42,
        "TimeLimit": 300,
        "MIPGap": 0.1,
        "SoftMemLimit": config["soft_memory_limit_decimal_gb"],
    }
    started = time.perf_counter()
    before_cpu = time.process_time()
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 0)
        env.setParam("ThreadLimit", 16)
        env.start()
        with gp.read(str(path), env=env) as model:
            source_sense = model.ModelSense
            model.ModelSense = gp.GRB.MINIMIZE
            model.update()
            for key, value in parameters.items():
                model.setParam(key, value)
            if any(model.getParamInfo(k)[2] != v for k, v in parameters.items()):
                raise ValueError("effective_parameter_mismatch")
            read_setup = time.perf_counter() - started
            load_before = list(os.getloadavg())
            optimize_start = time.perf_counter()
            model.optimize()
            optimize_seconds = time.perf_counter() - optimize_start
            count = model.SolCount
            gap = finite(model.MIPGap) if count else None
            receipt = {
                **row,
                "plan_sha256": expected_sha,
                "parameters": parameters,
                "parameters_sha256": hashlib.sha256(
                    canonical(parameters).encode()
                ).hexdigest(),
                "affinity": affinity,
                "source_objective_sense": "MINIMIZE"
                if source_sense == 1
                else "MAXIMIZE",
                "effective_objective_sense": "MINIMIZE",
                "solver_status": model.Status,
                "solution_count": count,
                "primal": finite(model.ObjVal) if count else None,
                "dual": finite(model.ObjBound),
                "mip_gap_relative": gap,
                "termination": termination(model.Status, gap, count, 0.1),
                "model_read_setup_seconds": read_setup,
                "optimize_wall_seconds": optimize_seconds,
                "solver_runtime_seconds": model.Runtime,
                "node_count": model.NodeCount,
                "process_cpu_seconds": time.process_time() - before_cpu,
                "process_peak_rss_bytes": resource.getrusage(
                    resource.RUSAGE_SELF
                ).ru_maxrss
                * 1024,
                "slurm_job_id": os.environ["SLURM_JOB_ID"],
                "gurobi_version": list(gp.gurobi.version()),
                "shared_node": True,
                "system_load_average_before": load_before,
                "system_load_average_after": list(os.getloadavg()),
                "process_cpu_scope": "since_environment_setup_excluding_import_and_source_hashing",
                "scientific_reporting_eligible": False,
            }
    receipt["model_unchanged_after_execution"] = (
        digest(path) == row["original_lp_sha256"]
    )
    write_json(output / "attempt_report.json", receipt)
    if not receipt["model_unchanged_after_execution"]:
        raise ValueError("source_changed_preserve_attempt_report")


def run(plan_dir, expected_sha, raw_root):
    verified_plan(plan_dir, expected_sha)
    affinity = qualify_affinity()
    plan_dir = Path(plan_dir)
    report_path = plan_dir / "pilot_execution_report.json"
    if report_path.exists() or any(plan_dir.glob("*-threads*")):
        raise ValueError("pilot_already_started_no_automatic_rerun")
    started = time.perf_counter()
    executions = []
    failure = None
    try:
        for threads in CAPS:
            for difficulty in ("easy", "medium"):
                print(f"PR66_ATTEMPT={difficulty} THREADS={threads}", flush=True)
                name = f"{difficulty}-threads{threads}"
                execution = {"attempt": name, "exit_code": None, "report_sha256": None}
                executions.append(execution)
                with (plan_dir / f"{name}.private.log").open("xb") as log:
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(Path(__file__).resolve()),
                            "attempt",
                            "--plan-dir",
                            str(plan_dir),
                            "--expected-plan-sha",
                            expected_sha,
                            "--raw-root",
                            str(raw_root),
                            "--threads",
                            str(threads),
                            "--difficulty",
                            difficulty,
                        ],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=480,
                        check=False,
                    )
                artifact = plan_dir / name / "attempt_report.json"
                execution.update(
                    exit_code=result.returncode,
                    report_sha256=digest(artifact) if artifact.is_file() else None,
                )
                if result.returncode:
                    raise ValueError("attempt_failed_preserve_private_log")
                if strict_json(artifact)["solver_status"] not in {2, 9}:
                    raise ValueError("resource_or_solver_stop_pause_remaining_matrix")
    except Exception as error:
        failure = type(error).__name__
        raise
    finally:
        write_json(
            report_path,
            {
                "plan_sha256": expected_sha,
                "affinity": affinity,
                "executions": executions,
                "failure_type": failure,
                "wall_seconds": time.perf_counter() - started,
                "scientific_reporting_eligible": False,
            },
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "attempt"))
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--role-plan", type=Path)
    parser.add_argument("--expected-role-sha")
    parser.add_argument("--expected-plan-sha")
    parser.add_argument("--threads", type=int)
    parser.add_argument("--difficulty", choices=("easy", "medium"))
    args = parser.parse_args()
    if args.action == "freeze":
        if not args.role_plan or not args.expected_role_sha:
            parser.error("freeze requires --role-plan and --expected-role-sha")
        freeze(args.raw_root, args.role_plan, args.expected_role_sha, args.plan_dir)
        print("PR66_PAIR_AND_PROFILE_FROZEN_NO_OPTIMIZATION")
    elif args.action == "run":
        run(args.plan_dir, args.expected_plan_sha, args.raw_root)
    else:
        attempt(
            args.plan_dir,
            args.expected_plan_sha,
            args.raw_root,
            args.threads,
            args.difficulty,
        )
