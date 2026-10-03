"""CLI for validation-bound, held-out Gasse evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.evaluation.gasse_reconnected import (
    EVALUATION_PLAN_NAME,
    GasseEvaluationError,
    build_evaluation_plan,
    execute_evaluation,
)
from cfl_gnn.training.gasse_reconnected import GasseTrainingError, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Gasse once on the immutable held-out test partition."
    )
    parser.add_argument("--training_plan", type=Path, required=True)
    parser.add_argument("--training_report", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--graph_dataset_dir", type=Path, required=True)
    parser.add_argument("--parent_collection_run_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = build_evaluation_plan(
            training_plan_path=args.training_plan,
            training_report_path=args.training_report,
            checkpoint_path=args.checkpoint,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / EVALUATION_PLAN_NAME, plan)
        print(
            f"[INFO] contract={plan['contract_sha256']} | "
            f"test={len(plan['test_records'])} | "
            f"threshold={plan['probability_threshold']:.6g}"
        )
        print("[INFO] threshold_source=validation | test_usage=evaluation_only")
        print(f"[INFO] Plan: {args.output_dir / EVALUATION_PLAN_NAME}")
        if args.dry_run:
            return 0
        report = execute_evaluation(
            plan,
            graph_root=args.graph_dataset_dir,
            label_root=args.parent_collection_run_root,
            checkpoint_path=args.checkpoint,
            output_dir=args.output_dir,
            device_name=args.device,
            overwrite=args.overwrite,
        )
    except (
        GasseEvaluationError,
        GasseTrainingError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2
    print(
        f"[INFO] gate={report['gate_status']} | "
        f"test_graphs={report['test_graphs_loaded']} | "
        f"f1={report['aggregate_metrics']['f1_score']:.6g}"
    )
    return 0 if report["gate_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
