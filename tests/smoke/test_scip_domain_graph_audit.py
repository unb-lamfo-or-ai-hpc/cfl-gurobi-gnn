"""Dependency-light tests for SCIP domain-variant graph observability."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from cfl_gnn.analysis import scip_domain_graph_audit as audit


def _snapshot(
    *,
    file_name: str,
    lower_bounds: list[float],
    upper_bounds: list[float],
    encoded_bounds: list[tuple[float, float]],
    topology: str = "topology",
    matrix: str = "matrix",
    objective: str = "objective",
) -> dict[str, object]:
    variable_x = np.zeros((len(lower_bounds), 7), dtype=np.float32)
    variable_x[:, 1] = [value[0] for value in encoded_bounds]
    variable_x[:, 2] = [value[1] for value in encoded_bounds]
    variable_x[:, 5] = 1.0
    feature_hash = audit._tensor_sha256(
        [f"x{index}" for index in range(len(lower_bounds))],
        audit.VARIABLE_FEATURE_NAMES,
        variable_x,
    )
    graph_hash = audit._canonical_sha256(
        {
            "topology": topology,
            "variable_features": feature_hash,
            "constraint_features": "constraints",
        }
    )
    return {
        "file_name": file_name,
        "artifact_sha256": audit._canonical_sha256(file_name),
        "signature": {"rows": 1, "columns": len(lower_bounds), "nonzeros": 2},
        "formulation_fingerprints": {
            "matrix_sha256": matrix,
            "objective_sha256": objective,
            "domain_sha256": audit._canonical_sha256(
                [lower_bounds, upper_bounds]
            ),
            "formulation_sha256": audit._canonical_sha256(
                [matrix, objective, lower_bounds, upper_bounds]
            ),
        },
        "graph_fingerprints": {
            "topology_sha256": topology,
            "variable_features_sha256": feature_hash,
            "constraint_features_sha256": "constraints",
            "complete_graph_sha256": graph_hash,
        },
        "_variable_names": [f"x{index}" for index in range(len(lower_bounds))],
        "_variable_types": np.asarray(["I"] * len(lower_bounds)),
        "_lower_bounds": np.asarray(lower_bounds, dtype=np.float64),
        "_upper_bounds": np.asarray(upper_bounds, dtype=np.float64),
        "_variable_x": variable_x,
    }


def test_plan_is_deterministic_and_path_sanitized(tmp_path: Path) -> None:
    root = tmp_path / "root_mip_baseline.lp"
    node = tmp_path / "node_000_2_mip.lp"
    root.write_text("root", encoding="utf-8")
    node.write_text("node", encoding="utf-8")

    first = audit.build_audit_plan(
        root_mip=root, node_mips=[node], output_dir=tmp_path / "one"
    )
    second = audit.build_audit_plan(
        root_mip=root, node_mips=[node], output_dir=tmp_path / "two"
    )

    assert first.contract_sha256 == second.contract_sha256
    serialized = json.dumps(first.to_summary())
    assert str(tmp_path) not in serialized
    assert first.to_summary()["eligibility"] == {
        "dataset_eligible": False,
        "label_eligible": False,
    }
    assert len(first.to_summary()["graph_builder_source_sha256"]) == 64


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BINARY", "B"),
        ("B", "B"),
        ("INTEGER", "I"),
        ("IMPLINT", "I"),
        ("CONTINUOUS", "C"),
        ("C", "C"),
    ],
)
def test_variable_type_normalization(raw: str, expected: str) -> None:
    assert audit.normalize_variable_type(raw) == expected


def test_unknown_variable_type_fails_closed() -> None:
    with pytest.raises(audit.GraphObservabilityAuditError):
        audit.normalize_variable_type("SEMICONTINUOUS")


def test_domain_change_survives_encoding_with_same_topology() -> None:
    root = _snapshot(
        file_name="root.lp",
        lower_bounds=[0.0, 0.0],
        upper_bounds=[1.0, 1.0],
        encoded_bounds=[(0.0, 0.6931472), (0.0, 0.6931472)],
    )
    candidate = _snapshot(
        file_name="node.lp",
        lower_bounds=[0.0, 1.0],
        upper_bounds=[1.0, 1.0],
        encoded_bounds=[(0.0, 0.6931472), (0.6931472, 0.6931472)],
    )

    result = audit.compare_graph_snapshots(root, candidate)

    assert result["gate_status"] == "passed"
    assert result["reason_code"] == "domain_difference_observed_in_graph_features"
    assert result["raw_bound_change_count"] == 1
    assert result["encoded_bound_change_count"] == 1
    assert result["topology_same_as_root"] is True
    assert result["node_features_distinct_from_root"] is True
    assert result["graph_distinct_from_root"] is True
    assert result["dataset_eligible"] is False
    assert result["label_eligible"] is False


def test_raw_domain_change_lost_by_encoding_fails() -> None:
    root = _snapshot(
        file_name="root.lp",
        lower_bounds=[70_000.0],
        upper_bounds=[100_000.0],
        encoded_bounds=[(11.002117, 11.002117)],
    )
    candidate = _snapshot(
        file_name="node.lp",
        lower_bounds=[80_000.0],
        upper_bounds=[100_000.0],
        encoded_bounds=[(11.002117, 11.002117)],
    )

    result = audit.compare_graph_snapshots(root, candidate)

    assert result["gate_status"] == "failed"
    assert result["reason_code"] == "raw_domain_change_lost_in_graph_encoding"
    assert result["lost_raw_domain_change_count"] == 1


def test_domain_only_candidate_cannot_change_topology() -> None:
    root = _snapshot(
        file_name="root.lp",
        lower_bounds=[0.0],
        upper_bounds=[1.0],
        encoded_bounds=[(0.0, 0.6931472)],
    )
    candidate = _snapshot(
        file_name="node.lp",
        lower_bounds=[1.0],
        upper_bounds=[1.0],
        encoded_bounds=[(0.6931472, 0.6931472)],
        topology="different-topology",
    )

    result = audit.compare_graph_snapshots(root, candidate)

    assert result["gate_status"] == "failed"
    assert result["reason_code"] == "graph_structure_changed_for_domain_only_candidate"


def test_sibling_graph_fingerprint_collision_fails_overall_gate() -> None:
    candidate = {
        "gate_status": "passed",
        "raw_bound_change_count": 1,
        "encoded_bound_change_count": 1,
        "lost_raw_domain_change_count": 0,
        "formulation_fingerprints": {"formulation_sha256": "formulation-a"},
        "graph_fingerprints": {"complete_graph_sha256": "graph-a"},
    }
    collision = {
        **candidate,
        "formulation_fingerprints": {"formulation_sha256": "formulation-b"},
    }

    summary = audit.summarize_candidate_results([candidate, collision])

    assert summary["gate_passed"] is False
    assert summary["unique_formulations"] == 2
    assert summary["unique_graphs"] == 1
    assert summary["reason_code"] == "candidate_graph_fingerprint_collision"


def test_dry_run_does_not_import_solver_or_graph_stack(tmp_path: Path) -> None:
    root = tmp_path / "root.lp"
    node = tmp_path / "node.lp"
    root.write_text("root", encoding="utf-8")
    node.write_text("node", encoding="utf-8")
    output = tmp_path / "output"

    result = audit.main(
        [
            "--root_mip",
            str(root),
            "--node_mips",
            str(node),
            "--output_dir",
            str(output),
            "--dry_run",
        ]
    )

    assert result == 0
    assert (output / audit.PLAN_NAME).is_file()
    assert "pyscipopt" not in audit.__dict__
    assert "torch" not in audit.__dict__


def test_invalid_plan_inputs_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "root.lp"
    root.write_text("root", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one"):
        audit.build_audit_plan(root_mip=root, node_mips=[], output_dir=tmp_path)
    with pytest.raises(ValueError, match="cannot also"):
        audit.build_audit_plan(
            root_mip=root, node_mips=[root], output_dir=tmp_path
        )


def test_source_has_no_dataset_integration_or_pyomo() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")
    assert "import pyomo" not in source
    assert "from pyomo" not in source
    assert "torch.save" not in source
    assert '"dataset_eligible": False' in source
    assert '"label_eligible": False' in source
