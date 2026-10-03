import json
from pathlib import Path
import pytest
from cfl_gnn.pipelines.confirmation_campaign import audit_confirmation, COHORT
from cfl_gnn.graph.instance_provenance import sha256_file


def test_frozen_42_inventory_preserves_inadmissible_mediums(tmp_path):
    for identity in COHORT:
        category = identity.rsplit("_", 1)[0]
        graph = tmp_path / "graphs" / category / "processed" / f"{identity}.pt"
        graph.parent.mkdir(parents=True, exist_ok=True)
        graph.write_bytes(b"fixture_not_deserialized")
        graph.with_suffix(".provenance.json").write_text(json.dumps({
            "graph_sha256": sha256_file(graph), "label_provenance": {"mip_gap": .5 if "medium" in identity else 0.},
            "context_provenance": {"mode": "root_node_relaxation"}}))
    report = audit_confirmation(graph_dir=tmp_path / "graphs",
        parent_manifest=Path(__file__).resolve().parents[2] / "configs/splits/cfl_90_seed42_folds.csv",
        output_dir=tmp_path / "audit")
    assert report["counts"] == {"planned": 42, "discovered": 42, "gap_admissible": 30}
    assert report["partition_population"] == {"train": 24, "validation": 10, "test": 8}
    assert len(report["repair_parent_ids"]) == 12
    assert not report["training_ready"]
    assert not report["scientific_reporting_eligible"]
    assert str(tmp_path) not in json.dumps(report)


def test_v2_protocol_is_versioned_not_a_silent_legacy_rewrite():
    from cfl_gnn.training.gasse_reconnected import load_protocol, git_blob_sha1, LEGACY_GASSE_GIT_BLOB_SHA1
    root = Path(__file__).resolve().parents[2]
    protocol = load_protocol(root / "configs/training/gasse_confirmation_v2.json")
    assert protocol["architecture"]["model_version"] == "gasse_v2_alternating_prenorm"
    assert protocol["optimization"]["epochs"] == protocol["optimization"]["patience"] == 100
    assert git_blob_sha1(root / "src/cfl_gnn/models/gasse.py") == LEGACY_GASSE_GIT_BLOB_SHA1
