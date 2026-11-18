"""One explicitly decided CPU recovery of the H25 whole-process timeout.

Reuse the four sealed preparation artifacts from job 3905. The original
pilot and solver implementation remain unchanged. Never resumes or appends
to an old solve; all six technical calls are fresh and separately claimed.
"""

import argparse
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import sys
import time
from pathlib import Path

import pr98_hard_inputs as inputs
import pr98_hard_pilot as pilot
import pr98_pilot_license_recovery as license_recovery

need = inputs.require
PARENT = inputs.EVIDENCE / "pr98-hard.mHdQl2rp"
PARENT_SOURCE = "2d081b8c610c319cbaea8a5e0ae32f864cf77949"
PARENT_PREFLIGHT = "3bbbe31b373b15bb4b4733c9cbef113497cda71bc8c38dc187e907d5706c9b4d"
INPUTS_SHA = "3922d7d27f6076bc3e2b2e60f28d7b0837947576e7f9ce65c4a92055ff32f687"
PARENT_JOB = "3905"
CLAIM = "pr98-h25-deadline-recovery-3905.claim.json"
DEADLINE = 900
BUDGET = {
    "instance": "H25",
    "seed": 42,
    "threads": 4,
    "ConcurrentMIP": [1, 2],
    "new_root_calls": 0,
    "new_forward_calls": 0,
    "new_training_calls": 0,
    "new_pilot_solve_calls_maximum": 6,
    "seconds_per_solve": 120,
    "whole_child_deadline_seconds": DEADLINE,
    "physical_cores_reserved": 4,
    "memory_gib_reserved": 64,
    "GPUs_reserved": 0,
    "wall_seconds_reserved": 7200,
    "automatic_retry": False,
}
ARTIFACT_HASHES = {
    "root_sha256": "62f77703731aef24f72db13a96b8d120fa4b085bdaba8e39b34df957e42dbb7f",
    "graph_sha256": "55a4dade1c13d7568418397d0b00fa09940feaa7f8501a08973b1660143bd723",
    "prediction_sha256": "79b136fb35123dfc0e68e81558b7452f260846869cd9efdc858eff76aabb8137",
    "private_starts_sha256": "6765fd91a740d9e5929ed2d600ed5f3033293be11e8c6bdd2aa07bc65e65f62d",
}


def parent_snapshot(fresh_accounting=False):
    from pr94_isolated_preparation import accounting, command

    need(PARENT.is_dir() and not PARENT.is_symlink(), "parent_stage")
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    need(
        command(["git", "-C", str(PARENT / "source"), "rev-parse", "HEAD"], env=env)
        == PARENT_SOURCE,
        "parent_source",
    )
    need(
        not command(
            [
                "git",
                "-C",
                str(PARENT / "source"),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            env=env,
        ),
        "parent_changed",
    )
    need(
        inputs.digest(PARENT / "preflight.json") == PARENT_PREFLIGHT, "parent_preflight"
    )
    need(inputs.digest(PARENT / "inputs.private.json") == INPUTS_SHA, "parent_inputs")
    old_approval = inputs.read(PARENT / "pilot-approval.json")
    need(
        old_approval == inputs.read(license_recovery.claim_path(PARENT))
        and old_approval["budget"] == pilot.BUDGET
        and old_approval["preflight_sha256"] == PARENT_PREFLIGHT,
        "parent_approval",
    )
    need(
        inputs.read(PARENT / "pilot-submission.json")
        == {
            "job_id": PARENT_JOB,
            "preflight_sha256": PARENT_PREFLIGHT,
            "scope": pilot.PILOT_SCOPE,
        },
        "parent_submission",
    )
    config = inputs.read(PARENT / "inputs.private.json")
    receipt, _ = pilot.verify_artifacts(
        PARENT / "run/pilot/preparation", config["models"]["H25"]
    )
    need(
        all(receipt[key] == value for key, value in ARTIFACT_HASHES.items())
        and not receipt["abstained"],
        "reviewed_parent_artifacts",
    )
    folder = PARENT / "run/pilot"
    need(not (folder / "complete.json").exists(), "parent_already_complete")
    prep = inputs.read(folder / "preparation.supervision.private.json")
    need(prep["child_exit_code"] == 0 and prep["guard_stop"] is None, "preparation")
    supervision = inputs.read(folder / "c1-M0.supervision.private.json")
    need(
        supervision["child_exit_code"] == -15
        and supervision["guard_stop"] == "child_deadline_exceeded",
        "parent_timeout",
    )
    need(
        inputs.read(folder / "c1-M0/solve.intent.json") == {"maximum_calls": 1}
        and not (folder / "c1-M0/result.private.json").exists(),
        "interrupted_control",
    )
    for c in pilot.PROFILES:
        for m in pilot.ORDER:
            if (c, m) != (1, "M0"):
                need(not (folder / f"c{c}-{m}").exists(), "unexpected_parent_call")
    log = folder / "c1-M0/gurobi.private.log"
    need(log.stat().st_size <= 1024**2, "bounded_log")
    text = log.read_text(encoding="utf8", errors="replace")
    need(
        "TimeLimit  120" in text
        and "Time limit reached" in text
        and "in 121.78 seconds" in text
        and "Best objective 2.091003359181e+02" in text,
        "reviewed_solver_termination",
    )
    names = [
        "preflight.json",
        "inputs.private.json",
        "pilot-approval.json",
        "pilot-submission.json",
        "pilot-held-profile.private.json",
        "license-recovery.json",
        "pilot-3905.private.err",
        "pilot-3905.private.out",
        "run/pilot/batch.json",
        "run/pilot/preparation.supervision.private.json",
        "run/pilot/preparation.console.private.log",
        "run/pilot/preparation/artifact-receipt.json",
        "run/pilot/preparation/root.intent.json",
        "run/pilot/preparation/forward.intent.json",
        "run/pilot/c1-M0.supervision.private.json",
        "run/pilot/c1-M0.console.private.log",
        "run/pilot/c1-M0/solve.intent.json",
        "run/pilot/c1-M0/gurobi.private.log",
    ]
    hashes = {}
    for name in names:
        path = PARENT / name
        need(path.is_file() and not path.is_symlink(), "regular_parent_evidence")
        hashes[name] = inputs.digest(path)
    if fresh_accounting:
        result = accounting(PARENT, "pilot")
        rows = {r["JobID"]: r for r in result["rows"]}
        need(result["job_id"] == PARENT_JOB and result["terminal"], "parent_terminal")
        for job in (PARENT_JOB, PARENT_JOB + ".batch"):
            need(
                rows[job]["State"] == "FAILED" and rows[job]["ExitCode"] == "1:0",
                "parent_accounting",
            )
        need(rows[PARENT_JOB + ".extern"]["State"] == "COMPLETED", "parent_extern")
    return {
        "stage": str(PARENT),
        "job_id": PARENT_JOB,
        "source_commit": PARENT_SOURCE,
        "files_sha256": hashes,
        "artifacts": ARTIFACT_HASHES,
        "parent_claim_sha256": inputs.digest(
            inputs.EVIDENCE / license_recovery.RECOVERY_CLAIM
        ),
    }


def held_profile(text, job):
    fields = dict(x.split("=", 1) for x in text.split() if "=" in x)
    for key, expected in {
        "JobId": job,
        "JobState": "PENDING",
        "Reason": "JobHeldUser",
        "Partition": "batch",
        "Requeue": "0",
        "Restarts": "0",
        "NumTasks": "1",
        "CPUs/Task": "4",
        "TimeLimit": "02:00:00",
    }.items():
        need(fields.get(key) == expected, "held_" + key)
    need(fields.get("NumNodes") in {"1", "1-1"}, "held_nodes")
    need(fields.get("NumCPUs") in {"4", "8"}, "held_cpus")
    need(fields.get("MinMemoryNode") in {"64G", "65536M"}, "held_memory")
    pairs = [
        x.split("=", 1)
        for x in fields.get("TRES", fields.get("ReqTRES", "")).split(",")
    ]
    need(all(len(x) == 2 for x in pairs), "held_tres_parse")
    tres = dict(pairs)
    need(
        len(tres) == len(pairs)
        and set(tres) <= {"cpu", "mem", "node", "billing", "gres/gpu"}
        and tres.get("mem") in {"64G", "65536M"}
        and tres.get("cpu") == fields.get("NumCPUs")
        and tres.get("node") == "1"
        and tres.get("gres/gpu", "0") == "0",
        "held_tres",
    )
    return fields


def approval(stage, accepted, fresh_accounting=False):
    pilot.admitted(stage, accepted)
    value = inputs.read(stage / "deadline-recovery.json")
    need(
        value == inputs.read(inputs.EVIDENCE / CLAIM)
        and value["budget"] == BUDGET
        and value["scope"] == pilot.PILOT_SCOPE
        and value["decision"] == "AUTORIZO RECUPERACAO H25 3905"
        and value["preflight_sha256"] == accepted
        and value["source_commit"] == inputs.source_commit()
        and value["license"] == license_recovery.license_binding(),
        "recovery_approval",
    )
    from pr94_isolated_preparation import versions

    need(value["versions"] == versions(), "environment_changed")
    need(
        value["parent"] == parent_snapshot(fresh_accounting), "parent_evidence_changed"
    )
    need(inputs.digest(stage / "inputs.private.json") == INPUTS_SHA, "same_inputs")
    return value


def submit(stage, accepted, decision):
    from pr94_isolated_preparation import command, storage, versions

    need(decision == "AUTORIZO RECUPERACAO H25 3905", "specific_recovery_decision")
    need(stage.resolve() != PARENT.resolve(), "isolated_stage")
    pilot.admitted(stage, accepted)
    need(inputs.digest(stage / "inputs.private.json") == INPUTS_SHA, "same_inputs")
    storage(stage, admission=True)
    value = {
        "scope": pilot.PILOT_SCOPE,
        "budget": BUDGET,
        "decision": decision,
        "source_commit": inputs.source_commit(),
        "preflight_sha256": accepted,
        "license": license_recovery.license_binding(),
        "versions": versions(),
        "parent": parent_snapshot(fresh_accounting=True),
    }
    # The claim is durable before copying or calling sbatch. No partial retry.
    inputs.write_once(inputs.EVIDENCE / CLAIM, value)
    inputs.write_once(stage / "deadline-recovery.json", value)
    inputs.write_once(stage / "pilot-approval.json", value)
    folder = stage / "run/pilot/preparation"
    folder.mkdir(parents=True)
    for name in (*pilot.ARTIFACTS.values(), "artifact-receipt.json"):
        source = PARENT / "run/pilot/preparation" / name
        with source.open("rb") as reader, (folder / name).open("xb") as writer:
            shutil.copyfileobj(reader, writer, 1024**2)
            writer.flush()
            os.fsync(writer.fileno())
        need(inputs.digest(folder / name) == inputs.digest(source), "copy_hash")
    row, _, _ = pilot.admitted(stage, accepted)
    pilot.verify_artifacts(folder, row)
    command_line = shlex.join(
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
            "--time=02:00:00",
            "--job-name=cfl_pr98_H25_cpu",
            "--export=ALL,GRB_LICENSE_FILE=" + str(license_recovery.LICENSE_PATH),
            "--chdir=" + str(inputs.ROOT),
            "--output=" + str(stage / "pilot-%j.private.out"),
            "--error=" + str(stage / "pilot-%j.private.err"),
            "--wrap=" + command_line,
        ],
        env={**pilot.clean_env(), "CUDA_VISIBLE_DEVICES": ""},
    )
    inputs.write_once(stage / "pilot-sbatch.private.json", {"response": response})
    job = response.split(";", 1)[0]
    need(re.fullmatch("[0-9]+", job), "ambiguous_submission_preserve_claim")
    submission = {
        "job_id": job,
        "preflight_sha256": accepted,
        "scope": pilot.PILOT_SCOPE,
    }
    inputs.write_once(stage / "pilot-submission.json", submission)
    profile = held_profile(command(["scontrol", "show", "job", job, "-o"]), job)
    inputs.write_once(stage / "pilot-held-profile.private.json", profile)
    command(["scontrol", "release", job])
    print(json.dumps(submission, sort_keys=True))


def runtime(stage, accepted):
    from pr94_isolated_preparation import allocation

    approval(stage, accepted)
    # This established function enforces four physical cores/64 GiB, with
    # topology affinity and the qualified cgroup gate. It does not require GPU.
    job, gate, observed = allocation("guidance", stage)
    need(
        inputs.read(stage / "pilot-submission.json")
        == {"job_id": job, "preflight_sha256": accepted, "scope": pilot.PILOT_SCOPE},
        "job_identity",
    )
    need(not os.environ.get("SLURM_JOB_GPUS"), "no_GPU_allocation")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    return job, gate, observed


def batch(stage, accepted):
    import resource

    from paired_memory_runtime_v2 import supervise

    job, gate, observed = runtime(stage, accepted)
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * inputs.CHUNK, 512 * inputs.CHUNK))
    folder = stage / "run/pilot"
    inputs.write_once(folder / "batch.json", {"job_id": job, "allocation": observed})
    for c in pilot.PROFILES:
        for m in pilot.ORDER:
            command = [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "child",
                str(stage),
                accepted,
                "--concurrent",
                str(c),
                "--method",
                m,
            ]
            key = f"c{c}-{m}"
            result = supervise(
                command, folder / (key + ".console.private.log"), DEADLINE, gate
            )
            inputs.write_once(folder / (key + ".supervision.private.json"), result)
            need(
                result["guard_stop"] is None and result["child_exit_code"] == 0,
                "pilot_child_failed_preserve_evidence",
            )
    inputs.write_once(
        folder / "complete.json", {"job_id": job, "scope": pilot.PILOT_SCOPE}
    )


def child(stage, accepted, concurrent, method):
    print(
        json.dumps({"phase": "child_started", "monotonic": time.monotonic()}),
        flush=True,
    )
    _, gate, _ = runtime(stage, accepted)
    row, model, _ = pilot.admitted(stage, accepted)
    need(concurrent in pilot.PROFILES and method in pilot.ORDER, "cell")
    print(
        json.dumps({"phase": "admitted_before_solve", "monotonic": time.monotonic()}),
        flush=True,
    )
    pilot.solve_cell(stage / "run/pilot", model, row, gate, concurrent, method)
    print(
        json.dumps({"phase": "result_written", "monotonic": time.monotonic()}),
        flush=True,
    )


def report(stage, accepted):
    approval(stage, accepted)
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        pilot.report(stage, accepted)
    result = json.loads(captured.getvalue())
    for cell in result["cells"]:
        path = (
            stage
            / "run/pilot"
            / f"c{cell['ConcurrentMIP']}-{cell['method']}"
            / "result.private.json"
        )
        if path.exists():
            value = inputs.read(path)
            cell["timing"] = value["timing"]
            cell["terminal_solve"] = value["solve"]
            audit = value["independent_feasibility"]
            cell["independent_audit_valid"] = None if audit is None else audit["valid"]
    result.update(
        {
            "predecessor_job_id": PARENT_JOB,
            "recovery_budget": BUDGET,
            "new_root_calls": 0,
            "new_forward_calls": 0,
            "preparation_artifacts_reused_from_job": PARENT_JOB,
            "artifact_receipt_call_counts_refer_to_parent": True,
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("submit", "batch", "child", "report"))
    parser.add_argument("stage", type=Path)
    parser.add_argument("preflight_sha256")
    parser.add_argument("--decision")
    parser.add_argument("--concurrent", type=int)
    parser.add_argument("--method", choices=pilot.ORDER)
    args = parser.parse_args()
    os.umask(0o077)
    stage = inputs.site_stage(args.stage)
    if args.command == "submit":
        submit(stage, args.preflight_sha256, args.decision)
    elif args.command == "batch":
        batch(stage, args.preflight_sha256)
    elif args.command == "child":
        child(stage, args.preflight_sha256, args.concurrent, args.method)
    else:
        report(stage, args.preflight_sha256)


if __name__ == "__main__":
    main()
