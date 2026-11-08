#!/usr/bin/env python3
"""One explicitly admitted H25 technical pilot, isolated from research runs."""

import argparse
import gzip
import json
import os
import re
import shlex
import sys
from pathlib import Path

import pr98_hard_inputs as inputs

GIB = 1024**3
THREADS = 4
SOLVER_SECONDS = 120
ROOT_DEADLINE = 1440
SOLVE_DEADLINE = 300
PROFILES = (1, 2)
ORDER = ("M0", "M1", "M2")
PILOT_SCOPE = "technical_only_not_campaign_evidence"
BUDGET = {
    "instance": inputs.PILOT,
    "seed": 42,
    "threads": THREADS,
    "ConcurrentMIP": list(PROFILES),
    "root_calls": 1,
    "root_solver_seconds": 600,
    "forward_calls": 1,
    "pilot_solve_calls": 6,
    "seconds_per_solve": SOLVER_SECONDS,
    "physical_cores_reserved": 4,
    "memory_gib_reserved": 64,
    "V100s_reserved": 1,
    "wall_seconds_reserved": 3600,
    "automatic_retry": False,
}
ARTIFACTS = {
    "root_sha256": "root.private.json.gz",
    "graph_sha256": "graph.private.pt",
    "prediction_sha256": "predictions.private.json",
    "private_starts_sha256": "starts.private.json",
}
need = inputs.require


def admitted(stage, accepted):
    preflight = stage / "preflight.json"
    need(inputs.digest(preflight) == accepted, "preflight_hash")
    report = inputs.read(preflight)
    need(report["source_commit"] == inputs.source_commit(), "installed_source")
    need(
        inputs.digest(stage / "inputs.private.json") == report["private_inputs_sha256"],
        "input_manifest",
    )
    need(report["pilot_input_matched"], "pilot_model_not_qualified")
    config = inputs.read(stage / "inputs.private.json")
    row = config["models"][inputs.PILOT]
    need(row["parent"] == "CFL_hard_instance_25", "pilot_parent")
    model = inputs.data_file(Path(row["model"]), inputs.DATA)
    archive_size, archive_hash = inputs.ARCHIVE[inputs.PILOT]
    need(
        model.stat().st_size == archive_size
        and inputs.digest(model) == row["model_sha256"] == archive_hash,
        "pilot_model_hash",
    )
    checkpoint = inputs.data_file(Path(config["checkpoint"]), inputs.DATA)
    need(inputs.digest(checkpoint) == inputs.CHECKPOINT, "checkpoint_hash")
    return row, model, checkpoint


def clean_env():
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in {"PYTHONHOME", "PYTHONPATH"}
    }


def submit(stage, accepted, decision):
    from pr94_isolated_preparation import command, held_profile, storage, versions

    need(decision.strip(), "explicit_pilot_decision_required")
    admitted(stage, accepted)
    environment = versions()
    storage(stage, admission=True)
    approval = {
        "preflight_sha256": accepted,
        "budget": BUDGET,
        "decision": decision,
        "versions": environment,
        "scope": PILOT_SCOPE,
    }
    # Global, write-once claim survives a partial/ambiguous sbatch and new stage creation.
    inputs.write_once(inputs.EVIDENCE / "pr98-h25-technical-pilot.claim.json", approval)
    inputs.write_once(stage / "pilot-approval.json", approval)
    batch = shlex.join(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "batch",
            str(stage),
            accepted,
        ]
    )
    response = command(
        [
            "sbatch",
            "--parsable",
            "--hold",
            "--no-requeue",
            "--partition=batch",
            "--nodes=1-1",
            "--ntasks=1",
            "--cpus-per-task=4",
            "--hint=nomultithread",
            "--mem=64G",
            "--gres=gpu:1",
            "--time=01:00:00",
            "--job-name=cfl_pr98_H25",
            "--chdir=" + str(inputs.ROOT),
            "--output=" + str(stage / "pilot-%j.private.out"),
            "--error=" + str(stage / "pilot-%j.private.err"),
            "--wrap=" + batch,
        ],
        env=clean_env(),
    )
    inputs.write_once(stage / "pilot-sbatch.private.json", {"response": response})
    job = response.split(";", 1)[0]
    need(re.fullmatch(r"[0-9]+", job), "ambiguous_submission_preserve_claim")
    submission = {"job_id": job, "preflight_sha256": accepted, "scope": PILOT_SCOPE}
    inputs.write_once(stage / "pilot-submission.json", submission)
    profile = held_profile(
        command(["scontrol", "show", "job", job, "-o"]), job, "guidance"
    )
    inputs.write_once(stage / "pilot-held-profile.private.json", profile)
    command(["scontrol", "release", job])
    print(json.dumps(submission, sort_keys=True))


def runtime_admission(stage, accepted):
    from pr94_isolated_preparation import allocation, versions

    approval = inputs.read(stage / "pilot-approval.json")
    need(
        inputs.read(inputs.EVIDENCE / "pr98-h25-technical-pilot.claim.json") == approval
        and approval["preflight_sha256"] == accepted
        and approval["budget"] == BUDGET
        and approval["versions"] == versions(),
        "pilot_approval",
    )
    job, gate, allocation_receipt = allocation("guidance", stage)
    need(
        inputs.read(stage / "pilot-submission.json")
        == {"job_id": job, "preflight_sha256": accepted, "scope": PILOT_SCOPE},
        "job_identity",
    )
    return job, gate, allocation_receipt


def intent(folder, name, gate):
    need(gate.sample() < 56 * GIB, "memory_before_call")
    inputs.write_once(folder / (name + ".intent.json"), {"maximum_calls": 1})


def prepare(folder, model, row, checkpoint, gate):
    import pr94_isolated_preparation as prior
    import pr94_preparation_science as science
    import torch

    need(
        torch.cuda.is_available() and torch.cuda.device_count() == 1,
        "one_V100_required",
    )
    props = torch.cuda.get_device_properties(0)
    need(
        "V100" in props.name
        and torch.cuda.get_device_capability(0) == (7, 0)
        and props.total_memory >= 30 * GIB,
        "V100_32GB_required",
    )
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    torch.set_num_threads(1)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    root = science.capture(
        model, row["model_sha256"], folder, lambda: intent(folder, "root", gate)
    )
    path = folder / ARTIFACTS["root_sha256"]
    with path.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as zipped:
            zipped.write(prior.encoded(root))
        prior.sync(stream)
    binding = {**row, "root_sha256": inputs.digest(path)}
    del binding["model"]
    for key in (
        "variable_order_sha256",
        "vector_sha256",
        "solver_parameter_sha256",
        "mathematical_signature_sha256",
        "variable_count",
    ):
        binding[key] = root[key]
    del root
    root = prior.read_root(path, binding)
    device = torch.device("cuda:0")
    network = science.checkpoint_model(checkpoint, device)
    artifact = science.guidance_one(
        row["parent"],
        binding,
        model,
        root,
        network,
        device,
        folder,
        lambda: intent(folder, "forward", gate),
    )
    inputs.write_once(
        folder / "artifact-receipt.json",
        {
            **binding,
            **artifact,
            "root_optimization_calls": 1,
            "scope": PILOT_SCOPE,
            "GPU_name": props.name,
            "GPU_total_memory_bytes": props.total_memory,
            "effective_objective_sense": "MINIMIZE",
        },
    )


def verify_artifacts(folder, row):
    from pr94_evaluation_contract import validate_start

    receipt = inputs.read(folder / "artifact-receipt.json")
    need(
        receipt["parent"] == row["parent"]
        and receipt["model_sha256"] == row["model_sha256"]
        and receipt["checkpoint_sha256"] == inputs.CHECKPOINT,
        "artifact_identity",
    )
    need(
        receipt["root_optimization_calls"] == receipt["forward_calls"] == 1
        and receipt["training_calls"] == 0
        and receipt["labels_loaded"] is False
        and receipt["graph_round_trip"] is True
        and receipt["effective_objective_sense"] == "MINIMIZE",
        "artifact_lineage",
    )
    for key, name in ARTIFACTS.items():
        path = folder / name
        need(
            path.is_file()
            and not path.is_symlink()
            and inputs.digest(path) == receipt[key],
            "artifact_bytes_" + key,
        )
    starts = inputs.read(folder / ARTIFACTS["private_starts_sha256"])
    validate_start(receipt, starts)
    return receipt, starts


class Policy:
    THRESHOLDS = ()
    ALLOW_ABSTENTION = True
    RECORD_PROGRESS = False

    @staticmethod
    def parameters(cell):
        from pr94_evaluation_contract import baseline_parameters

        return {
            **baseline_parameters(),
            "Threads": THREADS,
            "Seed": 42,
            "ConcurrentMIP": cell["concurrent"],
            "TimeLimit": SOLVER_SECONDS,
            "MIPGap": 1e-4,
            "SoftMemLimit": 48,
        }

    @staticmethod
    def Recorder():
        return None


def solve_cell(folder, model, row, gate, concurrent, method):
    from pr94_evaluation_solver import solve

    # The encompassing allocation holds a GPU for preparation. The solver child cannot use it.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    receipt, starts = verify_artifacts(folder / "preparation", row)
    need(not receipt["abstained"], "pilot_cannot_validate_Start_delivery_on_abstention")
    trial = folder / f"c{concurrent}-{method}"
    trial.mkdir()
    chosen = (
        None
        if method == "M0"
        else starts["root_lp" if method == "M1" else "gnn"]["assignments"]
    )
    result = solve(
        model,
        row["model_sha256"],
        [],
        "unguided_control" if chosen is None else "partial_mip_start",
        preselected_assignments=chosen,
        reported_method=method,
        private_log_path=trial / "gurobi.private.log",
        solution_path=trial / "solution.private.json.gz",
        cell={
            "method": method,
            "seed": 42,
            "concurrent": concurrent,
            "model_sha256": row["model_sha256"],
        },
        before_optimize=lambda: intent(trial, "solve", gate),
        execution_policy=Policy,
    )
    inputs.write_once(trial / "result.private.json", result)
    need(result["gate_status"] == "passed", "pilot_solver_gate")
    expected_count = 0 if method == "M0" else receipt["selected_support"]
    need(
        result["start"]["submitted_assignments"] == expected_count,
        "pilot_Start_support",
    )
    if method != "M0":
        need(
            result["start"]["assignment_sha256"]
            == receipt[method + "_assignment_sha256"],
            "pilot_Start_hash",
        )


def batch(stage, accepted):
    import resource

    from paired_memory_runtime_v2 import supervise

    admitted(stage, accepted)
    job, gate, allocation = runtime_admission(stage, accepted)
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * inputs.CHUNK, 512 * inputs.CHUNK))
    folder = stage / "run" / "pilot"
    folder.mkdir(parents=True)
    inputs.write_once(
        folder / "batch.json",
        {"job_id": job, "allocation": allocation, "preflight_sha256": accepted},
    )
    command = [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "child",
        str(stage),
        accepted,
    ]

    def step(key, seconds, args):
        observed = supervise(
            command + args, folder / (key + ".console.private.log"), seconds, gate
        )
        # Detailed diagnostics are private. No console or model paths go in the receipt.
        inputs.write_once(folder / (key + ".supervision.private.json"), observed)
        need(
            observed["guard_stop"] is None and observed["child_exit_code"] == 0,
            "pilot_child_failed_preserve_evidence",
        )

    step("preparation", ROOT_DEADLINE, ["prepare"])
    for concurrent in PROFILES:
        for method in ORDER:
            step(
                f"c{concurrent}-{method}",
                SOLVE_DEADLINE,
                ["solve", "--concurrent", str(concurrent), "--method", method],
            )
    inputs.write_once(folder / "complete.json", {"job_id": job, "scope": PILOT_SCOPE})


def child(stage, accepted, args):
    row, model, checkpoint = admitted(stage, accepted)
    _, gate, _ = runtime_admission(stage, accepted)
    folder = stage / "run" / "pilot"
    need(folder.is_dir() and not folder.is_symlink(), "pilot_run_folder")
    if args.kind == "prepare":
        prep = folder / "preparation"
        prep.mkdir()
        prepare(prep, model, row, checkpoint, gate)
    else:
        need(args.concurrent in PROFILES and args.method in ORDER, "pilot_cell")
        solve_cell(folder, model, row, gate, args.concurrent, args.method)


def report(stage, accepted):
    from pr94_isolated_preparation import accounting

    row, _, _ = admitted(stage, accepted)
    job = accounting(stage, "pilot")
    need(job["terminal"], "pilot_accounting_not_terminal")
    folder = stage / "run" / "pilot"
    receipt = None
    if (folder / "preparation" / "artifact-receipt.json").exists():
        receipt, _ = verify_artifacts(folder / "preparation", row)
    cells = []
    for concurrent in PROFILES:
        for method in ORDER:
            cell = folder / f"c{concurrent}-{method}"
            supervision = folder / f"c{concurrent}-{method}.supervision.private.json"
            data = inputs.read(supervision) if supervision.exists() else {}
            result = cell / "result.private.json"
            record = {
                "ConcurrentMIP": concurrent,
                "method": method,
                "intent_recorded": (cell / "solve.intent.json").exists(),
                "sampled_cgroup_peak_bytes": data.get("sampled_cgroup_peak_bytes"),
                "guard_stop": data.get("guard_stop"),
                "child_exit_code": data.get("child_exit_code"),
            }
            if result.exists():
                value = inputs.read(result)
                need(
                    value["parameters"]
                    == Policy.parameters({"concurrent": concurrent}),
                    "terminal_effective_parameters",
                )
                need(
                    receipt is not None
                    and value["mathematical_signature_sha256"]
                    == receipt["mathematical_signature_sha256"],
                    "terminal_root_and_solver_model_signature",
                )
                record.update(
                    {
                        "gate_status": value["gate_status"],
                        "solver_status": value["solve"]["solve_status_code"],
                        "solver_runtime_seconds": value["solve"][
                            "solver_runtime_seconds"
                        ],
                        "Start_submitted": value["start"]["submitted_assignments"],
                        "Start_message_scope": "first_racer"
                        if concurrent > 1
                        else "conventional",
                        "result_sha256": inputs.digest(result),
                    }
                )
            cells.append(record)
    prep = folder / "preparation.supervision.private.json"
    prepared = inputs.read(prep) if prep.exists() else {}
    out = {
        "accounting": job,
        "preflight_sha256": accepted,
        "artifact_receipt": receipt,
        "preparation_sampled_cgroup_peak_bytes": prepared.get(
            "sampled_cgroup_peak_bytes"
        ),
        "preparation_guard_stop": prepared.get("guard_stop"),
        "root_intent": (folder / "preparation" / "root.intent.json").exists(),
        "forward_intent": (folder / "preparation" / "forward.intent.json").exists(),
        "cells": cells,
        "scope": PILOT_SCOPE,
        "complete_marker": (folder / "complete.json").exists(),
    }
    print(json.dumps(out, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    commands = {
        name: subs.add_parser(name) for name in ("submit", "batch", "child", "report")
    }
    for sub in commands.values():
        sub.add_argument("stage", type=Path)
        sub.add_argument("preflight_sha256")
    commands["submit"].add_argument("--decision", required=True)
    commands["child"].add_argument("kind", choices=("prepare", "solve"))
    commands["child"].add_argument("--concurrent", type=int)
    commands["child"].add_argument("--method", choices=ORDER)
    args = parser.parse_args()
    os.umask(0o077)
    stage = inputs.site_stage(args.stage)
    if args.command == "submit":
        submit(stage, args.preflight_sha256, args.decision)
    elif args.command == "batch":
        batch(stage, args.preflight_sha256)
    elif args.command == "child":
        child(stage, args.preflight_sha256, args)
    else:
        report(stage, args.preflight_sha256)


if __name__ == "__main__":
    main()
