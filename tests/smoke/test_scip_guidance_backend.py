"""Exercise SCIP binding changes and fresh recovery independently of Gurobi licensing."""
import pytest
pytest.importorskip("pyscipopt")
from cfl_gnn.solvers.neural_guidance import NativeModel
from cfl_gnn.experiments.neural_guidance_policy import guidance_directives

def test_fresh_scip_restores_original_model_and_does_not_reuse_restricted_bound(tmp_path):
    path = tmp_path / "fixture.lp"
    path.write_text("Maximize\n obj: x + 2 y\nSubject To\n cover: x + y >= 1\nBinary\n x y\nEnd\n")
    predictions = [dict(variable_name=n, predicted_value=v, probability=float(v), confidence=1., priority=100)
                   for n,v in [("x",0), ("y",1)]]
    restricted = NativeModel(path, "scip", 5.)
    try:
        signature = (restricted.domains, restricted.rows)
        restricted.apply(guidance_directives(predictions, method="confidence_partial_fixing_with_recovery", fraction=1.))
        result = restricted.optimize()
        assert result["primal"] == 2.
    finally:
        restricted.close()
    recovery = NativeModel(path, "scip", 5.)
    try:
        assert (recovery.domains, recovery.rows) == signature
        recovery.start(result["values"])
        full = recovery.optimize()
        assert full["primal"] == full["dual"] == 1.
    finally:
        recovery.close()
