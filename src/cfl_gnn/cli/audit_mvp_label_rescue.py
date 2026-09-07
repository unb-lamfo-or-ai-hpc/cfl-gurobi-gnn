"""CLI for the aggregate MVP label-rescue audit."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.pipelines.mvp_label_rescue import audit_rescue_runs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit all precommitted label-rescue tasks."
    )
    parser.add_argument("--vertical_slice_dir", type=Path, required=True)
    parser.add_argument("--rescue_run_root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_rescue_runs(
            vertical_slice_dir=args.vertical_slice_dir,
            rescue_run_root=args.rescue_run_root,
            overwrite=args.overwrite,
        )
        summary = report["summary"]
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"passed={summary['tasks_passed']}/{summary['tasks_planned']}"
        )
        return 0 if report["gate_status"] == "passed" else 1
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
