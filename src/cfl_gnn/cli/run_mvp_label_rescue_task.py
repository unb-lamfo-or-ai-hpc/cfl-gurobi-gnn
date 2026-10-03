"""CLI for one precommitted MVP label-rescue task."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.pipelines.mvp_label_rescue import execute_rescue_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one immutable-benchmark parent-label rescue task."
    )
    parser.add_argument("--vertical_slice_dir", type=Path, required=True)
    parser.add_argument("--benchmark_run_root", type=Path, required=True)
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--rescue_run_root", type=Path, required=True)
    parser.add_argument("--task_index", type=int, required=True)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = execute_rescue_task(
            vertical_slice_dir=args.vertical_slice_dir,
            benchmark_run_root=args.benchmark_run_root,
            base_source_dir=args.base_source_dir,
            rescue_run_root=args.rescue_run_root,
            task_index=args.task_index,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        if args.dry_run:
            task = report["task"]
            print(
                f"[INFO] dry-run task={task['rescue_task_index']} | "
                f"solver={task['solver']} | parent={task['source_instance_id']}"
            )
            return 0
        print(
            f"[INFO] gate={report['gate_status']} | solver={report['solver']} | "
            f"parent={report['task']['source_instance_id']} | "
            f"gap={report['solve']['mip_gap_relative']}"
        )
        return 0 if report["gate_status"] == "passed" else 1
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
