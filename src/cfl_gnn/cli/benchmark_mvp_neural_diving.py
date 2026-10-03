"""CLI for the equal-budget Gurobi/SCIP Neural Diving smoke."""

from __future__ import annotations

import argparse
from pathlib import Path

from cfl_gnn.experiments.mvp_neural_diving import (
    DEFAULT_CONFIG,
    PLAN_NAME,
    REPORT_NAME,
    MvpNeuralDivingError,
    audit_run,
    build_plan,
    run_task,
    write_json,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the paired equal-budget MVP Neural Diving experiment."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Verify PR #36 and write the run plan.")
    plan.add_argument("--evaluation_dir", type=Path, required=True)
    plan.add_argument("--base_source_dir", type=Path, required=True)
    plan.add_argument("--output_dir", type=Path, required=True)
    plan.add_argument("--time_limit_seconds", type=int, default=3600)
    plan.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    plan.add_argument("--overwrite", action="store_true")

    task = subparsers.add_parser("run-task", help="Execute one fresh solver task.")
    task.add_argument("--plan", type=Path, required=True)
    task.add_argument("--evaluation_dir", type=Path, required=True)
    task.add_argument("--base_source_dir", type=Path, required=True)
    task.add_argument("--output_dir", type=Path, required=True)
    task.add_argument("--task_index", type=int, required=True)
    task.add_argument("--overwrite", action="store_true")

    audit = subparsers.add_parser("audit", help="Aggregate and gate all task outputs.")
    audit.add_argument("--plan", type=Path, required=True)
    audit.add_argument("--output_dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "plan":
            plan_path = args.output_dir / PLAN_NAME
            if plan_path.exists() and not args.overwrite:
                raise MvpNeuralDivingError("plan exists; use --overwrite")
            plan = build_plan(
                args.evaluation_dir,
                args.base_source_dir,
                time_limit_seconds=args.time_limit_seconds,
                config_path=args.config,
            )
            write_json(plan_path, plan)
            print(
                f"[INFO] contract={plan['contract_sha256']} | "
                f"tasks={plan['task_count']} | "
                f"time_limit={plan['time_limit_seconds']}s"
            )
            print("[INFO] design=4 GNN arms x 2 solvers + 2 solver controls")
            print(f"[INFO] Plan: {plan_path}")
            return 0
        if args.command == "run-task":
            result = run_task(
                args.plan,
                args.evaluation_dir,
                args.base_source_dir,
                args.output_dir,
                task_index=args.task_index,
                overwrite=args.overwrite,
            )
            outcome = result["outcome"]
            timing = result["time_regions"]
            print(
                f"[INFO] task={result['task_index']} | "
                f"solver={result['target_solver']} | "
                f"status={outcome['solve_status']} | "
                f"gap={outcome['terminal_mip_gap_relative']}"
            )
            print(
                f"[INFO] total={timing['total_wall_time_seconds']:.6f}s | "
                f"read={timing['data_read_wall_time_seconds']:.6f}s | "
                f"build={timing['model_build_wall_time_seconds']:.6f}s | "
                f"optimize={timing['model_optimize_wall_time_seconds']:.6f}s"
            )
            return 0
        report = audit_run(args.plan, args.output_dir)
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"completed={report['execution']['completed_runs']}/"
            f"{report['execution']['planned_runs']}"
        )
        print(f"[INFO] Report: {args.output_dir / REPORT_NAME}")
        return 0 if report["gate_status"] == "passed" else 1
    except (MvpNeuralDivingError, FileNotFoundError, KeyError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
