"""Dependency-free tests for parent-instance graph consumption."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from cfl_gnn.cli.audit_instance_training_split import main as audit_main
from cfl_gnn.graph.instance_dataset import (
    ParentInstanceDataset,
    validate_loaded_graph,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.splits.instance_folds import build_planned_manifest, write_manifest
from cfl_gnn.splits.instance_partitions import (
    InstanceDatasetContractError,
    InstanceGraphRecord,
    assert_no_partition_leakage,
    audit_instance_dataset,
)


def _entry_for_fold(entries, fold):
    return next(
        entry
        for entry in entries
        if entry.category == "CFL_easy_instance" and entry.fold == fold
    )


def _write_graph(
    root: Path, entry, *, gap: float | None = 0.0, schema: int = 2
) -> Path:
    graph_path = (
        root
        / entry.category
        / "processed"
        / f"{entry.source_instance_id}.pt"
    )
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_bytes(f"graph:{entry.source_instance_id}".encode("utf-8"))
    if gap is None:
        band = "unknown"
    elif gap <= 1e-4:
        band = "optimal_tolerance"
    elif gap <= 0.10:
        band = "gap_le_10pct"
    elif gap <= 0.40:
        band = "gap_le_40pct"
    else:
        band = "gap_gt_40pct"
    sidecar = {
        "schema_version": schema,
        "instance": entry.source_instance_id,
        "fold": entry.fold,
        "parent_category": entry.category,
        "sampling_strategy": "parent_instance_best_available",
        "objective_sense": "MINIMIZE",
        "label_source": "solutions.pickle.gz",
        "label_provenance": {
            "artifact": "solutions.pickle.gz",
            "mip_gap": gap,
            "mip_gap_band": band,
        },
        "candidate_audit": {"selected_artifact": "solutions.pickle.gz"},
        "graph_sha256": sha256_file(graph_path),
    }
    graph_path.with_suffix(".provenance.json").write_text(
        json.dumps(sidecar), encoding="utf-8"
    )
    return graph_path


def test_partial_inventory_uses_canonical_roles_without_reassignment(
    tmp_path: Path,
) -> None:
    manifest = build_planned_manifest()
    for fold in range(5):
        _write_graph(tmp_path, _entry_for_fold(manifest, fold))

    audit = audit_instance_dataset(
        tmp_path,
        manifest,
        rotation=0,
        label_policy="optimal_only",
    )
    assert audit.discovered_graphs == 5
    assert len(audit.missing) == 85
    assert len(audit.records_for_role("train")) == 3
    assert len(audit.records_for_role("validation")) == 1
    assert len(audit.records_for_role("test")) == 1
    assert audit.contract_valid
    assert audit.to_summary()["population_status"] == "development_partial"
    assert_no_partition_leakage(audit.eligible)


def test_label_policy_excludes_high_gap_without_hiding_it(tmp_path: Path) -> None:
    manifest = build_planned_manifest()
    selected = [_entry_for_fold(manifest, fold) for fold in range(5)]
    for index, entry in enumerate(selected):
        _write_graph(tmp_path, entry, gap=0.75 if index == 0 else 0.0)

    strict = audit_instance_dataset(
        tmp_path,
        manifest,
        rotation=0,
        label_policy="optimal_only",
    )
    assert len(strict.eligible) == 4
    assert len(strict.excluded) == 1
    assert strict.excluded[0].mip_gap_band == "gap_gt_40pct"
    assert strict.to_summary()["excluded_by_label_policy"] == 1

    development = audit_instance_dataset(
        tmp_path,
        manifest,
        rotation=0,
        label_policy="all_available",
    )
    assert len(development.eligible) == 5
    assert "non_optimal_labels_development_only" in development.to_summary()[
        "warnings"
    ]


def test_current_42_instance_evidence_has_expected_rotation_zero_counts(
    tmp_path: Path,
) -> None:
    manifest = build_planned_manifest()
    available_ids = {
        *(f"CFL_easy_instance_{index}" for index in range(30)),
        *(f"CFL_medium_instance_{index}" for index in range(7)),
        *(f"CFL_medium_instance_{index}" for index in range(15, 20)),
    }
    for entry in manifest:
        if entry.source_instance_id in available_ids:
            gap = 0.0 if entry.difficulty == "easy" else 0.75
            _write_graph(tmp_path, entry, gap=gap)

    strict = audit_instance_dataset(
        tmp_path,
        manifest,
        rotation=0,
        label_policy="optimal_only",
    ).to_summary()
    assert strict["eligible_graphs"] == 30
    assert strict["excluded_by_label_policy"] == 12
    assert {
        role: strict["partitions"][role]["total"]
        for role in ("train", "validation", "test")
    } == {"train": 18, "validation": 6, "test": 6}

    development = audit_instance_dataset(
        tmp_path,
        manifest,
        rotation=0,
        label_policy="all_available",
    ).to_summary()
    assert development["eligible_graphs"] == 42
    assert {
        role: development["partitions"][role]["total"]
        for role in ("train", "validation", "test")
    } == {"train": 24, "validation": 10, "test": 8}


def test_stale_sidecar_and_hash_mismatch_fail_closed(tmp_path: Path) -> None:
    manifest = build_planned_manifest()
    stale_entry = _entry_for_fold(manifest, 0)
    corrupt_entry = _entry_for_fold(manifest, 1)
    _write_graph(tmp_path, stale_entry, schema=1)
    corrupt_path = _write_graph(tmp_path, corrupt_entry)
    corrupt_path.write_bytes(b"changed-after-sidecar")

    audit = audit_instance_dataset(tmp_path, manifest, rotation=0)
    reasons = {item.source_instance_id: item.reason for item in audit.invalid}
    assert "schema_version mismatch" in reasons[stale_entry.source_instance_id]
    assert reasons[corrupt_entry.source_instance_id] == "graph SHA-256 mismatch"
    assert not audit.contract_valid


def test_unknown_gap_is_valid_provenance_but_never_training_eligible(
    tmp_path: Path,
) -> None:
    manifest = build_planned_manifest()
    entry = _entry_for_fold(manifest, 0)
    _write_graph(tmp_path, entry, gap=None)

    for policy in ("optimal_only", "all_available"):
        audit = audit_instance_dataset(
            tmp_path,
            manifest,
            rotation=0,
            label_policy=policy,
        )
        assert not audit.invalid
        assert not audit.eligible
        assert audit.excluded[0].mip_gap_band == "unknown"


def test_unplanned_graph_and_orphan_sidecar_are_reported(tmp_path: Path) -> None:
    manifest = build_planned_manifest()
    unplanned = tmp_path / "CFL_easy_instance" / "processed" / "data_0.pt"
    unplanned.parent.mkdir(parents=True)
    unplanned.write_bytes(b"legacy")
    orphan = unplanned.parent / "CFL_easy_instance_1.provenance.json"
    orphan.write_text("{}", encoding="utf-8")

    audit = audit_instance_dataset(tmp_path, manifest, rotation=0)
    reasons = [item.reason for item in audit.invalid]
    assert "graph is not present in the canonical manifest" in reasons
    assert "orphan provenance sidecar without graph" in reasons
    assert audit.discovered_graphs == 1


def test_loaded_graph_metadata_is_cross_checked() -> None:
    record = InstanceGraphRecord(
        source_instance_id="CFL_easy_instance_0",
        category="CFL_easy_instance",
        difficulty="easy",
        fold=2,
        role="train",
        graph_path=Path("graph.pt"),
        provenance_path=Path("graph.provenance.json"),
        label_source="solutions.pickle.gz",
        mip_gap=0.0,
        mip_gap_band="optimal_tolerance",
    )
    graph = SimpleNamespace(
        source_instance_id=record.source_instance_id,
        instance_fold=record.fold,
        parent_category=record.category,
        label_source=record.label_source,
        label_mip_gap_band=record.mip_gap_band,
    )
    validate_loaded_graph(graph, record)
    graph.instance_fold = 4
    with pytest.raises(ValueError, match="instance_fold"):
        validate_loaded_graph(graph, record)


def test_parent_instance_dataset_loads_only_audited_records(monkeypatch) -> None:
    record = InstanceGraphRecord(
        source_instance_id="CFL_easy_instance_0",
        category="CFL_easy_instance",
        difficulty="easy",
        fold=2,
        role="train",
        graph_path=Path("graph.pt"),
        provenance_path=Path("graph.provenance.json"),
        label_source="solutions.pickle.gz",
        mip_gap=0.0,
        mip_gap_band="optimal_tolerance",
    )
    graph = SimpleNamespace(
        source_instance_id=record.source_instance_id,
        instance_fold=record.fold,
        parent_category=record.category,
        label_source=record.label_source,
        label_mip_gap_band=record.mip_gap_band,
    )
    calls = []

    def fake_load(path, *, weights_only):
        calls.append((path, weights_only))
        return graph

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(load=fake_load))
    dataset = ParentInstanceDataset([record])
    assert len(dataset) == 1
    assert dataset.source_instance_ids == (record.source_instance_id,)
    assert dataset[0] is graph
    assert calls == [(record.graph_path, False)]


def test_explicit_leakage_guard_rejects_repeated_parent() -> None:
    base = dict(
        source_instance_id="CFL_easy_instance_0",
        category="CFL_easy_instance",
        difficulty="easy",
        fold=0,
        graph_path=Path("graph.pt"),
        provenance_path=Path("graph.provenance.json"),
        label_source="solutions.pickle.gz",
        mip_gap=0.0,
        mip_gap_band="optimal_tolerance",
    )
    records = [
        InstanceGraphRecord(role="train", **base),
        InstanceGraphRecord(role="test", **base),
    ]
    with pytest.raises(InstanceDatasetContractError, match="leakage"):
        assert_no_partition_leakage(records)


def test_cli_writes_sanitized_report_without_loading_torch(tmp_path: Path) -> None:
    manifest = build_planned_manifest()
    manifest_path = tmp_path / "folds.csv"
    write_manifest(manifest_path, manifest)
    for fold in range(5):
        _write_graph(tmp_path / "graphs", _entry_for_fold(manifest, fold))
    report_path = tmp_path / "audit.json"

    exit_code = audit_main(
        [
            "--manifest",
            str(manifest_path),
            "--base_pyg_dir",
            str(tmp_path / "graphs"),
            "--rotation",
            "0",
            "--report",
            str(report_path),
        ]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["contract_valid"] is True
    assert "dataset_root" not in report
    assert report["partitions"]["train"]["total"] == 3
