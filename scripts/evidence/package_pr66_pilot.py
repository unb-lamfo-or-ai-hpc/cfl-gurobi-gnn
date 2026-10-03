"""Verify and package allowlisted CPU pilot receipts, not private logs or raw LPs.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import tarfile
from pathlib import Path

from collect_computational_ledger import digest
from pr66_thread_pilot import CAPS, canonical, strict_json, verified_plan
from publish_mvp2_baseline import PRIVATE


def verify(directory, expected_sha):
    plan = verified_plan(directory, expected_sha)
    config = plan["config"]
    execution = strict_json(directory / "pilot_execution_report.json")
    expected_names = [f"{d}-threads{t}" for t in CAPS for d in ("easy", "medium")]
    names = [r["attempt"] for r in execution["executions"]]
    if (
        execution["plan_sha256"] != expected_sha
        or names != expected_names[: len(names)]
        or not names
        or len(names) > 10
        or execution["scientific_reporting_eligible"]
    ):
        raise ValueError("invalid_execution_matrix")
    rows, payloads = [], {}
    for item in execution["executions"]:
        name = item["attempt"]
        path = directory / name / "attempt_report.json"
        if item["report_sha256"] is None:
            if path.exists() or item["exit_code"] == 0:
                raise ValueError("unbound_attempt_report")
            continue
        if path.is_symlink() or digest(path) != item["report_sha256"]:
            raise ValueError("attempt_hash_mismatch")
        report = strict_json(path)
        difficulty, cap = name.split("-threads")
        model = next(m for m in plan["models"] if m["difficulty"] == difficulty)
        parameters = {
            "Threads": int(cap),
            "Seed": config["seed"],
            "TimeLimit": config["time_limit_seconds"],
            "MIPGap": config["mip_gap_relative"],
            "SoftMemLimit": config["soft_memory_limit_decimal_gb"],
        }
        import hashlib

        if (
            report["plan_sha256"] != expected_sha
            or report["parameters"] != parameters
            or report["parameters_sha256"]
            != hashlib.sha256(canonical(parameters).encode()).hexdigest()
            or any(report[k] != v for k, v in model.items())
            or report["effective_objective_sense"] != "MINIMIZE"
            or report["source_objective_sense"] != config["source_objective_sense"]
            or report.get("objective_sense_override_applied") is not True
            or report["gurobi_version"] != config["gurobi_version"]
            or not report["model_unchanged_after_execution"]
            or report["scientific_reporting_eligible"]
            or report["affinity"]["physical_cores"] != 16
        ):
            raise ValueError("attempt_contract_mismatch")
        defaults = report["algorithm_defaults"]
        if set(defaults) != set(config["default_parameters_observed"]) or any(
            v["effective"] != v["version_default"] for v in defaults.values()
        ):
            raise ValueError("algorithm_defaults_mismatch")
        for key in (
            "optimize_wall_seconds",
            "process_cpu_seconds",
            "process_peak_rss_bytes",
        ):
            value = report[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError("invalid_measurement")
        gap = report["mip_gap_relative"]
        if gap is not None and (
            isinstance(gap, bool)
            or not isinstance(gap, (int, float))
            or gap < 0
            or not math.isfinite(gap)
        ):
            raise ValueError("invalid_gap")
        rows.append(
            {
                "source_instance_id": report["source_instance_id"],
                "difficulty": difficulty,
                "threads": int(cap),
                "source_objective_sense": report["source_objective_sense"],
                "effective_objective_sense": report["effective_objective_sense"],
                "objective_sense_override_applied": report[
                    "objective_sense_override_applied"
                ],
                "solver_status": report["solver_status"],
                "mip_gap_relative": gap,
                "termination": report["termination"],
                "optimize_wall_seconds": report["optimize_wall_seconds"],
                "process_cpu_seconds": report["process_cpu_seconds"],
                "process_peak_rss_bytes": report["process_peak_rss_bytes"],
                "primal": report["primal"],
                "dual": report["dual"],
            }
        )
        payloads[f"{name}/attempt_report.json"] = path.read_bytes()
    complete = (
        len(rows) == 10
        and execution["failure_type"] is None
        and all(item["exit_code"] == 0 for item in execution["executions"])
    )
    if execution["failure_type"] is None and not complete:
        raise ValueError("incomplete_execution_claims_success")
    payloads["pilot_plan.json"] = (directory / "pilot_plan.json").read_bytes()
    payloads["pilot_execution_report.json"] = (
        directory / "pilot_execution_report.json"
    ).read_bytes()
    return rows, payloads, complete


def package(directory, expected_sha, output):
    directory, output = Path(directory), Path(output)
    if output.exists():
        raise ValueError("fresh_package_required")
    rows, payloads, complete = verify(directory, expected_sha)
    buffer = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    payloads["thread_screen_outcomes.csv"] = buffer.getvalue().encode()
    payloads["verification.json"] = (
        json.dumps(
            {
                "schema_version": 1,
                "plan_sha256": expected_sha,
                "complete_matrix": complete,
                "attempt_reports_verified": len(rows),
                "scientific_reporting_eligible": False,
                "raw_inputs_included": False,
                "private_logs_included": False,
                "scope": "pilot_receipt_integrity_not_general_scaling_evidence",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode()
    for data in payloads.values():
        if PRIVATE.search(data.decode("utf-8")):
            raise ValueError("declared_text_sanitization_failed")
    import hashlib

    payloads["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(payloads.items())
    ).encode()
    with (
        output.open("xb") as stream,
        tarfile.open(fileobj=stream, mode="w:gz") as archive,
    ):
        for name, data in sorted(payloads.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mtime = 0
            archive.addfile(member, io.BytesIO(data))
    with tarfile.open(output, "r:gz") as archive:
        if {m.name for m in archive.getmembers()} != set(payloads) or any(
            archive.extractfile(name).read() != data for name, data in payloads.items()
        ):
            raise ValueError("archive_readback_mismatch")
    print("PR66_ATTEMPT_HASHES_AND_CONTRACT_OK")
    print("PR66_DECLARED_TEXT_SANITIZATION_OK")
    print(f"COMPLETE_MATRIX={str(complete).lower()}")
    print(f"PACKAGE_SHA256={digest(output)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_dir", type=Path)
    parser.add_argument("--expected-plan-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package(args.plan_dir, args.expected_plan_sha, args.output)
