from __future__ import annotations

import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines import gurobi_derived_training_dataset as pipeline
from cfl_gnn.training.gasse_reconnected import (
    canonical_sha256,
    validate_training_plan,
)


def _original_plan(tmp_path: Path, solver: str) -> tuple[dict, Path, Path]:
    graph_root = tmp_path / "parent-graphs"
    label_root = tmp_path / "parent-labels"
    graph = graph_root / "graphs" / "parent.pt"
    root = graph_root / "roots" / "parent.root.json.gz"
    label = label_root / "runs" / solver / "parent.solution.json.gz"
    graph.parent.mkdir(parents=True, exist_ok=True)
    root.parent.mkdir(parents=True, exist_ok=True)
    label.parent.mkdir(parents=True, exist_ok=True)
    graph.write_bytes(b"parent-graph")
    root.write_bytes(b"parent-root")
    label.write_bytes(f"parent-label-{solver}".encode())
    record = {
        "sample_id": "CFL_easy_instance_2",
        "parent_instance_id": "CFL_easy_instance_2",
        "source_instance_id": "CFL_easy_instance_2",
        "category": "CFL_easy_instance",
        "difficulty": "easy",
        "fold": 2,
        "role": "train",
        "sampling_strategy": "original",
        "mip_sha256": "a" * 64,
        "graph_relative_path": "graphs/parent.pt",
        "graph_sha256": sha256_file(graph),
        "root_relative_path": "roots/parent.root.json.gz",
        "root_sha256": sha256_file(root),
        "graph_authority": "gurobi",
        "label_solver": solver,
        "label_contract_sha256": "b" * 64,
        "label_run_relative_path": f"runs/{solver}",
        "label_file_name": label.name,
        "label_sha256": sha256_file(label),
        "label_mip_gap_relative": 0.0,
        "label_objective": 6.5,
        "label_execution_time_seconds": 10.0,
    }
    contract = {
        "schema_version": 1,
        "dataset_variant": "fixture",
        "graph_dataset_contract_sha256": "c" * 64,
        "parent_collection_contract_sha256": "d" * 64,
        "graph_identity": "one_graph_per_mathematical_mip",
        "graph_authority": "gurobi",
        "label_solver": solver,
        "label_view": "named_solution_overlay_at_load_time",
        "legacy_gasse_git_blob_sha1": "e2937ebcca149f8a99ec437c3c8e7fd31e49438b",
        "implementation_sha256": {},
        "protocol": {
            "sampling": {"draws_per_parent_per_epoch": 4},
        },
        "protocol_sha256": "e" * 64,
        "records": [record],
        "excluded_records": [],
        "partition_counts": {"train": 1, "validation": 0, "test": 0},
        "parent_ids_by_role": {
            "train": ["CFL_easy_instance_2"],
            "validation": [],
            "test": [],
        },
        "test_partition_usage": "held_out_not_loaded_during_training",
        "allow_partial_smoke": True,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "training_ready": False,
        "engineering_smoke_ready": True,
        "held_out_evaluation_ready": False,
        "warnings": ["partial_partition_inventory_engineering_smoke_only"],
        "next_gate": "gasse_train_only_engineering_smoke",
    }, graph_root, label_root


def _derived_spec(tmp_path: Path, solver: str, radius: int) -> SimpleNamespace:
    candidate = tmp_path / f"{solver}-candidate-{radius}.lp"
    solution = tmp_path / f"{solver}-solution-{radius}.json.gz"
    candidate.write_text(f"derived-{solver}-{radius}", encoding="utf-8")
    candidate_sha = sha256_file(candidate)
    with gzip.open(solution, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "candidate_sha256": candidate_sha,
                "solution_source": {
                    "gurobi": "independent_gurobi_optimization",
                    "scip": "independent_pyscipopt_optimization",
                }[solver],
                "variables": [{"name": "x", "value": 1.0}],
            },
            stream,
        )
    sample_id = f"CFL_easy_instance_2__{solver}__lb_r{radius}"
    payload = {
        "solver": solver,
        "sample_id": sample_id,
        "parent_instance_id": "CFL_easy_instance_2",
        "candidate": {"file_name": candidate.name, "sha256": candidate_sha},
    }
    return SimpleNamespace(
        solver=solver,
        sample_id=sample_id,
        parent_instance_id="CFL_easy_instance_2",
        category="CFL_easy_instance",
        difficulty="easy",
        fold=2,
        candidate_path=candidate,
        candidate_sha256=candidate_sha,
        solution_path=solution,
        solution_sha256=sha256_file(solution),
        derived_solve_contract_sha256=f"{solver[0]}" * 64,
        label_mip_gap_relative=0.0,
        label_objective=6.4,
        label_execution_time_seconds=20.0,
        source_incumbent_id=f"{solver}:center",
        source_incumbent_artifact_sha256="f" * 64,
        radius=radius,
        radius_fraction=0.001,
        contract_payload=lambda: payload,
    )


def _prepared(tmp_path: Path) -> tuple[pipeline.PreparedDataset, Path, Path]:
    gurobi, graph_root, label_root = _original_plan(tmp_path, "gurobi")
    scip, _, _ = _original_plan(tmp_path, "scip")
    samples = (
        _derived_spec(tmp_path, "gurobi", 148),
        _derived_spec(tmp_path, "scip", 148),
    )
    source_plan = SimpleNamespace(samples=samples, contract_sha256="1" * 64)
    contract = {
        "schema_version": 1,
        "dataset_variant": "fixture",
        "graph_authority": "gurobi",
        "root_lp_contract": {
            "time_limit_seconds": 60.0,
            "zero_fallback_allowed": False,
        },
    }
    plan = {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "summary": {"derived_graphs_planned": 2},
        "next_gate": "execution",
    }
    return (
        pipeline.PreparedDataset(
            plan=plan,
            source_plan=source_plan,
            original_plans={"gurobi": gurobi, "scip": scip},
        ),
        graph_root,
        label_root,
    )


def test_execution_packages_four_valid_training_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, graph_root, label_root = _prepared(tmp_path)

    def fake_capture(*args, **kwargs):
        return {
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "variable_order_sha256": "2" * 64,
            "vector_sha256": "3" * 64,
            "relaxation_vector": [0.5],
        }

    def fake_write(path, payload):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"root")
        return sha256_file(path)

    def fake_graph(*, output_path, sample_metadata, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(sample_metadata["sample_id"].encode())
        return {
            "graph_sha256": sha256_file(output_path),
            "variables": 3,
            "constraints": 4,
            "nonzeros": 8,
            "binary_variables": 3,
            "integer_variables": 0,
            "continuous_variables": 0,
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
            "root_lp_feature_exactly_encoded": True,
        }

    monkeypatch.setattr(pipeline, "capture_root_relaxation", fake_capture)
    monkeypatch.setattr(pipeline, "write_root_artifact", fake_write)
    monkeypatch.setattr(pipeline, "build_graph_artifact", fake_graph)
    output = tmp_path / "output"
    report = pipeline.execute_dataset(
        prepared,
        parent_graph_dataset_dir=graph_root,
        parent_collection_run_root=label_root,
        output_dir=output,
    )

    assert report["gate_status"] == "passed"
    assert report["summary"]["derived_graphs_written"] == 2
    assert report["summary"]["derived_by_solver"] == {"gurobi": 1, "scip": 1}
    assert report["summary"]["arm_plans_written"] == 4
    assert report["graph_contract"]["authority"] == "gurobi"
    assert report["graph_contract"]["zero_fallback_allowed"] is False
    for arm_id, descriptor in report["arms"].items():
        arm = json.loads((output / descriptor["file_name"]).read_text())
        validate_training_plan(arm)
        assert all(record["role"] == "train" for record in arm["records"])
        derived = [
            record
            for record in arm["records"]
            if record["sampling_strategy"] != "original"
        ]
        assert bool(derived) == arm_id.endswith("incumbent_augmented")
        assert all(record["graph_authority"] == "gurobi" for record in derived)
        assert all(
            record["mip_sha256"] != "a" * 64 for record in derived
        )


def test_parent_label_cannot_be_reused_for_a_derived_mip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, graph_root, label_root = _prepared(tmp_path)
    sample = prepared.source_plan.samples[0]
    with gzip.open(sample.solution_path, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "candidate_sha256": "a" * 64,
                "solution_source": "independent_gurobi_optimization",
            },
            stream,
        )
    sample.solution_sha256 = sha256_file(sample.solution_path)

    with pytest.raises(
        pipeline.GurobiDerivedTrainingError,
        match="independent solution",
    ):
        pipeline.execute_dataset(
            prepared,
            parent_graph_dataset_dir=graph_root,
            parent_collection_run_root=label_root,
            output_dir=tmp_path / "output",
        )


def test_changed_candidate_is_rejected_before_gurobi_execution(
    tmp_path: Path,
) -> None:
    prepared, graph_root, label_root = _prepared(tmp_path)
    prepared.source_plan.samples[0].candidate_path.write_text(
        "changed-after-planning", encoding="utf-8"
    )

    with pytest.raises(
        pipeline.GurobiDerivedTrainingError,
        match="derived candidate SHA-256 mismatch",
    ):
        pipeline.execute_dataset(
            prepared,
            parent_graph_dataset_dir=graph_root,
            parent_collection_run_root=label_root,
            output_dir=tmp_path / "output",
        )


def test_prepare_rejects_asymmetric_solver_designs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gurobi, graph_root, label_root = _original_plan(tmp_path, "gurobi")
    scip, _, _ = _original_plan(tmp_path, "scip")
    gurobi_sample = _derived_spec(tmp_path, "gurobi", 148)
    scip_sample = _derived_spec(tmp_path, "scip", 148)
    scip_sample.radius_fraction = 0.005
    source_plan = SimpleNamespace(
        samples=(gurobi_sample, scip_sample), contract_sha256="1" * 64
    )
    monkeypatch.setattr(pipeline, "build_source_plan", lambda **kwargs: source_plan)
    monkeypatch.setattr(
        pipeline,
        "build_gasse_training_plan",
        lambda **kwargs: {
            "gurobi": gurobi,
            "scip": scip,
        }[kwargs["label_solver"]],
    )

    with pytest.raises(
        pipeline.GurobiDerivedTrainingError,
        match="derived designs are not symmetric",
    ):
        pipeline.prepare_dataset(
            sources=(),
            output_dir=tmp_path / "output",
            experiment_config_path=tmp_path / "experiment.json",
            parent_manifest_path=tmp_path / "manifest.csv",
            parent_graph_dataset_dir=graph_root,
            parent_collection_plan_dir=tmp_path / "plans",
            parent_collection_run_root=label_root,
            training_protocol_path=tmp_path / "training.json",
            allow_partial_smoke=True,
        )


def test_graph_builder_exposes_label_solver_without_changing_authority() -> None:
    source = (
        Path(pipeline.__file__).resolve().parents[1]
        / "graph"
        / "gurobi_graph_artifact.py"
    ).read_text(encoding="utf-8")
    assert 'graph.graph_authority = "gurobi"' in source
    assert 'sample_metadata.get("label_source_solver", "gurobi")' in source


def test_authoritative_pipeline_has_no_zero_ablation_or_pyscipopt_reader() -> None:
    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    assert "zero_ablation" not in source
    assert "from pyscipopt" not in source
    assert "capture_root_relaxation" in source
    assert "parent_label_reuse_for_descendants_allowed" in source
