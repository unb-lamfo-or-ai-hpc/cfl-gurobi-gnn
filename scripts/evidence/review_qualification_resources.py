"""Offline job3479 cost review and read-only, current Slurm configuration.

No optimization, submission, license access, raw log, or historical inference.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PACKAGE_SHA = "fc4b00066a53868e61f07540d8db2d1377ea2da65fc0f405ab592c444b45fc22"
AUDIT_SHA = "0c26533eb90b27b4e1115500997682af3d95713edd6197bc0f8d0a4eeb432eee"
EVIDENCE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
CONFIG_FIELDS = (
    "JobAcctGatherType",
    "JobAcctGatherFrequency",
    "JobAcctGatherParams",
    "TaskPlugin",
    "ProctrackType",
)


def require(ok):
    if not ok:
        raise ValueError("qualification_resource_contract_failed")


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def numeric(value):
    require(type(value) in {int, float} and math.isfinite(value) and value >= 0)
    return value


def audit_bytes(raw):
    require(digest(raw) == AUDIT_SHA)
    return json.loads(raw)


def projection(outer, request, receipt, audit):
    """Inputs are validated sealed payloads; all PR73 provenance is cross-bound."""
    from pr66_reconciliation import seconds

    child = receipt["child"]
    callback = child["result"]["gurobi_callback"]
    accounting = outer["accounting"]
    require(accounting["job_id"] == child["slurm_job_id"] == audit["job_id"] == "3479")
    require(accounting["terminal"] is True and accounting["state"] == "COMPLETED")
    require(receipt["status"] == "completed" and child["optimization_calls"] == 1)
    require(audit["package_sha256"] == PACKAGE_SHA)
    require(audit["source_commit"] == request["source_commit"])
    require(audit["approval_sha256"] == outer["approval_sha256"])
    require(audit["approval_sha256"] == request["approval_record_sha256"])
    require(audit["plan_sha256"] == outer["plan_sha256"])
    require(audit["console_log_sha256"] == receipt["console_log"]["log_sha256"])
    require(audit["gurobi_log_sha256"] == child["gurobi_log"]["log_sha256"])
    require(audit["callback_mip_calls"] == callback["counters"]["mip_calls"])
    require(audit["callback_mipsol_calls"] == callback["counters"]["mipsol_calls"])
    require(audit["worker_ru_maxrss_bytes"] == child["peak_rss_bytes"])
    for name in ("memory_metrics_reconciled", "scientific_reporting_eligible"):
        require(audit[name] is False)
    require(audit["installed_callback_observation_supported"] is True)
    require(audit["terminal_numeric_parity_supported"] is True)
    require(
        audit["raw_logs_included"] is False and audit["optimization_runs_added"] == 0
    )
    roots = [r for r in accounting["rows"] if r["JobID"] == "3479"]
    steps = [r for r in accounting["rows"] if r["JobID"] == "3479.0"]
    require(len(roots) == len(steps) == 1)
    root, step = roots[0], steps[0]
    require(root["ExitCode"] == step["ExitCode"] == "0:0")
    require(audit["slurm_step_max_rss"] == step["MaxRSS"])
    elapsed = numeric(root["ElapsedRaw"])
    cpus = numeric(root["AllocCPUS"])
    cpu_seconds = seconds(root["TotalCPU"])
    require(cpu_seconds is not None)
    solver = numeric(child["result"]["terminal"]["solver_runtime_seconds"])
    process_cpu = numeric(child["current_process_cpu_seconds"])
    callback_wall = numeric(callback["callback_external_wall_seconds"])
    callback_cpu = numeric(callback["callback_current_process_cpu_seconds"])
    require(solver > 0 and process_cpu > 0)
    return {
        "schema_version": 1,
        "protocol_id": "job3479_resource_scope_review_v1",
        "job_id": "3479",
        "source_commit": request["source_commit"],
        "package_sha256": PACKAGE_SHA,
        "private_review_sha256": AUDIT_SHA,
        "plan_sha256": outer["plan_sha256"],
        "approval_sha256": outer["approval_sha256"],
        "allocation_cost": {
            "allocation_elapsed_seconds": elapsed,
            "reported_alloc_cpus": cpus,
            "logical_allocation_cpu_hours": cpus * elapsed / 3600,
            "reported_total_cpu_seconds": cpu_seconds,
            "reported_total_cpu_hours": cpu_seconds / 3600,
            "step_rows_added_to_allocation": False,
            "allocated_physical_core_hours_qualified": False,
        },
        "clocks": {
            "solver_runtime_seconds": solver,
            "supervisor_wall_seconds": numeric(receipt["supervisor_wall_seconds"]),
            "child_current_process_cpu_seconds": process_cpu,
            "child_phases": child["phases"],
            "phase_clocks_cover_entire_child_lifecycle": False,
            "root_tree_phase_costs_qualified": False,
        },
        "callback_instrumentation": {
            "external_wall_seconds": callback_wall,
            "current_process_cpu_seconds": callback_cpu,
            "external_wall_fraction_of_solver_runtime": callback_wall / solver,
            "cpu_fraction_of_child_process_cpu": callback_cpu / process_cpu,
            "mip_calls": callback["counters"]["mip_calls"],
            "mipsol_calls": callback["counters"]["mipsol_calls"],
            "counterfactual_slowdown_qualified": False,
            "overhead_subtracted": False,
        },
        "memory_observations": {
            "slurm_step_max_rss": step["MaxRSS"],
            "worker_ru_maxrss_bytes": child["peak_rss_bytes"],
            "metrics_reconciled": False,
            "higher_budget_memory_safety_qualified": False,
        },
        "installed_callback_observation_supported": True,
        "comparison_submission_ready": False,
        "scientific_reporting_eligible": False,
        "raw_logs_included": False,
        "optimization_runs_added": 0,
    }


def summarize(package):
    import qualification_workflow as workflow

    root = Path(__file__).resolve().parents[2]
    audit = audit_bytes(
        (root / "docs/evidence/pr73/job3479/job3479_private_review.json").read_bytes()
    )
    outer = workflow.validate_archive(package, PACKAGE_SHA)
    payloads = workflow.archive_payloads(
        package.read_bytes(), workflow.PUBLIC, workflow.LIMIT
    )
    nested = workflow.archive_payloads(
        payloads["attempt.tar.gz"], workflow.worker.PUBLIC, workflow.worker.MAX_JSON
    )
    request = workflow.worker.strict_payload(nested["request.json"])
    receipt = workflow.worker.strict_payload(nested["attempt_receipt.json"])
    return projection(outer, request, receipt, audit)


def config_value(name, value):
    if name == "JobAcctGatherType":
        return (
            value
            if value
            in {"jobacct_gather/cgroup", "jobacct_gather/linux", "jobacct_gather/none"}
            else None
        )
    if name == "JobAcctGatherFrequency":
        if re.fullmatch(r"[0-9]{1,6}", value):
            return {"task": int(value)}
        pairs = value.split(",")
        result = {}
        for pair in pairs:
            match = re.fullmatch(r"(task|energy|network|filesystem)=([0-9]{1,6})", pair)
            if match is None or match[1] in result:
                return None
            result[match[1]] = int(match[2])
        return result
    allow = {
        "JobAcctGatherParams": {
            "UsePss",
            "UsePSS",
            "NoShared",
            "OverMemoryKill",
            "no_file_cache",
        },
        "TaskPlugin": {"task/affinity", "task/cgroup", "task/none"},
        "ProctrackType": {"proctrack/cgroup", "proctrack/linuxproc", "proctrack/pgid"},
    }[name]
    if value in {"(null)", "none", ""}:
        return []
    tokens = value.split(",")
    return sorted(set(tokens)) if all(token in allow for token in tokens) else None


def config_projection(raw):
    """Discard every field/value outside the fixed public schema; never echo raw."""
    require(isinstance(raw, bytes) and len(raw) <= 256 * 1024)
    text = raw.decode("utf-8", errors="strict")
    found = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([A-Za-z]+)\s*=\s*(.*?)\s*", line)
        if match and match[1] in CONFIG_FIELDS:
            require(match[1] not in found)
            found[match[1]] = config_value(match[1], match[2])
    values = {name: found.get(name) for name in CONFIG_FIELDS}
    return {
        "allowlisted_configuration": values,
        "unavailable_or_redacted_fields": [
            name for name in CONFIG_FIELDS if values[name] is None
        ],
    }


def query(args):
    try:
        result = subprocess.run(args, capture_output=True, timeout=20, check=False)
        if result.returncode == 0 and len(result.stdout) <= 256 * 1024:
            return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def current_site(source_sha):
    require(isinstance(source_sha, str) and re.fullmatch(r"[0-9a-f]{40}", source_sha))
    version_raw = query(["scontrol", "--version"])
    config_raw = query(["scontrol", "show", "config"])
    version = None
    if version_raw is not None:
        match = re.fullmatch(rb"slurm ([0-9]+\.[0-9]+\.[0-9]+)\s*", version_raw)
        version = match[1].decode("ascii") if match else None
    config = config_projection(config_raw or b"")
    return {
        "schema_version": 1,
        "protocol_id": "current_slurm_resource_context_v1",
        "collector_source_commit": source_sha,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "slurm_version": version,
        "configuration_query_succeeded": config_raw is not None,
        **config,
        "historical_job3479_configuration_verified": False,
        "historical_memory_metrics_reconciled": False,
        "higher_budget_memory_safety_qualified": False,
        "comparison_submission_ready": False,
        "scientific_reporting_eligible": False,
        "raw_configuration_included": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "maximum_scheduler_queries": 2,
    }


def site_location(output):
    require(sys.platform == "linux")
    require(socket.gethostname().split(".")[0] == "dgx-dasci")
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env")
    root = EVIDENCE / "pr74"
    require(root.resolve(strict=True) == root)
    output = output.absolute()
    require(output.parent == root and output.resolve() == output)
    require(not output.exists() and not output.is_symlink())
    return output


def write_fresh(output, filename, value):
    require(not output.exists() and not output.is_symlink())
    output.mkdir(mode=0o700, parents=False)
    raw = encoded(value)
    with (output / filename).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sha = digest(raw)
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write((sha + "  " + filename + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    return sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("summarize", "site"))
    parser.add_argument("--package", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "site":
        output = site_location(args.output)
        require(args.package is None)
        value = current_site(args.source_sha)
        filename = "current_slurm_resource_context.json"
    else:
        require(args.package is not None and args.source_sha is None)
        output = args.output.absolute()
        require(not output.exists() and not output.is_symlink())
        value = summarize(args.package)
        filename = "job3479_resource_review.json"
    sha = write_fresh(output, filename, value)
    print("PR74_RECEIPT_SHA256=" + sha)
    print(encoded(value).decode(), end="")
    print("PR74_READ_ONLY_NO_OPTIMIZATION_NO_SUBMISSION_NO_SCIENTIFIC_PROMOTION")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("PR74_RESOURCE_REVIEW_STOPPED_PRESERVE_EVIDENCE", file=sys.stderr)
        sys.exit(2)
