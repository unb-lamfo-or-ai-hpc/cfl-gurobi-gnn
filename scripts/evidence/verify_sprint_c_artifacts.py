"""Verify selected historical graph/label bytes without deserialization or solving."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import stat
import sys
import time
from pathlib import Path, PurePosixPath

import audit_sprint_c_inputs as metadata

SELECTION = {
    "easy": (
        "cbf0fe92b07aa79de97b9ac616a64178534156b58224fd43ae8494b9d54839ae",
        "easy_only_medium_transfer_v1",
        {"train": 18, "validation": 6, "test": 6},
    ),
    "mixed": (
        "07c3377c20ef49c0ad3ae33a6b57d9dd70f92fc48a32f5f80c25b5cb32aa5da4",
        "pr57_54_parent_development_v1",
        {"train": 34, "validation": 10, "test": 10},
    ),
}
SOURCE_RECEIPT = "1183e69f817a62ae249e2d41a110de941084b19cfbfa4c641d03248a3796781e"
REPORT_NAMES = {"confirmation_graph_report.json", "pr57_54_graph_report.json"}


class AuditStop(ValueError):
    """Only fixed public codes, never private exception strings."""


class Reader:
    def __init__(self, root, *, seconds=180, max_bytes=8 * 1024**3):
        self.root = Path(root).resolve(strict=True)
        self.deadline = time.monotonic() + seconds
        self.maximum = max_bytes
        self.bytes_read = 0
        self.entries = 0
        self.files = []
        self.cache = {}
        self.links_skipped = 0

    def tick(self):
        if time.monotonic() > self.deadline:
            raise AuditStop("time_budget_exceeded")

    def safe(self, path):
        path = Path(path)
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            raise AuditStop("outside_data_root") from None
        cursor = self.root
        for part in relative.parts:
            if part in metadata.EXCLUDED or part in ("..", "."):
                raise AuditStop("excluded_path")
            cursor /= part
            if cursor.is_symlink():
                raise AuditStop("symlink_reference")
        if not path.resolve().is_relative_to(self.root):
            raise AuditStop("outside_data_root")
        return path

    def scan(self):
        def visit(path):
            with os.scandir(path) as stream:
                for entry in stream:
                    self.entries += 1
                    self.tick()
                    if self.entries > 20000:
                        raise AuditStop("entry_budget_exceeded")
                    if entry.name in metadata.EXCLUDED:
                        continue
                    if entry.is_symlink():
                        self.links_skipped += 1
                    elif entry.is_dir(follow_symlinks=False):
                        visit(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        self.files.append(Path(entry.path))

        for group in metadata.GROUPS:
            path = self.root / group
            if path.is_symlink():
                self.links_skipped += 1
            elif path.is_dir():
                visit(path)

    def read(self, path, *, content=False):
        path = self.safe(path)
        self.tick()
        before = path.stat()
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if not content and path in self.cache:
            cached_identity, sha = self.cache[path]
            if identity != cached_identity:
                raise AuditStop("artifact_changed")
            return sha
        limit = 8 * 1024**2 if content else 2 * 1024**3
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise AuditStop("file_size_or_type_limit")
        if self.bytes_read + before.st_size > self.maximum:
            raise AuditStop("byte_budget_exceeded")
        result, chunks, count = hashlib.sha256(), [], 0
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            if not os.path.samestat(before, os.fstat(stream.fileno())):
                raise AuditStop("artifact_changed")
            while True:
                self.tick()
                block = stream.read(min(1024**2, before.st_size - count + 1))
                if not block:
                    break
                count += len(block)
                self.bytes_read += len(block)
                if count > before.st_size or self.bytes_read > self.maximum:
                    raise AuditStop("artifact_changed_or_budget_exceeded")
                result.update(block)
                if content:
                    chunks.append(block)
            after = os.fstat(stream.fileno())
        end = path.stat()
        if (
            count != before.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or not os.path.samestat(before, end)
            or end.st_mtime_ns != before.st_mtime_ns
        ):
            raise AuditStop("artifact_changed")
        self.cache[path] = (identity, result.hexdigest())
        return b"".join(chunks) if content else result.hexdigest()

    def reference(self, base, relative):
        if (
            not isinstance(relative, str)
            or not relative
            or "\\" in relative
            or ":" in relative
        ):
            raise AuditStop("invalid_relative_reference")
        parts = PurePosixPath(relative)
        if parts.is_absolute() or ".." in parts.parts:
            raise AuditStop("invalid_relative_reference")
        return self.safe(base.joinpath(*parts.parts))

    def verify(self, path, expected):
        if not isinstance(expected, str) or not metadata.HASH.fullmatch(expected):
            raise AuditStop("invalid_expected_hash")
        actual = self.read(path)
        if actual != expected:
            raise AuditStop("artifact_hash_mismatch")
        return {
            "sha256": actual,
            "artifact_id": metadata.digest(
                path.relative_to(self.root).as_posix().encode()
            ),
            "bytes": path.stat().st_size,
        }


def verify_plan(reader, plan, report_path, report, expected_counts, split):
    summary = metadata.plan_summary(plan)
    if (
        not summary["metadata_consistent"]
        or summary["partition_counts"] != expected_counts
    ):
        raise AuditStop("plan_metadata_or_counts_failed")
    if report.get("gate_status") != "passed":
        raise AuditStop("source_graph_report_failed")
    descriptor = report["manifest"]
    manifest_path = reader.reference(report_path.parent, descriptor["relative_path"])
    manifest = reader.verify(manifest_path, descriptor["sha256"])
    raw = reader.read(manifest_path, content=True)
    rows = [metadata.strict_json(line) for line in raw.splitlines() if line.strip()]
    if len(rows) > 10000 or any(not isinstance(row, dict) for row in rows):
        raise AuditStop("invalid_graph_manifest")
    by_parent = {}
    for row in rows:
        parent = row.get("parent_instance_id")
        if not isinstance(parent, str) or parent in by_parent:
            raise AuditStop("duplicate_or_missing_manifest_parent")
        by_parent[parent] = row
    graph_root = (
        reader.root / "bipartite_graphs"
        if plan["dataset_variant"] == "pr57_54_parent_development_v1"
        else report_path.parent
    )
    output = []
    for row in plan["records"]:
        parent = row["parent_instance_id"]
        expected_fold, role = split[parent]
        if (
            row.get("source_instance_id") != parent
            or row.get("sample_id") != parent
            or row.get("fold") != expected_fold
            or row["role"] != role
        ):
            raise AuditStop("canonical_split_or_identity_mismatch")
        if by_parent.get(parent) != row:
            raise AuditStop("manifest_record_mismatch")
        item = {
            "parent": parent,
            "role": role,
            "mip_sha256_declared": row["mip_sha256"],
            "label_gap_declared": row["label_mip_gap_relative"],
        }
        for kind in ("graph", "root"):
            path = reader.reference(graph_root, row[f"{kind}_relative_path"])
            item[kind] = reader.verify(path, row[f"{kind}_sha256"])
        label_relative = row["label_run_relative_path"] + "/" + row["label_file_name"]
        reader.reference(
            reader.root, label_relative
        )  # Reject unsafe suffixes before lookup.
        suffix = PurePosixPath(label_relative).parts
        candidates = [
            p
            for p in reader.files
            if tuple(p.relative_to(reader.root).parts[-len(suffix) :]) == suffix
        ]
        if len(candidates) != 1:
            raise AuditStop("label_location_missing_or_ambiguous")
        item["label"] = reader.verify(candidates[0], row["label_sha256"])
        output.append(item)
    return {
        "manifest": manifest,
        "partition_counts": summary["partition_counts"],
        "parents": output,
        "selected_artifact_bytes_verified": True,
    }


def collect(root, *, selection=SELECTION, seconds=180, max_bytes=8 * 1024**3):
    reader = Reader(root, seconds=seconds, max_bytes=max_bytes)
    reader.scan()
    plans, reports = {}, {}
    for path in reader.files:
        if path.name == "gasse_training_plan.json" or path.name in REPORT_NAMES:
            raw = reader.read(path, content=True)
            sha = metadata.digest(raw)
            target = plans if path.name == "gasse_training_plan.json" else reports
            target.setdefault(sha, []).append((path, raw))
    split_path = (
        Path(__file__).resolve().parents[2] / "configs/splits/cfl_90_seed42_folds.csv"
    )
    split = {}
    with split_path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            fold = int(row["fold"])
            split[row["source_instance_id"]] = (
                fold,
                "test" if fold == 0 else "validation" if fold == 1 else "train",
            )
    results = {}
    for name, (sha, variant, counts) in selection.items():
        result = {"plan_sha256": sha, "selected_artifact_bytes_verified": False}
        results[name] = result
        try:
            copies = plans.get(sha, [])
            if not copies:
                raise AuditStop("selected_plan_missing")
            plan = metadata.strict_json(copies[0][1])
            if plan.get("dataset_variant") != variant:
                raise AuditStop("selected_variant_mismatch")
            result["identical_plan_copies"] = len(copies)
            candidates = reports.get(plan.get("graph_report_sha256"), [])
            if len(candidates) != 1:
                raise AuditStop("graph_report_missing_or_ambiguous")
            report_path, raw = candidates[0]
            result.update(
                verify_plan(
                    reader, plan, report_path, metadata.strict_json(raw), counts, split
                )
            )
            result["graph_report_sha256"] = metadata.digest(raw)
            result["state"] = "selected_bytes_and_split_verified"
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
            result["state"] = (
                str(error)
                if isinstance(error, AuditStop)
                else "unreadable_or_invalid_selected_artifact"
            )
    return {
        "schema_version": 1,
        "protocol_id": "sprint_c_selected_artifact_audit_v1",
        "source_metadata_receipt_sha256": SOURCE_RECEIPT,
        "implementation_sha256": {
            p.name: metadata.digest(p.read_bytes())
            for p in (Path(__file__), Path(metadata.__file__))
        },
        "split_manifest_sha256": metadata.digest(split_path.read_bytes()),
        "entries_observed": reader.entries,
        "bytes_read": reader.bytes_read,
        "symlinks_skipped": reader.links_skipped,
        "cohorts": results,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "raw_logs_included": False,
        "training_admitted": False,
        "scientific_reporting_eligible": False,
        "limitations": [
            "no_model_or_graph_deserialization",
            "variable_order_and_feasibility_not_recomputed",
            "feature_scaling_not_audited",
            "historical_training_usage_not_proven",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.resolve().is_relative_to(
            args.data_root.resolve()
        ):
            raise AuditStop("unsafe_or_existing_output")
        result = collect(args.data_root)
        raw = (
            json.dumps(result, sort_keys=True, indent=2, allow_nan=False).encode()
            + b"\n"
        )
        with args.output.open("xb") as stream:
            stream.write(raw)
        print(
            json.dumps(
                {
                    "receipt_sha256": metadata.digest(raw),
                    "cohorts": {k: v["state"] for k, v in result["cohorts"].items()},
                    "training_admitted": False,
                    "optimization_runs_added": 0,
                }
            )
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(
            json.dumps(
                {
                    "state": str(error)
                    if isinstance(error, AuditStop)
                    else "collection_failed",
                    "private_text_included": False,
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
