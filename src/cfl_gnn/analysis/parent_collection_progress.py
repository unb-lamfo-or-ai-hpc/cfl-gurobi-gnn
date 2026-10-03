"""Audit scalable paired-parent collection progress without hiding failures."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.parent_collection_task import validate_campaign_plan
from cfl_gnn.pipelines.parent_population import PLAN_NAME, SOLVER_ORDER
from cfl_gnn.pipelines.parent_solutions import plan_name, report_name


SCHEMA_VERSION = 1
REPORT_NAME = "parent_collection_progress_report.json"
STATUS_NAME = "parent_collection_task_status.jsonl"
ELIGIBILITY_NAME = "paired_parent_eligibility.jsonl"
RESCUE_NAME = "{solver}_parent_rescue_tasks.jsonl"


class ParentCollectionProgressError(RuntimeError):
    """Raised when a campaign progress audit cannot be trusted."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise ParentCollectionProgressError(
            f"unreadable JSON artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise ParentCollectionProgressError(f"expected JSON object: {path.name}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, allow_nan=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def _finite(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return normalized if math.isfinite(normalized) else None


def _time_regions_valid(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    keys = (
        "total_wall_time_seconds",
        "data_read_wall_time_seconds",
        "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds",
    )
    regions = [_finite(value.get(key)) for key in keys]
    if any(region is None or region < 0 for region in regions):
        return False
    total, *components = regions
    assert total is not None
    return total + 1e-6 >= sum(float(component) for component in components)


def _artifact_hashes_valid(run_dir: Path, report: Mapping[str, Any]) -> bool:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, Mapping) or not artifacts:
        return False
    for descriptor in artifacts.values():
        if not isinstance(descriptor, Mapping):
            return False
        relative = str(descriptor.get("file_name", ""))
        path = run_dir / relative
        if not relative or not path.is_file():
            return False
        if sha256_file(path) != descriptor.get("sha256"):
            return False
    return True


def _next_budget(current: float, allowed: Sequence[Any]) -> float | None:
    larger = sorted(float(value) for value in allowed if float(value) > current)
    return larger[0] if larger else None


def _base_status(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_index": int(task["task_index"]),
        "solver_task_index": int(task["solver_task_index"]),
        "solver": str(task["solver"]),
        "source_instance_id": str(task["source_instance_id"]),
        "category": str(task["category"]),
        "difficulty": str(task["difficulty"]),
        "fold": int(task["fold"]),
        "role": str(task["role"]),
        "budget_id": str(task.get("budget_id", "legacy_unisolated_budget")),
        "time_limit_seconds": float(task.get("time_limit_seconds", 0.0)),
        "run_dir_relative_path": str(task["run_dir_relative_path"]),
    }


def _failed_status(
    task: Mapping[str, Any], *, reason: str, recommended_budget: float | None
) -> dict[str, Any]:
    return {
        **_base_status(task),
        "artifact_status": "invalid_or_missing",
        "reason_code": reason,
        "solve_status": None,
        "terminal_mip_gap_relative": None,
        "right_censored": None,
        "label_eligible": False,
        "augmentation_source_eligible": False,
        "four_time_regions_valid": False,
        "artifact_hashes_valid": False,
        "recommended_rescue_time_limit_seconds": recommended_budget,
    }


def inspect_parent_task(
    task: Mapping[str, Any],
    *,
    run_root: Path,
    maximum_gap: float,
    allowed_budgets: Sequence[Any],
) -> dict[str, Any]:
    """Inspect one planned task and classify retry versus terminal exclusion."""
    solver = str(task["solver"])
    run_dir = run_root / str(task["run_dir_relative_path"])
    current_budget = float(task.get("time_limit_seconds", 0.0))
    same_or_next = current_budget or min(float(item) for item in allowed_budgets)
    report_path = run_dir / report_name(solver)
    solver_plan_path = run_dir / plan_name(solver)
    if not report_path.is_file() or not solver_plan_path.is_file():
        return _failed_status(
            task, reason="solve_artifacts_missing", recommended_budget=same_or_next
        )
    try:
        report = _read_json(report_path)
        solver_plan = _read_json(solver_plan_path)
    except ParentCollectionProgressError:
        return _failed_status(
            task, reason="solve_artifacts_unreadable", recommended_budget=same_or_next
        )
    contract = solver_plan.get("contract_sha256")
    if not contract or report.get("contract_sha256") != contract:
        return _failed_status(
            task, reason="solve_contract_mismatch", recommended_budget=same_or_next
        )
    parent = report.get("parent")
    if not isinstance(parent, Mapping) or parent.get("sha256") != task.get(
        "parent_mip_sha256"
    ):
        return _failed_status(
            task, reason="parent_hash_mismatch", recommended_budget=same_or_next
        )
    checks = report.get("checks")
    if not isinstance(checks, Mapping) or not checks or not all(checks.values()):
        return _failed_status(
            task, reason="solver_checks_failed", recommended_budget=same_or_next
        )
    if not _artifact_hashes_valid(run_dir, report):
        return _failed_status(
            task, reason="artifact_hash_mismatch", recommended_budget=same_or_next
        )
    solve = report.get("solve")
    if not isinstance(solve, Mapping):
        return _failed_status(
            task, reason="solve_summary_missing", recommended_budget=same_or_next
        )
    gap = _finite(solve.get("mip_gap_relative"))
    optimize_time = _finite(solve.get("execution_time_seconds"))
    regions_valid = _time_regions_valid(report.get("time_regions"))
    if gap is None or gap < 0 or optimize_time is None or not regions_valid:
        return _failed_status(
            task,
            reason="performance_metrics_invalid",
            recommended_budget=same_or_next,
        )
    eligibility = report.get("eligibility")
    eligibility = eligibility if isinstance(eligibility, Mapping) else {}
    label_eligible = bool(eligibility.get("label_eligible")) and gap <= maximum_gap
    augmentation_eligible = (
        bool(eligibility.get("augmentation_source_eligible")) and label_eligible
    )
    solve_status = str(solve.get("solve_status", "unknown"))
    right_censored = solve_status.lower() not in {"optimal", "2"}
    next_budget = _next_budget(current_budget, allowed_budgets)
    recommended = next_budget if not label_eligible else None
    reason = (
        "valid_label_eligible"
        if label_eligible
        else (
            "valid_censored_label_requires_larger_budget"
            if recommended is not None
            else "valid_terminal_label_ineligible"
        )
    )
    regions = report["time_regions"]
    return {
        **_base_status(task),
        "artifact_status": "valid",
        "reason_code": reason,
        "solve_status": solve_status,
        "terminal_mip_gap_relative": gap,
        "right_censored": right_censored,
        "label_eligible": label_eligible,
        "augmentation_source_eligible": augmentation_eligible,
        "four_time_regions_valid": True,
        "artifact_hashes_valid": True,
        "total_wall_time_seconds": float(regions["total_wall_time_seconds"]),
        "data_read_wall_time_seconds": float(
            regions["data_read_wall_time_seconds"]
        ),
        "model_build_wall_time_seconds": float(
            regions["model_build_wall_time_seconds"]
        ),
        "model_optimize_wall_time_seconds": float(
            regions["model_optimize_wall_time_seconds"]
        ),
        "recommended_rescue_time_limit_seconds": recommended,
    }


def _rescue_record(status: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: status[key]
        for key in (
            "solver",
            "solver_task_index",
            "source_instance_id",
            "category",
            "difficulty",
            "fold",
            "role",
            "reason_code",
            "recommended_rescue_time_limit_seconds",
        )
    }


def audit_parent_collection_progress(
    *,
    plan_dir: str | Path,
    run_root: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a path-neutral progress and rescue contract for one campaign."""
    plan_root = Path(plan_dir).resolve()
    runs = Path(run_root).resolve()
    output = Path(output_dir).resolve()
    expected = [output / REPORT_NAME, output / STATUS_NAME, output / ELIGIBILITY_NAME]
    expected.extend(output / RESCUE_NAME.format(solver=item) for item in SOLVER_ORDER)
    if not overwrite and any(path.exists() for path in expected):
        raise ParentCollectionProgressError("progress outputs exist; use --overwrite")
    plan = _read_json(plan_root / PLAN_NAME)
    try:
        validate_campaign_plan(plan)
    except Exception as error:
        raise ParentCollectionProgressError("campaign contract mismatch") from error
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ParentCollectionProgressError("campaign has no planned tasks")
    maximum_gap = float(plan["maximum_admissible_relative_gap"])
    allowed_budgets = list(plan["allowed_time_limit_seconds"])
    statuses = [
        inspect_parent_task(
            task,
            run_root=runs,
            maximum_gap=maximum_gap,
            allowed_budgets=allowed_budgets,
        )
        for task in tasks
    ]
    by_parent: dict[str, dict[str, Mapping[str, Any]]] = {}
    for status in statuses:
        by_parent.setdefault(str(status["source_instance_id"]), {})[
            str(status["solver"])
        ] = status
    paired: list[dict[str, Any]] = []
    for parent_id, solvers in sorted(by_parent.items()):
        if set(solvers) != set(SOLVER_ORDER):
            raise ParentCollectionProgressError("paired solver task identity mismatch")
        gurobi = solvers["gurobi"]
        scip = solvers["scip"]
        both_valid = all(
            item["artifact_status"] == "valid" for item in (gurobi, scip)
        )
        paired_label = both_valid and all(
            bool(item["label_eligible"]) for item in (gurobi, scip)
        )
        paired_augmentation = paired_label and all(
            bool(item["augmentation_source_eligible"])
            for item in (gurobi, scip)
        )
        if not both_valid:
            missingness = "incomplete_or_invalid_execution"
        elif paired_label:
            missingness = "paired_eligible"
        elif gurobi["label_eligible"]:
            missingness = "gurobi_only_label_eligible"
        elif scip["label_eligible"]:
            missingness = "scip_only_label_eligible"
        else:
            missingness = "neither_label_eligible"
        paired.append(
            {
                "source_instance_id": parent_id,
                "category": gurobi["category"],
                "difficulty": gurobi["difficulty"],
                "fold": gurobi["fold"],
                "role": gurobi["role"],
                "gurobi_artifact_status": gurobi["artifact_status"],
                "scip_artifact_status": scip["artifact_status"],
                "gurobi_terminal_mip_gap_relative": gurobi[
                    "terminal_mip_gap_relative"
                ],
                "scip_terminal_mip_gap_relative": scip[
                    "terminal_mip_gap_relative"
                ],
                "paired_label_eligible": paired_label,
                "paired_augmentation_source_eligible": paired_augmentation,
                "missingness_class": missingness,
            }
        )
    rescue = {
        solver: [
            _rescue_record(status)
            for status in statuses
            if status["solver"] == solver
            and status["recommended_rescue_time_limit_seconds"] is not None
        ]
        for solver in SOLVER_ORDER
    }
    thresholds = [float(item) for item in plan["gap_sensitivity_thresholds_relative"]]
    sensitivity = {}
    for threshold in thresholds:
        sensitivity[f"gap_le_{threshold:g}"] = sum(
            item["gurobi_terminal_mip_gap_relative"] is not None
            and item["scip_terminal_mip_gap_relative"] is not None
            and float(item["gurobi_terminal_mip_gap_relative"]) <= threshold
            and float(item["scip_terminal_mip_gap_relative"]) <= threshold
            for item in paired
        )
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / STATUS_NAME, statuses)
    _write_jsonl(output / ELIGIBILITY_NAME, paired)
    for solver in SOLVER_ORDER:
        _write_jsonl(output / RESCUE_NAME.format(solver=solver), rescue[solver])
    valid_tasks = sum(item["artifact_status"] == "valid" for item in statuses)
    paired_labels = sum(bool(item["paired_label_eligible"]) for item in paired)
    paired_augmented = sum(
        bool(item["paired_augmentation_source_eligible"]) for item in paired
    )
    missingness = dict(Counter(item["missingness_class"] for item in paired))
    campaign_complete = valid_tasks == len(statuses)
    rescue_count = sum(len(items) for items in rescue.values())
    report = {
        "schema_version": SCHEMA_VERSION,
        "parent_collection_contract_sha256": plan["contract_sha256"],
        "gate_status": "passed",
        "probe_completed": True,
        "methodology": {
            "priority_solver": "gurobi",
            "scip_role": "matched_comparison_only",
            "execution_order": "gurobi_then_scip_within_each_parent_task",
            "censoring_policy": "retain_and_flag_no_naive_inference",
            "maximum_admissible_relative_gap": maximum_gap,
            "gap_sensitivity_thresholds_relative": thresholds,
            "time_regions": [
                "total_wall_time_seconds",
                "data_read_wall_time_seconds",
                "model_build_wall_time_seconds",
                "model_optimize_wall_time_seconds",
            ],
        },
        "summary": {
            "planned_parent_population": plan["planned_parent_population"],
            "available_parent_population": plan["available_parent_population"],
            "planned_tasks": len(statuses),
            "valid_tasks": valid_tasks,
            "invalid_or_missing_tasks": len(statuses) - valid_tasks,
            "paired_label_eligible_parents": paired_labels,
            "paired_augmentation_eligible_parents": paired_augmented,
            "right_censored_tasks": sum(
                item.get("right_censored") is True for item in statuses
            ),
            "rescue_tasks": rescue_count,
            "missingness_classes": dict(sorted(missingness.items())),
            "paired_gap_sensitivity": sensitivity,
        },
        "campaign_status": {
            "current_budget_execution_complete": campaign_complete,
            "rescue_required": rescue_count > 0,
            "paired_training_population_ready": paired_augmented > 0,
            "strict_90_parent_population_complete": (
                plan["available_parent_population"]
                == plan["planned_parent_population"]
                and campaign_complete
            ),
        },
        "outputs": {
            STATUS_NAME: {"sha256": sha256_file(output / STATUS_NAME)},
            ELIGIBILITY_NAME: {"sha256": sha256_file(output / ELIGIBILITY_NAME)},
            **{
                RESCUE_NAME.format(solver=solver): {
                    "sha256": sha256_file(output / RESCUE_NAME.format(solver=solver)),
                    "records": len(rescue[solver]),
                }
                for solver in SOLVER_ORDER
            },
        },
        "eligibility": {
            "progress_audit_valid": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": (
                "execute_parent_collection_rescue_manifests"
                if rescue_count
                else (
                    "complete_parent_collection_phase1_audit"
                    if campaign_complete
                    else "continue_current_budget_parent_collection"
                )
            )
        },
    }
    _write_json(output / REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit paired-parent campaign progress and write rescue manifests."
    )
    parser.add_argument("--plan_dir", type=Path, required=True)
    parser.add_argument("--run_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_parent_collection_progress(
            plan_dir=args.plan_dir,
            run_root=args.run_root,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, ParentCollectionProgressError) as error:
        print(f"[ERROR] {error}")
        return 2
    summary = report["summary"]
    print(
        f"[INFO] gate=passed | valid={summary['valid_tasks']}/"
        f"{summary['planned_tasks']} | paired={summary['paired_label_eligible_parents']} "
        f"| rescue={summary['rescue_tasks']}"
    )
    print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
