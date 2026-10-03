from __future__ import annotations

from pathlib import Path

import pytest

from cfl_gnn.solvers import gurobi_solution as module
from cfl_gnn.solvers.gurobi_solution import GurobiIncumbentCollector


class _Codes:
    MIPSOL = 1
    MIPSOL_OBJ = 2
    MIPSOL_OBJBND = 3
    RUNTIME = 4
    MIPSOL_NODCNT = 5
    MIPSOL_SOLCNT = 6


class _Stream:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def append(self, record: dict[str, object]) -> None:
        self.records.append(record)


class _Model:
    def __init__(self) -> None:
        self.objective = 10.0
        self.bound = 5.0
        self.runtime = 1.0
        self.node = 3
        self.count = 1
        self.vector = [1.0, 0.0]

    def cbGet(self, code: int) -> float:
        return {
            _Codes.MIPSOL_OBJ: self.objective,
            _Codes.MIPSOL_OBJBND: self.bound,
            _Codes.RUNTIME: self.runtime,
            _Codes.MIPSOL_NODCNT: self.node,
            _Codes.MIPSOL_SOLCNT: self.count,
        }[code]

    def cbGetSolution(self, variables: object) -> list[float]:
        return self.vector


def test_mipsol_callback_captures_strict_improvements_and_vectors() -> None:
    model = _Model()
    stream = _Stream()
    collector = GurobiIncumbentCollector(
        variables=(object(), object()),
        objective_sense="minimize",
        callback_codes=_Codes,
        stream=stream,  # type: ignore[arg-type]
    )

    collector.callback(model, _Codes.MIPSOL)
    model.objective = 10.0
    model.runtime = 1.5
    collector.callback(model, _Codes.MIPSOL)
    model.objective = 8.0
    model.bound = 6.0
    model.runtime = 2.0
    model.node = 9
    collector.callback(model, _Codes.MIPSOL)

    assert collector.events_seen == 3
    assert collector.non_improving_events_ignored == 1
    assert collector.errors == []
    assert [item["incumbent_objective"] for item in collector.trace] == [10.0, 8.0]
    assert collector.trace[0]["incumbent_mip_gap_relative_at_discovery"] == pytest.approx(0.5)
    assert collector.trace[1]["incumbent_mip_gap_percent_at_discovery"] == pytest.approx(25.0)
    assert stream.records[1]["solution_vector"] == [1.0, 0.0]


def test_non_mipsol_location_is_ignored() -> None:
    collector = GurobiIncumbentCollector(
        variables=(),
        objective_sense="minimize",
        callback_codes=_Codes,
    )
    collector.callback(_Model(), 999)
    assert collector.events_seen == 0
    assert collector.trace == []


def test_gurobi_and_pyarrow_are_lazy_and_pyomo_is_absent() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "cfl_gnn"
        / "solvers"
        / "gurobi_solution.py"
    ).read_text(encoding="utf-8")

    assert "gp" not in module.__dict__
    assert "def solve_named_mip" in source
    assert "GRB.Callback.MIPSOL" in source
    assert "MIPNODE" not in source
    assert '"solver_feasibility_check_space"' in source
    assert '"original_model_solution_quality"' in source
    assert "import pyomo" not in source
    assert "from pyomo" not in source
    assert '"time_regions"' in source
    assert "model_optimize_wall_time_seconds" in source
