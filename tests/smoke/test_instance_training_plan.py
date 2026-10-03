"""Dependency-free tests for parent-instance serial training admission."""

import argparse

from pathlib import Path

import pytest

from cfl_gnn.splits.instance_partitions import (
    InstanceDatasetAudit,
    InstanceGraphRecord,
    InvalidInstance,
)
from cfl_gnn.training.instance_plan import (
    InstanceTrainingPlanError,
    validate_instance_training_audit,
)
from cfl_gnn.training.instance_serial import _validate_expected_inventory


def _record(
    source_instance_id: str,
    *,
    role: str,
    fold: int,
    difficulty: str = "easy",
    mip_gap_band: str = "optimal_tolerance",
) -> InstanceGraphRecord:
    category = f"CFL_{difficulty}_instance"
    return InstanceGraphRecord(
        source_instance_id=source_instance_id,
        category=category,
        difficulty=difficulty,
        fold=fold,
        role=role,
        graph_path=Path("/machine-specific") / f"{source_instance_id}.pt",
        provenance_path=(
            Path("/machine-specific") / f"{source_instance_id}.provenance.json"
        ),
        label_source="solutions.pickle.gz",
        mip_gap=(
            0.0
            if mip_gap_band == "optimal_tolerance"
            else 0.05
            if mip_gap_band == "gap_le_10pct"
            else 0.5
        ),
        mip_gap_band=mip_gap_band,
    )


def _audit(
    *,
    label_policy: str = "optimal_only",
    manifest_size: int = 3,
    discovered_graphs: int = 3,
    eligible: tuple[InstanceGraphRecord, ...] | None = None,
    invalid: tuple[InvalidInstance, ...] = (),
) -> InstanceDatasetAudit:
    records = eligible or (
        _record("CFL_easy_instance_0", role="test", fold=0, difficulty="easy"),
        _record(
            "CFL_medium_instance_0",
            role="validation",
            fold=1,
            difficulty="medium",
        ),
        _record("CFL_hard_instance_0", role="train", fold=2, difficulty="hard"),
    )
    return InstanceDatasetAudit(
        dataset_root=Path("/machine-specific"),
        manifest_size=manifest_size,
        rotation=0,
        label_policy=label_policy,
        graph_hashes_verified=True,
        discovered_graphs=discovered_graphs,
        eligible=records,
        excluded=(),
        missing=(),
        invalid=invalid,
    )


def test_complete_optimal_audit_is_scientifically_eligible() -> None:
    plan = validate_instance_training_audit(_audit(), development_only=False)
    assert plan.scientific_reporting_eligible is True
    assert len(plan.contract_sha256) == 64
    assert plan.to_summary()["test_partition_usage"] == (
        "held_out_not_loaded_during_training"
    )


def test_partial_inventory_requires_explicit_development_mode() -> None:
    partial = _audit(manifest_size=90, discovered_graphs=3)
    with pytest.raises(InstanceTrainingPlanError, match="partial inventory"):
        validate_instance_training_audit(partial, development_only=False)

    plan = validate_instance_training_audit(partial, development_only=True)
    assert plan.scientific_reporting_eligible is False
    assert "development_only_training" in plan.to_summary()["warnings"]


def test_all_available_policy_requires_development_mode() -> None:
    records = (
        _record("CFL_easy_instance_0", role="test", fold=0),
        _record("CFL_easy_instance_1", role="validation", fold=1),
        _record(
            "CFL_medium_instance_0",
            role="train",
            fold=2,
            difficulty="medium",
            mip_gap_band="gap_gt_40pct",
        ),
    )
    audit = _audit(label_policy="all_available", eligible=records)
    with pytest.raises(InstanceTrainingPlanError, match="non-optimal labels"):
        validate_instance_training_audit(audit, development_only=False)
    assert (
        validate_instance_training_audit(audit, development_only=True)
        .audit.label_policy
        == "all_available"
    )


def test_invalid_graph_contract_always_fails_closed() -> None:
    invalid = InvalidInstance(
        source_instance_id="CFL_easy_instance_0",
        relative_graph_path="CFL_easy_instance/processed/bad.pt",
        reason="graph SHA-256 mismatch",
    )
    with pytest.raises(InstanceTrainingPlanError, match="SHA-256 mismatch"):
        validate_instance_training_audit(
            _audit(invalid=(invalid,)),
            development_only=True,
        )


def test_training_plan_report_is_path_sanitized_and_partitions_are_disjoint() -> None:
    plan = validate_instance_training_audit(_audit(), development_only=False)
    summary = plan.to_summary()
    rendered = str(summary)
    assert "/machine-specific" not in rendered
    partitions = summary["partitions"]
    ids = [set(partitions[role]["instances"]) for role in partitions]
    assert not ids[0] & ids[1]
    assert not ids[0] & ids[2]
    assert not ids[1] & ids[2]


def test_instance_serial_entrypoint_keeps_test_partition_held_out() -> None:
    project_root = Path(__file__).resolve().parents[2]
    trainer = (
        project_root / "src" / "cfl_gnn" / "training" / "instance_serial.py"
    ).read_text(encoding="utf-8")
    assert "random_split" not in trainer
    assert 'ParentInstanceDataset(plan.records_for_role("train"))' in trainer
    assert 'ParentInstanceDataset(plan.records_for_role("validation"))' in trainer
    assert 'ParentInstanceDataset(plan.records_for_role("test"))' not in trainer
    assert "Heavy ML imports remain behind" in trainer


def test_existing_graph_confirmation_inventory_is_exact() -> None:
    records = tuple(
        _record(
            f"CFL_easy_instance_{index}",
            role=("test", "validation", "train")[index % 3],
            fold=index % 3,
            difficulty="easy",
        )
        for index in range(30)
    ) + tuple(
        _record(
            f"CFL_medium_instance_{index}",
            role=("test", "validation", "train")[index % 3],
            fold=index % 3,
            difficulty="medium",
        )
        for index in range(15)
    )
    plan = validate_instance_training_audit(
        _audit(
            label_policy="all_available",
            manifest_size=90,
            discovered_graphs=45,
            eligible=records,
        ),
        development_only=True,
    )
    args = argparse.Namespace(
        expected_graphs=45,
        expected_discovered_graphs=45,
        expected_easy_graphs=30,
        expected_medium_graphs=15,
        expected_hard_graphs=0,
        maximum_label_mip_gap=0.1,
    )
    gate = _validate_expected_inventory(args, plan)
    assert gate["gate_status"] == "passed"
    assert gate["observed_by_difficulty"] == {
        "easy": 30,
        "medium": 15,
        "hard": 0,
    }


def test_existing_graph_confirmation_rejects_inventory_drift() -> None:
    plan = validate_instance_training_audit(
        _audit(manifest_size=90, discovered_graphs=3),
        development_only=True,
    )
    args = argparse.Namespace(
        expected_graphs=45,
        expected_discovered_graphs=45,
        expected_easy_graphs=30,
        expected_medium_graphs=15,
        expected_hard_graphs=0,
        maximum_label_mip_gap=0.1,
    )
    with pytest.raises(ValueError, match="confirmation cohort"):
        _validate_expected_inventory(args, plan)


def test_existing_graph_confirmation_rejects_label_above_gap_ceiling() -> None:
    records = (
        _record("CFL_easy_instance_0", role="test", fold=0),
        _record("CFL_easy_instance_1", role="validation", fold=1),
        InstanceGraphRecord(
            source_instance_id="CFL_medium_instance_0",
            category="CFL_medium_instance",
            difficulty="medium",
            fold=2,
            role="train",
            graph_path=Path("/machine-specific/medium.pt"),
            provenance_path=Path("/machine-specific/medium.provenance.json"),
            label_source="incumbents.parquet",
            mip_gap=0.11,
            mip_gap_band="gap_le_20pct",
        ),
    )
    plan = validate_instance_training_audit(
        _audit(
            label_policy="all_available",
            manifest_size=90,
            discovered_graphs=3,
            eligible=records,
        ),
        development_only=True,
    )
    args = argparse.Namespace(
        expected_graphs=None,
        expected_discovered_graphs=None,
        expected_easy_graphs=None,
        expected_medium_graphs=None,
        expected_hard_graphs=None,
        maximum_label_mip_gap=0.1,
    )
    with pytest.raises(ValueError, match="confirmation cohort"):
        _validate_expected_inventory(args, plan)

    gate = _validate_expected_inventory(args, plan, fail_closed=False)
    assert gate["gate_status"] == "failed"
    assert gate["failed_checks"] == ["all_labels_within_maximum_mip_gap"]
    assert gate["inadmissible_label_gaps"] == [
        {
            "source_instance_id": "CFL_medium_instance_0",
            "mip_gap_relative": 0.11,
        }
    ]


def test_gap_le_ten_percent_policy_is_explicit_and_development_only() -> None:
    records = (
        _record("CFL_easy_instance_0", role="test", fold=0),
        _record("CFL_easy_instance_1", role="validation", fold=1),
        _record(
            "CFL_medium_instance_0",
            role="train",
            fold=2,
            difficulty="medium",
            mip_gap_band="gap_le_10pct",
        ),
    )
    audit = _audit(label_policy="gap_le_10pct", eligible=records)
    with pytest.raises(InstanceTrainingPlanError, match="non-optimal labels"):
        validate_instance_training_audit(audit, development_only=False)
    plan = validate_instance_training_audit(audit, development_only=True)
    assert plan.audit.label_policy == "gap_le_10pct"
