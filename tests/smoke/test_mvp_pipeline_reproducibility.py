from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.analysis.mvp_pipeline_reproducibility import (
    LEDGER_NAME,
    MANIFEST_NAME,
    PLAN_NAME,
    REPORT_NAME,
    MvpPipelineReproducibilityError,
    canonical_sha256,
    run_audit,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.training.mvp_four_arm import EXPECTED_ARMS


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write(path: Path, value: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return sha256_file(path)


def _contract(plan: dict, excluded: set[str]) -> dict:
    plan["contract_sha256"] = canonical_sha256(
        {key: value for key, value in plan.items() if key not in excluded}
    )
    return plan


def _fixture(tmp_path: Path) -> tuple[dict[str, Path], Path]:
    roots = {name: tmp_path / name for name in (
        "dataset", "training", "evaluation", "benchmark", "comparison"
    )}
    config = tmp_path / "config.json"
    _write_json(
        config,
        {
            "schema_version": 1,
            "protocol_id": "mvp_pipeline_reproducibility_v1",
            "expected_stages": list(roots),
            "expected_arms": list(EXPECTED_ARMS),
            "required_gate_status": "passed",
            "artifact_policy": "sha256_path_sanitized_ledger",
            "contract_policy": "fail_closed_end_to_end_chain",
            "arm_selection_performed": False,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
    )

    dataset_plan = _contract(
        {"schema_version": 1, "dataset_variant": "test", "original_count": 6,
         "derived_count": 6},
        {"contract_sha256", "original_count", "derived_count"},
    )
    dataset_outputs = {}
    for key, name in (
        ("sample_manifest", "mvp_sample_manifest.jsonl"),
        ("original_graph_audit", "per_original_graph_audit.jsonl"),
        ("evaluation_reference_manifest", "evaluation_reference_manifest.jsonl"),
    ):
        dataset_outputs[key] = name
        dataset_outputs[f"{key}_sha256"] = _write(roots["dataset"] / name)
    dataset_outputs["arm_manifest_root"] = "arms"
    dataset_arms = {}
    for arm in EXPECTED_ARMS:
        digest = _write(roots["dataset"] / "arms" / f"{arm}.jsonl")
        dataset_arms[arm] = {"sha256": digest}
    dataset_report = {
        "contract_sha256": dataset_plan["contract_sha256"],
        "gate_status": "passed",
        "outputs": dataset_outputs,
        "arms": dataset_arms,
        "eligibility": {"development_only": True,
                        "scientific_reporting_eligible": False},
    }
    _write_json(roots["dataset"] / "mvp_dataset_composition_plan.json", dataset_plan)
    _write_json(
        roots["dataset"] / "mvp_dataset_composition_report.json",
        dataset_report,
    )

    training_plan = _contract(
        {
            "schema_version": 1,
            "dataset_contract_sha256": dataset_plan["contract_sha256"],
            "training_data_contract_sha256": "a" * 64,
            "contract_valid": True,
            "mvp_execution_ready": True,
            "test_graphs_loaded": 0,
            "next_gate": "four_arm_training_execution",
        },
        {"contract_sha256", "contract_valid", "mvp_execution_ready",
         "test_graphs_loaded", "next_gate"},
    )
    training_arms = {}
    for arm in EXPECTED_ARMS:
        arm_root = roots["training"] / "arms" / arm
        training_arms[arm] = {
            "checkpoint": {"sha256": _write(arm_root / "best_model.pt")},
            "history": {"sha256": _write(arm_root / "training_history.csv")},
            "summary_sha256": _write(arm_root / "arm_training_summary.json"),
        }
    training_report = {
        "training_run_contract_sha256": training_plan["contract_sha256"],
        "gate_status": "passed",
        "paired_controls": {"paired": True},
        "arms": training_arms,
        "eligibility": {"development_only": True,
                        "scientific_reporting_eligible": False},
    }
    training_plan_path = roots["training"] / "mvp_four_arm_training_plan.json"
    training_report_path = roots["training"] / "mvp_four_arm_training_report.json"
    _write_json(training_plan_path, training_plan)
    _write_json(training_report_path, training_report)

    evaluation_plan = _contract(
        {
            "schema_version": 1,
            "dataset_contract_sha256": dataset_plan["contract_sha256"],
            "training_run_contract_sha256": training_plan["contract_sha256"],
            "training_plan_sha256": sha256_file(training_plan_path),
            "training_report_sha256": sha256_file(training_report_path),
            "contract_valid": True,
            "arm_selection_performed": False,
            "all_four_arms_forwarded": True,
            "next_gate": "evaluation",
        },
        {"contract_sha256", "contract_valid", "arm_selection_performed",
         "all_four_arms_forwarded", "next_gate"},
    )
    metrics_sha = _write(roots["evaluation"] / "per_arm_test_metrics.csv")
    evaluation_arms = {}
    for arm in EXPECTED_ARMS:
        relative = f"arms/{arm}/hints/parent.jsonl.gz"
        evaluation_arms[arm] = {"hint_artifacts": [{
            "relative_path": relative,
            "sha256": _write(roots["evaluation"] / relative),
        }]}
    evaluation_report = {
        "evaluation_contract_sha256": evaluation_plan["contract_sha256"],
        "training_run_contract_sha256": training_plan["contract_sha256"],
        "gate_status": "passed",
        "common_controls": {"common_test": True},
        "arm_selection": {"performed": False},
        "arms": evaluation_arms,
        "outputs": {"per_arm_metrics_sha256": metrics_sha},
        "eligibility": {"development_only": True,
                        "scientific_reporting_eligible": False},
    }
    evaluation_plan_path = roots["evaluation"] / "mvp_four_arm_evaluation_plan.json"
    evaluation_report_path = roots["evaluation"] / "mvp_four_arm_evaluation_report.json"
    _write_json(evaluation_plan_path, evaluation_plan)
    _write_json(evaluation_report_path, evaluation_report)

    task_relative = "tasks/task_000.json"
    task_sha = _write(roots["benchmark"] / task_relative)
    benchmark_plan = {
        "schema_version": 1,
        "source_evaluation_contract_sha256": evaluation_plan["contract_sha256"],
        "source_evaluation_plan_sha256": sha256_file(evaluation_plan_path),
        "source_evaluation_report_sha256": sha256_file(evaluation_report_path),
        "tasks": [{"task_index": 0, "output_relative_path": task_relative}],
        "contract_valid": True,
        "task_count": 1,
        "next_gate": "benchmark",
    }
    benchmark_plan["contract_sha256"] = canonical_sha256({
        key: value for key, value in benchmark_plan.items()
        if key not in {"contract_sha256", "contract_valid", "task_count", "next_gate"}
    })
    benchmark_outputs = {}
    for key, name in (
        ("per_run_metrics", "per_run_solver_metrics.csv"),
        ("paired_comparisons", "paired_solver_comparisons.jsonl"),
    ):
        benchmark_outputs[f"{key}_sha256"] = _write(roots["benchmark"] / name)
    benchmark_report = {
        "benchmark_contract_sha256": benchmark_plan["contract_sha256"],
        "gate_status": "passed",
        "common_controls": {"equal_budget": True},
        "outputs": benchmark_outputs,
        "eligibility": {"development_only": True,
                        "scientific_reporting_eligible": False},
    }
    benchmark_plan_path = roots["benchmark"] / "mvp_neural_diving_plan.json"
    benchmark_report_path = roots["benchmark"] / "mvp_neural_diving_report.json"
    _write_json(benchmark_plan_path, benchmark_plan)
    _write_json(benchmark_report_path, benchmark_report)

    benchmark_files = {
        "benchmark_plan": benchmark_plan_path,
        "benchmark_report": benchmark_report_path,
        "per_run_metrics": roots["benchmark"] / "per_run_solver_metrics.csv",
        "paired_comparisons": roots["benchmark"] / "paired_solver_comparisons.jsonl",
    }
    comparison_plan = {
        "schema_version": 1,
        "source_benchmark_contract_sha256": benchmark_plan["contract_sha256"],
        "source_artifacts": {key: {"file_name": path.name,
                                    "sha256": sha256_file(path)}
                             for key, path in benchmark_files.items()},
        "source_task_results": [{"relative_path": task_relative,
                                 "sha256": task_sha}],
        "contract_valid": True,
        "next_gate": "comparison",
    }
    comparison_plan["contract_sha256"] = canonical_sha256({
        key: value for key, value in comparison_plan.items()
        if key not in {"contract_sha256", "contract_valid", "next_gate"}
    })
    comparison_outputs = {}
    for name in (
        "per_run_descriptive_metrics.csv",
        "per_arm_descriptive_summary.csv",
        "paired_descriptive_effects.csv",
    ):
        comparison_outputs[name] = {
            "file_name": name,
            "sha256": _write(roots["comparison"] / name),
        }
    manifest_name = "reproducibility_manifest.json"
    comparison_outputs["reproducibility_manifest"] = {
        "file_name": manifest_name,
        "sha256": _write(roots["comparison"] / manifest_name),
    }
    comparison_report = {
        "comparison_contract_sha256": comparison_plan["contract_sha256"],
        "gate_status": "passed",
        "common_controls": {"descriptive_only": True},
        "outputs": comparison_outputs,
        "eligibility": {"development_only": True,
                        "scientific_reporting_eligible": False},
    }
    _write_json(roots["comparison"] / "mvp_neural_diving_comparison_plan.json",
                comparison_plan)
    _write_json(roots["comparison"] / "mvp_neural_diving_comparison_report.json",
                comparison_report)
    return roots, config


def _run(tmp_path: Path, roots: dict[str, Path], config: Path, **kwargs):
    return run_audit(
        dataset_dir=roots["dataset"],
        training_dir=roots["training"],
        evaluation_dir=roots["evaluation"],
        benchmark_dir=roots["benchmark"],
        comparison_dir=roots["comparison"],
        output_dir=tmp_path / "output",
        config_path=config,
        **kwargs,
    )


def test_complete_chain_writes_sanitized_ledger(tmp_path: Path) -> None:
    roots, config = _fixture(tmp_path)
    report = _run(tmp_path, roots, config)
    assert report["gate_status"] == "passed"
    assert report["eligibility"]["pipeline_execution_ready"] is True
    assert report["eligibility"]["scientific_reporting_eligible"] is False
    output = tmp_path / "output"
    assert all((output / name).is_file() for name in (
        PLAN_NAME, REPORT_NAME, LEDGER_NAME, MANIFEST_NAME
    ))
    ledger = (output / LEDGER_NAME).read_text(encoding="utf-8")
    assert str(tmp_path) not in ledger
    assert report["artifact_ledger"]["records"] > 20


def test_dry_run_writes_only_the_plan(tmp_path: Path) -> None:
    roots, config = _fixture(tmp_path)
    plan = _run(tmp_path, roots, config, dry_run=True)
    assert plan["contract_valid"] is True
    assert (tmp_path / "output" / PLAN_NAME).is_file()
    assert not (tmp_path / "output" / REPORT_NAME).exists()


def test_changed_training_report_is_rejected(tmp_path: Path) -> None:
    roots, config = _fixture(tmp_path)
    path = roots["training"] / "mvp_four_arm_training_report.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(MvpPipelineReproducibilityError, match="artifact chain"):
        _run(tmp_path, roots, config)


def test_broken_contract_link_is_rejected(tmp_path: Path) -> None:
    roots, config = _fixture(tmp_path)
    path = roots["evaluation"] / "mvp_four_arm_evaluation_plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    plan["dataset_contract_sha256"] = "f" * 64
    excluded = {"contract_sha256", "contract_valid", "arm_selection_performed",
                "all_four_arms_forwarded", "next_gate"}
    _contract(plan, excluded)
    _write_json(path, plan)
    with pytest.raises(MvpPipelineReproducibilityError, match="contract chain"):
        _run(tmp_path, roots, config)


def test_changed_ledger_artifact_is_rejected(tmp_path: Path) -> None:
    roots, config = _fixture(tmp_path)
    path = roots["dataset"] / "arms" / f"{EXPECTED_ARMS[0]}.jsonl"
    path.write_text("changed\n", encoding="utf-8")
    with pytest.raises(MvpPipelineReproducibilityError, match="SHA-256"):
        _run(tmp_path, roots, config)


def test_non_precommitted_config_is_rejected(tmp_path: Path) -> None:
    roots, config = _fixture(tmp_path)
    value = json.loads(config.read_text(encoding="utf-8"))
    value["expected_arms"] = list(EXPECTED_ARMS[:-1])
    _write_json(config, value)
    with pytest.raises(MvpPipelineReproducibilityError, match="precommitted"):
        _run(tmp_path, roots, config)
