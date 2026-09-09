from __future__ import annotations

import gzip
import io
import json
from pathlib import Path

import pytest

from cfl_gnn.experiments import mvp_neural_diving as benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    PROJECT_ROOT
    / "configs"
    / "experiments"
    / "mvp_neural_diving_equal_budget_v1.json"
)


def _write_hint(path: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as text:
                for row in rows:
                    text.write(json.dumps(row, sort_keys=True) + "\n")
    return {
        "parent_instance_id": "CFL_easy_instance_0",
        "relative_path": path.relative_to(path.parents[3]).as_posix(),
        "sha256": benchmark.sha256_file(path),
        "semantic_sha256": benchmark.canonical_sha256(rows),
        "hints": len(rows),
        "contains_test_labels": False,
    }


def _fixture(tmp_path: Path):
    evaluation_dir = tmp_path / "evaluation"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    parent_relative = Path("CFL_easy_instance/LP/CFL_easy_instance_0.lp.gz")
    parent = source_dir / parent_relative
    parent.parent.mkdir(parents=True)
    parent.write_bytes(b"original held-out parent")
    evaluation_plan = {
        "contract_sha256": "a" * 64,
        "test_records": [
            {
                "parent_instance_id": "CFL_easy_instance_0",
                "difficulty": "easy",
                "fold": 0,
                "parent_mip_relative_path": parent_relative.as_posix(),
                "parent_mip_sha256": benchmark.sha256_file(parent),
            }
        ],
    }
    evaluation_dir.mkdir(parents=True)
    benchmark.write_json(
        evaluation_dir / benchmark.EVALUATION_PLAN_NAME, evaluation_plan
    )
    rows = [
        {
            "variable_name": f"x{index:02d}",
            "predicted_value": index % 2,
            "probability": 0.95 if index % 2 else 0.05,
            "confidence": 0.9,
            "priority": 90 - index,
        }
        for index in range(10)
    ]
    arms = {}
    for arm_id in benchmark.EXPECTED_ARMS:
        hint_path = evaluation_dir / "arms" / arm_id / "hints" / "test.jsonl.gz"
        arms[arm_id] = {
            "arm_id": arm_id,
            "solver": arm_id.split("_", 1)[0],
            "hint_artifacts": [_write_hint(hint_path, rows)],
        }
    evaluation_report = {
        "gate_status": "passed",
        "evaluation_contract_sha256": evaluation_plan["contract_sha256"],
        "arm_selection": {
            "performed": False,
            "forwarded_arms": list(benchmark.EXPECTED_ARMS),
        },
        "common_controls": {"same_test": True},
        "eligibility": {
            "solver_neutral_hints_eligible_for_engineering_smoke": True
        },
        "arms": arms,
    }
    benchmark.write_json(
        evaluation_dir / benchmark.EVALUATION_REPORT_NAME, evaluation_report
    )
    return evaluation_dir, source_dir, output_dir


def _plan(tmp_path: Path):
    evaluation_dir, source_dir, output_dir = _fixture(tmp_path)
    plan = benchmark.build_plan(
        evaluation_dir,
        source_dir,
        time_limit_seconds=3600,
        config_path=CONFIG,
    )
    plan_path = output_dir / benchmark.PLAN_NAME
    benchmark.write_json(plan_path, plan)
    return plan, plan_path, evaluation_dir, source_dir, output_dir


def _fake_adapter(model_path, task, fixings):
    del model_path
    return {
        "model_build_wall_time_seconds": 0.0,
        "model_optimize_wall_time_seconds": 0.0,
        "post_optimize_extraction_wall_time_seconds": 0.0,
        "outcome": {
            "solver_versions": {task["target_solver"]: "test"},
            "original_objective_sense": "MAXIMIZE",
            "effective_objective_sense": "MINIMIZE",
            "solve_status": "timelimit",
            "right_censored": True,
            "solution_count": 1,
            "best_objective": 2.0,
            "best_bound": 1.8,
            "terminal_mip_gap_relative": 0.1,
            "terminal_mip_gap_percent": 10.0,
            "solver_reported_optimize_time_seconds": 0.0,
            "nodes": 5,
            "model_signature": {"variables": 10, "constraints": 2},
            "fixed_values_seen": len(fixings),
        },
    }


def test_config_precommits_equal_budget_and_four_time_regions() -> None:
    config = benchmark.load_json(CONFIG)
    assert config["time_budget"]["minimum_seconds"] == 3600
    assert config["time_budget"]["maximum_seconds"] == 14400
    assert config["neural_diving_operator"]["fixing_fraction"] == 0.1
    assert set(config["time_regions"]) == {
        "total_wall_time_seconds",
        "data_read_wall_time_seconds",
        "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds",
    }


def test_plan_crosses_four_arms_with_two_solvers_and_controls(tmp_path: Path) -> None:
    plan, _, _, _, _ = _plan(tmp_path)
    assert plan["contract_valid"] is True
    assert plan["task_count"] == 10
    assert {task["target_solver"] for task in plan["tasks"]} == {"gurobi", "scip"}
    assert sum(task["run_kind"] == "guided" for task in plan["tasks"]) == 8
    assert sum(task["run_kind"] == "control" for task in plan["tasks"]) == 2
    assert str(tmp_path) not in json.dumps(plan)


@pytest.mark.parametrize("time_limit", [3599, 14401])
def test_plan_rejects_time_limit_outside_precommitted_range(
    tmp_path: Path, time_limit: int
) -> None:
    evaluation_dir, source_dir, _ = _fixture(tmp_path)
    with pytest.raises(benchmark.MvpNeuralDivingError, match="between"):
        benchmark.build_plan(
            evaluation_dir,
            source_dir,
            time_limit_seconds=time_limit,
            config_path=CONFIG,
        )


def test_fixing_selection_is_deterministic_and_uses_exact_fraction() -> None:
    rows = [
        {
            "variable_name": f"x{index}",
            "predicted_value": index % 2,
            "confidence": index / 100,
            "priority": index,
        }
        for index in range(100)
    ]
    first = benchmark.select_fixings(rows, 0.1)
    second = benchmark.select_fixings(list(reversed(rows)), 0.1)
    assert first == second
    assert len(first) == 10
    assert first[0]["variable_name"] == "x99"


def test_task_and_aggregate_audit_preserve_symmetric_fixings(tmp_path: Path) -> None:
    plan, plan_path, evaluation_dir, source_dir, output_dir = _plan(tmp_path)
    adapters = {"gurobi": _fake_adapter, "scip": _fake_adapter}
    for task_index in range(plan["task_count"]):
        result = benchmark.run_task(
            plan_path,
            evaluation_dir,
            source_dir,
            output_dir,
            task_index=task_index,
            adapters=adapters,
        )
        assert result["neural_diving"]["test_labels_consumed"] is False
        expected = 0 if result["run_kind"] == "control" else 1
        assert result["neural_diving"]["fixed_variable_count"] == expected
    report = benchmark.audit_run(plan_path, output_dir)
    assert report["gate_status"] == "passed"
    assert all(report["common_controls"].values())
    assert report["execution"] == {
        "planned_runs": 10,
        "completed_runs": 10,
        "held_out_parents": 1,
        "guided_runs": 8,
        "control_runs": 2,
    }
    assert sum(1 for _ in (output_dir / benchmark.COMPARISONS_NAME).open()) == 16
    assert sum(1 for _ in (output_dir / benchmark.RUN_METRICS_NAME).open()) == 11
    assert str(tmp_path) not in (output_dir / benchmark.REPORT_NAME).read_text()


def test_audit_rejects_missing_fresh_process_result(tmp_path: Path) -> None:
    _, plan_path, _, _, output_dir = _plan(tmp_path)
    with pytest.raises(benchmark.MvpNeuralDivingError, match="missing"):
        benchmark.audit_run(plan_path, output_dir)


def test_dasci_launchers_are_lf_only_and_bound_maximum_runtime() -> None:
    task_launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_mvp_neural_diving_task_array.sbs"
    )
    audit_launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_mvp_neural_diving_audit.sbs"
    )
    for launcher in (task_launcher, audit_launcher):
        assert b"\r" not in launcher.read_bytes()
        assert "SLURM_SUBMIT_DIR" in launcher.read_text()
    task_text = task_launcher.read_text()
    assert "--time=04:30:00" in task_text
    assert "SLURM_ARRAY_TASK_ID" in task_text
    assert "run-task" in task_text
