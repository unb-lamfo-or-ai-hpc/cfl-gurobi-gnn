"""Execute and audit the precommitted MVP parent-label rescue tasks."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from cfl_gnn.experiments.mvp_vertical_slice import (
    AUDIT_NAME as BENCHMARK_AUDIT_NAME,
    AUDIT_REPORT_NAME as BENCHMARK_AUDIT_REPORT_NAME,
    LABEL_RESCUE_TASKS_NAME,
    PLAN_NAME as VERTICAL_SLICE_PLAN_NAME,
    build_label_rescue_contract_payload,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.scip_parent_solutions import (
    INCUMBENTS_NAME,
    PLAN_NAME as PARENT_SOLVE_PLAN_NAME,
    REPORT_NAME as PARENT_SOLVE_REPORT_NAME,
    SOLUTION_NAME,
    VARIABLE_ORDER_NAME,
    ParentSolvePlan,
    run as run_parent_solve,
)


SCHEMA_VERSION = 1
AUDIT_SCHEMA_VERSION = 2
EXECUTION_PLAN_NAME = "mvp_label_rescue_execution_plan.json"
EXECUTION_REPORT_NAME = "mvp_label_rescue_execution_report.json"
PER_TASK_AUDIT_NAME = "per_label_rescue_task_audit.jsonl"
AUDIT_REPORT_NAME = "mvp_label_rescue_audit_report.json"


class MvpLabelRescueError(RuntimeError):
    """Raised when label rescue violates the precommitted contract."""


def _canonical_sha256(value: Any) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpLabelRescueError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise MvpLabelRescueError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    line_number = 0
    try:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError("record is not an object")
            records.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise MvpLabelRescueError(
            f"unreadable JSONL artifact: {path.name}:{line_number}"
        ) from error
    return records


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _contract_from_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"contract_sha256", "outputs"}
    }


@dataclass(frozen=True, slots=True)
class RescueInputs:
    vertical_plan: dict[str, Any]
    benchmark_report: dict[str, Any]
    benchmark_audit: tuple[dict[str, Any], ...]
    tasks: tuple[dict[str, Any], ...]
    rescue_contract_sha256: str


def load_rescue_inputs(vertical_slice_dir: str | Path) -> RescueInputs:
    """Validate the corrected PR #31 benchmark and rescue manifest."""
    root = Path(vertical_slice_dir).resolve()
    vertical_plan = _read_json(root / VERTICAL_SLICE_PLAN_NAME)
    vertical_contract = _contract_from_summary(vertical_plan)
    vertical_contract_sha256 = _canonical_sha256(vertical_contract)
    if vertical_plan.get("contract_sha256") != vertical_contract_sha256:
        raise MvpLabelRescueError("vertical-slice contract mismatch")

    benchmark_report = _read_json(root / BENCHMARK_AUDIT_REPORT_NAME)
    if benchmark_report.get("contract_sha256") != vertical_contract_sha256:
        raise MvpLabelRescueError("benchmark audit contract mismatch")
    if (
        benchmark_report.get("gates", {}).get("benchmark_observation_gate")
        != "passed"
    ):
        raise MvpLabelRescueError("paired benchmark observation gate is not passed")

    tasks_path = root / LABEL_RESCUE_TASKS_NAME
    expected_tasks_sha = benchmark_report.get("outputs", {}).get(
        "label_rescue_tasks_sha256"
    )
    if not tasks_path.is_file() or sha256_file(tasks_path) != expected_tasks_sha:
        raise MvpLabelRescueError("label-rescue manifest hash mismatch")
    tasks = _read_jsonl(tasks_path)
    if [task.get("rescue_task_index") for task in tasks] != list(range(len(tasks))):
        raise MvpLabelRescueError("label-rescue task indices are not contiguous")

    rescue_payload = build_label_rescue_contract_payload(
        vertical_slice_contract_sha256=vertical_contract_sha256,
        tasks=tasks,
    )
    rescue_contract_sha256 = _canonical_sha256(rescue_payload)
    if (
        benchmark_report.get("label_rescue", {}).get("contract_sha256")
        != rescue_contract_sha256
    ):
        raise MvpLabelRescueError("label-rescue contract mismatch")
    if benchmark_report.get("label_rescue", {}).get("tasks_planned") != len(tasks):
        raise MvpLabelRescueError("label-rescue task count mismatch")

    benchmark_audit = _read_jsonl(root / BENCHMARK_AUDIT_NAME)
    if len(benchmark_audit) != 12:
        raise MvpLabelRescueError("benchmark audit must contain twelve records")
    if any(item.get("benchmark_status") != "passed" for item in benchmark_audit):
        raise MvpLabelRescueError("benchmark audit contains an invalid observation")
    return RescueInputs(
        vertical_plan=vertical_plan,
        benchmark_report=benchmark_report,
        benchmark_audit=tuple(benchmark_audit),
        tasks=tuple(tasks),
        rescue_contract_sha256=rescue_contract_sha256,
    )


def _validate_task(task: Mapping[str, Any], *, expected_index: int) -> None:
    if task.get("rescue_task_index") != expected_index:
        raise MvpLabelRescueError("requested rescue task index mismatch")
    solver = task.get("solver")
    expected_profile = "default" if solver == "gurobi" else "feasibility"
    if (
        solver not in {"gurobi", "scip"}
        or task.get("solver_profile") != expected_profile
    ):
        raise MvpLabelRescueError("invalid rescue solver/profile pair")
    budget = task.get("solve_budget", {})
    if budget != {
        "time_limit_seconds": 14400.0,
        "node_limit": 4000000,
        "threads": 1,
        "seed": 42,
    }:
        raise MvpLabelRescueError("unexpected rescue solve budget")
    required_true = (
        "fresh_process",
        "cross_solver_warm_start_prohibited",
        "benchmark_artifacts_immutable",
    )
    if any(task.get(field) is not True for field in required_true):
        raise MvpLabelRescueError("rescue safety contract is incomplete")
    if task.get("warm_start_supplied") is not False:
        raise MvpLabelRescueError("label rescue must not use a warm start")


def _artifact_fingerprints(run_dir: Path, report: Mapping[str, Any]) -> dict[str, str]:
    result = {
        PARENT_SOLVE_PLAN_NAME: sha256_file(run_dir / PARENT_SOLVE_PLAN_NAME),
        PARENT_SOLVE_REPORT_NAME: sha256_file(run_dir / PARENT_SOLVE_REPORT_NAME),
    }
    for descriptor in report.get("artifacts", {}).values():
        if not isinstance(descriptor, dict) or not descriptor.get("file_name"):
            raise MvpLabelRescueError("invalid benchmark artifact descriptor")
        path = run_dir / str(descriptor["file_name"])
        digest = sha256_file(path)
        if digest != descriptor.get("sha256"):
            raise MvpLabelRescueError("benchmark artifact hash mismatch")
        result[path.name] = digest
    return dict(sorted(result.items()))


def build_rescue_task_plan(
    *,
    vertical_slice_dir: str | Path,
    benchmark_run_root: str | Path,
    base_source_dir: str | Path,
    rescue_run_root: str | Path,
    task_index: int,
) -> tuple[ParentSolvePlan, dict[str, Any]]:
    """Build one rescue task without consuming a benchmark incumbent."""
    inputs = load_rescue_inputs(vertical_slice_dir)
    if task_index < 0 or task_index >= len(inputs.tasks):
        raise MvpLabelRescueError("rescue task index is out of range")
    task = inputs.tasks[task_index]
    _validate_task(task, expected_index=task_index)

    audit_by_index = {
        int(item["task_index"]): item for item in inputs.benchmark_audit
    }
    benchmark_audit = audit_by_index.get(int(task["source_task_index"]))
    if benchmark_audit is None:
        raise MvpLabelRescueError("source benchmark audit record is missing")
    if (
        benchmark_audit.get("solver") != task.get("solver")
        or benchmark_audit.get("source_instance_id")
        != task.get("source_instance_id")
        or benchmark_audit.get("parent_contract_sha256")
        != task.get("benchmark_parent_contract_sha256")
        or benchmark_audit.get("mip_gap_relative")
        != task.get("benchmark_terminal_mip_gap_relative")
    ):
        raise MvpLabelRescueError("rescue task disagrees with benchmark audit")

    benchmark_dir = Path(benchmark_run_root).resolve() / str(
        task["benchmark_run_dir_relative_path"]
    )
    benchmark_plan = _read_json(benchmark_dir / PARENT_SOLVE_PLAN_NAME)
    benchmark_report = _read_json(benchmark_dir / PARENT_SOLVE_REPORT_NAME)
    if (
        benchmark_plan.get("contract_sha256")
        != task["benchmark_parent_contract_sha256"]
        or benchmark_report.get("contract_sha256")
        != task["benchmark_parent_contract_sha256"]
    ):
        raise MvpLabelRescueError("benchmark parent contract changed")
    benchmark_fingerprints = _artifact_fingerprints(
        benchmark_dir, benchmark_report
    )

    parent_mip = Path(base_source_dir).resolve() / str(
        task["parent_mip_relative_path"]
    )
    if not parent_mip.is_file() or sha256_file(parent_mip) != task["parent_mip_sha256"]:
        raise MvpLabelRescueError("rescue parent MIP hash mismatch")
    output_dir = Path(rescue_run_root).resolve() / str(
        task["rescue_run_dir_relative_path"]
    )
    budget = task["solve_budget"]
    parent_plan = ParentSolvePlan(
        solver=str(task["solver"]),
        parent_mip=parent_mip,
        output_dir=output_dir,
        parent_instance_id=str(task["source_instance_id"]),
        category=str(task["category"]),
        difficulty=str(task["difficulty"]),
        fold=int(task["fold"]),
        role=str(task["role"]),
        experiment_contract_sha256=str(
            inputs.vertical_plan["experiment_contract_sha256"]
        ),
        maximum_admissible_relative_gap=float(
            inputs.vertical_plan["maximum_admissible_relative_gap"]
        ),
        time_limit=float(budget["time_limit_seconds"]),
        node_limit=int(budget["node_limit"]),
        seed=int(budget["seed"]),
        threads=int(budget["threads"]),
        solver_profile=str(task["solver_profile"]),
    )
    execution_contract = {
        "schema_version": SCHEMA_VERSION,
        "dataset_variant": "mvp_vertical_slice_label_rescue_execution",
        "rescue_contract_sha256": inputs.rescue_contract_sha256,
        "task": dict(task),
        "benchmark_lineage": {
            "run_dir_relative_path": task["benchmark_run_dir_relative_path"],
            "parent_contract_sha256": task["benchmark_parent_contract_sha256"],
            "artifact_fingerprints": benchmark_fingerprints,
        },
        "parent_solve_contract": parent_plan.contract_payload,
        "eligibility": {
            "label_eligible": False,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
    }
    execution_plan = {
        **execution_contract,
        "contract_sha256": _canonical_sha256(execution_contract),
        "outputs": {
            "parent_solve_plan": PARENT_SOLVE_PLAN_NAME,
            "parent_solve_report": PARENT_SOLVE_REPORT_NAME,
            "report": EXECUTION_REPORT_NAME,
        },
    }
    return parent_plan, execution_plan


def execute_rescue_task(
    *,
    vertical_slice_dir: str | Path,
    benchmark_run_root: str | Path,
    base_source_dir: str | Path,
    rescue_run_root: str | Path,
    task_index: int,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Execute one fresh rescue solve and retain explicit benchmark lineage."""
    parent_plan, execution_plan = build_rescue_task_plan(
        vertical_slice_dir=vertical_slice_dir,
        benchmark_run_root=benchmark_run_root,
        base_source_dir=base_source_dir,
        rescue_run_root=rescue_run_root,
        task_index=task_index,
    )
    output = parent_plan.output_dir
    output.mkdir(parents=True, exist_ok=True)
    expected = (
        output / EXECUTION_PLAN_NAME,
        output / EXECUTION_REPORT_NAME,
        output / PARENT_SOLVE_PLAN_NAME,
        output / PARENT_SOLVE_REPORT_NAME,
    )
    if not overwrite and any(path.exists() for path in expected):
        raise MvpLabelRescueError("rescue output exists; use --overwrite")
    _write_json(output / EXECUTION_PLAN_NAME, execution_plan)
    _write_json(output / PARENT_SOLVE_PLAN_NAME, parent_plan.to_summary())
    if dry_run:
        return execution_plan

    benchmark_dir = Path(benchmark_run_root).resolve() / str(
        execution_plan["task"]["benchmark_run_dir_relative_path"]
    )
    benchmark_report = _read_json(benchmark_dir / PARENT_SOLVE_REPORT_NAME)
    before = _artifact_fingerprints(benchmark_dir, benchmark_report)
    parent_report = run_parent_solve(parent_plan)
    _write_json(output / PARENT_SOLVE_REPORT_NAME, parent_report)
    after = _artifact_fingerprints(benchmark_dir, benchmark_report)
    solve = parent_report.get("solve", {})
    gap = solve.get("mip_gap_relative")
    gap_admissible = (
        isinstance(gap, (int, float))
        and math.isfinite(float(gap))
        and 0.0 <= float(gap)
        <= parent_plan.maximum_admissible_relative_gap + 1e-12
    )
    checks = {
        "execution_contract_valid": (
            execution_plan["contract_sha256"]
            == _canonical_sha256(_contract_from_summary(execution_plan))
        ),
        "parent_solve_contract_match": (
            parent_report.get("contract_sha256") == parent_plan.contract_sha256
        ),
        "benchmark_artifacts_unchanged": before == after,
        "fresh_process": parent_report.get("checks", {}).get("fresh_process") is True,
        "no_warm_start": parent_report.get("checks", {}).get("no_warm_start") is True,
        "objective_minimize": solve.get("objective_sense") == "minimize",
        "terminal_gap_admissible": gap_admissible,
        "label_eligible": parent_report.get("eligibility", {}).get("label_eligible")
        is True,
    }
    passed = all(checks.values())
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": execution_plan["contract_sha256"],
        "rescue_contract_sha256": execution_plan["rescue_contract_sha256"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "gate_status": "passed" if passed else "inconclusive",
        "task": execution_plan["task"],
        "solver": parent_plan.solver,
        "solver_profile": parent_plan.solver_profile,
        "solve": dict(solve),
        "checks": checks,
        "artifacts": {
            "execution_plan": {
                "file_name": EXECUTION_PLAN_NAME,
                "sha256": sha256_file(output / EXECUTION_PLAN_NAME),
            },
            "parent_solve_plan": {
                "file_name": PARENT_SOLVE_PLAN_NAME,
                "sha256": sha256_file(output / PARENT_SOLVE_PLAN_NAME),
            },
            "parent_solve_report": {
                "file_name": PARENT_SOLVE_REPORT_NAME,
                "sha256": sha256_file(output / PARENT_SOLVE_REPORT_NAME),
            },
            "solution": parent_report["artifacts"]["solution"],
            "incumbents": parent_report["artifacts"]["incumbents"],
            "variable_order": parent_report["artifacts"]["variable_order"],
        },
        "eligibility": {
            "label_rescue_eligible": passed,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": (
                "rescued_parent_label_admissible"
                if passed
                else "rescued_parent_gap_above_policy"
            ),
            "next_gate": "aggregate_label_rescue_audit",
        },
    }
    _write_json(output / EXECUTION_REPORT_NAME, report)
    return report


def audit_rescue_runs(
    *,
    vertical_slice_dir: str | Path,
    rescue_run_root: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Separate execution integrity from rescue-label admissibility."""
    vertical_root = Path(vertical_slice_dir).resolve()
    rescue_root = Path(rescue_run_root).resolve()
    inputs = load_rescue_inputs(vertical_root)
    report_path = vertical_root / AUDIT_REPORT_NAME
    audit_path = vertical_root / PER_TASK_AUDIT_NAME
    if not overwrite and (report_path.exists() or audit_path.exists()):
        raise MvpLabelRescueError("rescue audit exists; use --overwrite")

    audits: list[dict[str, Any]] = []
    for task in inputs.tasks:
        run_dir = rescue_root / str(task["rescue_run_dir_relative_path"])
        execution_report_path = run_dir / EXECUTION_REPORT_NAME
        if not execution_report_path.is_file():
            audits.append(
                {
                    "rescue_task_index": task["rescue_task_index"],
                    "solver": task["solver"],
                    "source_instance_id": task["source_instance_id"],
                    "role": task["role"],
                    "integrity_status": "failed",
                    "label_status": "unavailable",
                    "status": "failed",
                    "reason_code": "rescue_execution_report_missing",
                }
            )
            continue
        execution_report = _read_json(execution_report_path)
        reported_checks = execution_report.get("checks", {})
        if not isinstance(reported_checks, dict):
            reported_checks = {}
        integrity_checks = {
            "rescue_contract_match": (
                execution_report.get("rescue_contract_sha256")
                == inputs.rescue_contract_sha256
            ),
            "task_identity_match": execution_report.get("task") == task,
            "probe_completed": execution_report.get("probe_completed") is True,
            "execution_contract_valid": reported_checks.get(
                "execution_contract_valid"
            )
            is True,
            "parent_solve_contract_match": reported_checks.get(
                "parent_solve_contract_match"
            )
            is True,
            "benchmark_artifacts_unchanged": reported_checks.get(
                "benchmark_artifacts_unchanged"
            )
            is True,
            "fresh_process": reported_checks.get("fresh_process") is True,
            "no_warm_start": reported_checks.get("no_warm_start") is True,
            "objective_minimize": reported_checks.get("objective_minimize") is True,
        }
        label_checks = {
            "execution_gate_passed": execution_report.get("gate_status") == "passed",
            "terminal_gap_admissible": reported_checks.get(
                "terminal_gap_admissible"
            )
            is True,
            "execution_label_check_passed": reported_checks.get("label_eligible")
            is True,
            "label_eligibility_declared": execution_report.get(
                "eligibility", {}
            ).get("label_rescue_eligible")
            is True,
        }
        artifact_checks: dict[str, bool] = {}
        descriptors = execution_report.get("artifacts", {})
        if not isinstance(descriptors, dict):
            descriptors = {}
        required_artifacts = (
            "execution_plan",
            "parent_solve_plan",
            "parent_solve_report",
            "solution",
            "incumbents",
            "variable_order",
        )
        for name in required_artifacts:
            descriptor = descriptors.get(name)
            if not isinstance(descriptor, dict):
                artifact_checks[name] = False
                continue
            path = run_dir / str(descriptor.get("file_name", ""))
            artifact_checks[name] = path.is_file() and sha256_file(
                path
            ) == descriptor.get("sha256")
        integrity_passed = all(integrity_checks.values()) and all(
            artifact_checks.values()
        )
        label_admissible = integrity_passed and all(label_checks.values())
        status = (
            "failed"
            if not integrity_passed
            else "passed"
            if label_admissible
            else "inconclusive"
        )
        audits.append(
            {
                "rescue_task_index": task["rescue_task_index"],
                "solver": task["solver"],
                "source_instance_id": task["source_instance_id"],
                "role": task["role"],
                "reason_code": task["reason_code"],
                "run_dir_relative_path": task["rescue_run_dir_relative_path"],
                "mip_gap_relative": execution_report.get("solve", {}).get(
                    "mip_gap_relative"
                ),
                "execution_time_seconds": execution_report.get("solve", {}).get(
                    "execution_time_seconds"
                ),
                "integrity_checks": integrity_checks,
                "label_checks": label_checks,
                "artifact_checks": artifact_checks,
                "integrity_status": "passed" if integrity_passed else "failed",
                "label_status": (
                    "unavailable"
                    if not integrity_passed
                    else "admissible"
                    if label_admissible
                    else "inadmissible"
                ),
                "status": status,
            }
        )
    integrity_passed_count = sum(
        item.get("integrity_status") == "passed" for item in audits
    )
    labels_admissible_count = sum(
        item.get("label_status") == "admissible" for item in audits
    )
    labels_inadmissible_count = sum(
        item.get("label_status") == "inadmissible" for item in audits
    )
    labels_unavailable_count = sum(
        item.get("label_status") == "unavailable" for item in audits
    )
    tasks_failed = sum(item["status"] == "failed" for item in audits)
    tasks_inconclusive = sum(item["status"] == "inconclusive" for item in audits)
    if tasks_failed:
        gate = "failed"
    elif labels_admissible_count == len(inputs.tasks) and inputs.tasks:
        gate = "passed"
    else:
        gate = "inconclusive"
    _write_jsonl(audit_path, audits)
    report = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "rescue_contract_sha256": inputs.rescue_contract_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "gate_status": gate,
        "summary": {
            "tasks_planned": len(inputs.tasks),
            "execution_integrity_passed": integrity_passed_count,
            "execution_integrity_failed": (
                len(inputs.tasks) - integrity_passed_count
            ),
            "labels_admissible": labels_admissible_count,
            "labels_inadmissible": labels_inadmissible_count,
            "labels_unavailable": labels_unavailable_count,
            "tasks_passed": labels_admissible_count,
            "tasks_inconclusive": tasks_inconclusive,
            "tasks_failed": tasks_failed,
        },
        "eligibility": {
            "label_rescue_complete": gate == "passed",
            "vertical_slice_composition_ready": gate == "passed",
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "outputs": {
            "per_task_audit": PER_TASK_AUDIT_NAME,
            "per_task_audit_sha256": sha256_file(audit_path),
        },
        "decision": {
            "reason_code": (
                "all_precommitted_parent_labels_rescued"
                if gate == "passed"
                else "rescue_execution_valid_labels_incomplete"
                if gate == "inconclusive"
                else "one_or_more_rescue_executions_invalid"
            ),
            "next_gate": (
                "train_parent_local_branching_and_derived_labels"
                if gate == "passed"
                else "define_reduced_mvp_slice_or_precommit_additional_rescue"
                if gate == "inconclusive"
                else "review_rescue_integrity_failures"
            ),
        },
    }
    _write_json(report_path, report)
    return report
