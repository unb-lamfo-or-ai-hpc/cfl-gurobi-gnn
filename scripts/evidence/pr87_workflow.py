"""Two serially dependent PR87 jobs; one-shot status/collection, never retry."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pr87_contract as c
from qualification_workflow import parse_accounting
from verify_sprint_c_artifacts import Reader


def command(args):
    return subprocess.run(
        args, capture_output=True, text=True, check=True, timeout=45
    ).stdout


def installed(stage):
    c.require(
        sys.platform == "linux" and socket.gethostname().split(".")[0] == "dgx-dasci",
        "dgx_dasci_required",
    )
    c.require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "tfm_env_required")
    commit = c.source()
    c.require(
        stage.resolve() == c.BASE / ("training-" + commit[:12])
        and c.REPO == stage / "source",
        "stage_source_identity",
    )
    return commit


def prepare(stage):
    commit = installed(stage)
    c.require(not (stage / "plan.json").exists(), "already_prepared_preserve_state")
    frozen = c.plan(commit)
    reader = Reader(c.DATA_ROOT, seconds=600, max_bytes=8 * 1024**3)
    reader.scan()
    paths = {
        c.sha(p.relative_to(reader.root).as_posix().encode()): p for p in reader.files
    }
    bindings = {}
    for row in frozen["records"]:
        parent = row["parent"]
        bindings[parent] = {}
        for kind in ("graph", "root", "label"):
            descriptor = row[kind]
            c.require(descriptor["artifact_id"] in paths, "frozen_artifact_missing")
            path = paths[descriptor["artifact_id"]]
            c.require(
                reader.verify(path, descriptor["sha256"]) == descriptor,
                "input_bytes_changed",
            )
            bindings[parent][kind] = str(path)
    # Private path map is never exported in public receipts.
    os.umask(0o077)
    c.write(stage / "private_bindings.json", bindings)
    sha = c.write(stage / "plan.json", frozen)
    print(
        json.dumps(
            {
                "plan_sha256": sha,
                "maximum_training_runs": 2,
                "optimization_calls": 0,
                "budget": frozen["protocol"]["budget"],
                "resource_budget_approved": False,
            }
        )
    )


def checked(stage):
    commit = installed(stage)
    frozen = c.read(stage / "plan.json")
    c.require(frozen == c.plan(commit), "plan_changed")
    return frozen


def profile(text, job, world):
    values = dict(re.findall(r"(?:^|\s)([A-Za-z][A-Za-z0-9_/-]*)=([^\s]+)", text))
    c.require(
        values.get("JobId") == job and values.get("JobState") == "PENDING",
        "held_job_identity",
    )
    c.require(
        values.get("NumNodes") in {"1", "1-1"} and values.get("NumTasks") == "1",
        "one_node_one_task",
    )
    c.require(
        values.get("CPUs/Task") == str(world * 4)
        and values.get("Requeue") == "0"
        and values.get("Restarts") == "0"
        and values.get("TimeLimit") == "12:00:00"
        and values.get("Partition") == "batch",
        "held_resources",
    )
    c.require(values.get("MinMemoryNode") in {"128G", "131072M"}, "held_memory")
    tres = dict(p.split("=", 1) for p in values.get("TRES", "").split(",") if "=" in p)
    c.require(
        tres.get("node") == "1" and tres.get("gres/gpu") == str(world), "held_gpu_count"
    )
    return {
        k: values[k]
        for k in (
            "JobId",
            "NumNodes",
            "NumTasks",
            "CPUs/Task",
            "MinMemoryNode",
            "Requeue",
            "Restarts",
            "TimeLimit",
            "Partition",
        )
    }


def submit(stage, approved_sha, authorization=None, authorization_sha=None):
    frozen = checked(stage)
    plan_sha = c.sha((stage / "plan.json").read_bytes())
    c.require(approved_sha == plan_sha, "explicit_approved_plan_required")
    c.require(
        authorization is not None and authorization_sha is not None,
        "separate_gpu_execution_authorization_required",
    )
    raw = Path(authorization).read_bytes()
    c.require(
        len(raw) < 16384 and c.sha(raw) == authorization_sha, "authorization_file_hash"
    )
    bindings_sha = c.sha((stage / "private_bindings.json").read_bytes())
    decision = c.validate_authorization(json.loads(raw), frozen, plan_sha, bindings_sha)
    # Claim precedes any side effect; uncertain/partial submissions never repeat.
    with (stage / "submission.claim").open("x"):
        pass
    with (stage / "execution_authorization.json").open("xb") as stream:
        stream.write(raw)
    c.write(
        stage / "approval.json",
        {
            "explicitly_approved": True,
            "plan_sha256": plan_sha,
            "bindings_sha256": bindings_sha,
            "budget": frozen["protocol"]["budget"],
            "seed": 42,
            "authorization_sha256": authorization_sha,
            "decision_reference": decision["decision_reference"],
            "automatic_retry": False,
        },
    )
    jobs = []
    for index, (_, world) in enumerate(frozen["protocol"]["pair_order"]):
        args = [
            "sbatch",
            "--parsable",
            "--hold",
            "--nodes=1-1",
            "--ntasks=1",
            f"--cpus-per-task={world * 4}",
            "--hint=nomultithread",
            "--mem=131072M",
            f"--gres=gpu:{world}",
            "--partition=batch",
            "--time=12:00:00",
            "--no-requeue",
            "--kill-on-invalid-dep=yes",
            "--job-name=cfl_pr87",
            "--output=" + str(stage / f"batch-{index}.private.out"),
            "--error=" + str(stage / f"batch-{index}.private.err"),
        ]
        if jobs:
            args.append("--dependency=afterok:" + jobs[-1])
        args.extend(
            [
                str(c.REPO / "scripts/evidence/operate_pr87_training.sh"),
                "batch",
                str(stage),
                str(index),
            ]
        )
        # Inherit tfm_env, but never ask sbatch to reinterpret commas in a path.
        reply = command(args).strip()
        job = reply.split(";", 1)[0]
        c.require(re.fullmatch(r"[0-9]+", job), "ambiguous_submission_preserve_claim")
        c.write(stage / f"submission-{index}.json", {"index": index, "job_id": job})
        observed = profile(command(["scontrol", "show", "job", "-o", job]), job, world)
        c.write(stage / f"profile-{index}.json", observed)
        jobs.append(job)
    # Only release after BOTH requested profiles pass. Still validate artifacts
    # of predecessor at batch entry, not just scheduler afterok.
    c.write(
        stage / "jobs.json", {"job_ids": jobs, "source_commit": frozen["source_commit"]}
    )
    for job in jobs:
        command(["scontrol", "release", job])
    c.write(stage / "released.json", {"job_ids": jobs, "automatic_retry": False})
    print(
        json.dumps(
            {
                "job_ids": jobs,
                "submission": "two_serial_jobs_released",
                "automatic_retry": False,
            }
        )
    )


def status(stage):
    checked(stage)
    jobs_path = stage / "jobs.json"
    # Partial submission still exposes IDs without permitting resubmission.
    jobs = (
        c.read(jobs_path)["job_ids"]
        if jobs_path.exists()
        else [c.read(p)["job_id"] for p in sorted(stage.glob("submission-*.json"))]
    )
    c.require(bool(jobs), "no_recorded_jobs_do_not_repeat_submission")
    output = command(
        [
            "sacct",
            "--jobs=" + ",".join(jobs),
            "--parsable2",
            "--noheader",
            "--format=JobID,State,ExitCode,ElapsedRaw,TotalCPU,AllocCPUS,ReqMem,MaxRSS",
        ]
    )
    groups = [
        parse_accounting(
            "\n".join(
                line
                for line in output.splitlines()
                if re.fullmatch(
                    re.escape(job) + r"(?:\.(?:batch|extern|[0-9]+))?",
                    line.split("|", 1)[0],
                )
            ),
            job,
        )
        for job in jobs
    ]
    return {
        "jobs": groups,
        "terminal": len(jobs) == 2 and all(g["terminal"] for g in groups),
    }


def run(stage, index):
    frozen = checked(stage)
    c.require(index in (0, 1), "index")
    seed, world = frozen["protocol"]["pair_order"][index]
    jobs = c.read(stage / "jobs.json")["job_ids"]
    c.require(os.environ.get("SLURM_JOB_ID") == jobs[index], "job_identity")
    c.require(
        c.read(stage / "approval.json")["plan_sha256"]
        == c.sha((stage / "plan.json").read_bytes()),
        "approval_plan",
    )
    # Submission, allocated launch and independent review protect different boundaries.
    approval = c.read(stage / "approval.json")
    auth_raw = (stage / "execution_authorization.json").read_bytes()
    c.require(
        c.sha(auth_raw) == approval["authorization_sha256"], "launch_authorization_hash"
    )
    c.require(
        approval["bindings_sha256"]
        == c.sha((stage / "private_bindings.json").read_bytes()),
        "launch_bindings_changed",
    )
    c.validate_authorization(
        json.loads(auth_raw),
        frozen,
        approval["plan_sha256"],
        approval["bindings_sha256"],
    )
    if index:
        c.validate_result(c.read(stage / "runs/0/result.json"), frozen, 0)
        prior = c.read(stage / "runs/0/supervisor.json")
        c.require(
            prior["child_exit_code"] == 0 and prior["guard_stop"] is None,
            "predecessor_stopped",
        )
    output = stage / "runs" / str(index)
    output.mkdir(parents=True, exist_ok=False)
    from pr87_resources import gate_class, supervise

    gate = gate_class()(os.environ["SLURM_JOB_ID"])
    args = [sys.executable, "-B"]
    if world == 4:
        args.extend(
            [
                "-m",
                "torch.distributed.run",
                "--standalone",
                "--nnodes=1",
                "--nproc-per-node=4",
                "--max-restarts=0",
            ]
        )
    args.extend(
        [
            str(c.REPO / "scripts/evidence/train_pr87.py"),
            "--stage",
            str(stage),
            "--index",
            str(index),
        ]
    )
    result = supervise(args, output / "console.private.log", gate, world)
    c.write(output / "supervisor.json", result)
    c.require(
        result["child_exit_code"] == 0 and result["guard_stop"] is None,
        "training_process_stopped",
    )
    value = c.validate_result(c.read(output / "result.json"), frozen, index)
    c.require(value["seed"] == seed, "seed")


def review(value):
    frozen = value["plan"]
    c.require(
        value["protocol_id"] == "pr87_matched_parent_training_v2"
        and frozen == c.plan(frozen["source_commit"]),
        "public_plan",
    )
    c.require(
        value["raw_logs_included"] is False
        and value["private_paths_included"] is False,
        "public_scope",
    )
    approval = value["approval"]
    raw = value["authorization_json"].encode("utf-8")
    c.require(
        c.sha(raw) == approval["authorization_sha256"], "review_authorization_hash"
    )
    expected_plan_sha = c.sha(
        (json.dumps(frozen, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    )
    c.require(
        approval["explicitly_approved"] is True
        and approval["plan_sha256"] == expected_plan_sha
        and approval["budget"] == frozen["protocol"]["budget"]
        and approval["seed"] == 42
        and approval["automatic_retry"] is False,
        "review_approval_scope",
    )
    decision = c.validate_authorization(
        json.loads(raw), frozen, expected_plan_sha, approval["bindings_sha256"]
    )
    c.require(
        decision["decision_reference"] == approval["decision_reference"],
        "review_decision",
    )
    c.require(
        len(value["results"]) == 2 and value["accounting"]["terminal"],
        "incomplete_pair",
    )
    for index, result in enumerate(value["results"]):
        c.validate_result(result, frozen, index)
        account = value["accounting"]["jobs"][index]
        c.require(
            account["job_id"] == result["job_id"] and account["state"] == "COMPLETED",
            "job_completion",
        )
        main = next(r for r in account["rows"] if r["JobID"] == result["job_id"])
        c.require(main["ExitCode"] == "0:0", "job_exit")
        supervisor = value["supervisors"][index]
        c.require(
            supervisor["child_exit_code"] == 0 and supervisor["guard_stop"] is None,
            "guard",
        )
    a, b = value["results"]
    for key in (
        "unfitted_state_sha256",
        "initial_state_sha256",
        "schedule_sha256",
        "pos_weight",
    ):
        c.require(a[key] == b[key], "paired_initialization_or_schedule_mismatch")
    paired_quality = {}
    for key in ("f1_score", "pr_auc"):
        serial = [r[key] for r in a["test"]["selected"]]
        ddp = [r[key] for r in b["test"]["selected"]]
        c.require(all(v is not None for v in serial + ddp), "macro_metric_unavailable")
        difference = sum(ddp) / 10 - sum(serial) / 10
        paired_quality[key] = {
            "serial_parent_macro": sum(serial) / 10,
            "ddp4_parent_macro": sum(ddp) / 10,
            "ddp4_minus_serial": difference,
            "loss_exceeds_descriptive_margin_002": difference < -0.02,
        }
    return {
        "complete_runs": 2,
        "matched_learning_work": True,
        "training_loop_speedup": a["training_loop_seconds"]
        / b["training_loop_seconds"],
        "parallel_efficiency": a["training_loop_seconds"]
        / b["training_loop_seconds"]
        / 4,
        "seed": 42,
        "selected_quality": paired_quality,
        "training_seed_uncertainty_claimed": False,
        "scientific_reporting_eligible": False,
    }


def collect(stage):
    frozen = checked(stage)
    account = status(stage)
    c.require(account["terminal"], "jobs_nonterminal_collect_later_no_wait")
    results, supervisors = [], []
    for index in (0, 1):
        path = stage / "runs" / str(index)
        results.append(
            c.read(path / "result.json") if (path / "result.json").exists() else None
        )
        supervisors.append(
            c.read(path / "supervisor.json")
            if (path / "supervisor.json").exists()
            else None
        )
    value = {
        "protocol_id": frozen["protocol"]["protocol_id"],
        "plan": frozen,
        "approval": c.read(stage / "approval.json"),
        "authorization_json": (stage / "execution_authorization.json")
        .read_bytes()
        .decode("utf-8"),
        "results": results,
        "supervisors": supervisors,
        "accounting": account,
        "raw_logs_included": False,
        "private_paths_included": False,
        "optimization_runs_added": 0,
        "scientific_reporting_eligible": False,
    }
    try:
        value["review"] = review(value)
        value["ready_for_independent_review"] = True
    except (ValueError, TypeError, KeyError):
        value["ready_for_independent_review"] = False
    target = stage / "public_return.json"
    if target.exists():
        prior = c.read(target)
        c.require(prior == value, "existing_return_preserved_no_overwrite")
        result_sha = c.sha(target.read_bytes())
    else:
        result_sha = c.write(target, value)
    print(
        json.dumps(
            {
                "return_sha256": result_sha,
                "output": str(target),
                "ready_for_independent_review": value["ready_for_independent_review"],
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "submit", "status", "collect", "run", "review")
    )
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--authorization-sha256")
    parser.add_argument("--index", type=int)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.action == "review":
        raw = args.receipt.read_bytes()
        c.require(
            len(raw) < 16 * 1024**2 and c.sha(raw) == args.expected_sha256,
            "download_hash",
        )
        print(json.dumps(review(json.loads(raw))))
    elif args.action == "prepare":
        prepare(args.stage)
    elif args.action == "submit":
        submit(
            args.stage,
            args.approved_plan_sha256,
            args.authorization,
            args.authorization_sha256,
        )
    elif args.action == "status":
        print(json.dumps(status(args.stage), indent=2))
    elif args.action == "collect":
        collect(args.stage)
    else:
        run(args.stage, args.index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
