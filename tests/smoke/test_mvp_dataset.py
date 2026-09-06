from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines import mvp_dataset as pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
PARENT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
PARENT_ID = "CFL_easy_instance_2"
CATEGORY = "CFL_easy_instance"


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _parent_run(tmp_path: Path, solver: str, parent: Path) -> pipeline.ParentRunInput:
    run = tmp_path / f"{solver}_run"
    run.mkdir()
    parent_sha = sha256_file(parent)
    solution = run / "parent_solution.json.gz"
    payload = {
        "candidate_sha256": parent_sha,
        "solution_objective": 6.4 if solver == "gurobi" else 6.5,
        "variables": [{"name": "x", "value": 1.0}],
    }
    with gzip.open(solution, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream)
    contract = ("a" if solver == "gurobi" else "b") * 64
    plan = {
        "contract_sha256": contract,
        "experiment_contract_sha256": pipeline.load_experiment_config(
            CONFIG
        ).contract_sha256,
        "solver_contract": {"solver": solver},
    }
    report = {
        "contract_sha256": contract,
        "probe_completed": True,
        "parent": {
            "source_instance_id": PARENT_ID,
            "category": CATEGORY,
            "difficulty": "easy",
            "fold": 2,
            "role": "train",
            "file_name": parent.name,
            "sha256": parent_sha,
        },
        "solve": {
            "solution_objective": payload["solution_objective"],
            "mip_gap_relative": 0.0 if solver == "gurobi" else 0.05,
            "mip_gap_percent": 0.0 if solver == "gurobi" else 5.0,
            "execution_time_seconds": 100.0 if solver == "gurobi" else 3600.0,
        },
        "checks": {"lineage": True, "feasible": True},
        "artifacts": {
            "solution": {
                "file_name": solution.name,
                "sha256": sha256_file(solution),
            }
        },
        "eligibility": {"label_eligible": True},
    }
    _write_json(run / "scip_parent_solve_plan.json", plan)
    _write_json(run / "scip_parent_solve_report.json", report)
    return pipeline.ParentRunInput(solver, run)


def _derived_record(tmp_path: Path, solver: str) -> dict[str, object]:
    graph = tmp_path / "derived" / "graphs" / solver / f"{solver}.pt"
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_bytes(f"graph-{solver}".encode())
    record = {
        "sample_id": f"{PARENT_ID}__{solver}__lb_r1",
        "parent_instance_id": PARENT_ID,
        "category": CATEGORY,
        "difficulty": "easy",
        "fold": 2,
        "solver": solver,
        "sampling_strategy": "incumbent_local_branching",
        "graph_path": f"graphs/{solver}/{solver}.pt",
        "graph_sha256": sha256_file(graph),
        "label_source": f"{solver}.solution.json.gz",
        "label_solution_sha256": ("c" if solver == "gurobi" else "d") * 64,
        "label_objective": 6.3,
        "label_mip_gap_relative": 0.01,
        "label_mip_gap_percent": 1.0,
        "label_execution_time_seconds": 200.0,
        "source_incumbent_id": f"{solver}:incumbent",
        "source_incumbent_artifact_sha256": (
            "e" if solver == "gurobi" else "f"
        ) * 64,
        "source_incumbent_objective": 6.6,
        "source_incumbent_mip_gap_relative": 0.05,
        "source_incumbent_mip_gap_percent": 5.0,
        "source_incumbent_execution_time_seconds": 100.0,
        "local_branching_radius": 1,
        "local_branching_radius_fraction": 0.001,
    }
    provenance = (
        tmp_path
        / "derived"
        / "provenance"
        / solver
        / f"{record['sample_id']}.provenance.json"
    )
    _write_json(
        provenance,
        {
            "sample": {"sample_id": record["sample_id"]},
            "graph": {"graph_sha256": record["graph_sha256"]},
            "eligibility": {"dataset_eligible": True},
        },
    )
    return record


def _inputs(tmp_path: Path):
    parent = tmp_path / "raw" / CATEGORY / "LP" / f"{PARENT_ID}.lp.gz"
    parent.parent.mkdir(parents=True)
    parent.write_bytes(b"parent")
    runs = [_parent_run(tmp_path, solver, parent) for solver in pipeline.SOLVERS]
    derived_root = tmp_path / "derived"
    records = [_derived_record(tmp_path, solver) for solver in pipeline.SOLVERS]
    with (derived_root / pipeline.MANIFEST_NAME).open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")
    config = pipeline.load_experiment_config(CONFIG)
    _write_json(
        derived_root / "mvp_derived_graph_report.json",
        {
            "gate_status": "passed",
            "experiment_contract_sha256": config.contract_sha256,
            "outputs": {
                "sample_manifest_sha256": sha256_file(
                    derived_root / pipeline.MANIFEST_NAME
                )
            },
            "eligibility": {"dataset_eligible": True},
        },
    )
    return parent.parents[2], runs, derived_root


def _plan(tmp_path: Path) -> pipeline.DatasetPlan:
    raw, runs, derived = _inputs(tmp_path)
    return pipeline.build_plan(
        parent_runs=runs,
        derived_graph_dir=derived,
        base_source_dir=raw,
        output_dir=tmp_path / "output",
        config_path=CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
    )


def test_plan_requires_matched_solver_parent_sets_and_is_sanitized(
    tmp_path: Path,
) -> None:
    raw, runs, derived = _inputs(tmp_path)
    with pytest.raises(pipeline.MvpDatasetError, match="parent sets must match"):
        pipeline.build_plan(
            parent_runs=runs[:1],
            derived_graph_dir=derived,
            base_source_dir=raw,
            output_dir=tmp_path / "bad",
            config_path=CONFIG,
            parent_manifest_path=PARENT_MANIFEST,
        )

    plan = pipeline.build_plan(
        parent_runs=runs,
        derived_graph_dir=derived,
        base_source_dir=raw,
        output_dir=tmp_path / "good",
        config_path=CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
    )
    serialized = json.dumps(plan.to_summary())
    assert str(tmp_path) not in serialized
    assert plan.to_summary()["root_lp_relaxation_policy"] == (
        "zero_ablation_for_all_mvp_graphs"
    )


def test_composition_writes_four_arms_with_equal_parent_mass(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    def fake_builder(spec: pipeline.OriginalGraphSpec, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(spec.sample_id.encode())
        return {
            "graph_sha256": sha256_file(output),
            "structural_graph_sha256": "1" * 64,
            "graph_content_sha256": ("2" if spec.solver == "gurobi" else "3") * 64,
            "variables": 3,
            "constraints": 2,
            "nonzeros": 4,
            "binary_variables": 1,
            "integer_variables": 0,
            "continuous_variables": 2,
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
        }

    report = pipeline.run_composition(
        plan,
        config_path=CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
        overwrite=False,
        graph_builder=fake_builder,
    )

    assert report["gate_status"] == "passed"
    assert report["summary"]["original_graphs_written"] == 2
    assert report["summary"]["derived_graphs_materialized"] == 2
    assert report["summary"]["four_arm_manifests_written"] == 4
    assert report["eligibility"]["dataset_eligible"] is True
    assert (
        len(pipeline.read_sample_manifest(plan.output_dir / pipeline.MANIFEST_NAME))
        == 4
    )
    for solver in pipeline.SOLVERS:
        original = pipeline._read_jsonl(
            plan.output_dir / pipeline.ARM_DIR / f"{solver}_original.jsonl"
        )
        augmented = pipeline._read_jsonl(
            plan.output_dir
            / pipeline.ARM_DIR
            / f"{solver}_incumbent_augmented.jsonl"
        )
        assert len(original) == 1
        assert original[0]["sample_weight"] == 1.0
        assert len(augmented) == 2
        assert {item["sample_weight"] for item in augmented} == {0.5}
        assert sum(item["sample_weight"] for item in augmented) == 1.0
    references = pipeline._read_jsonl(plan.output_dir / pipeline.REFERENCE_NAME)
    assert len(references) == 1
    assert references[0]["selected_solver"] == "gurobi"


def test_original_structure_must_match_across_solvers(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    def mismatched_builder(spec: pipeline.OriginalGraphSpec, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"graph")
        return {
            "graph_sha256": sha256_file(output),
            "structural_graph_sha256": spec.solver,
            "graph_content_sha256": spec.solver,
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
        }

    with pytest.raises(pipeline.MvpDatasetError, match="structure differs"):
        pipeline.run_composition(
            plan,
            config_path=CONFIG,
            parent_manifest_path=PARENT_MANIFEST,
            overwrite=False,
            graph_builder=mismatched_builder,
        )


def test_pipeline_excludes_pyomo_and_reuses_the_common_graph_builder() -> None:
    source = (
        PROJECT_ROOT / "src" / "cfl_gnn" / "pipelines" / "mvp_dataset.py"
    ).read_text()
    assert "build_graph_artifact" in source
    assert "zero_ablation_for_all_mvp_graphs" in source
    assert "equal_parent_mass" in source
    assert "import pyomo" not in source
    assert "from pyomo" not in source

