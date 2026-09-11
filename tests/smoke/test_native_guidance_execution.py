"""Real tiny MILP integrations, skipped only when the solver is unavailable."""
import pytest
pytest.importorskip("gurobipy")
pytest.importorskip("pyscipopt")
from cfl_gnn.solvers.neural_guidance import run_guidance


@pytest.fixture(autouse=True)
def working_license():
    import os
    import gurobipy as gp
    try:
        with gp.Env(params={"OutputFlag": 0}):
            pass
    except gp.GurobiError:
        if os.environ.get("CFL_REQUIRE_SOLVER_TESTS") == "1":
            raise
        pytest.skip("a working Gurobi license is required for independent feasibility authority")


@pytest.mark.parametrize("solver", ["gurobi", "scip"])
@pytest.mark.parametrize("method", ["unguided_control", "partial_mip_start",
    "confidence_partial_fixing_with_recovery", "local_branching_trust_region_with_recovery"])
def test_fresh_full_model_recovers_true_optimum(tmp_path, solver, method):
    path = tmp_path / "tiny.lp"
    path.write_text("Maximize\n obj: x + 2 y\nSubject To\n cover: x + y >= 1\nBinary\n x y\nEnd\n")
    rows = [dict(variable_name=n, predicted_value=v, probability=float(v), confidence=1., priority=100)
            for n, v in [("x", 0), ("y", 1)]]
    report = run_guidance(mip_path=path, predictions=rows, solver=solver, method=method,
                          fraction=1. if method.endswith("fixing_with_recovery") else None,
                          radius_fraction=.01 if method.startswith("local_branching") else None,
                          time_limit=5, engineering_smoke=True)
    assert report["gate_status"] == "passed"
    assert report["original_objective_sense"] == "MAXIMIZE"
    assert report["phases"][-1]["primal"] == pytest.approx(1.)
    assert report["independent_feasibility"]["valid"]
    assert report["common_mip_gap_relative"] == 0.
    if "recovery" in method:
        assert report["full_model_recovery_executed"]
        assert not report["restricted_dual_bounds_used_for_final_gap"]


def test_native_hints_preserve_feasible_region(tmp_path):
    path = tmp_path / "hint.lp"
    path.write_text("Maximize\n obj: x\nSubject To\n dummy: x >= 0\nBinary\n x\nEnd\n")
    report = run_guidance(mip_path=path, solver="gurobi", method="gurobi_variable_hints",
                          predictions=[dict(variable_name="x", predicted_value=1, probability=.9, confidence=.9, priority=90)],
                          time_limit=5, engineering_smoke=True)
    assert report["phases"][0]["primal"] == 0.
    assert not report["full_model_recovery_executed"]
