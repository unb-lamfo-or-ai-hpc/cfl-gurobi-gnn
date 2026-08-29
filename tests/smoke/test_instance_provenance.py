"""Dependency-free tests for parent-instance provenance and label quality."""

import hashlib
import json

import pytest

from cfl_gnn.graph.instance_provenance import (
    load_verified_graph_provenance,
    mip_gap_band,
    provenance_path,
    resolve_raw_instance_path,
    sha256_file,
    summarize_label_quality,
)


def write_verified_fixture(tmp_path):
    artifacts = {}
    for name in ("graph.pt", "raw.lp.gz", "features.gz", "metadata.json", "label.gz"):
        path = tmp_path / name
        path.write_bytes(name.encode("utf-8"))
        artifacts[name] = path
    result = {
        "schema_version": 1,
        "instance": "CFL_easy_instance_0",
        "fold": 0,
        "graph_sha256": sha256_file(artifacts["graph.pt"]),
        "structure_provenance": {
            "raw_instance_path": str(artifacts["raw.lp.gz"]),
            "raw_instance_sha256": sha256_file(artifacts["raw.lp.gz"]),
            "feature_artifact_path": str(artifacts["features.gz"]),
            "feature_artifact_sha256": sha256_file(artifacts["features.gz"]),
        },
        "collection_provenance": {
            "artifact_path": str(artifacts["metadata.json"]),
            "artifact_sha256": sha256_file(artifacts["metadata.json"]),
        },
        "context_provenance": {
            "artifact": None,
            "artifact_path": None,
            "artifact_sha256": None,
        },
        "label_provenance": {
            "artifact_path": str(artifacts["label.gz"]),
            "artifact_sha256": sha256_file(artifacts["label.gz"]),
        },
    }
    provenance_path(artifacts["graph.pt"]).write_text(
        json.dumps(result), encoding="utf-8"
    )
    return artifacts


def test_sha256_file_hashes_the_persisted_bytes(tmp_path) -> None:
    artifact = tmp_path / "instance.lp.gz"
    artifact.write_bytes(b"persisted compressed bytes")
    assert sha256_file(artifact) == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_raw_instance_falls_back_to_canonical_source_root(tmp_path) -> None:
    instance_id = "CFL_easy_instance_0"
    raw_path = tmp_path / "CFL_easy_instance" / "LP" / f"{instance_id}.lp.gz"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"lp")

    resolved = resolve_raw_instance_path(
        {"lp_file": "/stale/machine/path/CFL_easy_instance_0.lp.gz"},
        source_root=tmp_path,
        category="CFL_easy_instance",
        source_instance_id=instance_id,
    )
    assert resolved == raw_path.resolve()


def test_raw_instance_resolution_fails_closed(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="raw MILPBench instance"):
        resolve_raw_instance_path(
            {},
            source_root=tmp_path,
            category="CFL_easy_instance",
            source_instance_id="CFL_easy_instance_0",
        )


def test_existing_graph_is_reused_only_when_all_hashes_match(tmp_path) -> None:
    artifacts = write_verified_fixture(tmp_path)
    result = load_verified_graph_provenance(
        artifacts["graph.pt"],
        expected_instance="CFL_easy_instance_0",
        expected_fold=0,
        current_relaxation_path=tmp_path / "node_relaxations.parquet",
    )
    assert result is not None

    artifacts["label.gz"].write_bytes(b"changed label artifact")
    assert (
        load_verified_graph_provenance(
            artifacts["graph.pt"],
            expected_instance="CFL_easy_instance_0",
            expected_fold=0,
            current_relaxation_path=tmp_path / "node_relaxations.parquet",
        )
        is None
    )


def test_new_root_relaxation_invalidates_a_zero_fallback_graph(tmp_path) -> None:
    artifacts = write_verified_fixture(tmp_path)
    relaxation_path = tmp_path / "node_relaxations.parquet"
    relaxation_path.write_bytes(b"new context")
    assert (
        load_verified_graph_provenance(
            artifacts["graph.pt"],
            expected_instance="CFL_easy_instance_0",
            expected_fold=0,
            current_relaxation_path=relaxation_path,
        )
        is None
    )


@pytest.mark.parametrize(
    ("gap", "expected"),
    [
        (0.0, "optimal_tolerance"),
        (1e-4, "optimal_tolerance"),
        (0.10, "gap_le_10pct"),
        (0.40, "gap_le_40pct"),
        (0.41, "gap_gt_40pct"),
        (None, "unknown"),
        (float("nan"), "unknown"),
    ],
)
def test_mip_gap_bands_are_explicit(gap, expected) -> None:
    assert mip_gap_band(gap) == expected


def test_label_quality_summary_includes_generated_and_reused_graphs() -> None:
    results = [
        {
            "status": "generated",
            "label_provenance": {
                "artifact": "solutions.pickle.gz",
                "mip_gap_band": "optimal_tolerance",
            },
        },
        {
            "status": "skipped_existing",
            "label_provenance": {
                "artifact": "incumbents.parquet",
                "mip_gap_band": "gap_gt_40pct",
            },
        },
    ]
    assert summarize_label_quality(results) == {
        "by_artifact": {
            "incumbents.parquet": 1,
            "solutions.pickle.gz": 1,
        },
        "by_mip_gap_band": {
            "gap_gt_40pct": 1,
            "optimal_tolerance": 1,
        },
    }
