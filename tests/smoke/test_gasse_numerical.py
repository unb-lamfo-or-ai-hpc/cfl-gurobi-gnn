"""Exercise the original toy generator, alternating prenorm and serialization."""
import importlib.util
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
from torch_geometric.data import HeteroData
from cfl_gnn.models.gasse_calibrated import GasseGNN, fit_training_prenorm
from cfl_gnn.models.gasse import _scatter_sum
from cfl_gnn.training.binary_contract import binary_targets


def toy():
    path = Path(__file__).resolve().parents[2] / "sandbox" / "toy_bipartite.py"
    spec = importlib.util.spec_from_file_location("cfl_toy_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_graph(seed=42)


def args(graph):
    edge = graph["var", "to", "cons"]
    return dict(x_var=graph["var"].x, x_cons=graph["cons"].x,
                edge_v2c=edge.edge_index, edge_attr=edge.edge_attr,
                binary_mask=graph["var"].binary_mask)


def test_updated_constraint_messages_fit_the_variable_prenorm(tmp_path):
    torch.set_num_threads(1)
    graph = toy()
    model = GasseGNN(4, 3, 2, hidden_dim=8, num_layers=1)
    kw = args(graph)
    model.fit_prenorm(**{k:v for k,v in kw.items() if k != "binary_mask"})
    with torch.no_grad():
        hv = torch.relu(model.var_encoder(kw["x_var"]))
        hc = torch.relu(model.cons_encoder(kw["x_cons"]))
        conv = model.convs[0]
        vi, ci = kw["edge_v2c"]
        msg = conv._edge_input(hc, hv, kw["edge_v2c"], kw["edge_attr"])
        sums = _scatter_sum(conv.g_C(msg), ci, len(hc))
        hc = torch.relu(conv.f_C(torch.cat([hc, conv.prenorm_C(sums)], -1)))
        msg = conv._edge_input(hc, hv, kw["edge_v2c"], kw["edge_attr"])
        expected = _scatter_sum(conv.g_V(msg), vi, len(hv))
        torch.testing.assert_close(conv.prenorm_V.beta, expected.mean(0))
    labels = graph["var"].y[kw["binary_mask"]]
    optimizer = torch.optim.Adam(model.parameters(), lr=.01)
    initial = torch.nn.functional.binary_cross_entropy_with_logits(model(**kw), labels).item()
    for _ in range(120):
        optimizer.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(model(**kw), labels)
        loss.backward()
        assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
        optimizer.step()
    assert loss.item() < initial*.25
    target = tmp_path / "weights.pt"
    torch.save(model.state_dict(), target)
    replay = GasseGNN(4, 3, 2, hidden_dim=8, num_layers=1)
    replay.load_state_dict(torch.load(target, weights_only=True))
    torch.testing.assert_close(model(**kw), replay(**kw))
    # Reorder edges: aggregation must not depend on their storage order.
    perm = torch.randperm(kw["edge_v2c"].shape[1])
    other = kw | {"edge_v2c": kw["edge_v2c"][:, perm], "edge_attr": kw["edge_attr"][perm]}
    torch.testing.assert_close(model(**kw), model(**other), atol=1e-4, rtol=1e-4)


def test_all_training_population_prenorm_replays_identically():
    source = toy()
    graph = HeteroData()
    graph["variable"].x = source["var"].x
    graph["constraint"].x = source["cons"].x
    edge = source["var", "to", "cons"]
    graph["variable", "rev_coef", "constraint"].edge_index = edge.edge_index
    graph["variable", "rev_coef", "constraint"].edge_attr = edge.edge_attr
    torch.manual_seed(42)
    a = GasseGNN(4, 3, 2, hidden_dim=8, num_layers=2)
    b = GasseGNN(4, 3, 2, hidden_dim=8, num_layers=2)
    b.load_state_dict(a.state_dict())
    for model in (a, b):
        report = fit_training_prenorm(model, [graph.clone(), graph.clone()], "cpu")
        assert report["training_graphs"] == 2 and not report["validation_or_test_used"]
    for key in a.state_dict():
        torch.testing.assert_close(a.state_dict()[key], b.state_dict()[key])


def test_binary_targets_never_clamp_general_integers():
    graph = HeteroData()
    graph["variable"].x = torch.tensor([[0,0,.69314718,0,1,0,.5]], dtype=torch.float)
    graph["variable"].is_discrete = torch.tensor([True])
    graph["variable"].y = torch.tensor([1.])
    assert binary_targets(graph)[1].item() == 1.
    graph["variable"].y = torch.tensor([2.])
    with pytest.raises(ValueError):
        binary_targets(graph)


def test_node_permutation_and_disjoint_union_are_equivariant():
    torch.manual_seed(42)
    graph = toy()
    kw = args(graph)
    model = GasseGNN(4, 3, 2, hidden_dim=8, num_layers=2)
    model.fit_prenorm(**{k:v for k,v in kw.items() if k != "binary_mask"})
    nv, nc = len(kw["x_var"]), len(kw["x_cons"])
    pv, pc = torch.randperm(nv), torch.randperm(nc)
    ev, ec = kw["edge_v2c"]
    permuted = kw | {"x_var": kw["x_var"][pv], "x_cons": kw["x_cons"][pc],
        "binary_mask": torch.ones(nv, dtype=torch.bool),
        "edge_v2c": torch.stack([torch.argsort(pv)[ev], torch.argsort(pc)[ec]])}
    complete = kw | {"binary_mask": torch.ones(nv, dtype=torch.bool)}
    torch.testing.assert_close(model(**permuted), model(**complete)[pv], atol=1e-4, rtol=1e-4)
    doubled = {"x_var": kw["x_var"].repeat(2, 1), "x_cons": kw["x_cons"].repeat(2, 1),
        "edge_v2c": torch.cat([kw["edge_v2c"], kw["edge_v2c"] + torch.tensor([[nv], [nc]])], 1),
        "edge_attr": kw["edge_attr"].repeat(2, 1), "binary_mask": kw["binary_mask"].repeat(2)}
    torch.testing.assert_close(model(**doubled), model(**kw).repeat(2), atol=1e-4, rtol=1e-4)


def test_heldout_prediction_export_uses_real_pyg_batch_names(tmp_path, monkeypatch):
    import gzip
    import json
    from cfl_gnn.evaluation import gasse_reconnected as evaluator
    graph = HeteroData()
    graph["variable"].x = torch.tensor([[0., 0., .69314718, 0., 1., 0., .5]] * 3)
    graph["variable"].y = torch.tensor([1., 0., 0.])
    graph["variable"].is_discrete = torch.ones(3, dtype=torch.bool)
    graph["constraint"].x = torch.ones(1, 5)
    graph["variable", "rev_coef", "constraint"].edge_index = torch.tensor([[0,1,2], [0,0,0]])
    graph["variable", "rev_coef", "constraint"].edge_attr = torch.ones(3, 1)
    graph.variable_names = ["x0", "x1", "x2"]
    # Contract/ledger validation is tested separately; this exercises the real
    # numeric execution and PyG collation without requiring an external MILP.
    monkeypatch.setattr(evaluator, "validate_evaluation_plan", lambda plan: None)
    monkeypatch.setattr(evaluator, "GasseLabelViewDataset", lambda *a, **k: [graph.clone()])
    model = GasseGNN(7, 5, 1, hidden_dim=8, num_layers=1)
    model.fit_prenorm(graph["variable"].x, graph["constraint"].x,
                      graph["variable", "rev_coef", "constraint"].edge_index,
                      graph["variable", "rev_coef", "constraint"].edge_attr)
    checkpoint = tmp_path / "model.pt"
    torch.save(model.state_dict(), checkpoint)
    plan = {"contract_sha256": "a"*64,
            "architecture": {"model_version": "gasse_v2_alternating_prenorm", "hidden_dim": 8, "num_layers": 1},
            "test_records": [{"parent_instance_id": "toy", "difficulty": "easy", "mip_sha256": "b"*64}],
            "probability_threshold": .5, "threshold_source": "fixed_toy",
            "diagnostics": {"calibration_bins": 10}}
    report = evaluator.execute_evaluation(plan, graph_root=tmp_path, label_root=tmp_path,
        checkpoint_path=checkpoint, output_dir=tmp_path / "evaluation", device_name="cpu")
    assert report["gate_status"] == "passed"
    assert report["parent_macro_classification"]["f1_score"] >= 0
    with gzip.open(tmp_path / "evaluation/predictions/toy.json.gz", "rt") as stream:
        payload = json.load(stream)
    assert [p["variable_name"] for p in payload["predictions"]] == ["x0", "x1", "x2"]
    assert all("label" not in p and "target" not in p for p in payload["predictions"])
    assert payload["model_inference_wall_time_seconds"] >= 0
