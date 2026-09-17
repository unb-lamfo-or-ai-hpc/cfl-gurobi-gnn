"""Tiny licensed qualification; mandatory on DGX before the two-medium pilot."""
import os
import pytest

if os.environ.get("CFL_REQUIRE_SOLVER_TESTS") == "1":
    import gurobipy as gp
else:
    gp = pytest.importorskip("gurobipy")

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.graph.label_free_gurobi import prediction_rows
from cfl_gnn.solvers.paired_partial_start import solve


@pytest.fixture(autouse=True)
def licensed():
    try:
        with gp.Env(params={"OutputFlag": 0}):
            pass
    except gp.GurobiError:
        if os.environ.get("CFL_REQUIRE_SOLVER_TESTS") == "1":
            raise
        pytest.skip("working Gurobi license required")


@pytest.fixture
def mip(tmp_path):
    path = tmp_path / "toy.lp"
    path.write_text("Maximize\n obj: x + 2 y\nSubject To\n cover: x + y >= 1\nBinary\n x y\nEnd\n")
    return path


def test_partial_start_preserves_full_optimum_and_parameter_pairing(mip, tmp_path):
    rows = prediction_rows(["x", "y"], [.01, .99], .5)
    control = solve(mip, sha256_file(mip), [], "unguided_control", 5, True)
    guided = solve(mip, sha256_file(mip), rows, "partial_mip_start", 5, True, tmp_path / "guided.solution.json.gz")
    for report in (control, guided):
        assert report["gate_status"] == "passed"
        assert report["solve"]["primal"] == pytest.approx(1.)
        assert report["independent_feasibility"]["valid"]
        assert report["original_objective_sense"] == "MAXIMIZE"
        assert report["effective_objective_sense"] == "MINIMIZE"
        assert report["mathematical_model_unchanged"]
    assert control["parameters"] == guided["parameters"]
    assert control["start"]["submitted_assignments"] == 0
    assert guided["start"]["submitted_assignments"] == 1
    assert guided["start"]["unselected_starts_undefined"]
    assert guided["solution_artifact"]["sha256"] == sha256_file(tmp_path / "guided.solution.json.gz")


def test_unknown_prediction_support_rejected(mip):
    with pytest.raises(ValueError, match="binary support"):
        solve(mip, sha256_file(mip), prediction_rows(["z"], [.9], .5), "partial_mip_start", 5, True)


def test_source_hash_mismatch_rejected_before_solve(mip):
    with pytest.raises(ValueError, match="changed"):
        solve(mip, "0"*64, [], "unguided_control", 5, True)


def test_real_root_label_free_encoder_and_checkpoint_inference(tmp_path):
    if os.environ.get("CFL_REQUIRE_SOLVER_TESTS") == "1":
        import torch
        import torch_geometric
    else:
        torch = pytest.importorskip("torch")
        pytest.importorskip("torch_geometric")
    from cfl_gnn.graph.gurobi_graph_artifact import capture_root_relaxation, canonical_sha256
    from cfl_gnn.graph.label_free_gurobi import build_features, predict
    from cfl_gnn.models.versioning import model_class
    # Odd-cycle cover has a fractional root relaxation; no target solution read.
    path = tmp_path / "fractional.lp"
    path.write_text("Maximize\n obj: x + y + z\nSubject To\n a: x + y >= 1\n b: y + z >= 1\n c: x + z >= 1\nBinary\n x y z\nEnd\n")
    digest = sha256_file(path)
    root = capture_root_relaxation(path, expected_mip_sha256=digest, time_limit_seconds=10)
    graph, order, audit = build_features(path, digest, root)
    assert "y" not in graph["variable"] and "mip_gap" not in graph
    assert audit["root_lp_feature_exactly_encoded"] and not audit["target_labels_loaded"]
    architecture = dict(model_version="gasse_v2_alternating_prenorm", hidden_dim=8, num_layers=1)
    model = model_class(architecture["model_version"])(7, 5, 1, hidden_dim=8, num_layers=1)
    checkpoint = tmp_path / "toy-checkpoint.pt"
    torch.save(model.state_dict(), checkpoint)
    rows = predict(graph, order, checkpoint, architecture, .5, "cpu")
    assert [r["variable_name"] for r in rows] == order
    assert canonical_sha256(order) == audit["binary_order_sha256"]
    assert all(0 <= r["probability"] <= 1 for r in rows)
    graph["variable"].y = torch.zeros(len(order))
    with pytest.raises(ValueError, match="labelled"):
        predict(graph, order, checkpoint, architecture, .5, "cpu")
    root["variable_names"] = list(reversed(root["variable_names"]))
    with pytest.raises(ValueError, match="order"):
        build_features(path, digest, root)
