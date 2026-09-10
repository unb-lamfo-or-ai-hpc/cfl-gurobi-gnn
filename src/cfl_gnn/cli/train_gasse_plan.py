"""Train one persisted Gasse arm plan from a self-contained artifact package."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from cfl_gnn.training.gasse_reconnected import (
    GasseTrainingError,
    read_json,
    run_distributed_training,
    run_serial_training,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train one audited, persisted Gasse arm plan."
    )
    parser.add_argument("--training_plan", type=Path, required=True)
    parser.add_argument("--artifact_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("serial", "ddp"), default="serial")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rank = int(os.environ.get("RANK", "0"))
    try:
        plan = read_json(args.training_plan)
        if args.mode == "serial":
            report = run_serial_training(
                plan,
                graph_root=args.artifact_root,
                label_root=args.artifact_root,
                output_dir=args.output_dir,
                epochs_override=args.epochs,
                device_name=args.device,
                overwrite=args.overwrite,
            )
        else:
            report = run_distributed_training(
                plan,
                graph_root=args.artifact_root,
                label_root=args.artifact_root,
                output_dir=args.output_dir,
                epochs_override=args.epochs,
                overwrite=args.overwrite,
            )
    except (GasseTrainingError, OSError, TypeError, ValueError) as error:
        if rank == 0:
            print(f"[ERROR] {error}")
        return 2
    if rank == 0 and report is not None:
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"mode={report['execution_mode']} | epochs={report['epochs_completed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
