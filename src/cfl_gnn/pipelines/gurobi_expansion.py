"""Immutable, Gurobi-only eight-hour pilot for the remaining CFL population.

This module measures an empirical budget; it does not infer runtime from the
MILPBench pickle files or certify completion of the ninety-parent dataset.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import time
from pathlib import Path

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.pipelines import confirmation_execution as c
from cfl_gnn.pipelines import confirmation_revision as revision
from cfl_gnn.pipelines import parent_solutions as parent
from cfl_gnn.splits.instance_folds import build_planned_manifest, read_manifest, role_for_fold
from cfl_gnn.validation.mathematical import audit_gurobi_solution, common_gap

PLAN = "gurobi_expansion_plan.json"
TASK_REPORT = "gurobi_expansion_task_report.json"
REPORT = "gurobi_expansion_audit_report.json"
PILOT = ("CFL_medium_instance_3", "CFL_hard_instance_0")
REGIONS = ("total_wall_time_seconds", "data_read_wall_time_seconds",
           "model_build_wall_time_seconds", "model_optimize_wall_time_seconds")
POLICY = {"schema_version": 1, "protocol": "gurobi_90_expansion_pilot_v1",
          "solver": "gurobi", "objective_sense": "MINIMIZE", "seed": 42,
          "rotation": 0, "time_limit_seconds": 28800, "node_limit": 1000000,
          "threads": 1, "maximum_label_mip_gap_relative": .1,
          "warm_start": False, "planned_parent_population": 90,
          "preserved_parent_population": 39, "pending_parent_population": 51,
          "pilot_parent_ids": list(PILOT), "runtime_source": "empirically_measured",
          "development_only": True, "scientific_reporting_eligible": False}


def implementations():
    """Bind plans to the collection, validation and configuration implementations."""
    paths = ["src/cfl_gnn/pipelines/gurobi_expansion.py",
             "src/cfl_gnn/pipelines/scip_parent_solutions.py",
             "src/cfl_gnn/solvers/gurobi_solution.py",
             "src/cfl_gnn/pipelines/gurobi_incumbents.py",
             "src/cfl_gnn/solvers/pyscipopt_solution.py",
             "src/cfl_gnn/validation/mathematical.py",
             "configs/experiments/mvp_partial_v1.json",
             "configs/splits/cfl_90_seed42_folds.csv"]
    return {p: c.sha256_file(PROJECT_ROOT / p) for p in paths}


def scoped(data, path, subtree):
    data, path = Path(data).resolve(), Path(path).resolve()
    allowed = data / subtree
    if not path.is_relative_to(allowed) or path == allowed:
        raise ValueError("output must be a dedicated directory within the campaign subtree")
    return path


def new_directory(path):
    """Never reuse an output directory, even if the previous process was killed."""
    path.mkdir(parents=True, exist_ok=False)


def read_solution(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("solution must be a JSON object")
    return value


def prepare(data_root, source_campaign_dir, revision_dir, campaign_dir):
    data, source = Path(data_root).resolve(), Path(source_campaign_dir).resolve()
    output = scoped(data, campaign_dir, "analysis/gurobi_expansion")
    approved, _, _, rows = revision.load(source, revision_dir)
    if len(rows) != 39 or {r["source_instance_id"] for r in rows} != set(revision.COHORT):
        raise ValueError("approved thirty-nine-parent cohort required")
    entries = read_manifest(PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv")
    if entries != build_planned_manifest(seed=42):
        raise ValueError("canonical ninety-parent split changed")
    old = {r["source_instance_id"]: r for r in rows}
    inventory, preserved = [], []
    for e in entries:
        stem = f"raw/MILPBench/CFL/{e.category}/LP/{e.source_instance_id}.lp"
        candidates = [c.safe_path(data, stem + suffix) for suffix in (".gz", "")]
        candidates = [p for p in candidates if p.is_file() and p.stat().st_size]
        if len(candidates) != 1:
            raise ValueError("each parent requires exactly one nonempty original LP or LP gzip")
        mip = c.descriptor(data, candidates[0])
        record = {"source_instance_id": e.source_instance_id, "category": e.category,
                  "difficulty": e.difficulty, "fold": e.fold, "role": role_for_fold(e.fold, 0),
                  "mip": mip, "disposition": "preserved" if e.source_instance_id in old else "pending"}
        inventory.append(record)
        if e.source_instance_id in old:
            row = old[e.source_instance_id]
            if row["mip"] != mip:
                raise ValueError("preserved source MIP differs from the approved cohort")
            solution = c.checked(source, row["solution"])
            report = c.checked(source, row["report"])
            payload = read_solution(solution)
            if (payload.get("source_instance_id") != e.source_instance_id
                    or payload.get("source_mip_sha256") != mip["sha256"]
                    or payload.get("solution_source") != "independently_audited_gurobi_confirmation_label"
                    or payload.get("effective_objective_sense") != "MINIMIZE"
                    or payload.get("mathematical_audit", {}).get("valid") is not True
                    or not c.eligible_gap(payload.get("mip_gap_relative"))):
                raise ValueError("preserved label failed its existing admission receipt")
            preserved.append({**record, "solution": c.descriptor(data, solution),
                              "report": c.descriptor(data, report)})
    pending = [r for r in inventory if r["disposition"] == "pending"]
    by_id = {r["source_instance_id"]: r for r in pending}
    tasks = [{**by_id[identity], "task_index": i,
              "run_relative_path": f"budget_28800s/gurobi/{by_id[identity]['category']}/{identity}"}
             for i, identity in enumerate(PILOT)]
    if len(pending) != 51:
        raise ValueError("pending population differs from the precommitted expansion")
    payload = {**POLICY, "implementation_sha256": implementations(),
               "source_revision_contract_sha256": approved["contract_sha256"],
               "source_revision": c.descriptor(data, Path(revision_dir) / revision.NAME),
               "inventory": inventory, "preserved": preserved, "tasks": tasks,
               "historical_runtime_policy": "retain_original_records_never_invent_missing_times",
               "time_regions": list(REGIONS), "dataset_eligible": False}
    result = {**payload, "contract_sha256": c.canonical_sha256(payload)}
    new_directory(output)
    c.write_json(output / PLAN, result)
    return result


def load_plan(campaign_dir):
    value = c.read_json(Path(campaign_dir) / PLAN)
    payload = {k: v for k, v in value.items() if k != "contract_sha256"}
    if (c.canonical_sha256(payload) != value.get("contract_sha256")
            or any(value.get(k) != v for k, v in POLICY.items())
            or value.get("implementation_sha256") != implementations()
            or [r["source_instance_id"] for r in value["tasks"]] != list(PILOT)
            or [r["task_index"] for r in value["tasks"]] != [0, 1]):
        raise ValueError("pilot contract or implementation changed")
    return value


def verify_sources(data, plan):
    c.checked(data, plan["source_revision"])
    for row in plan["preserved"]:
        for key in ("mip", "solution", "report"):
            c.checked(data, row[key])


def independently_audit(mip, payload):
    """Validate the final vector against the original MIP without optimization."""
    import gurobipy as gp
    variables = payload["variables"]
    named = {v["name"]: v["value"] for v in variables}
    if len(named) != len(variables):
        raise ValueError("duplicate solution variable identity")
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 0)
        env.start()
        with gp.read(str(mip), env=env) as model:
            model.ModelSense = gp.GRB.MINIMIZE
            model.update()
            result = audit_gurobi_solution(model, named, payload["solution_objective"])
    gap = common_gap(result["recomputed_objective"], payload.get("best_bound"))
    reported = payload.get("mip_gap_relative")
    result["gap_consistent"] = (gap is not None and reported is not None
        and math.isclose(gap, reported, rel_tol=1e-5, abs_tol=1e-8))
    bound = payload.get("best_bound")
    result["minimization_bound_consistent"] = (bound is not None
        and bound <= result["recomputed_objective"] + 1e-6)
    result["valid"] = (result["valid"] and result["gap_consistent"]
                       and result["minimization_bound_consistent"])
    return result


def classify(report, payload, mathematical):
    """Separate technical validity, censoring and label admission."""
    checks = dict(report["checks"])
    count = payload.get("solution_count", 0)
    status = payload.get("solve_status")
    censored = status in {"timelimit", "nodelimit"}
    if count == 0 and (censored or status == "infeasible"):
        # Absence of a feasible vector is an outcome, not an exception. Retain
        # identity, callback, stream, timing and environment checks unchanged.
        for key in ("feasible_solution", "online_incumbent_observed", "trace_consistent",
                    "named_solution_present", "terminal_gap_finite"):
            checks.pop(key, None)
    checks["supported_terminal_status"] = status in {"optimal", "timelimit", "nodelimit", "infeasible"}
    checks["independent_solution_valid"] = mathematical.get("valid") is True if count else not payload.get("variables")
    valid = all(v is True for v in checks.values())
    admitted = valid and count > 0 and c.eligible_gap(payload.get("mip_gap_relative"))
    reason = ("label_admitted" if admitted else "technical_or_mathematical_audit_failed" if not valid
              else "no_feasible_solution_observed" if count == 0 else "gap_above_admission_threshold")
    return {"execution_valid": valid, "label_eligible": admitted,
            "right_censored": censored, "reason_code": reason, "checks": checks}


def seal(value):
    return {**value, "receipt_sha256": c.canonical_sha256(value)}


def verify_receipt(output, plan, task):
    value = c.read_json(output / TASK_REPORT)
    payload = {k: v for k, v in value.items() if k != "receipt_sha256"}
    if (c.canonical_sha256(payload) != value.get("receipt_sha256")
            or value.get("campaign_contract_sha256") != plan["contract_sha256"]
            or value.get("source_instance_id") != task["source_instance_id"]
            or value.get("mip_sha256") != task["mip"]["sha256"]):
        raise ValueError("task receipt identity or hash mismatch")
    for artifact in value.get("artifacts", {}).values():
        c.checked(output, artifact)
    return value


def execute(data_root, campaign_dir, run_root, task_index):
    data = Path(data_root).resolve()
    root = scoped(data, run_root, "intermediate/gurobi_expansion")
    plan = load_plan(campaign_dir)
    if task_index not in (0, 1):
        raise ValueError("pilot task index must be zero or one")
    task = plan["tasks"][task_index]
    verify_sources(data, plan)
    mip = c.checked(data, task["mip"])
    output = c.safe_path(root, task["run_relative_path"])
    if (output / TASK_REPORT).is_file():
        result = verify_receipt(output, plan, task)
        if result.get("execution_valid") is not True:
            raise ValueError("failed attempt retained; use a new run root for a reviewed retry")
        return result
    # Atomic directory creation is also the per-task lock. A killed task leaves
    # evidence in place and cannot silently restart or overwrite it.
    solve = parent.build_plan(parent_mip=mip, output_dir=output,
        parent_instance_id=task["source_instance_id"], category=task["category"],
        difficulty=task["difficulty"], fold=task["fold"], config_path=parent.DEFAULT_CONFIG,
        time_limit=plan["time_limit_seconds"], node_limit=plan["node_limit"], seed=42,
        threads=1, solver_profile="default", solver="gurobi")
    if solve.role != task["role"] or solve.maximum_admissible_relative_gap != .1:
        raise ValueError("collector configuration differs from campaign policy")
    new_directory(output)
    started = time.perf_counter()
    base = {"schema_version": 1, "campaign_contract_sha256": plan["contract_sha256"],
            "source_instance_id": task["source_instance_id"], "role": task["role"],
            "fold": task["fold"], "difficulty": task["difficulty"],
            "mip_sha256": task["mip"]["sha256"], "solver": "gurobi",
            "budget_seconds": 28800, "dataset_eligible": False,
            "scientific_reporting_eligible": False}
    artifacts = {}
    try:
        summary = solve.to_summary()
        summary["outputs"].pop("legacy_plan_alias", None)
        summary["outputs"].pop("legacy_report_alias", None)
        c.write_json(output / parent.plan_name("gurobi"), summary)
        report = parent.run(solve)
        c.write_json(output / parent.report_name("gurobi"), report)
        for name in (parent.plan_name("gurobi"), parent.report_name("gurobi"),
                     parent.SOLUTION_NAME, parent.INCUMBENTS_NAME, parent.VARIABLE_ORDER_NAME):
            artifacts[name] = c.descriptor(output, output / name)
        payload = read_solution(output / parent.SOLUTION_NAME)
        parameters = payload.get("solver_parameter_map", {})
        report["checks"]["worker_contract_matches"] = payload.get("contract_sha256") == solve.contract_sha256
        report["checks"]["effective_budget_matches"] = all(parameters.get(k) == v for k, v in {
            "TimeLimit": 28800, "NodeLimit": 1000000, "Threads": 1, "Seed": 42, "ModelSense": 1}.items())
        report["checks"]["parameter_hash_valid"] = payload.get("solver_parameter_sha256") == c.canonical_sha256(parameters)
        mathematical = (independently_audit(mip, payload) if payload.get("solution_count", 0) > 0
                        else {"valid": None, "reason_code": "no_vector_to_audit"})
        result = {**base, **classify(report, payload, mathematical),
                  "mathematical_audit": mathematical, "solve": report["solve"],
                  "time_regions": report["time_regions"],
                  "time_region_semantics": report["time_region_semantics"],
                  "solver_versions": report["solver_versions"],
                  "solver_parameter_sha256": report["solver_parameter_sha256"],
                  "online_incumbent_capture": report["online_incumbent_capture"]}
    except Exception as error:
        # Do not serialize exception text: solver errors can contain paths,
        # license details or credentials. Raw Slurm logs remain local evidence.
        result = {**base, "execution_valid": False, "label_eligible": False,
                  "right_censored": None, "reason_code": "worker_or_audit_exception",
                  "error_type": type(error).__name__}
    result.update(artifacts=artifacts, task_wall_time_seconds=time.perf_counter() - started,
        task_wall_time_semantics="collection_export_and_independent_audit_before_receipt_write",
        historical_cumulative_runtime_seconds=None,
        historical_cost_policy="not_reconstructed_do_not_treat_unknown_as_zero")
    result = seal(result)
    c.write_json(output / TASK_REPORT, result)
    return result


def audit(data_root, campaign_dir, run_root, output_dir):
    data = Path(data_root).resolve()
    root = scoped(data, run_root, "intermediate/gurobi_expansion")
    output = scoped(data, output_dir, "analysis/gurobi_expansion")
    plan = load_plan(campaign_dir)
    verify_sources(data, plan)
    records = []
    for task in plan["tasks"]:
        c.checked(data, task["mip"])
        folder = c.safe_path(root, task["run_relative_path"])
        try:
            receipt = verify_receipt(folder, plan, task)
            records.append({**receipt, "task_receipt": c.descriptor(data, folder / TASK_REPORT)})
        except (ValueError, OSError, KeyError, TypeError):
            records.append({"source_instance_id": task["source_instance_id"],
                            "execution_valid": False, "label_eligible": False,
                            "reason_code": "missing_or_invalid_receipt"})
    valid = sum(r["execution_valid"] is True for r in records)
    admitted = sum(r["label_eligible"] is True for r in records)
    new_directory(output)
    c.write_json(output / "pilot_task_metrics.json", {"records": records})
    columns = ["source_instance_id", "execution_valid", "label_eligible", "right_censored",
               "reason_code", "solve_status", "mip_gap_relative", "execution_time_seconds",
               *REGIONS, "task_wall_time_seconds"]
    with (output / "pilot_runtime_outcomes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in records:
            flattened = {**row, **row.get("solve", {}), **row.get("time_regions", {})}
            writer.writerow({k: flattened.get(k) for k in columns})
    result = {"schema_version": 1, "contract_sha256": plan["contract_sha256"],
              "gate_status": "passed" if valid == 2 else "failed",
              "summary": {"planned_tasks": 2, "valid_tasks": valid,
                          "failed_or_missing_tasks": 2 - valid, "new_labels_admitted": admitted,
                          "preserved_labels": 39, "admitted_population": 39 + admitted,
                          "unresolved_population": 51 - admitted,
                          "right_censored_tasks": sum(r.get("right_censored") is True for r in records)},
              "eligibility": {"dataset_eligible": False, "development_only": True,
                              "scientific_reporting_eligible": False},
              "decision": {"next_gate": "review_pilot_resources_and_remaining_campaign",
                           "full_campaign_authorized_by_this_report": False},
              "outputs": {n: c.descriptor(output, output / n)
                          for n in ("pilot_task_metrics.json", "pilot_runtime_outcomes.csv")}}
    c.write_json(output / REPORT, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "task", "audit"):
        p = commands.add_parser(name)
        p.add_argument("--data_root", required=True, type=Path)
        p.add_argument("--campaign_dir", required=True, type=Path)
        if name == "prepare":
            p.add_argument("--source_campaign_dir", required=True, type=Path)
            p.add_argument("--revision_dir", required=True, type=Path)
        else:
            p.add_argument("--run_root", required=True, type=Path)
            if name == "task":
                p.add_argument("--task_index", required=True, type=int)
            else:
                p.add_argument("--output_dir", required=True, type=Path)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = {"prepare": prepare, "task": execute, "audit": audit}[command](**args)
    except Exception as error:
        print(f"[ERROR] {c.error_reason(error)} ({type(error).__name__})")
        return 2
    if command == "prepare":
        print(f"[INFO] contract={result['contract_sha256']} | preserved=39 | pending=51 | pilot=2 | MINIMIZE | time_limit=28800")
        return 0
    ok = result.get("execution_valid") is True if command == "task" else result["gate_status"] == "passed"
    print(f"[INFO] {command} | execution_valid={ok} | dataset_eligible=false")
    return 0 if ok else 1
