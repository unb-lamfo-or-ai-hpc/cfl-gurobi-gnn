"""Dependency-free checks for the PR #49 neural-guidance policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.experiments import neural_guidance_policy as policy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    PROJECT_ROOT
    / "configs"
    / "experiments"
    / "neural_guidance_policy_v1.json"
)


def _rows() -> list[dict[str, object]]:
    return [
        {
            "variable_name": "x_b",
            "predicted_value": 1,
            "probability": 0.9,
            "confidence": 0.8,
            "priority": 80,
        },
        {
            "variable_name": "x_a",
            "predicted_value": 0,
            "probability": 0.1,
            "confidence": 0.8,
            "priority": 80,
        },
        {
            "variable_name": "x_c",
            "predicted_value": 1,
            "probability": 0.7,
            "confidence": 0.4,
            "priority": 40,
        },
    ]


def test_policy_contract_is_complete_and_development_only() -> None:
    plan = policy.build_plan(CONFIG)
    assert plan["contract_valid"] is True
    assert all(plan["checks"].values())
    assert plan["decision"]["primary_method"] == "gurobi_variable_hints"
    assert plan["decision"]["next_gate"] == (
        "paired_neural_guidance_benchmark_execution"
    )
    assert plan["development_only"] is True
    assert plan["scientific_reporting_eligible"] is False


def test_hard_fixing_is_not_primary_and_recovery_is_mandatory() -> None:
    plan = policy.build_plan(CONFIG)
    boundaries = plan["methodological_boundaries"]
    assert boundaries["hard_fixing_equivalent_to_variable_hints"] is False
    assert boundaries["binding_methods_require_full_model_recovery"] is True
    assert plan["checks"]["hard_fixing_is_not_primary"] is True
    assert plan["checks"]["all_binding_methods_have_recovery"] is True


def test_prediction_order_and_partial_coverage_are_deterministic() -> None:
    ranked = policy.rank_predictions(_rows())
    assert [row["variable_name"] for row in ranked] == ["x_a", "x_b", "x_c"]
    selected = policy.select_coverage(_rows(), 0.5)
    assert [row["variable_name"] for row in selected] == ["x_a"]


def test_variable_hints_are_nonbinding_and_cover_all_predictions() -> None:
    directives = policy.guidance_directives(
        _rows(), method="gurobi_variable_hints"
    )
    assert len(directives["assignments"]) == 3
    assert directives["binding_during_restricted_phase"] is False
    assert directives["recovery_required"] is False


def test_restricted_method_requires_recovery() -> None:
    directives = policy.guidance_directives(
        _rows(),
        method="confidence_partial_fixing_with_recovery",
        fraction=0.5,
    )
    assert len(directives["assignments"]) == 1
    assert directives["binding_during_restricted_phase"] is True
    assert directives["recovery_required"] is True


def test_prediction_rows_reject_test_labels() -> None:
    rows = _rows()
    rows[0]["target"] = 1
    with pytest.raises(policy.NeuralGuidancePolicyError, match="test labels"):
        policy.rank_predictions(rows)


def test_cli_writes_path_neutral_auditable_outputs(tmp_path: Path) -> None:
    assert policy.main(
        [
            "--config",
            str(CONFIG),
            "--output_dir",
            str(tmp_path),
            "--dry_run",
        ]
    ) == 0
    report = json.loads((tmp_path / policy.REPORT_NAME).read_text(encoding="utf-8"))
    assert report["gate_status"] == "passed"
    assert report["execution"]["solver_runs_executed"] == 0
    serialized = json.dumps(report)
    assert "/raid/" not in serialized
    assert "gurobi.lic" not in serialized


def test_dasci_launcher_is_lf_only_and_does_not_solve() -> None:
    launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_neural_guidance_policy_audit.sbs"
    )
    payload = launcher.read_bytes()
    assert b"\r" not in payload
    text = payload.decode("utf-8")
    assert "plan_neural_guidance_policy" in text
    assert "model.optimize" not in text
    assert "--time=00:10:00" in text

