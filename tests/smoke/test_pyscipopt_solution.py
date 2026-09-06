from __future__ import annotations

from pathlib import Path

import pytest

from cfl_gnn.solvers.pyscipopt_solution import (
    ONLINE_GAP_AVAILABILITY,
    OnlineIncumbentCollector,
    audit_incumbent_trace,
)


class _Variable:
    def __init__(self, name: str) -> None:
        self.name = name


class _Stream:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def append(self, record: dict[str, object]) -> None:
        self.records.append(record)


class _Model:
    def __init__(self) -> None:
        self.objective = 10.0
        self.bound = 5.0
        self.time = 1.25
        self.nodes = 3
        self.values = {"x": 1.0, "y": 0.0}

    def getBestSol(self) -> object:
        return self

    def getSolObjVal(self, solution: object, original: bool = True) -> float:
        assert solution is self
        assert original is True
        return self.objective

    def getSolTime(self, solution: object) -> float:
        assert solution is self
        return self.time

    def getSolvingTime(self) -> float:
        raise AssertionError("the callback must prefer the solution timestamp")

    def getDualbound(self) -> float:
        return self.bound

    def getNNodes(self) -> int:
        return self.nodes

    def getNBestSolsFound(self) -> int:
        return 1

    def getSolVal(self, solution: object, variable: _Variable) -> float:
        assert solution is self
        return self.values[variable.name]


def test_bestsolfound_callback_streams_vectors_and_primary_metrics() -> None:
    model = _Model()
    stream = _Stream()
    collector = OnlineIncumbentCollector(
        variables=(_Variable("x"), _Variable("y")),
        objective_sense="minimize",
        stream=stream,  # type: ignore[arg-type]
    )

    collector.callback(model, object())
    model.objective = 8.0
    model.bound = 6.0
    model.time = 2.5
    model.nodes = 9
    collector.callback(model, object())

    assert collector.errors == []
    assert [item["incumbent_objective"] for item in collector.trace] == [10.0, 8.0]
    assert collector.trace[0]["incumbent_mip_gap_relative_at_discovery"] == pytest.approx(0.5)
    assert collector.trace[1]["incumbent_mip_gap_percent_at_discovery"] == pytest.approx(25.0)
    assert collector.trace[1]["mip_gap_at_discovery_availability"] == ONLINE_GAP_AVAILABILITY
    assert stream.records[0]["solution_vector"] == [1.0, 0.0]


def test_incumbent_trace_audit_accepts_consistent_minimization_trace() -> None:
    trace = [
        {
            "incumbent_objective": 10.0,
            "incumbent_discovery_time_seconds": 1.0,
            "incumbent_mip_gap_relative_at_discovery": 0.5,
            "incumbent_mip_gap_percent_at_discovery": 50.0,
        },
        {
            "incumbent_objective": 8.0,
            "incumbent_discovery_time_seconds": 2.0,
            "incumbent_mip_gap_relative_at_discovery": 0.25,
            "incumbent_mip_gap_percent_at_discovery": 25.0,
        },
    ]

    audit = audit_incumbent_trace(
        trace,
        objective_sense="minimize",
        final_objective=8.0,
        final_discovery_time=2.0,
    )

    assert audit["incumbent_trace_consistent"] is True


def test_incumbent_trace_audit_rejects_wrong_final_incumbent() -> None:
    audit = audit_incumbent_trace(
        [
            {
                "incumbent_objective": 8.0,
                "incumbent_discovery_time_seconds": 2.0,
                "incumbent_mip_gap_relative_at_discovery": 0.25,
                "incumbent_mip_gap_percent_at_discovery": 25.0,
            }
        ],
        objective_sense="minimize",
        final_objective=7.0,
        final_discovery_time=2.0,
    )

    assert audit["final_incumbent_objective_matches"] is False
    assert audit["incumbent_trace_consistent"] is False


def test_trace_audit_accepts_numerically_tiny_improvement() -> None:
    trace = [
        {
            "incumbent_objective": 10.0,
            "incumbent_discovery_time_seconds": 1.0,
            "incumbent_mip_gap_relative_at_discovery": 0.5,
            "incumbent_mip_gap_percent_at_discovery": 50.0,
        },
        {
            "incumbent_objective": 10.0 - 5e-9,
            "incumbent_discovery_time_seconds": 2.0,
            "incumbent_mip_gap_relative_at_discovery": 0.4,
            "incumbent_mip_gap_percent_at_discovery": 40.0,
        },
    ]

    audit = audit_incumbent_trace(
        trace,
        objective_sense="minimize",
        final_objective=10.0 - 5e-9,
        final_discovery_time=2.0,
    )

    assert audit["incumbent_objectives_monotonic"] is True
    assert audit["incumbent_trace_consistent"] is True
    assert audit["objective_tolerance"] == 1e-9


def test_shared_kernel_uses_callback_api_without_pyomo() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "cfl_gnn"
        / "solvers"
        / "pyscipopt_solution.py"
    ).read_text(encoding="utf-8")

    assert "BESTSOLFOUND" in source
    assert "attachEventHandlerCallback" in source
    assert "getSolTime(solution)" in source
    assert "original=True" in source
    assert '"solver_feasibility_check_space": "original_problem"' in source
    assert "import pyomo" not in source
    assert "from pyomo" not in source
