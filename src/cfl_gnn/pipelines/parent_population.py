"""Plan a resumable Gurobi-first campaign over original CFL parents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold


SCHEMA_VERSION = 1
PLAN_NAME = "parent_collection_plan.json"
TASKS_NAME = "parent_collection_tasks.jsonl"
SOLVER_TASKS_NAME = "{solver}_parent_collection_tasks.jsonl"
DEFAULT_CAMPAIGN_CONFIG = (
    PROJECT_ROOT / "configs" / "experiments" / "parent_collection_v1.json"
)
DEFAULT_EXPERIMENT_CONFIG = (
    PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
)
DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
SOLVER_ORDER = ("gurobi", "scip")


class ParentPopulationError(RuntimeError):
    """Raised when the parent-population campaign contract is invalid."""


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise ParentPopulationError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ParentPopulationError(f"expected JSON object: {path.name}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
            for value in values
        ),
        encoding="utf-8",
    )


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ParentPopulationError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ParentPopulationError(f"{field} must be a positive integer") from error
    if normalized <= 0 or normalized != value:
        raise ParentPopulationError(f"{field} must be a positive integer")
    return normalized


def _validate_campaign_config(
    value: Mapping[str, Any], *, time_limit: float | None
) -> tuple[dict[str, Any], tuple[float, ...]]:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ParentPopulationError("unsupported parent-collection schema")
    if value.get("solver_order") != list(SOLVER_ORDER):
        raise ParentPopulationError("solver_order must be gurobi followed by scip")
    if value.get("priority_solver") != "gurobi":
        raise ParentPopulationError("Gurobi must remain the priority solver")
    if value.get("scip_role") != "matched_comparison_only":
        raise ParentPopulationError("SCIP must remain a matched comparison solver")
    if value.get("objective_sense") != "MINIMIZE":
        raise ParentPopulationError("CFL parent solves must force MINIMIZE")
    budget = value.get("solve_budget")
    if not isinstance(budget, dict):
        raise ParentPopulationError("solve_budget must be an object")
    selected_limit = float(
        budget.get("time_limit_seconds") if time_limit is None else time_limit
    )
    allowed = value.get("allowed_time_limit_seconds")
    if not isinstance(allowed, list) or not allowed:
        raise ParentPopulationError("allowed_time_limit_seconds must be non-empty")
    allowed_limits = tuple(float(item) for item in allowed)
    if selected_limit not in allowed_limits:
        raise ParentPopulationError(
            "time_limit must be one of the precommitted campaign budgets"
        )
    normalized = {
        "time_limit_seconds": selected_limit,
        "node_limit": _positive_int(budget.get("node_limit"), field="node_limit"),
        "threads": _positive_int(budget.get("threads"), field="threads"),
        "seed": int(budget.get("seed")),
        "solver_profile": str(budget.get("solver_profile")),
    }
    if normalized["solver_profile"] != "default":
        raise ParentPopulationError("the parent campaign requires the default profile")
    return normalized, allowed_limits


def build_parent_collection_plan(
    *,
    base_source_dir: str | Path,
    parent_manifest_path: str | Path,
    campaign_config_path: str | Path,
    experiment_config_path: str | Path,
    instances: Sequence[str] | None = None,
    time_limit: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build a path-neutral plan with all Gurobi tasks before SCIP tasks."""
    source_root = Path(base_source_dir).resolve()
    if not source_root.is_dir():
        raise ParentPopulationError("base source directory is unavailable")
    campaign = _read_json(Path(campaign_config_path))
    budget, allowed_limits = _validate_campaign_config(
        campaign, time_limit=time_limit
    )
    experiment = load_experiment_config(experiment_config_path)
    entries = list(read_manifest(parent_manifest_path))
    entry_by_id = {entry.source_instance_id: entry for entry in entries}
    requested = list(instances) if instances else [
        entry.source_instance_id for entry in entries
    ]
    if len(requested) != len(set(requested)):
        raise ParentPopulationError("requested parent instances must be unique")
    unknown = sorted(set(requested) - set(entry_by_id))
    if unknown:
        raise ParentPopulationError(
            "requested parents are absent from the manifest: " + ", ".join(unknown)
        )

    available: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for instance_id in requested:
        entry = entry_by_id[instance_id]
        candidates = (
            Path(entry.category) / "LP" / f"{instance_id}.lp.gz",
            Path(entry.category) / "LP" / f"{instance_id}.lp",
        )
        relative = next(
            (candidate for candidate in candidates if (source_root / candidate).is_file()),
            None,
        )
        if relative is None:
            missing.append(
                {
                    "source_instance_id": instance_id,
                    "expected_relative_path": candidates[0].as_posix(),
                }
            )
            continue
        source = source_root / relative
        available.append(
            {
                "source_instance_id": instance_id,
                "category": entry.category,
                "difficulty": entry.difficulty,
                "fold": entry.fold,
                "role": role_for_fold(entry.fold, experiment.rotation),
                "parent_mip_relative_path": relative.as_posix(),
                "parent_mip_sha256": sha256_file(source),
            }
        )

    available.sort(key=lambda item: item["source_instance_id"])
    tasks: list[dict[str, Any]] = []
    solver_tasks: dict[str, list[dict[str, Any]]] = {solver: [] for solver in SOLVER_ORDER}
    for phase_index, solver in enumerate(SOLVER_ORDER):
        for parent in available:
            solver_index = len(solver_tasks[solver])
            budget_id = f"budget_{int(budget['time_limit_seconds'])}s"
            task = {
                "task_index": len(tasks),
                "solver_task_index": solver_index,
                "solver_phase_index": phase_index,
                "solver": solver,
                "budget_id": budget_id,
                "time_limit_seconds": budget["time_limit_seconds"],
                **parent,
                "run_dir_relative_path": (
                    f"{budget_id}/{solver}/{parent['category']}/"
                    f"{parent['source_instance_id']}"
                ),
            }
            tasks.append(task)
            solver_tasks[solver].append(task)

    planned_population = int(campaign.get("planned_parent_population", len(entries)))
    if planned_population != len(entries):
        raise ParentPopulationError(
            "planned_parent_population disagrees with the parent manifest"
        )
    contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": str(campaign.get("campaign_id")),
        "population_policy": "available_manifest_parents_with_planned_90_target",
        "priority_solver": "gurobi",
        "scip_role": "matched_comparison_only",
        "solver_order": list(SOLVER_ORDER),
        "solver_phase_dependency": "scip_afterok_gurobi",
        "objective_sense": "MINIMIZE",
        "original_objective_sense_recorded": True,
        "experiment_contract_sha256": experiment.contract_sha256,
        "parent_manifest_sha256": sha256_file(parent_manifest_path),
        "planned_parent_population": planned_population,
        "requested_parent_population": len(requested),
        "available_parent_population": len(available),
        "missing_parent_population": len(missing),
        "solve_budget": budget,
        "allowed_time_limit_seconds": list(allowed_limits),
        "gap_sensitivity_thresholds_relative": list(
            experiment.gap_policy.sensitivity_thresholds_relative
        ),
        "maximum_admissible_relative_gap": (
            experiment.gap_policy.maximum_admissible_relative_gap
        ),
        "parents": available,
        "missing_parents": missing,
        "tasks": tasks,
    }
    contract_sha256 = canonical_sha256(contract_payload)
    plan = {
        **contract_payload,
        "contract_sha256": contract_sha256,
        "population_status": (
            "complete" if len(available) == planned_population else "development_partial"
        ),
        "execution": {
            "gurobi_phase_tasks": len(solver_tasks["gurobi"]),
            "scip_phase_tasks": len(solver_tasks["scip"]),
            "required_submission_order": ["gurobi", "scip"],
            "scip_submission_dependency": "afterok:<gurobi_array_job_id>",
            "resume_policy": "hash_validated_completed_report_only",
            "preferred_execution_mode": "paired_parent_array_gurobi_then_scip",
            "recommended_max_parallel_parents": 4,
            "budget_isolated_run_directories": True,
        },
        "outputs": {
            "combined_tasks": TASKS_NAME,
            "gurobi_tasks": SOLVER_TASKS_NAME.format(solver="gurobi"),
            "scip_tasks": SOLVER_TASKS_NAME.format(solver="scip"),
            "phase1_audit": "parent_collection_audit_report.json",
        },
        "eligibility": {
            "execution_ready": bool(available),
            "development_only": len(available) < planned_population,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": (
                "gurobi_first_parent_collection_plan_ready"
                if available
                else "no_original_parent_mips_available"
            ),
            "next_gate": "gurobi_parent_collection_phase",
        },
    }
    return plan, tasks


def write_parent_collection_plan(
    *,
    base_source_dir: str | Path,
    output_dir: str | Path,
    parent_manifest_path: str | Path = DEFAULT_MANIFEST,
    campaign_config_path: str | Path = DEFAULT_CAMPAIGN_CONFIG,
    experiment_config_path: str | Path = DEFAULT_EXPERIMENT_CONFIG,
    instances: Sequence[str] | None = None,
    time_limit: float | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    expected = [output / PLAN_NAME, output / TASKS_NAME]
    expected.extend(
        output / SOLVER_TASKS_NAME.format(solver=solver) for solver in SOLVER_ORDER
    )
    if not overwrite and any(path.exists() for path in expected):
        raise ParentPopulationError("parent collection plan exists; use --overwrite")
    plan, tasks = build_parent_collection_plan(
        base_source_dir=base_source_dir,
        parent_manifest_path=parent_manifest_path,
        campaign_config_path=campaign_config_path,
        experiment_config_path=experiment_config_path,
        instances=instances,
        time_limit=time_limit,
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / PLAN_NAME, plan)
    _write_jsonl(output / TASKS_NAME, tasks)
    for solver in SOLVER_ORDER:
        _write_jsonl(
            output / SOLVER_TASKS_NAME.format(solver=solver),
            (task for task in tasks if task["solver"] == solver),
        )
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan a resumable Gurobi-first original-parent campaign."
    )
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--parent_manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--campaign_config", type=Path, default=DEFAULT_CAMPAIGN_CONFIG)
    parser.add_argument("--experiment_config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG)
    parser.add_argument("--instances", nargs="*")
    parser.add_argument("--time_limit", type=float)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = write_parent_collection_plan(
            base_source_dir=args.base_source_dir,
            output_dir=args.output_dir,
            parent_manifest_path=args.parent_manifest,
            campaign_config_path=args.campaign_config,
            experiment_config_path=args.experiment_config,
            instances=args.instances,
            time_limit=args.time_limit,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, ParentPopulationError) as error:
        print(f"[ERROR] {error}")
        return 2
    print(
        f"[INFO] contract={plan['contract_sha256']} | "
        f"parents={plan['available_parent_population']}/"
        f"{plan['planned_parent_population']} | tasks={len(plan['tasks'])}"
    )
    print("[INFO] execution order=gurobi -> scip(afterok) | resume=hash_validated")
    print(f"[INFO] Plan: {Path(args.output_dir).resolve() / PLAN_NAME}")
    return 0 if plan["eligibility"]["execution_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
