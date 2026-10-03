"""CLI for the paired six-parent MVP vertical-slice preflight."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.experiments.mvp_vertical_slice import (
    MvpVerticalSliceError,
    write_vertical_slice_plan,
)
from cfl_gnn.paths import PROJECT_ROOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan twelve paired parent solves.")
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument(
        "--slice_config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "experiments" / "mvp_vertical_slice_v1.json",
    )
    parser.add_argument(
        "--parent_manifest",
        type=Path,
        default=PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv",
    )
    parser.add_argument(
        "--experiment_config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = write_vertical_slice_plan(
            base_source_dir=args.base_source_dir,
            output_dir=args.output_dir,
            slice_config_path=args.slice_config,
            parent_manifest_path=args.parent_manifest,
            experiment_config_path=args.experiment_config,
            overwrite=args.overwrite,
        )
        summary = report["summary"]
        print(
            f"[INFO] gate={report['gate_status']} | parents={summary['parents']} | "
            f"tasks={summary['parent_solve_tasks']} | train={summary['parents_by_role']['train']}"
        )
        print(f"[INFO] Plan: {args.output_dir / 'mvp_vertical_slice_plan.json'}")
        return 0
    except (OSError, TypeError, ValueError, MvpVerticalSliceError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
