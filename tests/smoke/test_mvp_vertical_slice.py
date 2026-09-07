"""Dependency-light tests for the paired six-parent vertical slice."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.experiments.mvp_vertical_slice import (
    AUDIT_REPORT_NAME,
    PARENT_RUNS_NAME,
    PARENT_SOLVE_REPORT_NAME,
    PLAN_NAME,
    PREFLIGHT_REPORT_NAME,
    TASKS_NAME,
    MvpVerticalSliceError,
    audit_vertical_slice_parent_runs,
    write_vertical_slice_plan,
)
from cfl_gnn.graph.instance_provenance import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLICE_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_vertical_slice_v1.json"
EXPERIMENT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
PARENT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def _raw_population(root: Path) -> None:
    config = json.loads(SLICE_CONFIG.read_text(encoding="utf-8"))
    for parent in config["parents"]:
        instance_id = parent["source_instance_id"]
        category = instance_id.rsplit("_", 1)[0]
        path = root / category / "LP" / f"{instance_id}.lp.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original:{instance_id}".encode("utf-8"))


def _plan(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    output = tmp_path / "plan"
    _raw_population(raw)
    report = write_vertical_slice_plan(
        base_source_dir=raw,
        output_dir=output,
        slice_config_path=SLICE_CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
        experiment_config_path=EXPERIMENT_CONFIG,
    )
    assert report["gate_status"] == "passed"
    return output


def test_vertical_slice_preflight_is_balanced_and_sanitized(tmp_path: Path) -> None:
    output = _plan(tmp_path)
    plan = json.loads((output / PLAN_NAME).read_text(encoding="utf-8"))
    report = json.loads((output / PREFLIGHT_REPORT_NAME).read_text(encoding="utf-8"))
    tasks = [
        json.loads(line)
        for line in (output / TASKS_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(tasks) == 12
    assert {task["solver"] for task in tasks} == {"gurobi", "scip"}
    assert report["summary"]["parents_by_role"] == {
        "test": 2,
        "train": 2,
        "validation": 2,
    }
    assert report["summary"]["parents_by_difficulty"] == {"easy": 3, "medium": 3}
    assert sum(task["augmentation_required"] for task in tasks) == 4
    assert all(not Path(task["parent_mip_relative_path"]).is_absolute() for task in tasks)
    assert str(tmp_path) not in json.dumps({"plan": plan, "report": report, "tasks": tasks})


def test_vertical_slice_rejects_missing_parent_mip(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    with pytest.raises(MvpVerticalSliceError, match="missing original parent MIP"):
        write_vertical_slice_plan(
            base_source_dir=raw,
            output_dir=tmp_path / "plan",
            slice_config_path=SLICE_CONFIG,
            parent_manifest_path=PARENT_MANIFEST,
            experiment_config_path=EXPERIMENT_CONFIG,
        )


def _write_parent_run(
    run_dir: Path, task: dict[str, object], *, mip_gap_relative: float = 0.05
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, object]] = {}
    for name, file_name in (
        ("solution", "parent_solution.json.gz"),
        ("incumbents", "incumbents.parquet"),
        ("variable_order", "incumbent_variable_order.json.gz"),
    ):
        path = run_dir / file_name
        path.write_bytes(f"{task['solver']}:{task['source_instance_id']}:{name}".encode())
        artifacts[name] = {"file_name": file_name, "sha256": sha256_file(path)}
    role = str(task["role"])
    label_eligible = mip_gap_relative <= 0.10
    report = {
        "gate_status": (
            "passed" if role == "train" and label_eligible else "inconclusive"
        ),
        "parent": {
            "source_instance_id": task["source_instance_id"],
            "category": task["category"],
            "difficulty": task["difficulty"],
            "fold": task["fold"],
            "role": role,
            "sha256": task["parent_mip_sha256"],
        },
        "solve": {
            "objective_sense": "minimize",
            "mip_gap_relative": mip_gap_relative,
            "execution_time_seconds": 3600.0,
            "solution_objective": 10.0,
        },
        "checks": {"synthetic_instrumentation": True},
        "eligibility": {
            "label_eligible": label_eligible,
            "augmentation_source_eligible": role == "train" and label_eligible,
        },
        "artifacts": artifacts,
    }
    (run_dir / PARENT_SOLVE_REPORT_NAME).write_text(
        json.dumps(report, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_parent_run_audit_requires_all_twelve_paired_results(tmp_path: Path) -> None:
    plan_dir = _plan(tmp_path)
    tasks = [
        json.loads(line)
        for line in (plan_dir / TASKS_NAME).read_text(encoding="utf-8").splitlines()
    ]
    run_root = tmp_path / "runs"
    for task in tasks:
        _write_parent_run(run_root / task["run_dir_relative_path"], task)
    report = audit_vertical_slice_parent_runs(plan_dir=plan_dir, run_root=run_root)
    assert report["gate_status"] == "passed"
    assert report["gates"] == {
        "benchmark_observation_gate": "passed",
        "solver_arm_training_label_gate": "passed",
        "common_evaluation_reference_gate": "passed",
    }
    assert report["summary"]["benchmark_tasks_passed"] == 12
    assert report["summary"]["paired_parent_population"] is True
    assert report["summary"]["parent_runs_written"] == 12
    rows = (plan_dir / PARENT_RUNS_NAME).read_text(encoding="utf-8").splitlines()
    assert len(rows) == 12
    assert all(not Path(row.split("\t", 1)[1]).is_absolute() for row in rows)
    serialized = (plan_dir / AUDIT_REPORT_NAME).read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized


def test_parent_audit_preserves_benchmark_and_separates_label_gates(
    tmp_path: Path,
) -> None:
    plan_dir = _plan(tmp_path)
    tasks = [
        json.loads(line)
        for line in (plan_dir / TASKS_NAME).read_text(encoding="utf-8").splitlines()
    ]
    ineligible = {
        ("scip", "CFL_easy_instance_1"),
        ("scip", "CFL_medium_instance_0"),
        ("gurobi", "CFL_medium_instance_2"),
        ("scip", "CFL_medium_instance_2"),
        ("gurobi", "CFL_medium_instance_5"),
        ("scip", "CFL_medium_instance_5"),
    }
    run_root = tmp_path / "runs"
    for task in tasks:
        key = (str(task["solver"]), str(task["source_instance_id"]))
        _write_parent_run(
            run_root / task["run_dir_relative_path"],
            task,
            mip_gap_relative=0.20 if key in ineligible else 0.05,
        )

    report = audit_vertical_slice_parent_runs(plan_dir=plan_dir, run_root=run_root)

    assert report["gate_status"] == "inconclusive"
    assert report["gates"] == {
        "benchmark_observation_gate": "passed",
        "solver_arm_training_label_gate": "incomplete",
        "common_evaluation_reference_gate": "incomplete",
    }
    assert report["summary"]["benchmark_tasks_passed"] == 12
    assert report["summary"]["labels_eligible"] == 6
    assert report["summary"]["training_labels_eligible"] == 2
    assert report["summary"]["evaluation_references_covered"] == 3
    assert report["summary"]["parent_runs_written"] == 12

