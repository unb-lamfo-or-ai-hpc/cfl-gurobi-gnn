"""Dependency-light tests for the precommitted MVP label rescue."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import cfl_gnn.pipelines.mvp_label_rescue as rescue_module
from cfl_gnn.experiments.mvp_vertical_slice import (
    LABEL_RESCUE_TASKS_NAME,
    PLAN_NAME,
    TASKS_NAME,
    audit_vertical_slice_parent_runs,
    write_vertical_slice_plan,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.mvp_label_rescue import (
    AUDIT_REPORT_NAME,
    EXECUTION_PLAN_NAME,
    EXECUTION_REPORT_NAME,
    MvpLabelRescueError,
    PER_TASK_AUDIT_NAME,
    audit_rescue_runs,
    build_rescue_task_plan,
    execute_rescue_task,
)
from cfl_gnn.pipelines.scip_parent_solutions import (
    PLAN_NAME as PARENT_PLAN_NAME,
    REPORT_NAME as PARENT_REPORT_NAME,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLICE_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_vertical_slice_v1.json"
EXPERIMENT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
PARENT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    ).hexdigest()


def _write_parent_run(
    run_dir: Path,
    task: dict[str, object],
    *,
    experiment_contract_sha256: str,
    mip_gap_relative: float,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, str]] = {}
    for key, name in (
        ("solution", "parent_solution.json.gz"),
        ("incumbents", "incumbents.parquet"),
        ("variable_order", "incumbent_variable_order.json.gz"),
    ):
        path = run_dir / name
        artifact_content = f"{task['solver']}:{task['source_instance_id']}:{key}"
        path.write_bytes(artifact_content.encode())
        artifacts[key] = {"file_name": name, "sha256": sha256_file(path)}
    solver = str(task["solver"])
    role = str(task["role"])
    payload = {
        "schema_version": 1,
        "dataset_variant": f"{solver}_original_parent_solution",
        "experiment_contract_sha256": experiment_contract_sha256,
        "parent": {
            "source_instance_id": task["source_instance_id"],
            "category": task["category"],
            "difficulty": task["difficulty"],
            "fold": task["fold"],
            "role": role,
            "file_name": f"{task['source_instance_id']}.lp.gz",
            "sha256": task["parent_mip_sha256"],
        },
        "solver_contract": {
            "solver": solver,
            "interface": "gurobipy" if solver == "gurobi" else "pyscipopt",
            "solver_profile": "default",
            "force_minimize": True,
            "time_limit_seconds": 3600.0,
            "node_limit": 1_000_000,
            "threads": 1,
            "seed": 42,
            "fresh_process": True,
            "warm_start_supplied": False,
        },
        "gap_policy": {"maximum_admissible_relative_gap": 0.10},
        "eligibility": {
            "label_eligible": False,
            "augmentation_source_eligible": False,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
    }
    contract = _canonical_sha256(payload)
    (run_dir / PARENT_PLAN_NAME).write_text(
        json.dumps({**payload, "contract_sha256": contract, "outputs": {}}) + "\n",
        encoding="utf-8",
    )
    label_eligible = mip_gap_relative <= 0.10
    report = {
        "contract_sha256": contract,
        "gate_status": (
            "passed" if role == "train" and label_eligible else "inconclusive"
        ),
        "parent": payload["parent"],
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
    (run_dir / PARENT_REPORT_NAME).write_text(
        json.dumps(report) + "\n", encoding="utf-8"
    )


def _corrected_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw = tmp_path / "raw"
    config = json.loads(SLICE_CONFIG.read_text(encoding="utf-8"))
    for parent in config["parents"]:
        instance_id = parent["source_instance_id"]
        category = instance_id.rsplit("_", 1)[0]
        path = raw / category / "LP" / f"{instance_id}.lp.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original:{instance_id}".encode())
    plan_dir = tmp_path / "vertical"
    write_vertical_slice_plan(
        base_source_dir=raw,
        output_dir=plan_dir,
        slice_config_path=SLICE_CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
        experiment_config_path=EXPERIMENT_CONFIG,
    )
    plan = json.loads((plan_dir / PLAN_NAME).read_text(encoding="utf-8"))
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
    benchmark_root = tmp_path / "benchmark"
    for task in tasks:
        key = (str(task["solver"]), str(task["source_instance_id"]))
        _write_parent_run(
            benchmark_root / str(task["run_dir_relative_path"]),
            task,
            experiment_contract_sha256=plan["experiment_contract_sha256"],
            mip_gap_relative=0.20 if key in ineligible else 0.05,
        )
    report = audit_vertical_slice_parent_runs(
        plan_dir=plan_dir, run_root=benchmark_root
    )
    assert report["gates"]["benchmark_observation_gate"] == "passed"
    assert report["label_rescue"]["tasks_planned"] == 3
    return plan_dir, benchmark_root, raw


def test_rescue_task_plan_is_precommitted_and_path_free(tmp_path: Path) -> None:
    plan_dir, benchmark_root, raw = _corrected_fixture(tmp_path)
    rescue_root = tmp_path / "rescue"
    gurobi_plan, gurobi_execution = build_rescue_task_plan(
        vertical_slice_dir=plan_dir,
        benchmark_run_root=benchmark_root,
        base_source_dir=raw,
        rescue_run_root=rescue_root,
        task_index=0,
    )
    scip_plan, scip_execution = build_rescue_task_plan(
        vertical_slice_dir=plan_dir,
        benchmark_run_root=benchmark_root,
        base_source_dir=raw,
        rescue_run_root=rescue_root,
        task_index=1,
    )
    assert (gurobi_plan.solver, gurobi_plan.solver_profile) == ("gurobi", "default")
    assert (scip_plan.solver, scip_plan.solver_profile) == ("scip", "feasibility")
    assert gurobi_plan.time_limit == scip_plan.time_limit == 14400.0
    assert gurobi_plan.node_limit == scip_plan.node_limit == 4_000_000
    serialized = json.dumps([gurobi_execution, scip_execution])
    assert str(tmp_path) not in serialized
    assert gurobi_execution["task"]["benchmark_artifacts_immutable"] is True


def test_rescue_dry_run_writes_only_contract_plans(tmp_path: Path) -> None:
    plan_dir, benchmark_root, raw = _corrected_fixture(tmp_path)
    rescue_root = tmp_path / "rescue"
    result = execute_rescue_task(
        vertical_slice_dir=plan_dir,
        benchmark_run_root=benchmark_root,
        base_source_dir=raw,
        rescue_run_root=rescue_root,
        task_index=0,
        dry_run=True,
    )
    run_dir = rescue_root / result["task"]["rescue_run_dir_relative_path"]
    assert (run_dir / EXECUTION_PLAN_NAME).is_file()
    assert (run_dir / PARENT_PLAN_NAME).is_file()
    assert not (run_dir / EXECUTION_REPORT_NAME).exists()


def test_rescue_manifest_tampering_is_rejected(tmp_path: Path) -> None:
    plan_dir, benchmark_root, raw = _corrected_fixture(tmp_path)
    manifest = plan_dir / LABEL_RESCUE_TASKS_NAME
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(MvpLabelRescueError, match="manifest hash mismatch"):
        build_rescue_task_plan(
            vertical_slice_dir=plan_dir,
            benchmark_run_root=benchmark_root,
            base_source_dir=raw,
            rescue_run_root=tmp_path / "rescue",
            task_index=0,
        )


def test_rescue_execution_preserves_benchmark_and_accepts_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir, benchmark_root, raw = _corrected_fixture(tmp_path)
    rescue_root = tmp_path / "rescue"
    benchmark_before = {
        path.relative_to(benchmark_root).as_posix(): sha256_file(path)
        for path in benchmark_root.rglob("*")
        if path.is_file()
    }

    def fake_parent_solve(plan: object) -> dict[str, object]:
        output = plan.output_dir
        artifacts: dict[str, dict[str, str]] = {}
        for key, name in (
            ("solution", "parent_solution.json.gz"),
            ("incumbents", "incumbents.parquet"),
            ("variable_order", "incumbent_variable_order.json.gz"),
        ):
            path = output / name
            path.write_bytes(f"rescued:{key}".encode())
            artifacts[key] = {"file_name": name, "sha256": sha256_file(path)}
        return {
            "contract_sha256": plan.contract_sha256,
            "solve": {
                "objective_sense": "minimize",
                "mip_gap_relative": 0.075,
                "execution_time_seconds": 8000.0,
            },
            "checks": {"fresh_process": True, "no_warm_start": True},
            "eligibility": {"label_eligible": True},
            "artifacts": artifacts,
        }

    monkeypatch.setattr(rescue_module, "run_parent_solve", fake_parent_solve)
    report = execute_rescue_task(
        vertical_slice_dir=plan_dir,
        benchmark_run_root=benchmark_root,
        base_source_dir=raw,
        rescue_run_root=rescue_root,
        task_index=0,
    )
    benchmark_after = {
        path.relative_to(benchmark_root).as_posix(): sha256_file(path)
        for path in benchmark_root.rglob("*")
        if path.is_file()
    }
    assert report["gate_status"] == "passed"
    assert report["checks"]["benchmark_artifacts_unchanged"] is True
    assert report["solve"]["mip_gap_relative"] == 0.075
    assert benchmark_before == benchmark_after


def test_aggregate_audit_requires_all_three_rescue_reports(tmp_path: Path) -> None:
    plan_dir, _, _ = _corrected_fixture(tmp_path)
    rescue_root = tmp_path / "rescue"
    tasks = [
        json.loads(line)
        for line in (plan_dir / LABEL_RESCUE_TASKS_NAME)
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    benchmark_report = json.loads(
        (plan_dir / "mvp_vertical_slice_parent_audit_report.json").read_text(
            encoding="utf-8"
        )
    )
    rescue_contract = benchmark_report["label_rescue"]["contract_sha256"]
    for task in tasks:
        run_dir = rescue_root / task["rescue_run_dir_relative_path"]
        run_dir.mkdir(parents=True, exist_ok=True)
        descriptors = {}
        for key, name in (
            ("execution_plan", EXECUTION_PLAN_NAME),
            ("parent_solve_plan", PARENT_PLAN_NAME),
            ("parent_solve_report", PARENT_REPORT_NAME),
            ("solution", "parent_solution.json.gz"),
            ("incumbents", "incumbents.parquet"),
            ("variable_order", "incumbent_variable_order.json.gz"),
        ):
            path = run_dir / name
            path.write_bytes(f"rescue:{task['rescue_task_index']}:{key}".encode())
            descriptors[key] = {"file_name": name, "sha256": sha256_file(path)}
        report = {
            "rescue_contract_sha256": rescue_contract,
            "gate_status": "passed",
            "task": task,
            "solve": {"mip_gap_relative": 0.05, "execution_time_seconds": 5000.0},
            "checks": {
                "benchmark_artifacts_unchanged": True,
                "fresh_process": True,
                "no_warm_start": True,
            },
            "artifacts": descriptors,
            "eligibility": {"label_rescue_eligible": True},
        }
        (run_dir / EXECUTION_REPORT_NAME).write_text(
            json.dumps(report) + "\n", encoding="utf-8"
        )
    report = audit_rescue_runs(
        vertical_slice_dir=plan_dir, rescue_run_root=rescue_root
    )
    assert report["gate_status"] == "passed"
    assert report["summary"] == {
        "tasks_planned": 3,
        "tasks_passed": 3,
        "tasks_failed": 0,
    }
    assert (plan_dir / PER_TASK_AUDIT_NAME).is_file()
    assert (plan_dir / AUDIT_REPORT_NAME).is_file()

