from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.augmentation import local_branching as module
from cfl_gnn.augmentation.local_branching import (
    AugmentationError,
    IncumbentRecord,
    VariableDomain,
    build_local_branching_constraints,
    incumbent_from_gurobi_record,
    load_pyscipopt_solution,
    validate_artifact_parent_instance,
    load_solver_solution_json,
)
from cfl_gnn.augmentation.solver_backends import ParentInspection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"


def _incumbent(values: dict[str, float], *, solver: str = "gurobi") -> IncumbentRecord:
    return IncumbentRecord(
        source_solver=solver,
        source_format="test",
        source_artifact="incumbent.test",
        source_artifact_sha256="a" * 64,
        source_model_sha256=None,
        source_index=0,
        incumbent_id=f"{solver}:test:0",
        objective=6.2,
        admission_mip_gap_relative=0.05,
        admission_mip_gap_percent=5.0,
        admission_mip_gap_measurement="test",
        terminal_mip_gap_relative=0.05,
        terminal_mip_gap_percent=5.0,
        execution_time_seconds=100.0,
        execution_time_semantics="test",
        recorded_time=100.0,
        time_normalization_method="test",
        time_origin=None,
        discovery_time_seconds=90.0,
        discovery_mip_gap_relative=0.06,
        discovery_mip_gap_percent=6.0,
        values_by_name=values,
    )


def test_local_branching_linearization_and_radius_are_canonical() -> None:
    variables = [
        VariableDomain(f"x{index}", "BINARY", 0.0, 1.0)
        for index in range(1000)
    ]
    values = {variable.name: float(int(variable.name[1:]) % 2) for variable in variables}
    constraints = build_local_branching_constraints(
        variables,
        _incumbent(values),
        radius_fractions=(0.001, 0.005, 0.01),
        minimum_radius=1,
        maximum_derived=3,
    )

    assert [item.radius for item in constraints] == [1, 5, 10]
    assert constraints[0].incumbent_zero_count == 500
    assert constraints[0].incumbent_one_count == 500
    assert constraints[0].coefficients["x0"] == 1
    assert constraints[0].coefficients["x1"] == -1
    assert constraints[0].rhs == 1 - 500


def test_equal_integer_radii_are_deduplicated_for_toy_models() -> None:
    variables = [
        VariableDomain("a", "BINARY", 0.0, 1.0),
        VariableDomain("b", "BINARY", 0.0, 1.0),
        VariableDomain("continuous", "CONTINUOUS", 0.0, 10.0),
    ]
    constraints = build_local_branching_constraints(
        variables,
        _incumbent({"a": 0.0, "b": 1.0, "continuous": 3.0}),
        radius_fractions=(0.001, 0.005, 0.01),
        minimum_radius=1,
        maximum_derived=3,
    )
    assert len(constraints) == 1
    assert constraints[0].radius == 1


def test_fractional_binary_incumbent_is_rejected() -> None:
    with pytest.raises(AugmentationError, match="fractional"):
        build_local_branching_constraints(
            [VariableDomain("x", "BINARY", 0.0, 1.0)],
            _incumbent({"x": 0.5}),
            radius_fractions=(0.1,),
            minimum_radius=1,
            maximum_derived=1,
        )


def test_pyscipopt_solution_loader_preserves_primary_metrics(tmp_path: Path) -> None:
    path = tmp_path / "solution.json.gz"
    payload = {
        "solution_source": "independent_pyscipopt_optimization",
        "solution_objective": 6.23,
        "mip_gap_relative": 0.054,
        "mip_gap_percent": 5.4,
        "execution_time_seconds": 3600.0,
        "best_incumbent_discovery_time_seconds": 1200.0,
        "incumbent_trace": [
            {
                "incumbent_mip_gap_relative_at_discovery": 0.06,
                "incumbent_mip_gap_percent_at_discovery": 6.0,
            }
        ],
        "variables": [
            {"name": "x0", "value": 0.0},
            {"name": "x1", "value": 1.0},
        ],
    }
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream)

    record = load_pyscipopt_solution(path)

    assert record.source_solver == "scip"
    assert record.objective == pytest.approx(6.23)
    assert record.terminal_mip_gap_relative == pytest.approx(0.054)
    assert record.execution_time_seconds == pytest.approx(3600.0)
    assert record.discovery_time_seconds == pytest.approx(1200.0)
    assert record.values_by_name == {"x0": 0.0, "x1": 1.0}


def test_modern_gurobi_solution_loader_preserves_named_parent_linkage(
    tmp_path: Path,
) -> None:
    path = tmp_path / "gurobi_parent.solution.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "solution_source": "independent_gurobi_optimization",
                "candidate_sha256": "c" * 64,
                "solution_objective": 6.2,
                "mip_gap_relative": 0.05,
                "mip_gap_percent": 5.0,
                "execution_time_seconds": 3600.0,
                "variables": [{"name": "x", "value": 1.0}],
            },
            stream,
        )

    record = load_solver_solution_json(path, source_solver="gurobi")

    assert record.source_solver == "gurobi"
    assert record.source_model_sha256 == "c" * 64
    assert record.source_format == "gurobi_solution_json"
    assert record.values_by_name == {"x": 1.0}


def test_gurobi_record_maps_positional_vector_to_parent_names() -> None:
    record = incumbent_from_gurobi_record(
        {
            "objective": 6.5,
            "mip_gap": 0.08,
            "time": 300.0,
            "solution_vector": [1.0, 0.0, 2.5],
        },
        ["x0", "x1", "flow"],
        artifact="incumbents.parquet",
        artifact_sha256="b" * 64,
        source_index=7,
    )
    assert record.incumbent_id.endswith(":7")
    assert record.values_by_name == {"x0": 1.0, "x1": 0.0, "flow": 2.5}
    assert record.admission_mip_gap_percent == pytest.approx(8.0)
    assert record.admission_mip_gap_measurement == "callback_at_incumbent_discovery"
    assert record.terminal_mip_gap_relative is None
    assert record.execution_time_seconds == pytest.approx(300.0)
    assert record.time_normalization_method == "recorded_gurobi_runtime_seconds"


def test_gurobi_legacy_epoch_is_normalized_from_first_incumbent() -> None:
    record = incumbent_from_gurobi_record(
        {
            "objective": 6.5,
            "mip_gap": 0.08,
            "time": 1_784_914_618.5,
            "solution_vector": [1.0],
        },
        ["x0"],
        artifact="incumbents.parquet",
        artifact_sha256="b" * 64,
        source_index=7,
        epoch_origin=1_784_914_000.0,
    )
    assert record.recorded_time == pytest.approx(1_784_914_618.5)
    assert record.execution_time_seconds == pytest.approx(618.5)
    assert record.discovery_time_seconds == pytest.approx(618.5)
    assert record.time_origin == pytest.approx(1_784_914_000.0)
    assert record.time_normalization_method == "unix_epoch_minus_first_incumbent"
    assert record.execution_time_semantics == (
        "elapsed_since_first_recorded_incumbent_proxy"
    )


def test_legacy_gurobi_artifact_rejects_equal_size_wrong_parent(
    tmp_path: Path,
) -> None:
    wrong = tmp_path / "CFL_easy_instance_28" / "incumbents.parquet"
    wrong.parent.mkdir()
    wrong.write_bytes(b"same-shaped incumbent stream")

    with pytest.raises(AugmentationError, match="does not belong"):
        validate_artifact_parent_instance(wrong, "CFL_easy_instance_2")


class _FakeBackend:
    def __init__(self, variables: list[VariableDomain]) -> None:
        self.variables = variables

    def inspect(self, path: Path) -> ParentInspection:
        return ParentInspection(tuple(self.variables), "MAXIMIZE")

    def write_variant(self, parent: Path, output: Path, constraint):
        output.write_text(
            json.dumps(constraint.contract_payload(), sort_keys=True),
            encoding="utf-8",
        )
        return {
            "writer": "fake",
            "artifact_format": "lp",
            "solver_version": "test",
        }


def test_cli_materializes_unlabelled_train_only_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent.lp"
    parent.write_text("Minimize\n obj: x\nEnd\n", encoding="utf-8")
    solution = tmp_path / "solution.json.gz"
    with gzip.open(solution, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "solution_source": "independent_pyscipopt_optimization",
                "objective": 6.0,
                "mip_gap_relative": 0.05,
                "mip_gap_percent": 5.0,
                "execution_time_seconds": 60.0,
                "variables": [
                    {"name": "x0", "value": 0.0},
                    {"name": "x1", "value": 1.0},
                ],
            },
            stream,
        )
    monkeypatch.setattr(
        module,
        "_backend",
        lambda name: _FakeBackend(
            [
                VariableDomain("x0", "BINARY", 0.0, 1.0),
                VariableDomain("x1", "BINARY", 0.0, 1.0),
            ]
        ),
    )
    output = tmp_path / "out"
    result = module.main(
        [
            "--solver",
            "scip",
            "--parent_mip",
            str(parent),
            "--incumbent_artifact",
            str(solution),
            "--incumbent_format",
            "pyscipopt_solution_json",
            "--parent_instance_id",
            "CFL_easy_instance_0",
            "--category",
            "CFL_easy_instance",
            "--difficulty",
            "easy",
            "--fold",
            "2",
            "--config",
            str(CONFIG),
            "--output_dir",
            str(output),
        ]
    )
    report = json.loads((output / module.REPORT_NAME).read_text(encoding="utf-8"))
    provenance = json.loads(next(output.glob("*.provenance.json")).read_text())

    assert result == 0
    assert report["gate_status"] == "passed"
    assert report["summary"]["variants_written"] == 1
    assert report["parent_model"]["effective_objective_sense"] == "MINIMIZE"
    assert report["eligibility"]["dataset_eligible"] is False
    assert provenance["role"] == "train"
    assert provenance["source_incumbent"]["performance_feature_tags"][
        "admission_mip_gap_relative"
    ] == pytest.approx(0.05)


def test_cli_rejects_cross_solver_incumbent_format(tmp_path: Path) -> None:
    parent = tmp_path / "parent.lp"
    incumbent = tmp_path / "solution.json.gz"
    parent.write_text("test", encoding="utf-8")
    incumbent.write_text("test", encoding="utf-8")
    result = module.main(
        [
            "--solver",
            "gurobi",
            "--parent_mip",
            str(parent),
            "--incumbent_artifact",
            str(incumbent),
            "--incumbent_format",
            "pyscipopt_solution_json",
            "--parent_instance_id",
            "instance",
            "--category",
            "category",
            "--difficulty",
            "easy",
            "--fold",
            "0",
            "--config",
            str(CONFIG),
            "--output_dir",
            str(tmp_path / "out"),
        ]
    )
    assert result == 2
