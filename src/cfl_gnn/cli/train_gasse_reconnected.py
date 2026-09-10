"""CLI for the manifest-driven serial and DDP Gasse baseline."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from cfl_gnn.training.gasse_reconnected import (
    GasseTrainingError,
    TRAINING_PLAN_NAME,
    build_gasse_training_plan,
    run_distributed_training,
    run_serial_training,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train the preserved Gasse model from audited parent manifests."
    )
    parser.add_argument("--graph_dataset_dir", type=Path, required=True)
    parser.add_argument("--parent_collection_plan_dir", type=Path, required=True)
    parser.add_argument("--parent_collection_run_root", type=Path, required=True)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("configs/training/gasse_reconnected_v1.json"),
    )
    parser.add_argument("--label_solver", choices=("gurobi", "scip"), required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("serial", "ddp"), default="serial")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--allow_partial_smoke", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rank = int(os.environ.get("RANK", "0"))
    try:
        plan = build_gasse_training_plan(
            graph_dataset_dir=args.graph_dataset_dir,
            parent_collection_plan_dir=args.parent_collection_plan_dir,
            parent_collection_run_root=args.parent_collection_run_root,
            protocol_path=args.protocol,
            label_solver=args.label_solver,
            allow_partial_smoke=args.allow_partial_smoke,
        )
        if rank == 0:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            write_json(args.output_dir / TRAINING_PLAN_NAME, plan)
            print(
                f"[INFO] contract={plan['contract_sha256']} | "
                f"solver={args.label_solver} | "
                f"train={plan['partition_counts']['train']} | "
                f"validation={plan['partition_counts']['validation']} | "
                f"test={plan['partition_counts']['test']}"
            )
            print("[INFO] graph_authority=gurobi | test_graphs_loaded=0")
            print(f"[INFO] Plan: {args.output_dir / TRAINING_PLAN_NAME}")
        if args.dry_run:
            return 0
        if args.mode == "serial":
            report = run_serial_training(
                plan,
                graph_root=args.graph_dataset_dir,
                label_root=args.parent_collection_run_root,
                output_dir=args.output_dir,
                epochs_override=args.epochs,
                device_name=args.device,
                overwrite=args.overwrite,
            )
        else:
            report = run_distributed_training(
                plan,
                graph_root=args.graph_dataset_dir,
                label_root=args.parent_collection_run_root,
                output_dir=args.output_dir,
                epochs_override=args.epochs,
                overwrite=args.overwrite,
            )
        if rank == 0 and report is not None:
            print(
                f"[INFO] gate={report['gate_status']} | "
                f"mode={report['execution_mode']} | epochs={report['epochs_completed']}"
            )
    except (GasseTrainingError, OSError, TypeError, ValueError) as error:
        if rank == 0:
            print(f"[ERROR] {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
