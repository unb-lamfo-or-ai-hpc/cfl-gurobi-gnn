"""Freeze the two-method design without executing a solver."""
import json

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.splits.instance_folds import read_manifest


def design():
    return json.loads((PROJECT_ROOT / "configs/experiments/easy_medium_partial_start_v1.json").read_text())


def test_explicit_design_only_no_scientific_or_execution_certificate():
    value = design()
    assert value["status"] == "precommitted_design_execution_not_implemented"
    assert value["development_only"] is True
    assert value["scientific_reporting_eligible"] is False
    assert value["expansion_requires_pilot_review"] is True


def test_primary_partial_start_is_not_hint_or_fixing():
    value = design()
    assert value["methods"] == ["unguided_control", "partial_mip_start"]
    assert value["binding_interventions_allowed"] is False
    assert value["coverage_fraction"] == .1
    assert value["fresh_model_per_method"] is True
    assert value["paired_parameters_identical_except_start"] is True


def test_medium_cohort_includes_prior_rejections_and_no_easy_or_hard():
    value = design()
    parents = [f"{value['expansion_parent_category']}_{i}" for i in value["expansion_parent_indices"]]
    expected = {e.source_instance_id for e in read_manifest(PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv") if e.difficulty == "medium"}
    assert len(parents) == 30 and set(parents) == expected
    assert value["pilot_parent_ids"] == ["CFL_medium_instance_0", "CFL_medium_instance_1"]
    assert value["target_label_admission_required"] is False
    assert value["target_labels_or_incumbents_allowed_as_input"] is False


def test_fixed_comparison_and_complete_cost_accounting():
    value = design()
    assert value["objective_sense"] == "MINIMIZE"
    assert value["seed"] == 42 and value["threads_per_run"] == 1
    assert value["optimization_time_limit_seconds"] == 3600
    assert value["model_source"] == "easy_only_medium_transfer_v1"
    assert value["threshold_source"] == "easy_validation_only"
    assert value["root_feature_authority"] == "gurobi"
    assert value["zero_root_fallback_allowed"] is False
    assert value["end_to_end_cost_required"] is True
    assert value["censoring_policy"] == "retain_and_flag_no_naive_inference"
