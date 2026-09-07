"""Plan and audit the paired six-parent MVP vertical slice."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold


SCHEMA_VERSION = 1
PLAN_NAME = "mvp_vertical_slice_plan.json"
TASKS_NAME = "parent_solve_tasks.jsonl"
PREFLIGHT_REPORT_NAME = "mvp_vertical_slice_preflight_report.json"
AUDIT_NAME = "per_parent_solve_audit.jsonl"
AUDIT_REPORT_NAME = "mvp_vertical_slice_parent_audit_report.json"
PARENT_RUNS_NAME = "parent_runs.tsv"
LABEL_RESCUE_TASKS_NAME = "label_rescue_tasks.jsonl"
PARENT_SOLVE_PLAN_NAME = "scip_parent_solve_plan.json"
PARENT_SOLVE_REPORT_NAME = "scip_parent_solve_report.json"
REQUIRED_SOLVERS = ("gurobi", "scip")
REQUIRED_ROLES = ("train", "validation", "test")
REQUIRED_DIFFICULTIES = ("easy", "medium")


class MvpVerticalSliceError(RuntimeError):
    """Raised when the paired vertical-slice contract fails closed."""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpVerticalSliceError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise MvpVerticalSliceError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    line_number = 0
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise TypeError("record is not an object")
                result.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise MvpVerticalSliceError(
            f"unreadable JSONL artifact: {path.name}:{line_number}"
        ) from error
    return result


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise MvpVerticalSliceError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpVerticalSliceError(f"{field} must be a positive integer") from error
    if normalized <= 0 or normalized != value:
        raise MvpVerticalSliceError(f"{field} must be a positive integer")
    return normalized


@dataclass(frozen=True, slots=True)
class SelectedParent:
    source_instance_id: str
    category: str
    difficulty: str
    fold: int
    role: str
    parent_mip_relative_path: str
    parent_mip_sha256: str

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "source_instance_id": self.source_instance_id,
            "category": self.category,
            "difficulty": self.difficulty,
            "fold": self.fold,
            "role": self.role,
            "parent_mip_relative_path": self.parent_mip_relative_path,
            "parent_mip_sha256": self.parent_mip_sha256,
        }


def _validate_slice_config(value: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise MvpVerticalSliceError("unsupported vertical-slice schema")
    if value.get("development_only") is not True:
        raise MvpVerticalSliceError("vertical slice must remain development-only")
    if value.get("selection_policy") != "explicit_balanced_role_difficulty_v1":
        raise MvpVerticalSliceError("unexpected vertical-slice selection policy")
    if value.get("solvers") != list(REQUIRED_SOLVERS):
        raise MvpVerticalSliceError("vertical slice requires Gurobi and SCIP")
    parents = value.get("parents")
    if not isinstance(parents, list) or len(parents) != 6:
        raise MvpVerticalSliceError("vertical slice requires exactly six parents")
    normalized: list[dict[str, Any]] = []
    for parent in parents:
        if not isinstance(parent, dict):
            raise MvpVerticalSliceError("vertical-slice parent must be an object")
        instance_id = str(parent.get("source_instance_id", "")).strip()
        role = str(parent.get("role", "")).strip()
        difficulty = str(parent.get("difficulty", "")).strip()
        if not instance_id or role not in REQUIRED_ROLES:
            raise MvpVerticalSliceError("invalid vertical-slice parent identity or role")
        if difficulty not in REQUIRED_DIFFICULTIES:
            raise MvpVerticalSliceError("vertical slice supports easy and medium")
        normalized.append(
            {
                "source_instance_id": instance_id,
                "role": role,
                "difficulty": difficulty,
            }
        )
    if len({parent["source_instance_id"] for parent in normalized}) != 6:
        raise MvpVerticalSliceError("vertical-slice parents must be unique")
    cells = Counter((parent["role"], parent["difficulty"]) for parent in normalized)
    expected = {(role, difficulty): 1 for role in REQUIRED_ROLES for difficulty in REQUIRED_DIFFICULTIES}
    if cells != expected:
        raise MvpVerticalSliceError("vertical slice must balance role and difficulty")
    return tuple(normalized)


def build_vertical_slice_plan(
    *,
    base_source_dir: str | Path,
    output_dir: str | Path,
    slice_config_path: str | Path,
    parent_manifest_path: str | Path,
    experiment_config_path: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Validate inputs and build twelve paired parent-solve tasks."""
    source_root = Path(base_source_dir).resolve()
    raw_slice = _read_json(Path(slice_config_path))
    configured = _validate_slice_config(raw_slice)
    experiment = load_experiment_config(experiment_config_path)
    if experiment.rotation != 0:
        raise MvpVerticalSliceError("vertical-slice v1 is precommitted to rotation 0")
    manifest = {item.source_instance_id: item for item in read_manifest(parent_manifest_path)}

    selected: list[SelectedParent] = []
    for requested in configured:
        instance_id = requested["source_instance_id"]
        entry = manifest.get(instance_id)
        if entry is None:
            raise MvpVerticalSliceError(f"parent is absent from manifest: {instance_id}")
        role = role_for_fold(entry.fold, experiment.rotation)
        if role != requested["role"] or entry.difficulty != requested["difficulty"]:
            raise MvpVerticalSliceError(f"parent metadata disagrees with manifest: {instance_id}")
        relative = Path(entry.category) / "LP" / f"{instance_id}.lp.gz"
        source = source_root / relative
        if not source.is_file():
            raise MvpVerticalSliceError(f"missing original parent MIP: {relative.as_posix()}")
        selected.append(
            SelectedParent(
                source_instance_id=instance_id,
                category=entry.category,
                difficulty=entry.difficulty,
                fold=entry.fold,
                role=role,
                parent_mip_relative_path=relative.as_posix(),
                parent_mip_sha256=sha256_file(source),
            )
        )

    budget = raw_slice.get("solve_budget", {})
    if not isinstance(budget, dict):
        raise MvpVerticalSliceError("solve_budget must be an object")
    time_limit = float(budget.get("time_limit_seconds"))
    if not math.isfinite(time_limit) or time_limit <= 0:
        raise MvpVerticalSliceError("time_limit_seconds must be positive and finite")
    normalized_budget = {
        "time_limit_seconds": time_limit,
        "node_limit": _positive_int(budget.get("node_limit"), field="node_limit"),
        "threads": _positive_int(budget.get("threads"), field="threads"),
            "seed": _positive_int(budget.get("seed"), field="seed"),
    }

    tasks: list[dict[str, Any]] = []
    for parent in sorted(selected, key=lambda item: item.source_instance_id):
        for solver in REQUIRED_SOLVERS:
            tasks.append(
                {
                    "task_index": len(tasks),
                    "solver": solver,
                    **parent.payload,
                    "run_dir_relative_path": f"{solver}/{parent.source_instance_id}",
                    "augmentation_required": parent.role == "train",
                }
            )
    contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "slice_id": str(raw_slice.get("slice_id")),
        "selection_policy": str(raw_slice.get("selection_policy")),
        "experiment_contract_sha256": experiment.contract_sha256,
        "development_only": True,
        "scientific_reporting_eligible": False,
        "solvers": list(REQUIRED_SOLVERS),
        "solve_budget": normalized_budget,
        "maximum_admissible_relative_gap": (
            experiment.gap_policy.maximum_admissible_relative_gap
        ),
        "parents": [parent.payload for parent in sorted(selected, key=lambda item: item.source_instance_id)],
        "tasks": tasks,
    }
    contract_sha256 = _canonical_sha256(contract_payload)
    plan = {
        **contract_payload,
        "contract_sha256": contract_sha256,
        "outputs": {
            "task_manifest": TASKS_NAME,
            "preflight_report": PREFLIGHT_REPORT_NAME,
            "parent_run_audit": AUDIT_REPORT_NAME,
            "parent_runs": PARENT_RUNS_NAME,
        },
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": contract_sha256,
        "gate_status": "passed",
        "summary": {
            "parents": 6,
            "parent_solve_tasks": len(tasks),
            "parents_by_role": dict(sorted(Counter(parent.role for parent in selected).items())),
            "parents_by_difficulty": dict(sorted(Counter(parent.difficulty for parent in selected).items())),
            "train_parents_requiring_augmentation": sum(parent.role == "train" for parent in selected),
        },
        "eligibility": {
            "execution_ready": True,
            "dataset_eligible": False,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "paired_vertical_slice_preflight_passed",
            "next_gate": "paired_gurobi_scip_parent_solves",
        },
    }
    return plan, tasks, report


def write_vertical_slice_plan(
    *,
    base_source_dir: str | Path,
    output_dir: str | Path,
    slice_config_path: str | Path,
    parent_manifest_path: str | Path,
    experiment_config_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    expected = (output / PLAN_NAME, output / TASKS_NAME, output / PREFLIGHT_REPORT_NAME)
    if not overwrite and any(path.exists() for path in expected):
        raise MvpVerticalSliceError("vertical-slice plan exists; use --overwrite")
    plan, tasks, report = build_vertical_slice_plan(
        base_source_dir=base_source_dir,
        output_dir=output,
        slice_config_path=slice_config_path,
        parent_manifest_path=parent_manifest_path,
        experiment_config_path=experiment_config_path,
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / PLAN_NAME, plan)
    _write_jsonl(output / TASKS_NAME, tasks)
    _write_json(output / PREFLIGHT_REPORT_NAME, report)
    return report


def audit_vertical_slice_parent_runs(
    *, plan_dir: str | Path, run_root: str | Path, overwrite: bool = False
) -> dict[str, Any]:
    """Separate benchmark validity from downstream label-coverage gates."""
    plan_root = Path(plan_dir).resolve()
    runs = Path(run_root).resolve()
    report_path = plan_root / AUDIT_REPORT_NAME
    audit_path = plan_root / AUDIT_NAME
    parent_runs_path = plan_root / PARENT_RUNS_NAME
    rescue_tasks_path = plan_root / LABEL_RESCUE_TASKS_NAME
    if not overwrite and any(
        path.exists()
        for path in (report_path, audit_path, parent_runs_path, rescue_tasks_path)
    ):
        raise MvpVerticalSliceError("parent audit exists; use --overwrite")
    plan = _read_json(plan_root / PLAN_NAME)
    tasks = _read_jsonl(plan_root / TASKS_NAME)
    if plan.get("tasks") != tasks:
        raise MvpVerticalSliceError("task manifest disagrees with vertical-slice plan")
    contract_payload = {key: value for key, value in plan.items() if key not in {"contract_sha256", "outputs"}}
    contract_sha256 = _canonical_sha256(contract_payload)
    if plan.get("contract_sha256") != contract_sha256:
        raise MvpVerticalSliceError("vertical-slice plan contract mismatch")

    audits: list[dict[str, Any]] = []
    benchmark_run_rows: list[tuple[str, str]] = []
    maximum_gap = float(plan["maximum_admissible_relative_gap"])
    for task in tasks:
        run_relative = str(task["run_dir_relative_path"])
        run_dir = runs / run_relative
        parent_plan_path = run_dir / PARENT_SOLVE_PLAN_NAME
        parent_report_path = run_dir / PARENT_SOLVE_REPORT_NAME
        if not parent_plan_path.is_file() or not parent_report_path.is_file():
            audits.append(
                {
                    "task_index": task["task_index"],
                    "solver": task["solver"],
                    "source_instance_id": task["source_instance_id"],
                    "role": task["role"],
                    "difficulty": task["difficulty"],
                    "run_dir_relative_path": run_relative,
                    "benchmark_status": "failed",
                    "label_eligible": False,
                    "status": "failed",
                    "reason_code": (
                        "parent_solve_plan_missing"
                        if not parent_plan_path.is_file()
                        else "parent_solve_report_missing"
                    ),
                }
            )
            continue
        parent_plan = _read_json(parent_plan_path)
        parent_report = _read_json(parent_report_path)
        parent = parent_report.get("parent", {})
        solve = parent_report.get("solve", {})
        eligibility = parent_report.get("eligibility", {})
        role = str(task["role"])
        raw_gap = solve.get("mip_gap_relative")
        raw_time = solve.get("execution_time_seconds")
        terminal_gap_finite = (
            isinstance(raw_gap, (int, float))
            and math.isfinite(float(raw_gap))
            and float(raw_gap) >= 0.0
        )
        gap_admissible = terminal_gap_finite and float(raw_gap) <= maximum_gap + 1e-12
        execution_time_valid = (
            isinstance(raw_time, (int, float))
            and math.isfinite(float(raw_time))
            and float(raw_time) >= 0.0
        )
        parent_checks = parent_report.get("checks", {})
        parent_plan_contract_payload = {
            key: value
            for key, value in parent_plan.items()
            if key not in {"contract_sha256", "outputs"}
        }
        parent_plan_contract_sha256 = _canonical_sha256(parent_plan_contract_payload)
        solver_contract = parent_plan.get("solver_contract", {})
        expected_budget = plan["solve_budget"]
        provenance_checks = {
            "parent_plan_contract_valid": (
                parent_plan.get("contract_sha256") == parent_plan_contract_sha256
            ),
            "parent_report_contract_match": (
                parent_report.get("contract_sha256") == parent_plan_contract_sha256
            ),
            "experiment_contract_match": (
                parent_plan.get("experiment_contract_sha256")
                == plan["experiment_contract_sha256"]
            ),
            "solver_identity_match": solver_contract.get("solver") == task["solver"],
            "solver_profile_default": solver_contract.get("solver_profile") == "default",
            "time_limit_match": (
                solver_contract.get("time_limit_seconds")
                == expected_budget["time_limit_seconds"]
            ),
            "node_limit_match": (
                solver_contract.get("node_limit") == expected_budget["node_limit"]
            ),
            "threads_match": solver_contract.get("threads") == expected_budget["threads"],
            "seed_match": solver_contract.get("seed") == expected_budget["seed"],
            "force_minimize": solver_contract.get("force_minimize") is True,
            "fresh_process": solver_contract.get("fresh_process") is True,
            "no_warm_start": solver_contract.get("warm_start_supplied") is False,
        }
        benchmark_checks = {
            "parent_identity_match": parent.get("source_instance_id") == task["source_instance_id"],
            "parent_sha256_match": parent.get("sha256") == task["parent_mip_sha256"],
            "parent_metadata_match": all(
                parent.get(field) == task[field]
                for field in ("category", "difficulty", "fold", "role")
            ),
            "objective_minimize": solve.get("objective_sense") == "minimize",
            "terminal_gap_finite": terminal_gap_finite,
            "execution_time_valid": execution_time_valid,
            "parent_instrumentation_checks_passed": (
                isinstance(parent_checks, dict)
                and bool(parent_checks)
                and all(value is True for value in parent_checks.values())
            ),
        }
        artifacts = parent_report.get("artifacts", {})
        artifact_checks: dict[str, bool] = {}
        for artifact_name in ("solution", "incumbents", "variable_order"):
            descriptor = artifacts.get(artifact_name, {})
            artifact = run_dir / str(descriptor.get("file_name", ""))
            artifact_checks[artifact_name] = (
                artifact.is_file() and sha256_file(artifact) == descriptor.get("sha256")
            )
        mechanically_valid = (
            all(provenance_checks.values())
            and all(benchmark_checks.values())
            and all(artifact_checks.values())
        )
        computed_label_eligible = mechanically_valid and gap_admissible
        computed_augmentation_eligible = computed_label_eligible and role == "train"
        expected_gate_status = (
            "failed"
            if not mechanically_valid
            else "passed"
            if computed_augmentation_eligible
            else "inconclusive"
        )
        contract_checks = {
            "label_eligibility_consistent": (
                eligibility.get("label_eligible") is computed_label_eligible
            ),
            "augmentation_eligibility_consistent": (
                eligibility.get("augmentation_source_eligible")
                is computed_augmentation_eligible
            ),
            "gate_status_consistent": (
                parent_report.get("gate_status") == expected_gate_status
            ),
        }
        benchmark_passed = mechanically_valid and all(contract_checks.values())
        audits.append(
            {
                "task_index": task["task_index"],
                "solver": task["solver"],
                "source_instance_id": task["source_instance_id"],
                "role": role,
                "difficulty": task["difficulty"],
                "parent_contract_sha256": parent_plan_contract_sha256,
                "solver_contract_sha256": _canonical_sha256(solver_contract),
                "parent_plan_sha256": sha256_file(parent_plan_path),
                "parent_report_sha256": sha256_file(parent_report_path),
                "run_dir_relative_path": run_relative,
                "mip_gap_relative": solve.get("mip_gap_relative"),
                "execution_time_seconds": solve.get("execution_time_seconds"),
                "solution_objective": solve.get("solution_objective"),
                "benchmark_checks": benchmark_checks,
                "provenance_checks": provenance_checks,
                "contract_checks": contract_checks,
                "label_checks": {
                    "maximum_admissible_relative_gap": maximum_gap,
                    "mip_gap_admissible": gap_admissible,
                },
                "artifact_checks": artifact_checks,
                "benchmark_status": "passed" if benchmark_passed else "failed",
                "label_eligible": benchmark_passed and gap_admissible,
                "augmentation_source_eligible": (
                    benchmark_passed and gap_admissible and role == "train"
                ),
                "status": "passed" if benchmark_passed else "failed",
            }
        )
        if benchmark_passed:
            benchmark_run_rows.append((str(task["solver"]), run_relative))

    benchmark_passed_count = sum(
        item.get("benchmark_status") == "passed" for item in audits
    )
    parent_sets = defaultdict(set)
    for item in audits:
        if item.get("benchmark_status") == "passed":
            parent_sets[item["solver"]].add(item["source_instance_id"])
    paired_benchmark_population = (
        len(parent_sets) == 2
        and parent_sets["gurobi"] == parent_sets["scip"]
        and len(parent_sets["gurobi"]) == 6
    )
    benchmark_gate = (
        "passed"
        if benchmark_passed_count == len(tasks) and paired_benchmark_population
        else "failed"
    )
    training_records = [item for item in audits if item.get("role") == "train"]
    training_labels_eligible = sum(
        item.get("label_eligible") is True for item in training_records
    )
    training_label_gate = (
        "passed" if training_labels_eligible == len(training_records) == 4 else "incomplete"
    )
    evaluation_parent_ids = {
        str(task["source_instance_id"])
        for task in tasks
        if task["role"] in {"validation", "test"}
    }
    evaluation_references_covered = sum(
        any(
            item.get("source_instance_id") == parent_id
            and item.get("label_eligible") is True
            for item in audits
        )
        for parent_id in evaluation_parent_ids
    )
    evaluation_reference_gate = (
        "passed"
        if evaluation_references_covered == len(evaluation_parent_ids) == 4
        else "incomplete"
    )
    composition_ready = (
        benchmark_gate == "passed"
        and training_label_gate == "passed"
        and evaluation_reference_gate == "passed"
    )
    gate = (
        "failed"
        if benchmark_gate == "failed"
        else "passed"
        if composition_ready
        else "inconclusive"
    )
    tasks_by_index = {int(task["task_index"]): task for task in tasks}

    def rescue_record(
        audit: Mapping[str, Any], *, reason_code: str
    ) -> dict[str, Any]:
        task = tasks_by_index[int(audit["task_index"])]
        solver = str(task["solver"])
        return {
            "rescue_task_index": -1,
            "source_task_index": task["task_index"],
            "solver": solver,
            "source_instance_id": task["source_instance_id"],
            "category": task["category"],
            "difficulty": task["difficulty"],
            "fold": task["fold"],
            "role": task["role"],
            "parent_mip_relative_path": task["parent_mip_relative_path"],
            "parent_mip_sha256": task["parent_mip_sha256"],
            "benchmark_run_dir_relative_path": task["run_dir_relative_path"],
            "benchmark_parent_contract_sha256": audit["parent_contract_sha256"],
            "benchmark_terminal_mip_gap_relative": audit["mip_gap_relative"],
            "reason_code": reason_code,
            "rescue_run_dir_relative_path": (
                f"{solver}/{task['source_instance_id']}"
            ),
            "solver_profile": "default" if solver == "gurobi" else "feasibility",
            "solve_budget": {
                "time_limit_seconds": 14400.0,
                "node_limit": 4000000,
                "threads": expected_budget["threads"],
                "seed": expected_budget["seed"],
            },
            "fresh_process": True,
            "warm_start_supplied": False,
            "cross_solver_warm_start_prohibited": True,
            "benchmark_artifacts_immutable": True,
        }

    rescue_tasks: list[dict[str, Any]] = []
    if benchmark_gate == "passed":
        for audit in sorted(audits, key=lambda item: int(item["task_index"])):
            if audit.get("role") == "train" and audit.get("label_eligible") is not True:
                rescue_tasks.append(
                    rescue_record(
                        audit, reason_code="solver_arm_training_label_missing"
                    )
                )
        for parent_id in sorted(evaluation_parent_ids):
            records = [
                item
                for item in audits
                if item.get("source_instance_id") == parent_id
                and item.get("benchmark_status") == "passed"
            ]
            if any(item.get("label_eligible") is True for item in records):
                continue
            selected = min(
                records,
                key=lambda item: (
                    float(item["mip_gap_relative"]),
                    str(item["solver"]),
                ),
            )
            rescue_tasks.append(
                rescue_record(
                    selected,
                    reason_code="common_evaluation_reference_missing",
                )
            )
    rescue_tasks.sort(key=lambda item: int(item["source_task_index"]))
    for rescue_index, rescue_task in enumerate(rescue_tasks):
        rescue_task["rescue_task_index"] = rescue_index
    rescue_contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_variant": "mvp_vertical_slice_label_rescue",
        "vertical_slice_contract_sha256": contract_sha256,
        "selection_policy": (
            "missing_train_solver_labels_and_missing_common_evaluation_references_v1"
        ),
        "benchmark_results_immutable": True,
        "tasks": rescue_tasks,
    }
    rescue_contract_sha256 = _canonical_sha256(rescue_contract_payload)
    _write_jsonl(rescue_tasks_path, rescue_tasks)
    _write_jsonl(audit_path, audits)
    if benchmark_gate == "passed":
        parent_runs_path.write_text(
            "".join(
                f"{solver}\t{relative}\n"
                for solver, relative in sorted(benchmark_run_rows)
            ),
            encoding="utf-8",
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": contract_sha256,
        "probe_completed": True,
        "gate_status": gate,
        "label_rescue": {
            "contract_sha256": rescue_contract_sha256,
            "tasks_planned": len(rescue_tasks),
            "solver_profiles": {
                "gurobi": "default",
                "scip": "feasibility",
            },
            "time_limit_seconds_per_task": 14400.0,
            "benchmark_results_immutable": True,
        },
        "gates": {
            "benchmark_observation_gate": benchmark_gate,
            "solver_arm_training_label_gate": training_label_gate,
            "common_evaluation_reference_gate": evaluation_reference_gate,
        },
        "summary": {
            "tasks_planned": len(tasks),
            "benchmark_tasks_passed": benchmark_passed_count,
            "benchmark_tasks_failed": len(tasks) - benchmark_passed_count,
            "labels_eligible": sum(
                item.get("label_eligible") is True for item in audits
            ),
            "labels_ineligible": sum(
                item.get("benchmark_status") == "passed"
                and item.get("label_eligible") is not True
                for item in audits
            ),
            "paired_parent_population": paired_benchmark_population,
            "training_solver_parent_pairs": len(training_records),
            "training_labels_eligible": training_labels_eligible,
            "evaluation_parents": len(evaluation_parent_ids),
            "evaluation_references_covered": evaluation_references_covered,
            "parent_runs_written": (
                len(benchmark_run_rows) if benchmark_gate == "passed" else 0
            ),
        },
        "eligibility": {
            "benchmark_observations_eligible": benchmark_gate == "passed",
            "solver_arm_training_labels_complete": training_label_gate == "passed",
            "common_evaluation_references_complete": (
                evaluation_reference_gate == "passed"
            ),
            "vertical_slice_composition_ready": composition_ready,
            "dataset_eligible": False,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "outputs": {
            "per_parent_solve_audit": AUDIT_NAME,
            "parent_runs": (
                PARENT_RUNS_NAME if benchmark_gate == "passed" else None
            ),
            "label_rescue_tasks": LABEL_RESCUE_TASKS_NAME,
            "label_rescue_tasks_sha256": sha256_file(rescue_tasks_path),
            "parent_run_path_semantics": "relative_to_runtime_parent_run_root",
        },
        "decision": {
            "reason_code": (
                "all_vertical_slice_labels_available"
                if composition_ready
                else "benchmark_observations_valid_label_rescue_required"
                if benchmark_gate == "passed"
                else "one_or_more_benchmark_observations_invalid"
            ),
            "next_gate": (
                "train_parent_local_branching_and_derived_labels"
                if composition_ready
                else "prepare_deterministic_label_rescue_manifest"
                if benchmark_gate == "passed"
                else "repair_invalid_benchmark_observations"
            ),
        },
    }
    _write_json(report_path, report)
    return report

