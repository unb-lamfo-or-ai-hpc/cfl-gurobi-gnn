#!/usr/bin/env python3
"""Installed synthetic fault qualification; no license, LP, scheduler or solve."""

import argparse
import io
import json
import sys
import unittest
from pathlib import Path

import paired_matrix_executor as matrix


def probe(output):
    matrix.workflow.host()
    head = matrix.workflow.source_head()
    matrix.reviewed_evidence()
    output = matrix.workflow.location(output)
    matrix.require(not output.exists())
    tests = matrix.workflow.SOURCE / "tests/evidence"
    suite = unittest.defaultTestLoader.discover(
        str(tests), pattern="test_paired_matrix_executor.py"
    )
    # Tests use fake Gurobi APIs and small real POSIX processes. Their private
    # mock logs/exceptions are not copied into the public result or console.
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    passed = result.wasSuccessful() and not result.skipped and result.testsRun >= 21
    value = {
        "schema_version": 1,
        "protocol_id": "installed_paired_matrix_no_solver_fault_probe_v1",
        "source_commit": head,
        "dependency_sha256": {
            **matrix.pins(),
            "paired_matrix_no_solver_probe.py": matrix.adapter.screen.digest(
                Path(__file__)
            ),
            "tests/evidence/test_paired_matrix_executor.py": matrix.adapter.screen.digest(
                tests / "test_paired_matrix_executor.py"
            ),
            "tests/evidence/test_isolated_attempt_worker.py": matrix.adapter.screen.digest(
                tests / "test_isolated_attempt_worker.py"
            ),
        },
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "passed_no_solver_fault_probe": passed,
        "actual_high_memory_pressure_injected": False,
        "kernel_ram_enforcement_in_allocation_qualified": False,
        "comparison_submission_ready": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
    }
    matrix.old.strict_payload(matrix.contract.encoded(value))
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    matrix.old.write_json(output / "no_solver_fault_probe.json", value)
    sha = matrix.adapter.screen.digest(output / "no_solver_fault_probe.json")
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write((sha + "  no_solver_fault_probe.json\n").encode())
    print(json.dumps(value, sort_keys=True, indent=2))
    print("PR75_PROBE_RECEIPT_SHA256=" + sha)
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        sys.exit(0 if probe(args.output) else 1)
    except Exception:
        print("PR75_PROBE_REJECTED_PRESERVE_EVIDENCE_NO_RETRY", file=sys.stderr)
        sys.exit(1)
