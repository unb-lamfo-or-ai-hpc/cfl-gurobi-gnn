"""Bounded byte inventory for M13/M26; no deserialization, inference or solver."""

import argparse
import json
import re
from pathlib import Path

import audit_sprint_c_inputs as meta
import collect_class_statistics as originals
from verify_sprint_c_artifacts import AuditStop, Reader

PROTOCOL = "e0_medium_existing_artifact_inventory_v1"
PARENTS = ("CFL_medium_instance_13", "CFL_medium_instance_26")
BASE = "91630762bf0b86ec153e2882c42dc83161eebe4a"
MAX_CANDIDATES = 64


def require(condition, code):
    if not condition:
        raise ValueError(code)


def parent_match(relative, parent):
    return (
        re.search(
            r"(?<![A-Za-z0-9])" + re.escape(parent) + r"(?![A-Za-z0-9])", relative
        )
        is not None
    )


def candidate_kind(relative):
    """Hints only; never infer mathematical validity from a filename."""
    name = relative.lower()
    basename = name.rsplit("/", 1)[-1]
    if any(
        word in basename for word in ("secret", "license", "solution", "label", ".log")
    ):
        return None
    if name.endswith((".pt", ".npz", ".pkl", ".pickle")):
        return "graph_or_tensor_candidate"
    if name.endswith((".json", ".json.gz")):
        if "root" in name or "relax" in name:
            return "root_metadata_candidate"
        if "predict" in name or "start" in name:
            return "prediction_or_start_candidate"
        return "metadata_candidate"
    return None


def collect(data_root, output):
    root, output = Path(data_root).resolve(strict=True), Path(output).resolve()
    require(not output.exists(), "fresh_output_required")
    require(
        not output.is_relative_to(root) and not root.is_relative_to(output),
        "output_outside_data",
    )
    reader = Reader(root, seconds=180, max_bytes=4 * 1024**3)
    rows, private, warnings = [], {}, []
    originals_state = {}

    def add(parent, path, kind):
        require(len(rows) < MAX_CANDIDATES, "candidate_limit")
        reader.safe(path)
        artifact_id = meta.digest(path.relative_to(root).as_posix().encode())
        sha = reader.read(path)
        rows.append(
            {
                "parent": parent,
                "kind": kind,
                "artifact_id": artifact_id,
                "sha256": sha,
                "bytes": path.stat().st_size,
                "content_semantics_qualified": False,
            }
        )
        private[artifact_id] = str(path)

    try:
        for parent in PARENTS:
            path, state = originals.original_model(
                root / "raw/MILPBench/CFL", "medium", int(parent.rsplit("_", 1)[1])
            )
            originals_state[parent] = state
            if path is not None:
                add(parent, path, "original_milp_bytes")
        reader.scan()
        for path in sorted(reader.files):
            relative = path.relative_to(root).as_posix()
            kind = candidate_kind(relative)
            if kind is None:
                continue
            for parent in PARENTS:
                if parent_match(relative, parent):
                    add(parent, path, kind)
    except (AuditStop, ValueError, OSError) as error:
        # No exception text/path is exported; retain partial, never admit a run.
        safe_codes = {
            "time_budget_exceeded",
            "entry_budget_exceeded",
            "byte_budget_exceeded",
            "candidate_limit",
            "file_size_or_type_limit",
            "symlink_reference",
            "outside_data_root",
            "excluded_path",
            "artifact_changed",
            "artifact_changed_or_budget_exceeded",
        }
        warnings.append(
            str(error)
            if str(error) in safe_codes
            else "bounded_inventory_stopped_" + type(error).__name__
        )
    value = {
        "protocol_id": PROTOCOL,
        "base_merge_commit": BASE,
        "collector_sha256_lf": meta.digest(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ),
        "parents": list(PARENTS),
        "canonical_role": "train",
        "learning_admitted": False,
        "historically_exposed": True,
        "state": "partial" if warnings else "bounded_inventory_complete",
        "discovery_scope": "two_canonical_originals_and_parent_named_files_in_existing_metadata_groups",
        "absence_proven": False,
        "originals": originals_state,
        "candidates": rows,
        "warnings": warnings,
        "entries_observed": reader.entries,
        "bytes_read": reader.bytes_read,
        "symlinks_skipped": reader.links_skipped,
        "limits": {
            "entries": 20000,
            "candidate_files": MAX_CANDIDATES,
            "bytes": 4 * 1024**3,
            "elapsed_seconds_between_io_checks": 180,
        },
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "forwards_added": 0,
        "scheduler_queries": 0,
        "submissions_added": 0,
        "solver_execution_admitted": False,
        "raw_paths_included": False,
        "raw_content_included": False,
        "scientific_reporting_eligible": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "private_paths.json").write_bytes(meta.canonical(private) + b"\n")
    data = (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    with (output / "inventory.json").open("xb") as stream:
        stream.write(data)
    print("E0_MEDIUM_INVENTORY_SHA256=" + meta.digest(data))
    print("E0_MEDIUM_INVENTORY_OUTPUT=" + str(output))
    print(
        json.dumps(
            {
                "state": value["state"],
                "candidates": len(rows),
                "optimization_runs_added": 0,
                "solver_execution_admitted": False,
            }
        )
    )
    return value


def validate(data, expected):
    require(meta.digest(data) == expected, "receipt_hash")
    value = meta.strict_json(data)
    require(
        value["protocol_id"] == PROTOCOL and value["parents"] == list(PARENTS),
        "identity",
    )
    require(value["base_merge_commit"] == BASE, "base")
    require(
        value["canonical_role"] == "train" and value["historically_exposed"] is True,
        "stratum",
    )
    for key in (
        "optimization_runs_added",
        "training_runs_added",
        "forwards_added",
        "scheduler_queries",
        "submissions_added",
    ):
        require(type(value[key]) is int and value[key] == 0, "execution_scope")
    for key in (
        "learning_admitted",
        "solver_execution_admitted",
        "raw_paths_included",
        "raw_content_included",
        "scientific_reporting_eligible",
        "absence_proven",
    ):
        require(value[key] is False, "scope")
    require(value["state"] in ("partial", "bounded_inventory_complete"), "state")
    require(len(value["candidates"]) <= MAX_CANDIDATES, "candidate_limit")
    seen = set()
    for row in value["candidates"]:
        require(
            set(row)
            == {
                "parent",
                "kind",
                "artifact_id",
                "sha256",
                "bytes",
                "content_semantics_qualified",
            },
            "candidate_schema",
        )
        require(
            row["parent"] in PARENTS and row["content_semantics_qualified"] is False,
            "candidate_scope",
        )
        require(
            row["kind"]
            in {
                "original_milp_bytes",
                "graph_or_tensor_candidate",
                "root_metadata_candidate",
                "prediction_or_start_candidate",
                "metadata_candidate",
            },
            "candidate_kind",
        )
        require(
            all(
                isinstance(row[k], str) and meta.HASH.fullmatch(row[k])
                for k in ("sha256", "artifact_id")
            ),
            "hash",
        )
        require(type(row["bytes"]) is int and 0 <= row["bytes"] <= 2 * 1024**3, "size")
        key = (row["parent"], row["artifact_id"])
        require(key not in seen, "duplicate_candidate")
        seen.add(key)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    col = sub.add_parser("collect")
    col.add_argument("--data-root", type=Path, required=True)
    col.add_argument("--output", type=Path, required=True)
    rev = sub.add_parser("review")
    rev.add_argument("--receipt", type=Path, required=True)
    rev.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    if args.command == "collect":
        return (
            0
            if collect(args.data_root, args.output)["state"]
            == "bounded_inventory_complete"
            else 2
        )
    value = validate(args.receipt.read_bytes(), args.expected_sha256)
    print(
        json.dumps(
            {
                "state": value["state"],
                "candidates": len(value["candidates"]),
                "solver_execution_admitted": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
