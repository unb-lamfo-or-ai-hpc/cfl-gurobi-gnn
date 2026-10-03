"""CLI entry point for the four-arm training loader and sampler audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.mvp_arm import (
    AUDIT_NAME,
    PLAN_NAME,
    DeterministicParentBalancedSampler,
    MvpTrainingDataError,
    build_training_data_plan,
    sampler_parent_counts,
    write_json,
)


DEFAULT_EXPERIMENT_CONFIG = (
    PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
)
DEFAULT_LOADER_POLICY = (
    PROJECT_ROOT / "configs" / "training" / "mvp_four_arm_loader_v1.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the four MVP arm manifests and parent-balanced sampler."
    )
    parser.add_argument("--dataset_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument(
        "--experiment_config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG
    )
    parser.add_argument("--loader_policy", type=Path, default=DEFAULT_LOADER_POLICY)
    parser.add_argument("--verify_loads", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _load_smoke(dataset_dir: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    from cfl_gnn.graph.mvp_arm_dataset import (
        MvpArmDataset,
        selected_common_reference_records,
        selected_records_for_arm,
    )

    loaded: list[dict[str, Any]] = []
    for arm_id in sorted(plan["arms"]):
        records = selected_records_for_arm(plan, arm_id)
        if not records:
            continue
        graph = MvpArmDataset(dataset_dir, records[:1], verify_hash_on_load=True)[0]
        loaded.append(
            {
                "arm_id": arm_id,
                "role": "train",
                "sample_id": str(graph.sample_id),
                "parent_instance_id": str(graph.parent_instance_id),
            }
        )
    validation = selected_common_reference_records(plan, "validation")
    if validation:
        graph = MvpArmDataset(
            dataset_dir, validation[:1], verify_hash_on_load=True
        )[0]
        loaded.append(
            {
                "arm_id": "common_reference",
                "role": "validation",
                "sample_id": str(graph.sample_id),
                "parent_instance_id": str(graph.parent_instance_id),
            }
        )
    return {
        "status": "passed",
        "graphs_loaded": len(loaded),
        "records": loaded,
        "test_graphs_loaded": 0,
    }


def _sampler_audit(plan: Mapping[str, Any]) -> dict[str, Any]:
    policy = plan["loader_policy"]
    result: dict[str, Any] = {}
    expected_length: int | None = None
    for arm_id, arm in sorted(plan["arms"].items()):
        records = arm["eligible_training_records"]
        sampler = DeterministicParentBalancedSampler(
            records,
            seed=int(policy["seed"]),
            draws_per_parent=int(policy["draws_per_parent_per_epoch"]),
        )
        indices = tuple(sampler)
        counts = sampler_parent_counts(records, indices)
        if counts and len(set(counts.values())) != 1:
            raise MvpTrainingDataError("sampler produced unequal parent draw counts")
        if expected_length is None:
            expected_length = len(indices)
        elif len(indices) != expected_length:
            raise MvpTrainingDataError("sampler epoch length differs across arms")
        result[arm_id] = {
            "draws": len(indices),
            "parent_draw_counts": counts,
            "deterministic_replay": indices == tuple(sampler),
        }
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan_path = args.output_dir / PLAN_NAME
    audit_path = args.output_dir / AUDIT_NAME
    try:
        if args.output_dir.exists() and (plan_path.exists() or audit_path.exists()):
            if not args.overwrite:
                raise FileExistsError(
                    "training loader output exists; use --overwrite or another output"
                )
        plan = build_training_data_plan(
            args.dataset_dir,
            experiment_config_path=args.experiment_config,
            loader_policy_path=args.loader_policy,
            verify_graph_hashes=True,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(plan_path, plan)
        sampler_audit = _sampler_audit(plan)
        load_smoke = (
            _load_smoke(args.dataset_dir, plan)
            if args.verify_loads
            else {
                "status": "not_requested",
                "graphs_loaded": 0,
                "test_graphs_loaded": 0,
            }
        )
        audit = {
            "schema_version": 1,
            "training_data_contract_sha256": plan["contract_sha256"],
            "contract_valid": True,
            "sampler_gate_status": "passed",
            "sampler": sampler_audit,
            "graph_load_smoke": load_smoke,
            "test_partition_usage": "held_out_not_loaded_during_training",
            "training_ready": plan["training_ready"],
            "held_out_evaluation_ready": plan["held_out_evaluation_ready"],
            "mvp_execution_ready": plan["mvp_execution_ready"],
            "development_only": True,
            "scientific_reporting_eligible": False,
            "warnings": plan["warnings"],
            "next_gate": plan["next_gate"],
        }
        write_json(audit_path, audit)
        counts = plan["partition_summary"]
        print(
            f"[INFO] contract={plan['contract_sha256']} | "
            f"train_parents={counts['common_training_parents']} | "
            f"validation={counts['common_validation_parents']} | "
            f"test={counts['common_test_parents']}"
        )
        print(
            f"[INFO] gap<={plan['loader_policy']['gap_threshold_relative']:.2%} | "
            f"sampler={plan['loader_policy']['sampler']}"
        )
        print("[INFO] test partition remains held out and was not loaded")
        for warning in plan["warnings"]:
            print(f"[WARNING] {warning}")
        print(f"[INFO] Plan: {plan_path}")
        print(f"[INFO] Audit: {audit_path}")
        return 0
    except (
        FileExistsError,
        OSError,
        TypeError,
        ValueError,
        MvpTrainingDataError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

