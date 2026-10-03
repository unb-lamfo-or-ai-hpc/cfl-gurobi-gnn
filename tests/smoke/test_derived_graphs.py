"""Dependency-light tests for MVP derived graph and manifest generation."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines import derived_graphs as pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
PARENT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _source(tmp_path: Path, solver: str) -> pipeline.SourceInput:
    candidate_dir = tmp_path / f"{solver}_candidates"
    solve_dir = tmp_path / f"{solver}_solve"
    candidate_dir.mkdir()
    (solve_dir / "solutions").mkdir(parents=True)
    config = pipeline.load_experiment_config(CONFIG)
    solve_contract = (solver[0] * 64) if solver != "scip" else ("c" * 64)
    metrics = []
    for radius, fraction in ((148, 0.001), (736, 0.005), (1472, 0.01)):
        sample_id = f"CFL_easy_instance_2__{solver}__lb_r{radius}"
        candidate = candidate_dir / f"{sample_id}.lp"
        candidate.write_text(f"candidate-{solver}-{radius}", encoding="utf-8")
        solution = solve_dir / "solutions" / f"{sample_id}.solution.json.gz"
        with gzip.open(solution, "wt", encoding="utf-8") as stream:
            json.dump(
                {
                    "candidate_sha256": sha256_file(candidate),
                    "variables": [{"name": "x", "value": 1.0}],
                },
                stream,
            )
        provenance = candidate_dir / f"{sample_id}.provenance.json"
        provenance_payload = {
            "solver": solver,
            "experiment_contract_sha256": config.contract_sha256,
            "parent_instance_id": "CFL_easy_instance_2",
            "role": "train",
            "output": {"file_name": candidate.name, "sha256": sha256_file(candidate)},
            "operator_contract_sha256": "a" * 64,
            "local_branching": {"radius": radius, "radius_fraction": fraction},
            "source_incumbent": {
                "incumbent_id": f"{solver}:center",
                "artifact_sha256": "b" * 64,
                "performance_feature_tags": {
                    "incumbent_objective": 6.5,
                    "admission_mip_gap_relative": 0.05,
                    "admission_mip_gap_percent": 5.0,
                    "execution_time_seconds": 100.0,
                },
            },
        }
        _write_json(provenance, provenance_payload)
        metrics.append(
            {
                "sample_id": sample_id,
                "solver": solver,
                "sampling_strategy": "incumbent_local_branching",
                "parent_instance_id": "CFL_easy_instance_2",
                "category": "CFL_easy_instance",
                "difficulty": "easy",
                "fold": 2,
                "role": "train",
                "candidate": {
                    "file_name": candidate.name,
                    "sha256": sha256_file(candidate),
                    "provenance_file_name": provenance.name,
                    "provenance_sha256": sha256_file(provenance),
                    "operator_contract_sha256": "a" * 64,
                    "radius": radius,
                    "radius_fraction": fraction,
                    "source_incumbent_id": f"{solver}:center",
                    "source_incumbent_artifact_sha256": "b" * 64,
                },
                "solve": {
                    "solution_objective": 6.4,
                    "mip_gap_relative": 0.0,
                    "mip_gap_percent": 0.0,
                    "execution_time_seconds": 200.0,
                },
                "gap_sensitivity_memberships": [
                    "gap_le_0.01",
                    "gap_le_0.05",
                    "gap_le_0.06",
                    "gap_le_0.1",
                ],
                "artifacts": {
                    "solution": {
                        "file_name": solution.name,
                        "sha256": sha256_file(solution),
                    }
                },
                "gate_status": "passed",
                "eligibility": {"label_eligible": True},
            }
        )
    _write_json(
        solve_dir / "derived_mip_solution_plan.json",
        {"contract_sha256": solve_contract},
    )
    _write_json(
        solve_dir / "derived_mip_solution_report.json",
        {
            "solver": solver,
            "contract_sha256": solve_contract,
            "experiment_contract_sha256": config.contract_sha256,
            "gate_status": "passed",
            "summary": {"candidate_count": 3},
            "eligibility": {"all_labels_eligible": True},
        },
    )
    with (solve_dir / "per_candidate_derived_metrics.jsonl").open(
        "w", encoding="utf-8"
    ) as stream:
        for item in metrics:
            stream.write(json.dumps(item) + "\n")
    return pipeline.SourceInput(solver, candidate_dir, solve_dir)


def _plan(tmp_path: Path) -> pipeline.DerivedGraphPlan:
    return pipeline.build_plan(
        sources=[_source(tmp_path, "gurobi"), _source(tmp_path, "scip")],
        output_dir=tmp_path / "output",
        config_path=CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
    )


def test_plan_is_symmetric_deterministic_and_path_sanitized(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    assert len(plan.samples) == 6
    assert {item.solver for item in plan.samples} == {"gurobi", "scip"}
    assert all(item.fold == 2 for item in plan.samples)
    assert all(item.radius in {148, 736, 1472} for item in plan.samples)
    serialized = json.dumps(plan.to_summary())
    assert str(tmp_path) not in serialized
    assert plan.to_summary()["root_lp_relaxation_policy"].startswith("zero_ablation")


def test_generation_emits_contract_valid_manifest(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    def fake_builder(spec: pipeline.DerivedGraphSpec, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(spec.sample_id.encode("utf-8"))
        return {
            "graph_sha256": sha256_file(output),
            "structural_graph_sha256": pipeline._canonical_sha256(
                [spec.solver, spec.radius]
            ),
            "graph_content_sha256": pipeline._canonical_sha256(spec.sample_id),
            "variables": 3,
            "constraints": 4,
            "nonzeros": 8,
            "binary_variables": 3,
            "integer_variables": 0,
            "continuous_variables": 0,
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
        }

    report = pipeline.run_generation(
        plan,
        config_path=CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
        overwrite=False,
        graph_builder=fake_builder,
    )

    assert report["gate_status"] == "passed"
    assert report["summary"]["graphs_written"] == 6
    assert report["summary"]["graphs_by_solver"] == {"gurobi": 3, "scip": 3}
    assert report["summary"]["manifest_contract_valid"] is True
    assert report["eligibility"]["dataset_eligible"] is True
    records = pipeline.read_sample_manifest(plan.output_dir / pipeline.MANIFEST_NAME)
    assert len(records) == 6
    assert all(item.sampling_strategy == "incumbent_local_branching" for item in records)
    assert len(list((plan.output_dir / "provenance").rglob("*.json"))) == 6


def test_candidate_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    gurobi = _source(tmp_path, "gurobi")
    scip = _source(tmp_path, "scip")
    next(gurobi.candidate_dir.glob("*.lp")).write_text("tampered", encoding="utf-8")

    with pytest.raises(pipeline.DerivedGraphError, match="SHA-256 mismatch"):
        pipeline.build_plan(
            sources=[gurobi, scip],
            output_dir=tmp_path / "output",
            config_path=CONFIG,
            parent_manifest_path=PARENT_MANIFEST,
        )


def test_duplicate_sibling_structure_fails_closed(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    def colliding_builder(spec: pipeline.DerivedGraphSpec, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(spec.sample_id.encode())
        return {
            "graph_sha256": sha256_file(output),
            "structural_graph_sha256": spec.solver,
            "graph_content_sha256": spec.sample_id,
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
        }

    with pytest.raises(pipeline.DerivedGraphError, match="duplicate derived"):
        pipeline.run_generation(
            plan,
            config_path=CONFIG,
            parent_manifest_path=PARENT_MANIFEST,
            overwrite=False,
            graph_builder=colliding_builder,
        )


@pytest.mark.parametrize(
    ("raw", "lower", "upper", "expected"),
    [
        ("BINARY", 0.0, 1.0, "B"),
        ("INTEGER", 0.0, 1.0, "B"),
        ("INTEGER", 0.0, 2.0, "I"),
        ("CONTINUOUS", 0.0, 1.0, "C"),
    ],
)
def test_lp_variable_types_are_canonicalized(
    raw: str, lower: float, upper: float, expected: str
) -> None:
    assert pipeline._canonical_variable_type(raw, lower, upper) == expected


def test_source_excludes_gurobi_and_pyomo_imports() -> None:
    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    assert "import gurobipy" not in source
    assert "import pyomo" not in source
    assert "from pyomo" not in source
    assert "from pyscipopt import Model" in source
