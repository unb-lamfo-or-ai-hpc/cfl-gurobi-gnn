"""CLI for the development-only four-arm Neural Diving review."""

from __future__ import annotations

import argparse
from pathlib import Path

from cfl_gnn.analysis.mvp_neural_diving_comparison import (
    DEFAULT_CONFIG,
    PLAN_NAME,
    REPORT_NAME,
    MvpComparisonError,
    build_plan,
    run_review,
)
from cfl_gnn.experiments.mvp_neural_diving import write_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review the equal-budget four-arm Neural Diving benchmark."
    )
    parser.add_argument("--benchmark_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.dry_run:
            plan_path = args.output_dir / PLAN_NAME
            if plan_path.exists() and not args.overwrite:
                raise MvpComparisonError("comparison plan exists; use --overwrite")
            plan = build_plan(args.benchmark_dir, config_path=args.config)
            write_json(plan_path, plan)
            print(
                f"[INFO] contract={plan['contract_sha256']} | "
                f"runs={plan['planned_runs']} | parents={plan['planned_parents']}"
            )
            print("[INFO] policy=descriptive_only_no_arm_selection")
            print(f"[INFO] Plan: {plan_path}")
            return 0
        report = run_review(
            args.benchmark_dir,
            args.output_dir,
            config_path=args.config,
            overwrite=args.overwrite,
        )
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"runs={report['execution']['runs']} | "
            f"effects={report['execution']['paired_descriptive_effects']}"
        )
        print("[INFO] arm selection is disabled for the partial MVP population")
        print(f"[INFO] Report: {args.output_dir / REPORT_NAME}")
        return 0 if report["gate_status"] == "passed" else 1
    except (MvpComparisonError, FileNotFoundError, KeyError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
