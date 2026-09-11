from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.evaluation import mvp_four_arm as evaluation
from cfl_gnn.training import mvp_four_arm as training


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAINING_PROTOCOL = (
    PROJECT_ROOT
    / "configs"
    / "training"
    / "scalable_four_arm_training_v1.json"
)
EVALUATION_PROTOCOL = (
    PROJECT_ROOT
    / "configs"
    / "evaluation"
    / "scalable_four_arm_held_out_v1.json"
)


def test_scalable_protocol_pins_seed_and_validation_only_selection() -> None:
    protocol = training.load_training_protocol(TRAINING_PROTOCOL)
    assert protocol.schema_version == 2
    assert protocol.seed == 42
    assert protocol.checkpoint_selection_metric == "validation_weighted_bce"
    assert protocol.threshold_selection_method == "maximum_validation_f1"
    assert protocol.legacy_gasse_git_blob_sha1 == (
        "e2937ebcca149f8a99ec437c3c8e7fd31e49438b"
    )
    payload = protocol.contract_payload
    assert payload["threshold_selection"]["test_partition_access"] == (
        "held_out_evaluation_only"
    )
    assert payload["comparison_controls"]["threshold_selection_policy"] == (
        "per_arm_common_validation_only"
    )


def test_threshold_selection_is_exact_deterministic_and_validation_only() -> None:
    selected = training.select_validation_threshold(
        targets=[1.0, 1.0, 0.0, 0.0],
        probabilities=[0.9, 0.6, 0.55, 0.1],
    )
    assert selected["probability_threshold"] == pytest.approx(0.6)
    assert selected["f1_score"] == pytest.approx(1.0)
    assert selected["tp"] == 2
    assert selected["fp"] == 0


def test_threshold_tie_break_prefers_closest_to_half_then_lower() -> None:
    selected = training.select_validation_threshold(
        targets=[0.0, 0.0], probabilities=[0.75, 0.25]
    )
    assert selected["probability_threshold"] == pytest.approx(0.5)


def test_scalable_evaluation_protocol_consumes_training_thresholds() -> None:
    protocol = evaluation.load_evaluation_protocol(EVALUATION_PROTOCOL)
    assert protocol.schema_version == 2
    assert protocol.probability_threshold is None
    assert protocol.threshold_source == (
        "per_arm_maximum_validation_f1_from_training_report"
    )


def test_scalable_slurm_launchers_are_lf_only_and_bind_protocols() -> None:
    for name in (
        "submit_scalable_four_arm_training.sbs",
        "submit_scalable_four_arm_evaluation.sbs",
    ):
        path = PROJECT_ROOT / "scripts" / "slurm" / "dasci" / name
        payload = path.read_bytes()
        assert b"\r" not in payload
        text = payload.decode("utf-8")
        assert "--device cuda" in text
        assert "scalable_four_arm" in text


def test_scalable_protocol_artifacts_are_path_neutral() -> None:
    for path in (TRAINING_PROTOCOL, EVALUATION_PROTOCOL):
        payload = json.loads(path.read_text(encoding="utf-8"))
        serialized = json.dumps(payload)
        assert "/raid/" not in serialized
        assert "gurobi.lic" not in serialized
