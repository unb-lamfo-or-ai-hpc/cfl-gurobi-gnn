"""CLI for auditing paired Gurobi/SCIP vertical-slice parent solves."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.experiments.mvp_vertical_slice import (
    MvpVerticalSliceError,
    audit_vertical_slice_parent_runs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit twelve paired parent solves.")
    parser.add_argument("--plan_dir", type=Path, required=True)
    parser.add_argument("--run_root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_vertical_slice_parent_runs(
            plan_dir=args.plan_dir,
            run_root=args.run_root,
            overwrite=args.overwrite,
        )
        summary = report["summary"]
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"benchmark={summary['benchmark_tasks_passed']}/{summary['tasks_planned']} | "
            f"train_labels={summary['training_labels_eligible']}/"
            f"{summary['training_solver_parent_pairs']} | "
            f"evaluation_references={summary['evaluation_references_covered']}/"
            f"{summary['evaluation_parents']} | "
            f"rescue={report['label_rescue']['tasks_planned']}"
        )
        return (
            0
            if report["gates"]["benchmark_observation_gate"] == "passed"
            else 1
        )
    except (OSError, TypeError, ValueError, MvpVerticalSliceError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

