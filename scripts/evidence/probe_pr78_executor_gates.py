"""Diagnose frozen executor gates; never claim a matrix or load the solver."""

import argparse
import hashlib
import importlib
import importlib.abc
import json
import os
import re
import socket
import sys
import traceback
from pathlib import Path

SOURCE = Path(
    "/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/recovery-source-173b63d62658"
)
FLOW = SOURCE.parent / "recovery-job3481-v2/flow"
HEAD = "173b63d62658731678357772fa2d3bba48f9bc81"
APPROVAL = "d17184004a1d22b425452d70d76d04722642914377bd002cbd2a6cbd9c449519"
PINS = {
    "paired_matrix_executor.py": "226e27e55700a6dced7bc1f697d4d3305cc3b48c8465fd6cf0ac35e2519cb271",
    "paired_memory_guard.py": "8f99b5bdaa8c4722618787b4409af56b95f25c8df2f1b284074fef860ec12186",
    "qualification_workflow.py": "46dc21ec98f525c2ea51978bf5f730799451c6542f72d476cc7bb7b29e15a3a9",
}


class NoSolver(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == "gurobipy":
            raise RuntimeError("solver_import_forbidden")
        return None


def stage(name, operation):
    try:
        operation()
        return {"stage": name, "passed": True}
    except Exception as exc:
        frames = []
        base = SOURCE / "scripts/evidence"
        for frame in traceback.extract_tb(exc.__traceback__):
            path = Path(frame.filename)
            if path.parent == base and path.suffix == ".py":
                frames.append({"file": path.name, "line": frame.lineno})
        return {
            "stage": name,
            "passed": False,
            "exception_type": type(exc).__name__
            if type(exc)
            in (
                ValueError,
                RuntimeError,
                OSError,
                FileNotFoundError,
                PermissionError,
                KeyError,
                TypeError,
                AssertionError,
            )
            else "other",
            "source_frames": frames,
            "exception_text_included": False,
        }


def environment():
    result = {}
    for key in (
        "SLURM_CPUS_PER_TASK",
        "SLURM_MEM_PER_NODE",
        "SLURM_JOB_NUM_NODES",
        "SLURM_RESTART_COUNT",
        "SLURM_JOB_ID",
    ):
        value = os.environ.get(key)
        result[key] = (
            value
            if value is None or re.fullmatch(r"[0-9]{1,20}", value)
            else "non_numeric"
        )
    for key in ("SLURM_JOB_GPUS", "SLURM_STEP_GPUS"):
        result[key + "_present"] = bool(os.environ.get(key))
    return result


def fingerprint_check():
    assert sys.platform == "linux"
    assert socket.gethostname().split(".")[0] == "dgx-dasci"
    assert os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env"
    assert SOURCE.resolve(strict=True) == SOURCE
    for name, sha in PINS.items():
        assert (
            hashlib.sha256(
                (SOURCE / "scripts/evidence" / name).read_bytes()
            ).hexdigest()
            == sha
        )


def gates(executor, allocated):
    plan = None

    def plan_gate():
        nonlocal plan
        plan = executor.load_flow(FLOW, APPROVAL)
        assert plan["source_commit"] == HEAD
        assert executor.workflow.source_head() == HEAD
        executor.reviewed_evidence()

    results = [stage("frozen_plan_approval_source_and_evidence", plan_gate)]
    if not results[0]["passed"] or not allocated:
        return results
    # Independent diagnostics expose multiple resource failures in one allocation.
    # No run_parent, claim_root, run_child or execute_attempt call is permitted.
    results.append(stage("execution_host", lambda: executor.execution_host(plan, FLOW)))
    results.append(
        stage(
            "kernel_memory_gate",
            lambda: executor.memory.MemoryGate(os.environ.get("SLURM_JOB_ID", "")),
        )
    )
    results.append(
        stage("physical_affinity_gate", executor.adapter.screen.qualify_affinity)
    )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("static", "allocated"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    allocated = args.mode == "allocated"
    report = {
        "schema_version": 1,
        "protocol_id": "pr78_no_solver_executor_gate_probe_v1",
        "historical_job_id": "3482",
        "reproduces_current_environment_not_historical_proof": True,
        "optimization_runs_added": 0,
        "matrix_claims_added": 0,
        "scheduler_queries": 0,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
        "environment": environment(),
        "stages": [stage("host_and_frozen_dependency_fingerprints", fingerprint_check)],
    }
    guard = NoSolver()
    sys.meta_path.insert(0, guard)
    try:
        if report["stages"][0]["passed"]:
            sys.path.insert(0, str(SOURCE / "scripts/evidence"))
            executor = None

            def import_executor():
                nonlocal executor
                executor = importlib.import_module("paired_matrix_executor")

            imported = stage("import_frozen_executor_without_solver", import_executor)
            report["stages"].append(imported)
            if imported["passed"]:
                report["stages"].extend(gates(executor, allocated))
    finally:
        sys.meta_path.remove(guard)
    report["all_requested_gates_passed"] = all(x["passed"] for x in report["stages"])
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    print(payload, end="")
    # An allocated diagnostic finishes normally even when it successfully finds
    # a failing gate. The JSON, not Slurm COMPLETED alone, determines qualification.
    return 0 if allocated or report["all_requested_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
