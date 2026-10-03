"""Execute one hash-bound parent collection task with conservative resume."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.parent_population import (
    DEFAULT_EXPERIMENT_CONFIG,
    PLAN_NAME,
    SOLVER_ORDER,
    SOLVER_TASKS_NAME,
    ParentPopulationError,
    canonical_sha256,
)
from cfl_gnn.pipelines.parent_solutions import (
    build_plan,
    main as parent_solution_main,
    plan_name,
    report_name,
)


CONTRACT_KEYS = (
    "schema_version",
    "campaign_id",
    "population_policy",
    "priority_solver",
    "scip_role",
    "solver_order",
    "solver_phase_dependency",
    "objective_sense",
    "original_objective_sense_recorded",
    "experiment_contract_sha256",
    "parent_manifest_sha256",
    "planned_parent_population",
    "requested_parent_population",
    "available_parent_population",
    "missing_parent_population",
    "solve_budget",
    "allowed_time_limit_seconds",
    "gap_sensitivity_thresholds_relative",
    "maximum_admissible_relative_gap",
    "parents",
    "missing_parents",
    "tasks",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise ParentPopulationError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ParentPopulationError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise TypeError("task is not an object")
                    records.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise ParentPopulationError(f"unreadable task manifest: {path.name}") from error
    return records


def validate_campaign_plan(plan: Mapping[str, Any]) -> None:
    try:
        payload = {key: plan[key] for key in CONTRACT_KEYS}
    except KeyError as error:
        raise ParentPopulationError(f"campaign plan is missing {error.args[0]}") from error
    if canonical_sha256(payload) != plan.get("contract_sha256"):
        raise ParentPopulationError("parent collection plan contract mismatch")
    if plan.get("solver_order") != list(SOLVER_ORDER):
        raise ParentPopulationError("parent collection solver order changed")


def _resume_artifacts_valid(
    *, output_dir: Path, solver: str, expected_contract: str, parent_sha256: str
) -> bool:
    parent_plan_path = output_dir / plan_name(solver)
    report_path = output_dir / report_name(solver)
    if not parent_plan_path.is_file() or not report_path.is_file():
        return False
    try:
        parent_plan = _read_json(parent_plan_path)
        report = _read_json(report_path)
        if parent_plan.get("contract_sha256") != expected_contract:
            return False
        if report.get("contract_sha256") != expected_contract:
            return False
        if report.get("parent", {}).get("sha256") != parent_sha256:
            return False
        checks = report.get("checks")
        if not isinstance(checks, dict) or not checks or not all(checks.values()):
            return False
        artifacts = report.get("artifacts")
        if not isinstance(artifacts, dict):
            return False
        for descriptor in artifacts.values():
            if not isinstance(descriptor, dict):
                return False
            path = output_dir / str(descriptor.get("file_name", ""))
            if not path.is_file() or sha256_file(path) != descriptor.get("sha256"):
                return False
    except (OSError, TypeError, ValueError, ParentPopulationError):
        return False
    return True


def execute_parent_collection_task(
    *,
    plan_dir: str | Path,
    solver: str,
    task_index: int,
    base_source_dir: str | Path,
    run_root: str | Path,
    experiment_config_path: str | Path = DEFAULT_EXPERIMENT_CONFIG,
    resume: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
) -> str:
    """Execute or safely reuse one task; return ``executed`` or ``reused``."""
    if solver not in SOLVER_ORDER:
        raise ParentPopulationError("solver must be gurobi or scip")
    plan_root = Path(plan_dir).resolve()
    plan = _read_json(plan_root / PLAN_NAME)
    validate_campaign_plan(plan)
    tasks = _read_jsonl(
        plan_root / SOLVER_TASKS_NAME.format(solver=solver)
    )
    if task_index < 0 or task_index >= len(tasks):
        raise ParentPopulationError(
            f"task index {task_index} is outside the {solver} task manifest"
        )
    task = tasks[task_index]
    if task.get("solver") != solver or task.get("solver_task_index") != task_index:
        raise ParentPopulationError("solver task identity mismatch")
    source = Path(base_source_dir).resolve() / str(task["parent_mip_relative_path"])
    if not source.is_file() or sha256_file(source) != task.get("parent_mip_sha256"):
        raise ParentPopulationError("parent MIP is missing or changed since planning")
    output = Path(run_root).resolve() / str(task["run_dir_relative_path"])
    budget = plan["solve_budget"]
    parent_plan = build_plan(
        parent_mip=source,
        output_dir=output,
        parent_instance_id=str(task["source_instance_id"]),
        category=str(task["category"]),
        difficulty=str(task["difficulty"]),
        fold=int(task["fold"]),
        config_path=experiment_config_path,
        time_limit=float(budget["time_limit_seconds"]),
        node_limit=int(budget["node_limit"]),
        seed=int(budget["seed"]),
        threads=int(budget["threads"]),
        solver_profile=str(budget["solver_profile"]),
        solver=solver,
    )
    if parent_plan.experiment_contract_sha256 != plan["experiment_contract_sha256"]:
        raise ParentPopulationError("experiment configuration changed since planning")
    if resume and _resume_artifacts_valid(
        output_dir=output,
        solver=solver,
        expected_contract=parent_plan.contract_sha256,
        parent_sha256=parent_plan.parent_sha256,
    ):
        print(
            f"[INFO] reused solver={solver} | "
            f"parent={task['source_instance_id']} | contract={parent_plan.contract_sha256}"
        )
        return "reused"

    argv = [
        "--parent_mip",
        str(source),
        "--parent_instance_id",
        str(task["source_instance_id"]),
        "--category",
        str(task["category"]),
        "--difficulty",
        str(task["difficulty"]),
        "--fold",
        str(task["fold"]),
        "--config",
        str(Path(experiment_config_path).resolve()),
        "--output_dir",
        str(output),
        "--time_limit",
        str(budget["time_limit_seconds"]),
        "--node_limit",
        str(budget["node_limit"]),
        "--threads",
        str(budget["threads"]),
        "--seed",
        str(budget["seed"]),
    ]
    if overwrite:
        argv.append("--overwrite")
    if dry_run:
        argv.append("--dry_run")
    exit_code = parent_solution_main(argv, solver=solver)
    if exit_code != 0:
        raise ParentPopulationError(
            f"{solver} parent collector exited with status {exit_code}"
        )
    return "executed"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute one task from a Gurobi-first parent campaign."
    )
    parser.add_argument("--plan_dir", type=Path, required=True)
    parser.add_argument("--solver", choices=SOLVER_ORDER, required=True)
    parser.add_argument("--task_index", type=int, required=True)
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--run_root", type=Path, required=True)
    parser.add_argument("--experiment_config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        status = execute_parent_collection_task(
            plan_dir=args.plan_dir,
            solver=args.solver,
            task_index=args.task_index,
            base_source_dir=args.base_source_dir,
            run_root=args.run_root,
            experiment_config_path=args.experiment_config,
            resume=args.resume,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, ParentPopulationError) as error:
        print(f"[ERROR] {error}")
        return 2
    print(f"[INFO] task_status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
