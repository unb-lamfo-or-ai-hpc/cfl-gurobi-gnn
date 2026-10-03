"""Reuse audited original graphs for a fresh easy-only Gasse experiment.

No solver is executed, no graph is regenerated, and no medium graph is loaded.
Historical training plans are immutable inputs, not pretrained checkpoints.
"""
from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.confirmation_execution import checked, error_reason, read_json, safe_path
from cfl_gnn.pipelines.confirmation_training import validate_training_receipt
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold
from cfl_gnn.training.gasse_reconnected import (
    LEGACY_GASSE_GIT_BLOB_SHA1, TRAINING_PLAN_NAME, TRAINING_REPORT_NAME,
    canonical_sha256, git_blob_sha1, load_protocol, run_serial_training,
    validate_training_plan, write_json,
)

PROTOCOL = PROJECT_ROOT / "configs/training/gasse_easy_transfer_v1.json"
MANIFEST = PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv"
READY = {"contract_valid", "training_ready", "engineering_smoke_ready", "held_out_evaluation_ready"}


def select_easy_records(source):
    """Require all thirty canonical easy originals, with their existing roles."""
    validate_training_plan(source)
    if source.get("dataset_variant") not in {
        "approved_39_parent_development_v1", "independently_admitted_confirmation_v1"
    } or source.get("graph_authority") != "gurobi" or source.get("label_solver") != "gurobi":
        raise ValueError("source must be an audited original confirmation plan")
    entries = {e.source_instance_id: e for e in read_manifest(MANIFEST) if e.difficulty == "easy"}
    records = []
    seen = set()
    for record in source["records"]:
        identity = record["source_instance_id"]
        if identity in seen:
            raise ValueError("duplicate source parent")
        seen.add(identity)
        if identity not in entries:
            if record.get("difficulty") == "easy":
                raise ValueError("unknown easy parent")
            continue
        entry = entries[identity]
        expected = {
            "sample_id": identity, "parent_instance_id": identity, "difficulty": "easy",
            "category": entry.category, "fold": entry.fold,
            "role": role_for_fold(entry.fold, 0), "sampling_strategy": "original",
            "graph_authority": "gurobi", "label_solver": "gurobi",
            "label_source": "independently_audited_gurobi_confirmation_label",
        }
        if any(record.get(k) != v for k, v in expected.items()):
            raise ValueError("easy parent identity role or provenance changed")
        gap = record.get("label_mip_gap_relative")
        if isinstance(gap, bool) or not isinstance(gap, (int, float)) or not math.isfinite(gap) or not 0 <= gap <= .1:
            raise ValueError("easy label does not meet the fixed gap ceiling")
        records.append(copy.deepcopy(record))
    if len(records) != 30 or {r["source_instance_id"] for r in records} != set(entries):
        raise ValueError("all thirty easy parents are required")
    if len({r["mip_sha256"] for r in records}) != 30:
        raise ValueError("duplicate easy formulation")
    return sorted(records, key=lambda r: r["source_instance_id"])


def build_plan(*, source_training_plan, graph_root, label_root):
    source_path = Path(source_training_plan)
    source = read_json(source_path)
    records = select_easy_records(source)
    for row in records:
        for artifact in ("graph", "root"):
            checked(graph_root, {"relative_path": row[f"{artifact}_relative_path"], "sha256": row[f"{artifact}_sha256"]})
        label_dir = safe_path(label_root, row["label_run_relative_path"])
        checked(label_dir, {"relative_path": row["label_file_name"], "sha256": row["label_sha256"]})
        receipt = read_json(checked(graph_root, row["receipt"]))
        audit = receipt.get("audit", {})
        if (receipt.get("source_instance_id") != row["source_instance_id"]
                or receipt.get("role") != row["role"] or receipt.get("fold") != row["fold"]
                or receipt.get("mip_sha256") != row["mip_sha256"]
                or receipt.get("graph") != {"relative_path": row["graph_relative_path"], "sha256": row["graph_sha256"]}
                or receipt.get("root") != {"relative_path": row["root_relative_path"], "sha256": row["root_sha256"]}
                or receipt.get("source_label", {}).get("sha256") != row["label_sha256"]
                or not all(audit.get(k) is True for k in (
                    "roundtrip_readable", "label_variable_identity_match", "root_lp_feature_exactly_encoded"))
                or audit.get("effective_objective_sense") != "MINIMIZE"
                or audit.get("independent_label_feasibility", {}).get("valid") is not True):
            raise ValueError("easy graph receipt does not certify indexed artifacts")
    if git_blob_sha1(PROJECT_ROOT / "src/cfl_gnn/models/gasse.py") != LEGACY_GASSE_GIT_BLOB_SHA1:
        raise ValueError("preserved Gasse architecture changed")
    protocol = load_protocol(PROTOCOL)
    if (protocol["protocol_id"] != "gasse_easy_only_medium_transfer_v1"
            or protocol["optimization"]["epochs"] != 100
            or protocol["optimization"]["patience"] != 100
            or protocol["optimization"]["seed"] != 42):
        raise ValueError("easy transfer requires the fixed 100 epoch seed42 protocol")
    counts = {role: sum(r["role"] == role for r in records) for role in ("train", "validation", "test")}
    if counts != {"train": 18, "validation": 6, "test": 6}:
        raise ValueError("canonical easy split changed")
    payload = {
        "schema_version": 1, "dataset_variant": "easy_only_medium_transfer_v1",
        "source_training_plan_sha256": sha256_file(source_path),
        "source_training_contract_sha256": source["contract_sha256"],
        "graph_dataset_contract_sha256": source["graph_dataset_contract_sha256"],
        "source_collection_contract_sha256": source["source_collection_contract_sha256"],
        "graph_report_sha256": source["graph_report_sha256"],
        "parent_manifest_sha256": sha256_file(MANIFEST), "rotation": 0,
        "graph_authority": "gurobi", "label_solver": "gurobi", "objective_sense": "MINIMIZE",
        "root_lp_policy": "first_optimal_root_gurobi_mipnode_no_zero_fallback",
        "protocol": protocol, "protocol_sha256": canonical_sha256(protocol),
        "legacy_gasse_git_blob_sha1": LEGACY_GASSE_GIT_BLOB_SHA1,
        "implementation_sha256": {name: sha256_file(PROJECT_ROOT / "src/cfl_gnn" / name) for name in (
            "pipelines/easy_transfer_training.py", "pipelines/confirmation_training.py",
            "models/gasse_calibrated.py", "models/versioning.py", "training/gasse_reconnected.py",
            "training/serial.py", "training/figures.py")},
        "records": records, "partition_counts": counts,
        "initialization": "fresh_seed42_no_pretrained_checkpoint",
        "medium_records_in_training_plan": 0,
        "normalization_scope": "easy_training_only",
        "test_partition_usage": "held_out_not_loaded_during_training",
        "development_only": True, "scientific_reporting_eligible": False,
    }
    return {**payload, "contract_sha256": canonical_sha256(payload), **dict.fromkeys(READY, True)}


def execute(*, source_training_plan, graph_root, label_root, output_dir, expected_contract, device="cuda"):
    plan = build_plan(source_training_plan=source_training_plan, graph_root=graph_root, label_root=label_root)
    if plan["contract_sha256"] != expected_contract:
        raise ValueError("preflight contract changed; do not train")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / TRAINING_PLAN_NAME, plan)
    report = run_serial_training(plan, graph_root=graph_root, label_root=label_root,
                                 output_dir=output, device_name=device)
    validate_training_receipt(report, output)
    result = {
        "gate_status": "passed", "training_contract_sha256": plan["contract_sha256"],
        "training_report_sha256": sha256_file(output / TRAINING_REPORT_NAME),
        "partition_counts": plan["partition_counts"], "epochs_completed": 100,
        "medium_graphs_loaded": 0, "test_graphs_loaded": report["test_graphs_loaded"],
        "checkpoint_selection": report["checkpoint_selection"], "threshold_source": report["threshold_source"],
        "development_only": True, "scientific_reporting_eligible": False,
        "next_gate": "paired_medium_partial_start_engineering_pilot",
    }
    write_json(output / "easy_transfer_training_report.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dry-run", "train"))
    parser.add_argument("--source_training_plan", type=Path, required=True)
    parser.add_argument("--graph_root", type=Path, required=True)
    parser.add_argument("--label_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--expected_contract")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args(argv)
    if args.command == "train" and not args.expected_contract:
        parser.error("train requires the successful preflight expected_contract")
    inputs = dict(source_training_plan=args.source_training_plan, graph_root=args.graph_root, label_root=args.label_root)
    try:
        if args.command == "dry-run":
            plan = build_plan(**inputs)
            args.output_dir.mkdir(parents=True, exist_ok=False)
            write_json(args.output_dir / TRAINING_PLAN_NAME, plan)
            print(f"[INFO] contract={plan['contract_sha256']} | easy=30 | train=18 | validation=6 | test=6 | medium=0")
        else:
            execute(**inputs, output_dir=args.output_dir, expected_contract=args.expected_contract, device=args.device)
            print("[INFO] easy-only training completed | epochs=100 | seed=42 | development_only=true")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"[ERROR] {error_reason(error)}")
        return 2
    return 0
