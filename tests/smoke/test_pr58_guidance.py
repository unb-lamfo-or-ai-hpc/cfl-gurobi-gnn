from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.experiments.pr58_guidance import (
    class_aware_gnn_assignments,
    matched_root_lp_assignments,
    support_size,
)
from cfl_gnn.pipelines.pr58_validation_guidance import _split_sets


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def prediction(name: str, probability: float, threshold: float = 0.8) -> dict:
    return {
        "variable_name": name,
        "probability": probability,
        "predicted_value": int(probability >= threshold),
        "confidence": max(probability, 1.0 - probability),
        "priority": int(round(100 * max(probability, 1.0 - probability))),
    }


def test_support_size_applies_relative_and_absolute_caps():
    assert support_size(100, 0.1, 20) == 10
    assert support_size(1000, 0.1, 20) == 20
    assert support_size(3, 0.1, 20) == 1
    with pytest.raises(ValueError):
        support_size(0, 0.1, 20)


def test_class_aware_support_keeps_rare_positive_before_confident_zeros():
    rows = [prediction("positive", 0.91)] + [
        prediction(f"zero_{index:02d}", probability)
        for index, probability in enumerate((0.001, 0.002, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07))
    ]
    result = class_aware_gnn_assignments(rows, fraction=0.2, absolute_cap=20)
    assert result["selected_support"] == 2
    assert result["positive_assignments"] == 1
    assert result["negative_assignments"] == 1
    assert [row["variable_name"] for row in result["assignments"]] == ["positive", "zero_00"]


def test_class_aware_selection_is_stable_under_input_permutation_and_ties():
    rows = [prediction("b", 0.9), prediction("a", 0.9)] + [
        prediction(f"z{index}", 0.01) for index in range(8)
    ]
    left = class_aware_gnn_assignments(rows, fraction=0.3, absolute_cap=20)
    right = class_aware_gnn_assignments(list(reversed(rows)), fraction=0.3, absolute_cap=20)
    assert left == right
    assert [row["variable_name"] for row in left["assignments"][:2]] == ["a", "b"]


def test_class_aware_policy_abstains_when_no_positive_is_predicted():
    result = class_aware_gnn_assignments(
        [prediction("x", 0.1), prediction("y", 0.2)],
        fraction=0.5,
        absolute_cap=20,
    )
    assert result["abstained"]
    assert result["assignments"] == []
    assert result["reason_code"] == "no_threshold_positive_prediction"


def test_root_lp_baseline_matches_support_and_positive_count():
    result = matched_root_lp_assignments(
        ["a", "b", "c", "d", "e"],
        [0.99, 0.8, 0.4, 0.02, 0.01],
        support=4,
        positive_assignments=2,
    )
    assert result["selected_support"] == 4
    assert result["positive_assignments"] == 2
    assert result["negative_assignments"] == 2
    assert [(row["variable_name"], row["value"]) for row in result["assignments"]] == [
        ("a", 1),
        ("b", 1),
        ("e", 0),
        ("d", 0),
    ]


def test_pr58_policy_freezes_validation_and_test_parent_sets():
    policy = json.loads(
        (PROJECT_ROOT / "configs/experiments/pr58_validation_guidance_v1.json").read_text()
    )
    assert policy["qualification_partition"] == "validation"
    assert policy["qualification_parent_ids"] == [
        "CFL_medium_instance_5",
        "CFL_medium_instance_6",
        "CFL_medium_instance_11",
        "CFL_medium_instance_14",
        "CFL_medium_instance_17",
        "CFL_medium_instance_19",
    ]
    assert policy["frozen_test_parent_ids"] == [
        "CFL_medium_instance_0",
        "CFL_medium_instance_4",
        "CFL_medium_instance_7",
        "CFL_medium_instance_9",
        "CFL_medium_instance_12",
        "CFL_medium_instance_20",
    ]
    assert set(policy["qualification_parent_ids"]).isdisjoint(policy["frozen_test_parent_ids"])
    assert policy["test_outcomes_available_to_qualification"] is False
    validation, test = _split_sets()
    assert validation == sorted(policy["qualification_parent_ids"])
    assert test == sorted(policy["frozen_test_parent_ids"])


def test_pr58_launchers_are_lf_only_and_never_train_or_execute_test_targets():
    launcher = PROJECT_ROOT / "scripts/slurm/dasci/launch_pr58_validation_guidance.sh"
    worker = PROJECT_ROOT / "scripts/slurm/dasci/submit_pr58_validation_guidance.sbs"
    audit = PROJECT_ROOT / "scripts/slurm/dasci/submit_pr58_validation_guidance_audit.sbs"
    for path in (launcher, worker, audit):
        payload = path.read_bytes()
        assert payload.startswith(b"#!/bin/bash\n")
        assert b"\r" not in payload
    combined = "\n".join(path.read_text() for path in (launcher, worker, audit))
    assert "run_pr58_validation_guidance" in combined
    assert "run_pr57_training train" not in combined
    assert "gasse_reconnected" not in combined
    assert "--array=0-5%2" in worker.read_text()


def test_pr58_pipeline_source_never_loads_target_labels_or_test_outcomes():
    source = (
        PROJECT_ROOT / "src/cfl_gnn/pipelines/pr58_validation_guidance.py"
    ).read_text()
    assert "target_labels_loaded\": False" in source
    assert "test_outcomes_loaded\": False" in source
    assert "solution_path" in source  # output evidence only
    assert "label_run_relative_path" not in source
    assert "frozen_test_targets" in source
