from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cfl_gnn.analysis.graph_clustering import cluster_graph_manifest
from cfl_gnn.analysis.graph_statistics import analyze_graph_manifest
from cfl_gnn.graph.gurobi_graph_artifact import compare_root_relaxations
from cfl_gnn.pipelines.gurobi_graph_dataset import (
    GurobiGraphDatasetError,
    build_graph_plan,
)
from cfl_gnn.pipelines.parent_population import write_parent_collection_plan


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
CAMPAIGN = PROJECT_ROOT / "configs" / "experiments" / "parent_collection_v1.json"
EXPERIMENT = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parent_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "raw"
    source = (
        source_root
        / "CFL_easy_instance"
        / "LP"
        / "CFL_easy_instance_2.lp.gz"
    )
    source.parent.mkdir(parents=True)
    source.write_bytes(b"parent-mip")
    plan_dir = tmp_path / "plan"
    plan = write_parent_collection_plan(
        base_source_dir=source_root,
        output_dir=plan_dir,
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_2",),
    )
    task = next(task for task in plan["tasks"] if task["solver"] == "gurobi")
    run_root = tmp_path / "runs"
    run_dir = run_root / task["run_dir_relative_path"]
    run_dir.mkdir(parents=True)
    solution = run_dir / "parent_solution.json.gz"
    with gzip.open(solution, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "solution_source": "independent_gurobi_optimization",
                "variables": [{"name": "x", "value": 1.0}],
            },
            stream,
        )
    report = {
        "contract_sha256": "parent-contract",
        "gate_status": "passed",
        "parent": {"sha256": task["parent_mip_sha256"]},
        "artifacts": {
            "solution": {"file_name": solution.name, "sha256": _sha256(solution)}
        },
        "eligibility": {"label_eligible": True},
    }
    (run_dir / "gurobi_parent_solve_report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    return source_root, plan_dir, run_root


def test_graph_plan_has_one_gurobi_graph_per_mathematical_mip(tmp_path: Path) -> None:
    source_root, plan_dir, run_root = _parent_fixture(tmp_path)

    plan = build_graph_plan(
        parent_collection_plan_dir=plan_dir,
        parent_collection_run_root=run_root,
        base_source_dir=source_root,
        output_dir=tmp_path / "graphs",
        instances=("CFL_easy_instance_2",),
    )

    assert plan["summary"]["graphs_planned"] == 1
    assert plan["summary"]["unique_mip_sha256"] == 1
    assert plan["graph_authority"] == "gurobi"
    assert plan["scip_graph_construction_allowed"] is False
    assert plan["incumbent_role"] == "label_and_provenance_only"
    assert plan["root_lp_contract"]["zero_fallback_allowed"] is False
    assert plan["specifications"][0]["label_source_solver"] == "gurobi"
    assert str(tmp_path) not in json.dumps(plan)


def test_required_legacy_parity_fails_closed_when_artifact_is_missing(
    tmp_path: Path,
) -> None:
    source_root, plan_dir, run_root = _parent_fixture(tmp_path)

    with pytest.raises(GurobiGraphDatasetError, match="legacy root parity"):
        build_graph_plan(
            parent_collection_plan_dir=plan_dir,
            parent_collection_run_root=run_root,
            base_source_dir=source_root,
            output_dir=tmp_path / "graphs",
            legacy_intermediate_dir=tmp_path / "legacy",
            instances=("CFL_easy_instance_2",),
            require_legacy_parity=True,
        )


def test_root_parity_is_tolerance_bound_and_shape_strict() -> None:
    passed = compare_root_relaxations([0.0, 0.5, 1.0], [0.0, 0.5, 1.0 + 1e-9])
    failed = compare_root_relaxations([0.0, 1.0], [0.0])

    assert passed["status"] == "passed"
    assert passed["vector_length"] == 3
    assert failed["status"] == "failed"
    assert failed["reason_code"] == "root_vector_shape_mismatch"


def _write_graph_manifest(tmp_path: Path) -> tuple[Path, Path, object]:
    variable = SimpleNamespace(
        x=np.asarray(
            [[0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.25],
             [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.75]],
            dtype=np.float32,
        ),
        y=np.asarray([1.0, 0.0], dtype=np.float32),
        is_discrete=np.asarray([1.0, 0.0], dtype=np.float32),
    )
    constraint = SimpleNamespace(x=np.ones((1, 5), dtype=np.float32))
    edge = SimpleNamespace(edge_index=np.asarray([[0, 1], [0, 0]]))

    class FakeGraph:
        mip_gap = 0.05
        exec_time = 60.0

        def __getitem__(self, key):
            return {
                "variable": variable,
                "constraint": constraint,
                ("variable", "rev_coef", "constraint"): edge,
            }[key]

    graph = FakeGraph()
    root = tmp_path / "artifacts"
    path = root / "graphs" / "sample.pt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic-graph")
    manifest = root / "gurobi_graph_manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "sample_id": "sample",
                "source_instance_id": "CFL_easy_instance_2",
                "difficulty": "easy",
                "sampling_strategy": "original",
                "graph_relative_path": "graphs/sample.pt",
                "graph_sha256": _sha256(path),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root, manifest, graph


def test_statistics_and_clustering_consume_the_same_hashed_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, manifest, graph = _write_graph_manifest(tmp_path)
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(load=lambda *args, **kwargs: graph),
    )

    statistics_report = analyze_graph_manifest(
        manifest_path=manifest,
        graph_root=root,
        output_dir=tmp_path / "statistics",
    )
    clustering_report = cluster_graph_manifest(
        manifest_path=manifest,
        graph_root=root,
        output_dir=tmp_path / "clustering",
    )

    assert statistics_report["gate_status"] == "passed"
    assert statistics_report["summary"]["graphs"] == 1
    assert clustering_report["gate_status"] == "passed"
    assert clustering_report["summary"]["clusters"] == 1
    assert (
        statistics_report["graph_manifest_sha256"]
        == clustering_report["graph_manifest_sha256"]
    )


def test_recovered_pipeline_has_no_zero_root_fallback_or_scip_graph_reader() -> None:
    graph_source = (
        PROJECT_ROOT / "src" / "cfl_gnn" / "graph" / "gurobi_graph_artifact.py"
    ).read_text(encoding="utf-8")
    pipeline_source = (
        PROJECT_ROOT / "src" / "cfl_gnn" / "pipelines" / "gurobi_graph_dataset.py"
    ).read_text(encoding="utf-8")

    assert "first_optimal_root_gurobi_mipnode" in graph_source
    assert "cbGetNodeRel" in graph_source
    assert "np.zeros" not in graph_source
    assert "from pyscipopt" not in graph_source
    assert '"scip_graph_construction_allowed": False' in pipeline_source
