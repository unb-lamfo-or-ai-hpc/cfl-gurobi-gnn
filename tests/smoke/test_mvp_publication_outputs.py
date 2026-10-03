from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from cfl_gnn.analysis import mvp_publication_outputs as outputs
from cfl_gnn.analysis.mvp_pipeline_reproducibility import canonical_sha256
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.training.mvp_four_arm import EXPECTED_ARMS


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fixture(tmp_path: Path) -> dict[str, Path]:
    roots = {name: tmp_path / name for name in (
        "training", "evaluation", "comparison", "reproducibility"
    )}
    config = tmp_path / "config.json"
    _json(
        config,
        {
            "schema_version": 1,
            "protocol_id": "mvp_publication_outputs_v1",
            "expected_arms": list(EXPECTED_ARMS),
            "expected_target_solvers": ["gurobi", "scip"],
            "gap_sensitivity_thresholds_relative": [0.01, 0.05, 0.1],
            "table_format": "csv_rfc4180_utf8",
            "figure_format": "deterministic_svg_vector",
            "timing_figure_scale": "log10_one_plus_seconds",
            "censoring_policy": "retain_and_mark_descriptive_only",
            "selection_policy": "no_arm_ranking_or_selection",
            "inference_policy": "descriptive_only_partial_parent_population",
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
    )
    history_fields = [
        "epoch", "train_loss", "validation_loss", "accuracy", "precision",
        "recall", "f1_score"
    ]
    ledger_sources = []
    for arm_index, arm in enumerate(EXPECTED_ARMS):
        relative = Path("arms") / arm / "training_history.csv"
        path = roots["training"] / relative
        _csv(path, history_fields, [
            {"epoch": epoch, "train_loss": 1.2 - 0.1 * epoch + arm_index / 100,
             "validation_loss": 1.1 - 0.05 * epoch, "accuracy": 0.99,
             "precision": 0.1, "recall": 0.2, "f1_score": 0.13}
            for epoch in (1, 2)
        ])
        ledger_sources.append(("training", relative.as_posix(), path))
    training_report = roots["training"] / "mvp_four_arm_training_report.json"
    _json(training_report, {
        "gate_status": "passed",
        "arms": {arm: {"epochs_completed": 2} for arm in EXPECTED_ARMS},
        "eligibility": {
            "development_only": True, "scientific_reporting_eligible": False
        },
    })
    ledger_sources.append(("training", training_report.name, training_report))

    gnn_path = roots["evaluation"] / "per_arm_test_metrics.csv"
    gnn_fields = ["arm_id", "n_test_parents", "n_targets",
                  "unweighted_bce_per_variable", "accuracy", "precision",
                  "recall", "f1_score"]
    _csv(gnn_path, gnn_fields, [
        {"arm_id": arm, "n_test_parents": 1, "n_targets": 100,
         "unweighted_bce_per_variable": 1.0, "accuracy": 0.99,
         "precision": 0.1 + index / 100, "recall": 0.2,
         "f1_score": 0.13}
        for index, arm in enumerate(EXPECTED_ARMS)
    ])
    evaluation_report = roots["evaluation"] / "mvp_four_arm_evaluation_report.json"
    _json(evaluation_report, {"gate_status": "passed", "eligibility": {
        "development_only": True, "scientific_reporting_eligible": False
    }})
    ledger_sources.extend([
        ("evaluation", gnn_path.name, gnn_path),
        ("evaluation", evaluation_report.name, evaluation_report),
    ])

    run_path = roots["comparison"] / "per_run_descriptive_metrics.csv"
    run_fields = [
        "run_id", "parent_instance_id", "target_solver", "arm_id", "run_kind",
        "solve_status", "right_censored", "terminal_mip_gap_relative",
        "terminal_mip_gap_percent", "best_objective", "best_bound", "nodes",
        "solution_count", "total_wall_time_seconds",
        "data_read_wall_time_seconds", "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds", "fixed_variable_count"
    ]
    run_rows = []
    for solver in ("gurobi", "scip"):
        for index, arm in enumerate(("unguided_control", *EXPECTED_ARMS)):
            run_rows.append({
                "run_id": f"{solver}_{index}", "parent_instance_id": "parent_0",
                "target_solver": solver, "arm_id": arm,
                "run_kind": "control" if index == 0 else "guided",
                "solve_status": "timelimit", "right_censored": solver == "scip",
                "terminal_mip_gap_relative": 0.1 - index / 100,
                "terminal_mip_gap_percent": 10 - index, "best_objective": 2,
                "best_bound": 1.8, "nodes": 10, "solution_count": 1,
                "total_wall_time_seconds": 10, "data_read_wall_time_seconds": 1,
                "model_build_wall_time_seconds": 2,
                "model_optimize_wall_time_seconds": 6,
                "fixed_variable_count": 0 if index == 0 else 10,
            })
    _csv(run_path, run_fields, run_rows)
    arm_path = roots["comparison"] / "per_arm_descriptive_summary.csv"
    _csv(arm_path, ["target_solver", "arm_id"], [
        {"target_solver": row["target_solver"], "arm_id": row["arm_id"]}
        for row in run_rows
    ])
    effect_path = roots["comparison"] / "paired_descriptive_effects.csv"
    effect_fields = ["comparison_type", "candidate_arm_id", "reference_arm_id",
                     "terminal_mip_gap_relative_improvement",
                     "model_optimize_wall_time_seconds_improvement",
                     "censoring_interpretation"]
    _csv(effect_path, effect_fields, [
        {"comparison_type": "guided_vs_control", "candidate_arm_id": arm,
         "reference_arm_id": "unguided_control",
         "terminal_mip_gap_relative_improvement": 0.01,
         "model_optimize_wall_time_seconds_improvement": 1.0,
         "censoring_interpretation": "uncensored_descriptive"}
        for arm in EXPECTED_ARMS
    ])
    comparison_report = (
        roots["comparison"] / "mvp_neural_diving_comparison_report.json"
    )
    _json(comparison_report, {
        "gate_status": "passed",
        "execution": {"runs": 10, "paired_descriptive_effects": 4},
        "censoring": {"right_censored_runs": 5},
        "eligibility": {
            "development_only": True,
            "scientific_reporting_eligible": False,
            "arm_selection_eligible": False,
        },
    })
    ledger_sources.extend([
        ("comparison", run_path.name, run_path),
        ("comparison", arm_path.name, arm_path),
        ("comparison", effect_path.name, effect_path),
        ("comparison", comparison_report.name, comparison_report),
    ])

    repro = roots["reproducibility"]
    ledger = repro / "mvp_pipeline_artifact_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("w", encoding="utf-8") as stream:
        for stage, relative, path in ledger_sources:
            stream.write(json.dumps({"stage": stage, "relative_path": relative,
                                     "sha256": sha256_file(path),
                                     "artifact_kind": "source",
                                     "size_bytes": path.stat().st_size}) + "\n")
    plan_core = {"schema_version": 1, "audit_stage": "test",
                 "development_only": True,
                 "scientific_reporting_eligible": False}
    repro_plan = {**plan_core, "contract_sha256": canonical_sha256(plan_core),
                  "contract_valid": True, "next_gate": "outputs"}
    _json(repro / "mvp_pipeline_reproducibility_plan.json", repro_plan)
    manifest = {"reproducibility_contract_sha256": repro_plan["contract_sha256"],
                "artifact_ledger": {"sha256": sha256_file(ledger)}}
    manifest_path = repro / "mvp_pipeline_reproducibility_manifest.json"
    _json(manifest_path, manifest)
    report = {
        "reproducibility_contract_sha256": repro_plan["contract_sha256"],
        "gate_status": "passed", "common_controls": {"chain": True},
        "outputs": {
            "artifact_ledger": {"sha256": sha256_file(ledger)},
            "reproducibility_manifest": {"sha256": sha256_file(manifest_path)},
        },
        "eligibility": {"publication_output_layer_ready": True,
                        "scientific_reporting_eligible": False},
    }
    _json(repro / "mvp_pipeline_reproducibility_report.json", report)
    roots["config"] = config
    return roots


def _run(tmp_path: Path, roots: dict[str, Path], **kwargs):
    return outputs.run_generation(
        training_dir=roots["training"], evaluation_dir=roots["evaluation"],
        comparison_dir=roots["comparison"],
        reproducibility_dir=roots["reproducibility"],
        output_dir=tmp_path / "output", config_path=roots["config"], **kwargs
    )


def test_generation_writes_six_tables_and_six_figures(tmp_path: Path) -> None:
    roots = _fixture(tmp_path)
    report = _run(tmp_path, roots)
    assert report["gate_status"] == "passed"
    assert report["summary"]["tables_written"] == 6
    assert report["summary"]["figures_written"] == 6
    assert all(report["common_controls"].values())
    assert report["eligibility"]["scientific_reporting_eligible"] is False
    assert all((tmp_path / "output" / name).is_file()
               for name in (*outputs.TABLES, *outputs.FIGURES))


def test_svg_outputs_are_vector_and_development_marked(tmp_path: Path) -> None:
    roots = _fixture(tmp_path)
    _run(tmp_path, roots)
    for name in outputs.FIGURES:
        payload = (tmp_path / "output" / name).read_text(encoding="utf-8")
        assert payload.startswith("<svg")
        assert "Development-only descriptive MVP" in payload
        assert str(tmp_path) not in payload


def test_manifest_hashes_every_generated_asset(tmp_path: Path) -> None:
    roots = _fixture(tmp_path)
    _run(tmp_path, roots)
    output = tmp_path / "output"
    manifest = json.loads((output / outputs.MANIFEST_NAME).read_text())
    assert set(manifest["artifacts"]) == set((*outputs.TABLES, *outputs.FIGURES))
    for name, record in manifest["artifacts"].items():
        assert record["sha256"] == sha256_file(output / name)


def test_changed_ledger_bound_input_is_rejected(tmp_path: Path) -> None:
    roots = _fixture(tmp_path)
    history = roots["training"] / "arms" / EXPECTED_ARMS[0] / "training_history.csv"
    history.write_text(history.read_text() + "changed\n", encoding="utf-8")
    with pytest.raises(outputs.MvpPublicationOutputsError, match="SHA-256"):
        _run(tmp_path, roots)


def test_dry_run_writes_only_contract_plan(tmp_path: Path) -> None:
    roots = _fixture(tmp_path)
    plan = _run(tmp_path, roots, dry_run=True)
    assert plan["contract_valid"] is True
    assert plan["planned_tables"] == list(outputs.TABLES)
    assert plan["planned_figures"] == list(outputs.FIGURES)
    assert (tmp_path / "output" / outputs.PLAN_NAME).is_file()
    assert not (tmp_path / "output" / outputs.REPORT_NAME).exists()


def test_config_forbids_selection_and_inference() -> None:
    config = json.loads(outputs.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert config["selection_policy"] == "no_arm_ranking_or_selection"
    assert config["inference_policy"] == (
        "descriptive_only_partial_parent_population"
    )
    assert config["scientific_reporting_eligible"] is False
