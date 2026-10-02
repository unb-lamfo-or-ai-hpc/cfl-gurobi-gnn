from __future__ import annotations

import inspect
import json
from pathlib import Path

from cfl_gnn.analysis import pr60_scientific_evidence as evidence


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_pr60_policy_locks_upstream_contracts_and_prevents_reselection():
    policy = json.loads(evidence.CONFIG.read_text())
    assert policy["training_contract_sha256"] == evidence.EXPECTED_TRAINING_CONTRACT
    assert policy["validation_contract_sha256"] == evidence.pr59.EXPECTED_VALIDATION_CONTRACT
    assert policy["heldout_contract_sha256"] == "94abd94ba3eb5d4023b95fc3009330073aad02f9232d018149af2498cf62a670"
    assert policy["confirmatory_significance_claim_allowed"] is False
    assert policy["policy_reselection_after_test"] is False
    assert policy["development_only"] is True
    assert policy["scientific_reporting_eligible"] is False


def test_pr60_stage_is_analysis_only_and_preserves_censoring():
    source = inspect.getsource(evidence)
    assert '"solver_runs_executed": 0' in source
    assert '"training_runs_executed": 0' in source
    assert "first_observed_gap_le_0.1_seconds" in source
    assert "right_censored_runs" in source
    assert "confirmatory_significance_claim_allowed" in source
    assert "statistics.fmean" in source
    assert "statistics.median" in source


def test_pr60_declares_complete_table_and_figure_inventory():
    assert set(evidence.TABLES) == {
        "table_training_epoch_metrics.csv",
        "table_predictive_metrics.csv",
        "table_solver_outcomes.csv",
        "table_paired_gap_effects.csv",
        "table_censoring_summary.csv",
        "table_heldout_influence_analysis.csv",
    }
    assert set(evidence.FIGURES) == {
        "figure_offline_online_pipeline.svg",
        "figure_training_validation_loss.svg",
        "figure_predictive_quality.svg",
        "figure_validation_test_gap_effects.svg",
        "figure_time_to_ten_percent_gap.svg",
    }


def test_pr60_launcher_is_lf_only_and_runs_no_solver_or_training():
    launcher = PROJECT_ROOT / "scripts/slurm/dasci/submit_pr60_scientific_evidence.sbs"
    payload = launcher.read_bytes()
    text = payload.decode()
    assert payload.startswith(b"#!/bin/bash\n")
    assert b"\r" not in payload
    assert "build_pr60_scientific_evidence" in text
    assert "gurobi" not in text.lower()
    assert "train" not in text.lower().replace("training_dir", "")


def test_pr60_influence_analysis_is_explicit_and_deterministic():
    effects = [
        {"partition": "test", "method": evidence.pr59.METHODS[2], "source_instance_id": "a", "terminal_gap_difference_guided_minus_control": -0.2},
        {"partition": "test", "method": evidence.pr59.METHODS[2], "source_instance_id": "b", "terminal_gap_difference_guided_minus_control": 0.1},
    ]
    rows = evidence._influence_rows(effects, [[], ["a"]])
    assert rows[0]["included_parents"] == 2
    assert rows[0]["gnn_gap_wins"] == 1
    assert rows[0]["mean_gap_difference_guided_minus_control"] == -0.05
    assert rows[1]["included_parents"] == 1
    assert rows[1]["mean_gap_difference_guided_minus_control"] == 0.1


def test_pr60_figures_disclose_direction_and_censoring():
    pipeline_svg = evidence._pipeline_svg()
    assert "OFFLINE" in pipeline_svg
    assert "ONLINE SOLVER APPLICATION" in pipeline_svg
    assert "cannot alter" in pipeline_svg
    time_svg = evidence._time_svg(
        [
            {
                "partition": "test",
                "source_instance_id": "CFL_medium_instance_0",
                "method": evidence.pr59.METHODS[0],
                "first_observed_gap_le_0.1_seconds": None,
            }
        ]
    )
    assert "censored" in time_svg
    assert "not observed hitting times" in time_svg
