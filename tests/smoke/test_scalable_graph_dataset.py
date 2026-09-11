from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cfl_gnn.analysis import scalable_graph_dataset as analysis
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines import derived_graphs
from cfl_gnn.pipelines.derived_graphs import SourceInput


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in records))


def test_derived_graph_plan_accepts_multiple_sources_per_solver(
    tmp_path: Path, monkeypatch
) -> None:
    config = SimpleNamespace(
        contract_sha256="a" * 64,
        rotation=0,
        augmentation=SimpleNamespace(maximum_derived_per_parent=3),
        gap_policy=SimpleNamespace(maximum_admissible_relative_gap=0.1),
    )
    monkeypatch.setattr(derived_graphs, "load_experiment_config", lambda path: config)
    monkeypatch.setattr(
        derived_graphs,
        "read_manifest",
        lambda path: [
            SimpleNamespace(
                source_instance_id="p1", fold=2, category="c", difficulty="easy"
            ),
            SimpleNamespace(
                source_instance_id="p2", fold=1, category="c", difficulty="easy"
            ),
        ],
    )
    monkeypatch.setattr(derived_graphs, "role_for_fold", lambda fold, rotation: "train")

    def fake_load(source, **kwargs):
        parent = source.candidate_dir.name
        return [
            SimpleNamespace(
                solver=source.solver,
                sample_id=f"{parent}-{source.solver}",
                parent_instance_id=parent,
                radius=1,
                label_mip_gap_relative=0.0,
            )
        ]

    monkeypatch.setattr(derived_graphs, "_load_source", fake_load)
    sources = tuple(
        SourceInput(solver=solver, candidate_dir=tmp_path / parent, solve_dir=tmp_path)
        for parent in ("p1", "p2")
        for solver in ("gurobi", "scip")
    )
    plan = derived_graphs.build_plan(
        sources=sources,
        output_dir=tmp_path / "out",
        config_path=tmp_path / "config.json",
        parent_manifest_path=tmp_path / "manifest.csv",
    )
    assert len(plan.samples) == 4
    assert {item.parent_instance_id for item in plan.samples} == {"p1", "p2"}


def test_structural_audit_deduplicates_original_label_views(
    tmp_path: Path, monkeypatch
) -> None:
    dataset = tmp_path / "dataset"
    graph = dataset / "graphs" / "original" / "p.pt"
    graph.parent.mkdir(parents=True)
    graph.write_bytes(b"graph")
    graph_hash = sha256_file(graph)
    records = [
        {
            "sample_id": "p",
            "source_instance_id": "p",
            "difficulty": "easy",
            "sampling_strategy": "original",
            "label_solver": solver,
            "mip_sha256": "m" * 64,
            "graph_relative_path": "graphs/original/p.pt",
            "graph_sha256": graph_hash,
        }
        for solver in ("scip", "gurobi")
    ]
    manifest = dataset / "gasse_augmented_manifest.jsonl"
    _write_jsonl(manifest, records)
    _write_json(
        dataset / "gurobi_derived_training_dataset_report.json",
        {
            "contract_sha256": "c" * 64,
            "gate_status": "passed",
            "graph_contract": {"authority": "gurobi"},
            "outputs": {
                "gasse_augmented_manifest.jsonl": {"sha256": sha256_file(manifest)}
            },
            "eligibility": {"dataset_eligible": True, "development_only": True},
        },
    )

    def fake_statistics(**kwargs):
        output = Path(kwargs["output_dir"])
        _write_json(output / "graph_statistics_report.json", {"gate_status": "passed"})
        return {"gate_status": "passed", "summary": {"graphs": 1}}

    def fake_clustering(**kwargs):
        output = Path(kwargs["output_dir"])
        _write_json(output / "graph_clustering_report.json", {"gate_status": "passed"})
        return {"gate_status": "passed", "summary": {"graphs": 1}}

    monkeypatch.setattr(analysis, "analyze_graph_manifest", fake_statistics)
    monkeypatch.setattr(analysis, "cluster_graph_manifest", fake_clustering)
    report = analysis.audit_scalable_graph_dataset(
        dataset_dir=dataset, output_dir=tmp_path / "audit"
    )
    structural = [
        json.loads(line)
        for line in (tmp_path / "audit" / analysis.STRUCTURAL_MANIFEST_NAME)
        .read_text()
        .splitlines()
    ]
    assert report["gate_status"] == "passed"
    assert report["summary"]["label_views"] == 2
    assert report["summary"]["structural_graphs"] == 1
    assert structural[0]["label_solver"] == "gurobi"

