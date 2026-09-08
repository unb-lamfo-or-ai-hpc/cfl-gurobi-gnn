"""CLI for the reduced easy-only MVP evidence contract."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.experiments.mvp_easy_vertical_slice import (
    MvpEasyVerticalSliceError,
    compose_easy_vertical_slice,
)
from cfl_gnn.paths import PROJECT_ROOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compose the development-only easy MVP vertical slice."
    )
    parser.add_argument("--vertical_slice_dir", type=Path, required=True)
    parser.add_argument("--benchmark_run_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=(
            PROJECT_ROOT
            / "configs"
            / "experiments"
            / "mvp_easy_vertical_slice_v1.json"
        ),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = compose_easy_vertical_slice(
            vertical_slice_dir=args.vertical_slice_dir,
            benchmark_run_root=args.benchmark_run_root,
            output_dir=args.output_dir,
            config_path=args.config,
            overwrite=args.overwrite,
        )
        summary = report["summary"]
        print(
            f"[INFO] gate={report['gate_status']} | parents={summary['parents']} | "
            f"labels={summary['labels']} | censored={summary['censored_evidence_records']}"
        )
        print("[INFO] test partition remains held out and no graph was deserialized")
        print(f"[INFO] Report: {args.output_dir / 'mvp_easy_vertical_slice_report.json'}")
        return 0
    except (OSError, TypeError, ValueError, MvpEasyVerticalSliceError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

