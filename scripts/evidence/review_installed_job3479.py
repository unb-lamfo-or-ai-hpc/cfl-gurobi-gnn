"""Read-only private-log parity audit for the single PR72 job 3479.

Output is a new, allowlisted JSON receipt on the physical RAID. No solver,
license, raw log, source model, or private path enters that receipt.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import hashlib
import os
import socket
import subprocess
import sys
import tarfile
from pathlib import Path

STAGE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence/pr72/qualification-d7ecfe5272c8")
SOURCE = STAGE / "source"
FLOW = STAGE / "flow"
EVIDENCE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
HEAD = "d7ecfe5272c8b4b997a2bb078287b6fc99db02e1"
PACKAGE_SHA = "fc4b00066a53868e61f07540d8db2d1377ea2da65fc0f405ab592c444b45fc22"
PLAN_SHA = "f4c4887c6fff64dfcd40d414fbdd34a76a45061eec8984c5ecdb5ee4a3b1ae84"
APPROVAL_SHA = "8a987c7f4d00ac91abd71c3769c4a81e7fb40e3ebeca21655dbf83a1d8b4b2f2"
WORKFLOW_SHA = "46dc21ec98f525c2ea51978bf5f730799451c6542f72d476cc7bb7b29e15a3a9"
PARSER_SHA = "21ccf71fa0890d2ba21614c5cf5355b9a8f3e7a95f64d7e103911929d08b1325"


def require(ok):
    if not ok:
        raise ValueError("job3479_private_review_contract_failed")


def load_reviewed_modules():
    workflow_path = SOURCE / "scripts/evidence/qualification_workflow.py"
    parser_path = SOURCE / "scripts/evidence/collect_pr66_log_phases.py"
    for path, digest in ((workflow_path, WORKFLOW_SHA), (parser_path, PARSER_SHA)):
        require(path.is_file() and not path.is_symlink())
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest)
    sys.path.insert(0, str(workflow_path.parent))
    import collect_pr66_log_phases as log_phases
    import qualification_workflow as workflow

    require(Path(workflow.__file__).resolve() == workflow_path)
    require(Path(log_phases.__file__).resolve() == parser_path)
    return workflow, log_phases


def host_and_source():
    require(
        sys.platform == "linux" and socket.gethostname().split(".")[0] == "dgx-dasci"
    )
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env")
    require(EVIDENCE.resolve(strict=True) == EVIDENCE)
    require(STAGE.resolve(strict=True) == STAGE)
    require(SOURCE.resolve(strict=True) == SOURCE)
    require(FLOW.resolve(strict=True) == FLOW)
    cmd = ["git", "-c", "safe.directory=" + str(SOURCE), "-C", str(SOURCE)]
    head = (
        subprocess.check_output([*cmd, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        .decode()
        .strip()
    )
    require(head == HEAD)
    require(
        not subprocess.check_output(
            [*cmd, "status", "--porcelain", "--untracked-files=all"],
            stderr=subprocess.DEVNULL,
        )
    )


def display_report(receipt, request):
    child = receipt["child"]
    result = child["result"]
    require(
        receipt["status"] == "completed" and receipt["optimization_calls_known"] == 1
    )
    require(child["slurm_job_id"] == "3479" and child["optimization_calls"] == 1)
    require(
        request["source_commit"] == HEAD
        and request["approval_record_sha256"] == APPROVAL_SHA
    )
    require(result["stop"] == "time_limit" and result["dropped_sample_count"] == 0)
    require(
        child["failure_code"] is None and result["gurobi_callback"]["failed"] is False
    )
    terminal = result["terminal"]
    require(terminal["primal"] is not None and terminal["dual"] is not None)
    return {
        "parameters": child["effective_parameters"],
        "solver_runtime_seconds": terminal["solver_runtime_seconds"],
        "node_count": terminal["node_count"],
        "primal": terminal["primal"],
        "dual": terminal["dual"],
        "mip_gap_relative": terminal["gap_relative"],
    }


def sanitized_review(workflow, log_phases, outer, request, receipt, log_text):
    require(
        outer["plan_sha256"] == PLAN_SHA and outer["approval_sha256"] == APPROVAL_SHA
    )
    require(outer["accounting"]["job_id"] == "3479")
    require(outer["accounting"]["state"] == "COMPLETED")
    require(outer["scientific_reporting_eligible"] is False)
    require(receipt["installed_callback_execution_qualified"] is False)
    report = display_report(receipt, request)
    observed = log_phases.parse_log(log_text, report)
    counts = receipt["child"]["result"]["gurobi_callback"]["counters"]
    parity = observed["log_state"] == "receipt_consistent_observations"
    supported = parity and counts["mip_calls"] > 0 and counts["mipsol_calls"] > 0
    step = next(row for row in outer["accounting"]["rows"] if row["JobID"] == "3479.0")
    return {
        "schema_version": 1,
        "source_commit": HEAD,
        "job_id": "3479",
        "package_sha256": PACKAGE_SHA,
        "plan_sha256": PLAN_SHA,
        "approval_sha256": APPROVAL_SHA,
        "gurobi_log_sha256": receipt["child"]["gurobi_log"]["log_sha256"],
        "console_log_sha256": receipt["console_log"]["log_sha256"],
        "log_state": observed["log_state"],
        "warnings": observed["warnings"],
        "terminal_numeric_parity_supported": parity,
        "installed_callback_observation_supported": supported,
        "callback_mip_calls": counts["mip_calls"],
        "callback_mipsol_calls": counts["mipsol_calls"],
        "solver_runtime_display_seconds": observed["solver_total_display_seconds"],
        "presolve_display_seconds": observed["presolve_display_seconds"],
        "root_relaxation_state": observed["root_relaxation_state"],
        "root_relaxation_display_seconds": observed["root_relaxation_display_seconds"],
        "slurm_step_max_rss": step["MaxRSS"],
        "worker_ru_maxrss_bytes": receipt["child"]["peak_rss_bytes"],
        "memory_metrics_reconciled": False,
        "root_tree_phase_costs_qualified": False,
        "true_first_crossings_qualified": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
        "raw_logs_included": False,
    }


def main(output):
    host_and_source()
    workflow, log_phases = load_reviewed_modules()
    package = FLOW / "return/qualification_package.tar.gz"
    manifest = FLOW / "return/PACKAGE_SHA256.txt"
    require(
        workflow.worker.read_bytes(manifest, 512)
        == (PACKAGE_SHA + "  qualification_package.tar.gz\n").encode()
    )
    outer = workflow.validate_archive(package, PACKAGE_SHA)
    private_payloads, receipt = workflow.worker.validate_directory(
        FLOW / "attempt", private=True
    )
    with tarfile.open(package, "r:gz") as archive:
        nested_raw = archive.extractfile("attempt.tar.gz").read()
    nested_payloads = workflow.archive_payloads(
        nested_raw, workflow.worker.PUBLIC, workflow.worker.MAX_JSON
    )
    require(nested_payloads == private_payloads)
    request = workflow.load(FLOW / "attempt/request.json")
    log_path = FLOW / "attempt/gurobi.private.log"
    log = workflow.worker.read_bytes(log_path, 8 * 1024 * 1024)
    require(
        hashlib.sha256(log).hexdigest() == receipt["child"]["gurobi_log"]["log_sha256"]
    )
    require(len(log) == receipt["child"]["gurobi_log"]["log_size_bytes"])
    try:
        review = sanitized_review(
            workflow, log_phases, outer, request, receipt, log.decode("utf-8")
        )
    except UnicodeDecodeError:
        review = sanitized_review(workflow, log_phases, outer, request, receipt, "")
        review["warnings"] = ["private_log_not_utf8"]
    require(workflow.worker.read_bytes(log_path, 8 * 1024 * 1024) == log)
    output = Path(output).absolute()
    require(output != EVIDENCE and output.is_relative_to(EVIDENCE / "pr73"))
    require(output.parent.resolve(strict=True) == EVIDENCE / "pr73")
    require(not output.exists() and not output.is_symlink())
    output.mkdir(mode=0o700)
    workflow.worker.write_json(output / "job3479_private_review.json", review)
    digest = hashlib.sha256(
        (output / "job3479_private_review.json").read_bytes()
    ).hexdigest()
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write((digest + "  job3479_private_review.json\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    print("PR73_PRIVATE_REVIEW_SHA256=" + digest)
    print("PR73_LOG_STATE=" + review["log_state"])
    print(
        "PR73_NUMERIC_PARITY_SUPPORTED="
        + str(review["terminal_numeric_parity_supported"]).lower()
    )
    print("PR73_NO_OPTIMIZATION_NO_RAW_LOG_EXPORT_NO_SCIENTIFIC_PROMOTION")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        main(args.output)
    except Exception:
        print("PR73_PRIVATE_REVIEW_STOPPED_PRESERVE_EVIDENCE", file=sys.stderr)
        sys.exit(2)
