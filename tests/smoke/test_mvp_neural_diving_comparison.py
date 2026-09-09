from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from cfl_gnn.analysis import mvp_neural_diving_comparison as comparison
from cfl_gnn.experiments import mvp_neural_diving as benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _source_benchmark(tmp_path: Path) -> Path:
    root = tmp_path / "benchmark"
    root.mkdir()
    tasks = []
    records = []
    index = 0
    for solver in benchmark.TARGET_SOLVERS:
        for arm_id in (None, *benchmark.EXPECTED_ARMS):
            run_kind = "control" if arm_id is None else "guided"
            task_contract = benchmark.canonical_sha256(
                {"index": index, "solver": solver, "arm": arm_id}
            )
            relative = Path("tasks") / f"task_{index:03d}.json"
            tasks.append(
                {
                    "task_index": index,
                    "run_id": f"run_{index:03d}",
                    "run_kind": run_kind,
                    "gnn_arm_id": arm_id,
                    "target_solver": solver,
                    "parent_instance_id": "CFL_easy_instance_0",
                    "task_contract_sha256": task_contract,
                    "output_relative_path": relative.as_posix(),
                }
            )
            arm_position = (
                0 if arm_id is None else benchmark.EXPECTED_ARMS.index(arm_id) + 1
            )
            gap = 0.10 - 0.01 * arm_position + (0.01 if solver == "scip" else 0)
            optimize = 6.0 + arm_position + (1.0 if solver == "scip" else 0)
            records.append(
                {
                    "schema_version": 1,
                    "task_contract_sha256": task_contract,
                    "task_index": index,
                    "run_id": f"run_{index:03d}",
                    "run_kind": run_kind,
                    "gnn_arm_id": arm_id,
                    "target_solver": solver,
                    "parent_instance_id": "CFL_easy_instance_0",
                    "gate_status": "passed",
                    "time_budget": {
                        "time_limit_seconds": 3600,
                        "threads": 1,
                        "seed": 42,
                    },
                    "time_regions": {
                        "total_wall_time_seconds": optimize + 4.0,
                        "data_read_wall_time_seconds": 1.0,
                        "model_build_wall_time_seconds": 2.0,
                        "model_optimize_wall_time_seconds": optimize,
                        "post_optimize_extraction_wall_time_seconds": 0.5,
                        "unattributed_overhead_wall_time_seconds": 0.5,
                    },
                    "neural_diving": {
                        "fixed_variable_count": 0 if arm_id is None else 10,
                        "selected_fixings_sha256": benchmark.canonical_sha256(
                            [] if arm_id is None else [arm_id]
                        ),
                        "test_labels_consumed": False,
                    },
                    "hardware": {"sha256": "f" * 64},
                    "outcome": {
                        "solve_status": "timelimit",
                        "right_censored": solver == "scip",
                        "solution_count": 1,
                        "best_objective": 2.0,
                        "best_bound": 1.8,
                        "nodes": 5,
                        "effective_objective_sense": "MINIMIZE",
                        "terminal_mip_gap_relative": gap,
                        "terminal_mip_gap_percent": gap * 100.0,
                        "solver_reported_optimize_time_seconds": optimize,
                    },
                    "eligibility": {"primary_outcomes_complete": True},
                }
            )
            index += 1
    core = {
        "schema_version": 1,
        "tasks": tasks,
        "held_out_parents": [{"parent_instance_id": "CFL_easy_instance_0"}],
        "time_limit_seconds": 3600,
        "experiment_config": {
            "time_budget": {"minimum_seconds": 3600, "maximum_seconds": 14400},
            "time_regions": {
                "total_wall_time_seconds": "external_wall_clock",
                "data_read_wall_time_seconds": "external_wall_clock",
                "model_build_wall_time_seconds": "external_wall_clock",
                "model_optimize_wall_time_seconds": "external_wall_clock",
            },
        },
    }
    plan = dict(core)
    plan["contract_sha256"] = benchmark.canonical_sha256(core)
    plan["contract_valid"] = True
    plan["task_count"] = len(tasks)
    plan["next_gate"] = "task_execution"
    benchmark.write_json(root / benchmark.PLAN_NAME, plan)
    for record, task in zip(records, tasks):
        record["benchmark_contract_sha256"] = plan["contract_sha256"]
        path = root / task["output_relative_path"]
        benchmark.write_json(path, record)
    report = benchmark.audit_run(root / benchmark.PLAN_NAME, root)
    assert report["gate_status"] == "passed"
    return root


def test_config_precommits_descriptive_no_selection_policy() -> None:
    config = benchmark.load_json(comparison.DEFAULT_CONFIG)
    assert config["selection_policy"] == "no_arm_ranking_or_selection"
    assert config["gap_sensitivity_thresholds_relative"] == [0.01, 0.05, 0.1]
    assert set(config["primary_outcomes"]) == {
        "terminal_mip_gap_relative",
        "model_optimize_wall_time_seconds",
    }


def test_review_writes_contract_checked_descriptive_outputs(tmp_path: Path) -> None:
    source = _source_benchmark(tmp_path)
    output = tmp_path / "review"
    report = comparison.run_review(source, output)
    assert report["gate_status"] == "passed"
    assert all(report["common_controls"].values())
    assert report["execution"] == {
        "parents": 1,
        "runs": 10,
        "guided_runs": 8,
        "control_runs": 2,
        "paired_descriptive_effects": 16,
    }
    assert report["eligibility"]["arm_selection_eligible"] is False
    assert report["eligibility"]["scientific_reporting_eligible"] is False
    assert sum(1 for _ in (output / comparison.RUN_TABLE_NAME).open()) == 11
    assert sum(1 for _ in (output / comparison.ARM_TABLE_NAME).open()) == 11
    assert sum(1 for _ in (output / comparison.EFFECT_TABLE_NAME).open()) == 17
    assert str(tmp_path) not in (output / comparison.REPORT_NAME).read_text()
    assert str(tmp_path) not in (output / comparison.MANIFEST_NAME).read_text()


def test_effect_table_marks_censored_comparisons_without_selecting_arm(
    tmp_path: Path,
) -> None:
    source = _source_benchmark(tmp_path)
    output = tmp_path / "review"
    comparison.run_review(source, output)
    with (output / comparison.EFFECT_TABLE_NAME).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["descriptive_joint_class"] for row in rows}
    assert any(
        row["censoring_interpretation"] == "right_censored_descriptive_only"
        for row in rows
    )
    assert all("winner" not in row for row in rows)


def test_review_recomputes_source_pairwise_deltas(tmp_path: Path) -> None:
    source = _source_benchmark(tmp_path)
    comparisons = source / benchmark.COMPARISONS_NAME
    rows = [json.loads(line) for line in comparisons.read_text().splitlines()]
    rows[0]["terminal_mip_gap_relative_delta"] = 99.0
    comparisons.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    report_path = source / benchmark.REPORT_NAME
    report = benchmark.load_json(report_path)
    report["outputs"]["paired_comparisons_sha256"] = benchmark.sha256_file(
        comparisons
    )
    benchmark.write_json(report_path, report)
    with pytest.raises(comparison.MvpComparisonError, match="paired gap delta"):
        comparison.run_review(source, tmp_path / "review")


def test_comparison_launcher_is_lf_only_and_uses_repository_root() -> None:
    launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_mvp_neural_diving_comparison.sbs"
    )
    assert b"\r" not in launcher.read_bytes()
    text = launcher.read_text()
    assert "SLURM_SUBMIT_DIR" in text
    assert "BENCHMARK_DIR" in text
    assert "review_mvp_neural_diving" in text


def test_research_note_defers_figures_and_quarto_template() -> None:
    note = (
        PROJECT_ROOT / "docs" / "research" / "mvp-four-arm-comparison.md"
    ).read_text()
    assert "training and validation loss by epoch" in note
    assert "GNN classification quality metrics" in note
    assert "external Quarto" in note
    assert "Manuscript template" in note
