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
    """Fail closed unless all twelve paired parent solves are admissible."""
    plan_root = Path(plan_dir).resolve()
    runs = Path(run_root).resolve()
    report_path = plan_root / AUDIT_REPORT_NAME
    audit_path = plan_root / AUDIT_NAME
    parent_runs_path = plan_root / PARENT_RUNS_NAME
    if not overwrite and any(path.exists() for path in (report_path, audit_path, parent_runs_path)):
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
    run_rows: list[tuple[str, str]] = []
    maximum_gap = float(plan["maximum_admissible_relative_gap"])
    for task in tasks:
        run_relative = str(task["run_dir_relative_path"])
        run_dir = runs / run_relative
        parent_report_path = run_dir / PARENT_SOLVE_REPORT_NAME
        if not parent_report_path.is_file():
            audits.append(
                {
                    "task_index": task["task_index"],
                    "solver": task["solver"],
                    "source_instance_id": task["source_instance_id"],
                    "role": task["role"],
                    "difficulty": task["difficulty"],
                    "run_dir_relative_path": run_relative,
                    "status": "failed",
                    "reason_code": "parent_solve_report_missing",
                }
            )
            continue
        parent_report = _read_json(parent_report_path)
        parent = parent_report.get("parent", {})
        solve = parent_report.get("solve", {})
        eligibility = parent_report.get("eligibility", {})
        role = str(task["role"])
        raw_gap = solve.get("mip_gap_relative")
        raw_time = solve.get("execution_time_seconds")
        gap_admissible = (
            isinstance(raw_gap, (int, float))
            and math.isfinite(float(raw_gap))
            and 0.0 <= float(raw_gap) <= maximum_gap + 1e-12
        )
        execution_time_valid = (
            isinstance(raw_time, (int, float))
            and math.isfinite(float(raw_time))
            and float(raw_time) >= 0.0
        )
        checks = {
            "parent_identity_match": parent.get("source_instance_id") == task["source_instance_id"],
            "parent_sha256_match": parent.get("sha256") == task["parent_mip_sha256"],
            "parent_metadata_match": all(
                parent.get(field) == task[field]
                for field in ("category", "difficulty", "fold", "role")
            ),
            "objective_minimize": solve.get("objective_sense") == "minimize",
            "mip_gap_admissible": gap_admissible,
            "execution_time_valid": execution_time_valid,
            "label_eligible": eligibility.get("label_eligible") is True,
            "augmentation_policy_match": eligibility.get("augmentation_source_eligible") == (role == "train"),
            "gate_status_expected": parent_report.get("gate_status") == ("passed" if role == "train" else "inconclusive"),
        }
        artifacts = parent_report.get("artifacts", {})
        artifact_checks: dict[str, bool] = {}
        for artifact_name in ("solution", "incumbents", "variable_order"):
            descriptor = artifacts.get(artifact_name, {})
            artifact = run_dir / str(descriptor.get("file_name", ""))
            artifact_checks[artifact_name] = (
                artifact.is_file() and sha256_file(artifact) == descriptor.get("sha256")
            )
        passed = all(checks.values()) and all(artifact_checks.values())
        audits.append(
            {
                "task_index": task["task_index"],
                "solver": task["solver"],
                "source_instance_id": task["source_instance_id"],
                "role": role,
                "difficulty": task["difficulty"],
                "run_dir_relative_path": run_relative,
                "mip_gap_relative": solve.get("mip_gap_relative"),
                "execution_time_seconds": solve.get("execution_time_seconds"),
                "checks": checks,
                "artifact_checks": artifact_checks,
                "status": "passed" if passed else "failed",
            }
        )
        if passed:
            run_rows.append((str(task["solver"]), run_relative))

    passed_count = sum(item["status"] == "passed" for item in audits)
    parent_sets = defaultdict(set)
    for item in audits:
        if item["status"] == "passed":
            parent_sets[item["solver"]].add(item["source_instance_id"])
    paired = (
        len(parent_sets) == 2
        and parent_sets["gurobi"] == parent_sets["scip"]
        and len(parent_sets["gurobi"]) == 6
    )
    gate = "passed" if passed_count == 12 and paired else "failed"
    _write_jsonl(audit_path, audits)
    if gate == "passed":
        parent_runs_path.write_text(
            "".join(f"{solver}\t{relative}\n" for solver, relative in sorted(run_rows)),
            encoding="utf-8",
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": contract_sha256,
        "probe_completed": True,
        "gate_status": gate,
        "summary": {
            "tasks_planned": len(tasks),
            "tasks_passed": passed_count,
            "tasks_failed": len(tasks) - passed_count,
            "paired_parent_population": paired,
            "parent_runs_written": len(run_rows) if gate == "passed" else 0,
        },
        "eligibility": {
            "original_parent_labels_eligible": gate == "passed",
            "vertical_slice_composition_ready": gate == "passed",
            "dataset_eligible": False,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "outputs": {
            "per_parent_solve_audit": AUDIT_NAME,
            "parent_runs": PARENT_RUNS_NAME if gate == "passed" else None,
            "parent_run_path_semantics": "relative_to_runtime_parent_run_root",
        },
        "decision": {
            "reason_code": (
                "all_paired_parent_solves_admissible"
                if gate == "passed"
                else "one_or_more_parent_solves_not_admissible"
            ),
            "next_gate": (
                "train_parent_local_branching_and_derived_labels"
                if gate == "passed"
                else "repair_or_repeat_failed_parent_solves"
            ),
        },
    }
    _write_json(report_path, report)
    return report
