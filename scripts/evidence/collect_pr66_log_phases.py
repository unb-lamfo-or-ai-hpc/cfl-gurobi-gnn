"""Collect allowlisted log observations for completed job 3468; never solve.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence/pr66/job3468"
PLAN_SHA = "7cfd6bf270e04f96c0745ebf61ae427a949d24a85b571879d9c746af1f75b152"
MANIFEST_SHA = "4d13059a47f862124babdb9377e7f6ab75d9562d1a4c7dec37e9ce88583b0c7f"
NAMES = [f"{d}-threads{t}" for t in (1, 2, 4, 8, 16) for d in ("easy", "medium")]
MAX_BYTES = 8 * 1024 * 1024
NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
WORK = rf"(?: \({NUM} work units\))?"
PRESOLVE = re.compile(rf"Presolve time: ({NUM})s")
RELAX = re.compile(
    rf"Root relaxation: (objective {NUM}|interrupted|infeasible|unbounded|cutoff), "
    rf"(\d+) iterations, ({NUM}) seconds{WORK}"
)
FOOTER = re.compile(
    rf"Explored (\d+) nodes \((\d+) simplex iterations\) in ({NUM}) seconds{WORK}"
)
BOUNDS = re.compile(rf"Best objective ({NUM}), best bound ({NUM}), gap ({NUM})%")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bounded_read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("unsafe_or_oversized_source")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("source_grew_beyond_bound")
    return data


def public_receipts(evidence=EVIDENCE):
    """Trust only the already reviewed original receipt bytes, not new claims."""
    manifest = bounded_read(evidence / "SHA256SUMS.txt")
    if sha(manifest) != MANIFEST_SHA:
        raise ValueError("reviewed_manifest_changed")
    expected = {f"{n}/attempt_report.json" for n in NAMES} | {
        "pilot_plan.json",
        "pilot_execution_report.json",
        "thread_screen_outcomes.csv",
        "verification.json",
    }
    payloads = {}
    for line in manifest.decode("ascii").splitlines():
        digest, name = line.split("  ", 1)
        if name not in expected or name in payloads:
            raise ValueError("unexpected_manifest_member")
        data = bounded_read(evidence / name)
        if sha(data) != digest:
            raise ValueError("reviewed_receipt_changed")
        payloads[name] = data
    if set(payloads) != expected or sha(payloads["pilot_plan.json"]) != PLAN_SHA:
        raise ValueError("incomplete_reviewed_receipts")
    return payloads


def parse_log(text, report):
    """Rounded display observations, not a disjoint phase-cost decomposition."""
    lines = [line.strip() for line in text.splitlines()]
    result = {
        "log_state": "unqualified",
        "presolve_display_seconds": None,
        "root_relaxation_state": "unavailable",
        "root_relaxation_display_seconds": None,
        "root_relaxation_iterations": None,
        "solver_total_display_seconds": None,
        "warnings": [],
    }
    headers = [s for s in lines if s.startswith("Gurobi Optimizer version ")]
    if len(headers) != 1 or not re.fullmatch(
        r"Gurobi Optimizer version 13\.0\.1(?:\s.*)?", headers[0]
    ):
        result["warnings"] = ["missing_foreign_or_multiple_solver_headers"]
        return result
    controls = {
        key: [float(m[1]) for s in lines if (m := re.fullmatch(rf"{key}\s+({NUM})", s))]
        for key in ("Threads", "Seed", "TimeLimit", "MIPGap", "SoftMemLimit")
    }
    if any(values != [report["parameters"][k]] for k, values in controls.items()):
        result["warnings"] = ["missing_duplicate_or_mismatched_controls"]
        return result
    footers = [m for s in lines if (m := FOOTER.fullmatch(s))]
    bounds = [m for s in lines if (m := BOUNDS.fullmatch(s))]
    if len(footers) != 1 or len(bounds) != 1:
        result["warnings"] = ["missing_or_multiple_terminal_summaries"]
        return result
    footer, bound = footers[0], bounds[0]
    runtime = float(footer[3])
    observed = [runtime, *(float(bound[i]) for i in (1, 2, 3))]
    if (
        not all(math.isfinite(v) for v in observed)
        or runtime < 0
        or abs(runtime - report["solver_runtime_seconds"]) > 0.051
        or int(footer[1]) != report["node_count"]
        or not math.isclose(
            float(bound[1]), report["primal"], rel_tol=1e-10, abs_tol=1e-10
        )
        or not math.isclose(
            float(bound[2]), report["dual"], rel_tol=1e-10, abs_tol=1e-10
        )
        or abs(float(bound[3]) / 100 - report["mip_gap_relative"]) > 0.000001
    ):
        result["warnings"] = ["terminal_summary_receipt_mismatch"]
        return result
    result["log_state"] = "receipt_consistent_observations"
    result["solver_total_display_seconds"] = runtime
    for prefix, pattern in (("presolve", PRESOLVE), ("root_relaxation", RELAX)):
        matches = [m for s in lines if (m := pattern.fullmatch(s))]
        # Unknown formats or multiple nested/concurrent summaries are unavailable.
        starts = "Presolve time:" if prefix == "presolve" else "Root relaxation:"
        candidate_count = sum(s.startswith(starts) for s in lines)
        if candidate_count != 1 or len(matches) != 1:
            result["warnings"].append(f"{prefix}_missing_multiple_or_unsupported")
            continue
        match = matches[0]
        duration = float(match[1 if prefix == "presolve" else 3])
        if not math.isfinite(duration) or not 0 <= duration <= runtime + 0.051:
            result["warnings"].append(f"{prefix}_invalid_duration")
            continue
        result[f"{prefix}_display_seconds"] = duration
        if prefix == "root_relaxation":
            result["root_relaxation_iterations"] = int(match[2])
            result["root_relaxation_state"] = (
                "completed" if match[1].startswith("objective ") else match[1]
            )
    return result


def collect(plan_dir, output, evidence=EVIDENCE):
    plan_dir, output = Path(plan_dir).resolve(), Path(output).absolute()
    payloads = public_receipts(evidence)
    if output.exists() or output.resolve().is_relative_to(plan_dir):
        raise ValueError("fresh_output_outside_source_required")
    for name, expected in payloads.items():
        if name.endswith(".json") and name != "verification.json":
            if bounded_read(plan_dir / name) != expected:
                raise ValueError("source_receipt_differs_from_reviewed_job3468")
    rows, logs = [], {}
    for name in NAMES:
        report_bytes = payloads[f"{name}/attempt_report.json"]
        report = json.loads(report_bytes)
        log_path = plan_dir / name / "gurobi.private.log"
        if log_path.is_symlink() or log_path.parent.is_symlink():
            raise ValueError("symlink_log_source_rejected")
        row = {
            "attempt": name,
            "source_instance_id": report["source_instance_id"],
            "threads": report["parameters"]["Threads"],
            "slurm_job_id": "3468",
            "attempt_report_sha256": sha(report_bytes),
            "log_sha256": None,
            "log_size_bytes": None,
            "model_read_setup_seconds": report["model_read_setup_seconds"],
            "optimize_wall_seconds": report["optimize_wall_seconds"],
            "solver_runtime_seconds": report["solver_runtime_seconds"],
            "node_count": report["node_count"],
            "termination": report["termination"],
            "log_state": "missing",
            "presolve_display_seconds": None,
            "root_relaxation_state": "unavailable",
            "root_relaxation_display_seconds": None,
            "root_relaxation_iterations": None,
            "solver_total_display_seconds": None,
            "warnings": [],
        }
        if log_path.exists():
            data = bounded_read(log_path)
            logs[name] = (log_path, sha(data))
            row.update(log_sha256=sha(data), log_size_bytes=len(data))
            try:
                row.update(parse_log(data.decode("utf-8"), report))
            except UnicodeDecodeError:
                row.update(log_state="unsupported_encoding", warnings=["not_utf8"])
        rows.append(row)
    # No mutation during reading; hashes are collection-time observations only.
    if any(sha(bounded_read(path)) != digest for path, digest in logs.values()):
        raise ValueError("log_changed_during_collection")
    for name, expected in payloads.items():
        if name.endswith(".json") and name != "verification.json":
            if bounded_read(plan_dir / name) != expected:
                raise ValueError("receipt_changed_during_collection")
    value = {
        "schema_version": 1,
        "parser": "gurobi_13_0_1_display_observations_v1",
        "collector_sha256": sha(Path(__file__).read_bytes()),
        "reviewed_manifest_sha256": MANIFEST_SHA,
        "plan_sha256": PLAN_SHA,
        "job_id": "3468",
        "log_provenance": "retained_sibling_collection_time_hash_not_execution_time_binding",
        "scientific_reporting_eligible": False,
        "phase_cpu_costs_qualified": False,
        "tree_phase_duration_qualified": False,
        "optimization_runs": 0,
        "private_logs_included": False,
        "rows": rows,
    }
    exported = {
        "phase_observations.json": (
            json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode()
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows({**r, "warnings": ";".join(r["warnings"])} for r in rows)
    exported["phase_observations.csv"] = stream.getvalue().encode()
    exported["SHA256SUMS.txt"] = "".join(
        f"{sha(data)}  {name}\n" for name, data in sorted(exported.items())
    ).encode()
    output.mkdir(parents=True, exist_ok=False)
    for name, data in exported.items():
        with (output / name).open("xb") as target:
            target.write(data)
    package = output / "pr66_phase_observations.tar.gz"
    with (
        package.open("xb") as target,
        tarfile.open(fileobj=target, mode="w:gz") as archive,
    ):
        for name, data in sorted(exported.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mtime = 0
            archive.addfile(member, io.BytesIO(data))
    with tarfile.open(package, "r:gz") as archive:
        if {m.name for m in archive.getmembers()} != set(exported) or any(
            archive.extractfile(name).read() != data for name, data in exported.items()
        ):
            raise ValueError("package_readback_mismatch")
    print("PR66_PHASE_OBSERVATIONS_READ_ONLY_NO_OPTIMIZATION")
    print(f"ROWS={len(rows)}")
    print(
        f"RECEIPT_CONSISTENT_LOGS={sum(r['log_state'] == 'receipt_consistent_observations' for r in rows)}"
    )
    print(f"PACKAGE_SHA256={sha(package.read_bytes())}")
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    collect(args.plan_dir, args.output)
