"""Bounded, metadata-only Sprint C audit. Never loads graphs or a solver."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import time
from pathlib import Path

PROTOCOL = "sprint_c_input_metadata_audit_v2"
REPORT_VARIANTS = {
    "easy_only_medium_transfer_v1",
    "pr57_54_parent_development_v1",
    "approved_39_parent_development_v1",
    "independently_admitted_confirmation_v1",
}
GROUPS = ("analysis", "models", "bipartite_graphs", "intermediate")
NAMES = {"gasse_training_plan.json", "gurobi_graph_manifest.jsonl"}
EXCLUDED = {"secrets", ".git", "__pycache__", "bootstrap", "tools"}
ROLES = ("train", "validation", "test")
PARENT = re.compile(r"CFL_(easy|medium|hard)_instance_([0-9]|[12][0-9])\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
IGNORED = {
    "contract_sha256",
    "contract_valid",
    "training_ready",
    "engineering_smoke_ready",
    "held_out_evaluation_ready",
    "warnings",
    "next_gate",
}
LIMITATIONS = [
    "declared_references_not_binary_hash_verified",
    "label_feasibility_and_variable_order_not_rechecked",
    "graph_numerical_features_not_loaded",
    "historical_costs_and_gpu_telemetry_not_reconstructed",
    "metadata_consistency_does_not_admit_training",
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite_json")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def plan_summary(plan):
    """Check declarations, not the bytes or feasibility of their referenced artifacts."""
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("unsupported_plan")
    issues = set()
    variant = plan.get(
        "dataset_variant", "gurobi_authoritative_graph_solver_label_view_v1"
    )
    report_backed = variant in REPORT_VARIANTS
    if (
        not report_backed
        and variant != "gurobi_authoritative_graph_solver_label_view_v1"
    ):
        issues.add("unsupported_dataset_variant")
    payload = {k: v for k, v in plan.items() if k not in IGNORED}
    if digest(canonical(payload)) != plan.get("contract_sha256"):
        issues.add("contract_hash_mismatch")
    records = plan.get("records")
    if not isinstance(records, list) or not records or len(records) > 10000:
        raise ValueError("invalid_records")
    parents = {role: set() for role in ROLES}
    counts = {role: 0 for role in ROLES}
    rows, samples, identities = [], set(), {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid_record")
        parent, role = record.get("parent_instance_id"), record.get("role")
        if (
            not isinstance(parent, str)
            or not PARENT.fullmatch(parent)
            or role not in ROLES
        ):
            issues.add("invalid_parent_or_role")
            continue
        parents[role].add(parent)
        counts[role] += 1
        sample = record.get("sample_id")
        if not isinstance(sample, str) or not sample or sample in samples:
            issues.add("missing_or_duplicate_sample")
        else:
            samples.add(sample)
        hashes = {}
        for key in (
            "mip_sha256",
            "graph_sha256",
            "root_sha256",
            "label_sha256",
            "label_contract_sha256",
        ):
            value = record.get(key)
            hashes[key] = (
                value if isinstance(value, str) and HASH.fullmatch(value) else None
            )
            if hashes[key] is None:
                issues.add("missing_or_invalid_identity_hash")
        mip, graph = hashes["mip_sha256"], hashes["graph_sha256"]
        if mip and graph:
            previous = identities.setdefault(mip, (graph, role))
            if previous[0] != graph:
                issues.add("one_mip_multiple_graph_hashes")
            if previous[1] != role:
                issues.add("mip_identity_role_leakage")
        gap = record.get("label_mip_gap_relative")
        valid_gap = (
            type(gap) in (int, float) and math.isfinite(gap) and 0 <= gap <= 0.10
        )
        if not valid_gap:
            issues.add("missing_or_ineligible_label_gap")
        if record.get("sampling_strategy") != "original":
            issues.add("non_original_requires_separate_admission")
        if record.get("graph_authority") != "gurobi" or record.get(
            "label_solver"
        ) not in ("gurobi", "scip"):
            issues.add("unsupported_graph_or_label_authority")
        rows.append(
            {
                "parent": parent,
                "role": role,
                "label_gap": gap if valid_gap else None,
                **hashes,
            }
        )
    if any(
        parents[a] & parents[b]
        for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))
    ):
        issues.add("parent_role_leakage")
    if any(not parents[role] for role in ROLES):
        issues.add("missing_role")
    if plan.get("partition_counts") != counts:
        issues.add("declared_partition_count_mismatch")
    if (not report_backed or "parent_ids_by_role" in plan) and plan.get(
        "parent_ids_by_role"
    ) != {r: sorted(parents[r]) for r in ROLES}:
        issues.add("declared_parent_roles_mismatch")
    manifest = plan.get("graph_manifest_sha256")
    report = plan.get("graph_report_sha256")
    if report_backed:
        manifest = None
    if report_backed and (not isinstance(report, str) or not HASH.fullmatch(report)):
        issues.add("invalid_graph_report_hash")
        report = None
    if not report_backed and (
        not isinstance(manifest, str) or not HASH.fullmatch(manifest)
    ):
        issues.add("invalid_graph_manifest_hash")
        manifest = None
    return {
        "dataset_variant": variant
        if report_backed or variant == "gurobi_authoritative_graph_solver_label_view_v1"
        else "unsupported",
        "reference_kind": "graph_report" if report_backed else "graph_manifest",
        "graph_report_sha256": report if report_backed else None,
        "record_count": len(records),
        "partition_counts": counts,
        "parent_ids_by_role": {r: sorted(parents[r]) for r in ROLES},
        "graph_manifest_sha256": manifest,
        "records": rows,
        "issues": sorted(issues),
        "metadata_consistent": not issues,
    }


def collect(root, *, max_entries=20000, max_bytes=64 * 1024 * 1024, seconds=45):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("data_root_not_directory")
    deadline = time.monotonic() + seconds
    entries, total, skipped = 0, 0, 0
    plans, manifests, failures = [], [], []
    present = []

    def tick():
        if entries > max_entries or time.monotonic() > deadline:
            raise ValueError("inventory_budget_exceeded")

    def walk(directory):
        nonlocal entries, skipped
        with os.scandir(directory) as stream:
            for entry in stream:
                entries += 1
                tick()
                if entry.is_symlink():
                    skipped += 1
                    continue
                if entry.name in EXCLUDED:
                    continue
                if entry.is_dir(follow_symlinks=False):
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
        present.append(group)
        for path in walk(directory):
            tick()
            artifact_id = digest(path.relative_to(root).as_posix().encode())
            try:
                before = path.lstat()
                if not stat.S_ISREG(before.st_mode) or before.st_size > 8 * 1024 * 1024:
                    raise ValueError("not_bounded_regular_metadata")
                if total + before.st_size > max_bytes:
                    raise ValueError("read_budget_exceeded")
                # Bounded read; reject replacement/symlink and concurrent mutation.
                flags = (
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_BINARY", 0)
                )
                with os.fdopen(os.open(path, flags), "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if not os.path.samestat(before, opened):
                        raise ValueError("metadata_changed")
                    data = stream.read(8 * 1024 * 1024 + 1)
                    after = os.fstat(stream.fileno())
                total += len(data)
                tick()
                if (
                    len(data) != before.st_size
                    or after.st_mtime_ns != before.st_mtime_ns
                    or not os.path.samestat(before, path.lstat())
                ):
                    raise ValueError("metadata_changed")
                base = {"artifact_id": artifact_id, "sha256": digest(data)}
                if path.name == "gasse_training_plan.json":
                    plans.append({**base, **plan_summary(strict_json(data))})
                else:
                    manifests.append(base)
            except (OSError, ValueError, TypeError, RecursionError):
                failures.append(
                    {
                        "artifact_id": artifact_id,
                        "state": "unreadable_or_invalid_metadata",
                    }
                )
    manifest_hashes = {m["sha256"] for m in manifests}
    for plan in plans:
        plan["graph_manifest_bytes_observed"] = (
            plan["graph_manifest_sha256"] in manifest_hashes
        )
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "groups_present": present,
        "entries_observed": entries,
        "metadata_bytes_read": total,
        "symlinks_skipped": skipped,
        "plans": sorted(plans, key=lambda p: p["artifact_id"]),
        "manifests": sorted(manifests, key=lambda p: p["artifact_id"]),
        "failures": sorted(failures, key=lambda p: p["artifact_id"]),
        "inventory_complete": not failures,
        "metadata_candidates_present": bool(plans),
        "training_admitted": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "raw_logs_included": False,
        "limitations": LIMITATIONS,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("output_exists")
        if args.output.resolve().is_relative_to(args.data_root.resolve()):
            raise ValueError("output_must_be_outside_dataset")
        result = collect(args.data_root)
        # One file only, exclusive creation; collection never mutates input metadata.
        encoded = (
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False).encode()
            + b"\n"
        )
        with args.output.open("xb") as stream:
            stream.write(encoded)
        print(
            json.dumps(
                {
                    "receipt_sha256": digest(encoded),
                    "plans_observed": len(result["plans"]),
                    "invalid_metadata": len(result["failures"]),
                    "training_admitted": False,
                    "optimization_runs_added": 0,
                }
            )
        )
        return 0
    except (OSError, ValueError, TypeError, RecursionError) as error:
        print(
            json.dumps(
                {
                    "state": "stopped_no_solver_preserve_inputs",
                    "error_type": type(error).__name__,
                    "private_text_included": False,
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
