"""Locate existing E0 method metadata; no solver, training or artifact loading."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import stat
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = "e0_existing_method_metadata_v1"
METHODS = (
    "unguided_control",
    "root_lp_matched_partial_start",
    "gnn_class_aware_partial_start",
)
NAMES = {f"{m}.json" for m in METHODS} | {
    "per_method_outcomes.json",
    "pr58_validation_guidance_plan.json",
    "pr59_heldout_guidance_plan.json",
}
GROUPS = ("analysis", "intermediate", "models")
EXCLUDED = {"secrets", ".git", "__pycache__", "bootstrap", "tools"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
SOLVE_FIELDS = (
    "primal",
    "dual",
    "terminal_mip_gap_relative",
    "solver_runtime_seconds",
    "model_optimize_wall_time_seconds",
    "total_wall_time_seconds",
    "first_observed_gap_le_0.1_seconds",
    "solve_status_code",
    "node_count",
)
PARAMETERS = (
    "Threads",
    "Seed",
    "TimeLimit",
    "MIPGap",
    "MIPGapAbs",
    "Presolve",
    "Heuristics",
    "Method",
    "NodeMethod",
    "Cuts",
    "MIPFocus",
    "StartNodeLimit",
    "NumericFocus",
    "FeasibilityTol",
    "IntFeasTol",
    "OptimalityTol",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def sha(value):
    return value if isinstance(value, str) and HEX.fullmatch(value) else None


def population():
    path = ROOT / "docs/evidence/pr80-results/e0_published_coverage.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 48 or len({(r["parent"], r["method"]) for r in rows}) != 48:
        raise ValueError("coverage_population_changed")
    return rows


def summarize(value, file_name, artifact_id, file_sha, targets):
    """Only allowlisted scalars leave HPC; no paths, free text or solver logs."""
    if not isinstance(value, dict):
        raise ValueError("object_required")
    base = {"artifact_id": artifact_id, "sha256": file_sha}
    if file_name.endswith("_plan.json"):
        policy = value.get("policy", {})
        if not isinstance(policy, dict):
            raise ValueError("invalid_policy")
        payload = {
            k: v
            for k, v in value.items()
            if k not in ("contract_sha256", "contract_valid")
        }
        return [], [
            {
                **base,
                "contract_sha256": sha(value.get("contract_sha256")),
                "contract_digest_matches": digest(canonical(payload).encode())
                == sha(value.get("contract_sha256")),
                "checkpoint_sha256": sha(value.get("checkpoint_sha256")),
                "training_contract_sha256": sha(value.get("training_contract_sha256")),
                "probability_threshold": number(value.get("probability_threshold")),
                "threads": number(policy.get("gurobi_threads")),
                "main_limit_seconds": number(
                    policy.get("optimization_time_limit_seconds")
                ),
            }
        ]
    records = (
        value.get("records") if file_name == "per_method_outcomes.json" else [value]
    )
    if not isinstance(records, list) or len(records) > 10000:
        raise ValueError("records_limit_or_schema")
    result = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("record_not_object")
        parent, method = row.get("source_instance_id"), row.get("method")
        if parent not in targets or method not in METHODS:
            continue
        solve = row.get("solve", row)
        params = row.get("parameters", {})
        timing = row.get("timing", {})
        start = row.get("start", row)
        if not all(isinstance(x, dict) for x in (solve, params, timing, start)):
            raise ValueError("nested_object_required")
        role = row.get("role")
        result.append(
            {
                **base,
                "parent": parent,
                "method": method,
                "kind": "aggregate"
                if file_name == "per_method_outcomes.json"
                else "method",
                "declared_role": role
                if role in ("train", "validation", "test")
                else None,
                "contract_sha256": sha(row.get("contract_sha256")),
                "mip_sha256": sha(row.get("mip_sha256")),
                "mathematical_signature_sha256": sha(
                    row.get("mathematical_signature_sha256")
                ),
                "parameter_sha256": sha(row.get("parameter_sha256")),
                "parameter_digest_matches": bool(params)
                and digest(canonical(params).encode())
                == sha(row.get("parameter_sha256")),
                "parameters": {k: number(params[k]) for k in PARAMETERS if k in params},
                "gate_passed_declared": row.get("gate_status") == "passed",
                "fresh_model_declared": row.get("fresh_model") is True,
                "model_unchanged_declared": row.get("mathematical_model_unchanged")
                is True,
                "independent_feasibility_declared": isinstance(
                    row.get("independent_feasibility"), dict
                )
                and row["independent_feasibility"].get("valid") is True,
                "outcomes": {k: number(solve.get(k)) for k in SOLVE_FIELDS},
                "timing": {
                    k: number(timing.get(k))
                    for k in (
                        "total_wall_time_seconds",
                        "data_read_wall_time_seconds",
                        "model_build_wall_time_seconds",
                        "model_optimize_wall_time_seconds",
                        "independent_audit_wall_time_seconds",
                        "solution_export_wall_time_seconds",
                    )
                },
                "right_censored": solve.get("right_censored")
                if type(solve.get("right_censored")) is bool
                else None,
                "submitted_assignments": number(start.get("submitted_assignments")),
                "start_status": start.get("status", start.get("start_status"))
                if start.get("status", start.get("start_status"))
                in (
                    "not_submitted",
                    "accepted",
                    "completion_observed_acceptance_unknown",
                    "no_new_incumbent",
                    "submitted_outcome_unknown",
                )
                else None,
                "reuse_admitted": False,
            }
        )
    return result, []


def collect(root, *, max_entries=50000, max_bytes=128 * 1024**2, seconds=120):
    root = Path(root).resolve(strict=True)
    targets = {r["parent"] for r in population()}
    deadline = time.monotonic() + seconds
    entries = total = skipped = 0
    candidates, plans, failures, groups = [], [], [], []

    def tick():
        if entries > max_entries or total > max_bytes or time.monotonic() > deadline:
            raise ValueError("bounded_scan_limit")

    def walk(directory):
        nonlocal entries, skipped
        with os.scandir(directory) as stream:
            for entry in stream:
                entries += 1
                tick()
                if entry.is_symlink():
                    skipped += 1
                elif entry.name in EXCLUDED:
                    continue
                elif entry.is_dir(follow_symlinks=False):
                    yield from walk(Path(entry.path))
                elif entry.name in NAMES and entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)

    for group in GROUPS:
        directory = root / group
        if directory.is_symlink():
            skipped += 1
            continue
        if not directory.is_dir():
            continue
        groups.append(group)
        for path in walk(directory):
            artifact = digest(path.relative_to(root).as_posix().encode())
            try:
                before = path.lstat()
                if not stat.S_ISREG(before.st_mode) or before.st_size > 8 * 1024**2:
                    raise ValueError("metadata_size_limit")
                if total + before.st_size > max_bytes:
                    raise ValueError("read_limit")
                flags = (
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_BINARY", 0)
                )
                with os.fdopen(os.open(path, flags), "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if not os.path.samestat(before, opened):
                        raise ValueError("changed_before_read")
                    data = stream.read(8 * 1024**2 + 1)
                    after = os.fstat(stream.fileno())
                total += len(data)
                tick()
                if (
                    len(data) != before.st_size
                    or after.st_mtime_ns != before.st_mtime_ns
                    or not os.path.samestat(before, path.lstat())
                ):
                    raise ValueError("changed_during_read")
                found, metadata = summarize(
                    strict_json(data), path.name, artifact, digest(data), targets
                )
                candidates.extend(found)
                plans.extend(metadata)
            except (OSError, ValueError, TypeError, RecursionError):
                failures.append(
                    {"artifact_id": artifact, "state": "unreadable_or_invalid_metadata"}
                )
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "groups_present": groups,
        "entries_observed": entries,
        "bytes_read": total,
        "symlinks_skipped": skipped,
        "recognized_metadata_scan_complete": not failures
        and len(groups) == len(GROUPS)
        and skipped == 0,
        "absence_proven": False,
        "candidates": sorted(candidates, key=canonical),
        "plans": sorted(plans, key=canonical),
        "failures": sorted(failures, key=canonical),
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "submissions_added": 0,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
        "solver_execution_admitted": False,
    }


def coverage(receipt):
    if receipt.get("protocol_id") != PROTOCOL or any(
        receipt.get(k) != v
        for k, v in {
            "optimization_runs_added": 0,
            "training_runs_added": 0,
            "submissions_added": 0,
            "raw_logs_included": False,
            "scientific_reporting_eligible": False,
            "solver_execution_admitted": False,
        }.items()
    ):
        raise ValueError("receipt_scope")
    rows = []
    for expected in population():
        matches = [
            r
            for r in receipt["candidates"]
            if (r["parent"], r["method"]) == (expected["parent"], expected["method"])
        ]
        unique = {r["sha256"] for r in matches if r["kind"] == "method"}
        rows.append(
            {
                "parent": expected["parent"],
                "canonical_role": expected["role"],
                "evaluation_stratum": "predictive_test"
                if expected["parent"].startswith("CFL_easy_")
                or expected["parent"]
                in {
                    "CFL_medium_instance_0",
                    "CFL_medium_instance_4",
                    "CFL_medium_instance_7",
                    "CFL_medium_instance_12",
                }
                else "label_excluded_historically_exposed",
                "method": expected["method"],
                "published_records": int(expected["published_records"]),
                "distinct_method_metadata": len(unique),
                "aggregate_metadata_rows": sum(
                    r["kind"] == "aggregate" for r in matches
                ),
                "state": "candidate_needs_compatibility_review"
                if unique
                else "aggregate_only"
                if matches
                else "not_found_in_recognized_scope",
                "role_disagreement": any(
                    r["declared_role"] not in (None, expected["role"]) for r in matches
                ),
                "reuse_admitted": False,
                "new_solve_admitted": False,
            }
        )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gather = sub.add_parser("collect")
    gather.add_argument("--data-root", type=Path, required=True)
    gather.add_argument("--output", type=Path, required=True)
    review = sub.add_parser("review")
    review.add_argument("--receipt", type=Path, required=True)
    review.add_argument("--expected-sha256", required=True)
    review.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "collect":
        if args.output.resolve().is_relative_to(args.data_root.resolve()):
            raise ValueError("output_inside_dataset")
        if args.output.exists():
            raise ValueError("preserve_existing_output")
        receipt = collect(args.data_root)
        data = (
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode()
        with args.output.open("xb") as stream:
            stream.write(data)
    else:
        if args.receipt.stat().st_size > 32 * 1024**2:
            raise ValueError("receipt_size_limit")
        data = args.receipt.read_bytes()
        if digest(data) != args.expected_sha256:
            raise ValueError("receipt_hash_mismatch")
        receipt = strict_json(data)
        rows = coverage(receipt)
        args.output_directory.mkdir(parents=True, exist_ok=False)
        with (args.output_directory / "coverage.csv").open(
            "x", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        proposal = {
            "receipt_sha256": digest(data),
            "rows": rows,
            "candidate_plan_metadata": receipt["plans"],
            "state": "metadata_reconciled_pending_compatibility_review",
            "execution_admitted": False,
            "next": "review_model_policy_parameters_solution_and_cost_provenance_before_freezing_missing_runs",
        }
        (args.output_directory / "proposal.json").write_text(
            json.dumps(proposal, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "receipt_sha256": digest(data),
                "candidate_rows": len(receipt["candidates"]),
                "plan_metadata": len(receipt["plans"]),
                "optimization_runs_added": 0,
                "solver_execution_admitted": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
