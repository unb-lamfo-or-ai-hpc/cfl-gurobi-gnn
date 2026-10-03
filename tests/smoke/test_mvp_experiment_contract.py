from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.cli.plan_mvp_experiment import main
from cfl_gnn.experiments.mvp_contract import (
    ContractError,
    MvpSampleRecord,
    build_mvp_plan,
    load_experiment_config,
)
from cfl_gnn.splits.instance_folds import InstanceFold


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def _parents() -> list[InstanceFold]:
    return [
        InstanceFold("CFL_easy_instance_0", "CFL_easy_instance", "easy", 0),
        InstanceFold("CFL_easy_instance_1", "CFL_easy_instance", "easy", 1),
        InstanceFold("CFL_easy_instance_2", "CFL_easy_instance", "easy", 2),
    ]


def _sample(
    *,
    sample_id: str,
    parent: InstanceFold,
    solver: str = "gurobi",
    sampling: str = "original",
    gap: float = 0.05,
    radius_fraction: float = 0.001,
) -> MvpSampleRecord:
    value = {
        "sample_id": sample_id,
        "parent_instance_id": parent.source_instance_id,
        "category": parent.category,
        "difficulty": parent.difficulty,
        "fold": parent.fold,
        "solver": solver,
        "sampling_strategy": sampling,
        "graph_path": f"graphs/{sample_id}.pt",
        "graph_sha256": "a" * 64,
        "label_source": f"{solver}_independent_solution",
        "label_solution_sha256": "c" * 64,
        "label_objective": 6.25,
        "label_mip_gap_relative": gap,
        "label_mip_gap_percent": 100.0 * gap,
        "label_execution_time_seconds": 3600.0,
        "source_incumbent_id": None,
        "source_incumbent_artifact_sha256": None,
        "source_incumbent_objective": None,
        "source_incumbent_mip_gap_relative": None,
        "source_incumbent_mip_gap_percent": None,
        "source_incumbent_execution_time_seconds": None,
        "local_branching_radius": None,
        "local_branching_radius_fraction": None,
    }
    if sampling == "incumbent_local_branching":
        value.update(
            source_incumbent_id=f"{solver}-inc-1",
            source_incumbent_artifact_sha256="d" * 64,
            source_incumbent_objective=6.5,
            source_incumbent_mip_gap_relative=0.08,
            source_incumbent_mip_gap_percent=8.0,
            source_incumbent_execution_time_seconds=1200.0,
            local_branching_radius=148,
            local_branching_radius_fraction=radius_fraction,
        )
    return MvpSampleRecord.from_mapping(value)


def test_repository_config_locks_four_arm_factorial_and_flexible_gap() -> None:
    config = load_experiment_config(CONFIG)

    assert config.development_only is True
    assert config.objective_sense == "MINIMIZE"
    assert config.gap_policy.maximum_admissible_relative_gap == 0.10
    assert config.gap_policy.sensitivity_thresholds_relative == (
        0.01,
        0.05,
        0.06,
        0.10,
    )
    assert {
        (arm.solver, arm.sampling_strategy) for arm in config.arms
    } == {
        ("gurobi", "original"),
        ("gurobi", "incumbent_local_branching"),
        ("scip", "original"),
        ("scip", "incumbent_local_branching"),
    }


def test_gap_memberships_are_nested_and_ten_percent_is_inclusive() -> None:
    policy = load_experiment_config(CONFIG).gap_policy

    assert policy.sensitivity_memberships(0.009) == (
        "gap_le_0.01",
        "gap_le_0.05",
        "gap_le_0.06",
        "gap_le_0.1",
    )
    assert policy.sensitivity_memberships(0.055) == (
        "gap_le_0.06",
        "gap_le_0.1",
    )
    assert policy.accepts(0.10)
    assert not policy.accepts(0.10001)


def test_valid_plan_accepts_original_test_but_derived_training_only() -> None:
    config = load_experiment_config(CONFIG)
    parents = _parents()
    samples = (
        _sample(sample_id="g-original-test", parent=parents[0]),
        _sample(
            sample_id="g-derived-train",
            parent=parents[2],
            sampling="incumbent_local_branching",
        ),
        _sample(
            sample_id="s-original-validation",
            parent=parents[1],
            solver="scip",
        ),
        _sample(
            sample_id="s-derived-train",
            parent=parents[2],
            solver="scip",
            sampling="incumbent_local_branching",
            gap=0.10,
        ),
    )

    plan = build_mvp_plan(config, parents, samples)

    assert plan["contract_valid"] is True
    assert plan["samples_eligible"] == 4
    assert plan["arms"]["gurobi_original"]["partitions"]["test"] == 1
    assert (
        plan["arms"]["gurobi_incumbent_augmented"]["partitions"]["train"]
        == 1
    )
    assert plan["arms"]["scip_original"]["partitions"]["validation"] == 1
    assert plan["arms"]["scip_incumbent_augmented"]["partitions"]["train"] == 1
    assert plan["gap_policy"]["eligible_by_sensitivity"]["gap_le_0.1"] == 4


@pytest.mark.parametrize(
    ("sample", "reason"),
    [
        (
            lambda parents: _sample(
                sample_id="derived-test",
                parent=parents[0],
                sampling="incumbent_local_branching",
            ),
            "derived_sample_outside_train",
        ),
        (
            lambda parents: _sample(
                sample_id="gap-too-large", parent=parents[2], gap=0.1001
            ),
            "label_gap_above_maximum",
        ),
        (
            lambda parents: _sample(
                sample_id="unplanned-radius",
                parent=parents[2],
                sampling="incumbent_local_branching",
                radius_fraction=0.02,
            ),
            "unplanned_local_branching_radius",
        ),
    ],
)
def test_plan_fails_closed(sample, reason: str) -> None:
    config = load_experiment_config(CONFIG)
    parents = _parents()

    plan = build_mvp_plan(config, parents, (sample(parents),))

    assert plan["contract_valid"] is False
    assert reason in plan["invalid_samples"][0]["reasons"]


def test_parent_fold_mismatch_is_invalid() -> None:
    config = load_experiment_config(CONFIG)
    parents = _parents()
    sample = _sample(sample_id="bad-fold", parent=parents[2])
    value = {name: getattr(sample, name) for name in sample.__dataclass_fields__}
    value["fold"] = 4
    mismatched = MvpSampleRecord(**value)

    plan = build_mvp_plan(config, parents, (mismatched,))

    assert plan["contract_valid"] is False
    assert "parent_contract_mismatch" in plan["invalid_samples"][0]["reasons"]


def test_cli_can_materialize_pre_generation_plan(tmp_path: Path) -> None:
    output = tmp_path / "plan.json"

    status = main(
        [
            "--config",
            str(CONFIG),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(output),
        ]
    )

    assert status == 0
    plan = json.loads(output.read_text(encoding="utf-8"))
    assert plan["samples_declared"] == 0
    assert plan["next_gate"] == "dataset_generation"
    assert plan["scientific_reporting_eligible"] is False


def test_strict_cli_rejects_empty_arm_inventory(tmp_path: Path) -> None:
    output = tmp_path / "plan.json"

    status = main(
        [
            "--config",
            str(CONFIG),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(output),
            "--strict_inventory",
        ]
    )

    assert status == 1


def test_config_without_complete_two_by_two_design_is_rejected(
    tmp_path: Path,
) -> None:
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    value["arms"].pop()
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ContractError, match="2x2"):
        load_experiment_config(path)


def test_original_sample_cannot_claim_incumbent_derivation() -> None:
    parent = _parents()[2]
    value = {
        "sample_id": "invalid-original",
        "parent_instance_id": parent.source_instance_id,
        "category": parent.category,
        "difficulty": parent.difficulty,
        "fold": parent.fold,
        "solver": "gurobi",
        "sampling_strategy": "original",
        "graph_path": "graph.pt",
        "graph_sha256": "b" * 64,
        "label_source": "gurobi_independent_solution",
        "label_solution_sha256": "c" * 64,
        "label_objective": 1.0,
        "label_mip_gap_relative": 0.0,
        "label_mip_gap_percent": 0.0,
        "label_execution_time_seconds": 1.0,
        "source_incumbent_id": "should-not-exist",
        "source_incumbent_artifact_sha256": None,
        "source_incumbent_objective": None,
        "source_incumbent_mip_gap_relative": None,
        "source_incumbent_mip_gap_percent": None,
        "source_incumbent_execution_time_seconds": None,
        "local_branching_radius": None,
        "local_branching_radius_fraction": None,
    }

    with pytest.raises(ContractError, match="cannot declare derivation"):
        MvpSampleRecord.from_mapping(value)


def test_gap_relative_and_percentage_must_agree() -> None:
    parent = _parents()[2]
    sample = _sample(sample_id="consistent", parent=parent)
    value = {name: getattr(sample, name) for name in sample.__dataclass_fields__}
    value["label_mip_gap_percent"] = 4.0

    with pytest.raises(ContractError, match="relative and percentage"):
        MvpSampleRecord.from_mapping(value)


def test_metric_change_changes_contract_hash(tmp_path: Path) -> None:
    original = load_experiment_config(CONFIG)
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    value["metrics"]["prediction_secondary"].append("accuracy")
    changed_path = tmp_path / "changed.json"
    changed_path.write_text(json.dumps(value), encoding="utf-8")

    changed = load_experiment_config(changed_path)

    assert changed.contract_sha256 != original.contract_sha256
