"""Scientific operations for the isolated PR94 preparation stage.

Imported only by an admitted batch child. No submission or training interface.
"""

import hashlib
import math
import time
from types import SimpleNamespace

import pr94_isolated_preparation as flow


def api():
    import gurobipy as gp
    from cfl_gnn.solvers.paired_partial_start import mathematical_signature
    from pr86_native_model import NativeModel

    return SimpleNamespace(
        gp=gp, NativeModel=NativeModel, signature=mathematical_signature
    )


def capture(mip, expected, folder, intent, runtime=None):
    runtime = runtime or api()
    gp = runtime.gp
    flow.need(list(gp.gurobi.version()) == [13, 0, 1], "gurobi_version")
    flow.need(flow.file_sha(mip) == expected, "model_hash")
    backend = runtime.NativeModel(mip, "gurobi", 600)
    found, failed = {}, []
    try:
        model = backend.model
        for key, value in flow.ROOT_PARAMETERS.items():
            setattr(model.Params, key, value)
        model.Params.LogFile = str(folder / "gurobi.private.log")
        model.update()
        flow.need(
            not (
                model.NumQNZs
                or model.NumQConstrs
                or model.NumGenConstrs
                or model.NumSOS
            ),
            "linear_MILP",
        )
        flow.need(model.ModelSense == gp.GRB.MINIMIZE, "MINIMIZE")
        flow.need(model.SolCount == 0 and model.NumStart == 0, "fresh_model")
        flow.need(
            all(getattr(model.Params, k) == v for k, v in flow.ROOT_PARAMETERS.items()),
            "root_parameters",
        )
        signature = runtime.signature(model)
        variables = tuple(model.getVars())
        names = [v.VarName for v in variables]
        flow.need(len(names) == len(set(names)) and names, "variable_order")

        def observer(m, where):
            if found or failed or where != gp.GRB.Callback.MIPNODE:
                return
            try:
                if (
                    int(m.cbGet(gp.GRB.Callback.MIPNODE_STATUS)) != gp.GRB.OPTIMAL
                    or abs(float(m.cbGet(gp.GRB.Callback.MIPNODE_NODCNT))) > 1e-9
                ):
                    return
                values = [float(v) for v in m.cbGetNodeRel(variables)]
                bound = float(m.cbGet(gp.GRB.Callback.MIPNODE_OBJBND))
                flow.need(
                    len(values) == len(names)
                    and all(math.isfinite(v) for v in values)
                    and math.isfinite(bound),
                    "finite_root",
                )
                found.update(vector=values, bound=bound)
                m.terminate()
            except Exception:
                failed.append(True)
                m.terminate()

        intent()  # Exclusive durable claim immediately before the only solve.
        model.optimize(observer)
        flow.need(
            not failed and found and int(model.Status) != 17, "optimal_root_missing"
        )
        flow.need(runtime.signature(model) == signature, "model_changed")
        flow.need(flow.file_sha(mip) == expected, "input_changed")
        parameters = {**flow.ROOT_PARAMETERS, "ModelSense": 1}
        return {
            "schema_version": 1,
            "authority": "gurobi",
            "source_mip_sha256": expected,
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "original_objective_sense": backend.original_sense,
            "effective_objective_sense": "MINIMIZE",
            "variable_count": len(names),
            "variable_names": names,
            "variable_order_sha256": flow.canonical_sha(names),
            "relaxation_vector": found["vector"],
            "vector_sha256": flow.canonical_sha(found["vector"]),
            "node_count": 0,
            "root_objective_bound": found["bound"],
            "solver_parameter_map": parameters,
            "solver_parameter_sha256": flow.canonical_sha(parameters),
            "mathematical_signature_sha256": signature,
        }
    finally:
        backend.close()


def tensor_sha(graph):
    """Logical tensor digest, separate from serialization bytes."""
    names = [
        ("variable", "x"),
        ("variable", "is_discrete"),
        ("constraint", "x"),
        (("variable", "rev_coef", "constraint"), "edge_index"),
        (("variable", "rev_coef", "constraint"), "edge_attr"),
        (("constraint", "coef", "variable"), "edge_index"),
        (("constraint", "coef", "variable"), "edge_attr"),
    ]
    result = hashlib.sha256()
    for store, key in names:
        value = graph[store][key].detach().cpu().contiguous().numpy()
        result.update(flow.encoded([store, key, str(value.dtype), list(value.shape)]))
        result.update(value.tobytes(order="C"))
    return result.hexdigest()


def graph_checks(graph, root, binary_order):
    import torch

    flow.need("y" not in graph["variable"], "target_label_in_graph")
    flow.need(
        not any(
            k in graph for k in ("mip_gap", "exec_time", "is_optimal", "incumbent_node")
        ),
        "target_metadata_in_graph",
    )
    n = len(root["variable_names"])
    flow.need(
        tuple(graph["variable"].x.shape) == (n, 7)
        and graph["constraint"].x.ndim == 2
        and graph["constraint"].x.shape[1] == 5,
        "feature_shapes",
    )
    expected = torch.tensor(root["relaxation_vector"], dtype=torch.float32)
    flow.need(torch.equal(graph["variable"].x[:, 6].cpu(), expected), "root_feature")
    mask = graph["variable"].is_discrete.bool().cpu()
    names = [name for name, use in zip(root["variable_names"], mask.tolist()) if use]
    flow.need(names == binary_order and len(names) == len(set(names)), "binary_order")
    edge = graph["variable", "rev_coef", "constraint"]
    reverse = graph["constraint", "coef", "variable"]
    flow.need(
        tuple(edge.edge_attr.shape) == (edge.edge_index.shape[1], 1)
        and torch.equal(edge.edge_index.flip(0), reverse.edge_index)
        and torch.equal(edge.edge_attr, reverse.edge_attr),
        "edge_order",
    )
    for value in (
        graph["variable"].x,
        graph["constraint"].x,
        edge.edge_attr,
    ):
        flow.need(bool(torch.isfinite(value).all()), "finite_features")
    flow.need(
        edge.edge_index.numel() == 0
        or (
            int(edge.edge_index.min()) >= 0
            and int(edge.edge_index[0].max()) < n
            and int(edge.edge_index[1].max()) < len(graph["constraint"].x)
        ),
        "edge_bounds",
    )


def checkpoint_model(path, device):
    import torch
    from cfl_gnn.models.versioning import model_class

    with path.open("rb") as stream:
        flow.need(flow.stream_sha(stream) == flow.CHECKPOINT, "checkpoint_hash")
        stream.seek(0)
        state = torch.load(stream, map_location="cpu", weights_only=True)
        stream.seek(0)
        flow.need(flow.stream_sha(stream) == flow.CHECKPOINT, "checkpoint_changed")
    model = model_class("gasse_v2_alternating_prenorm")(
        var_in_dim=7,
        cons_in_dim=5,
        edge_dim=1,
        hidden_dim=32,
        num_layers=2,
    )
    model.load_state_dict(
        {k.removeprefix("module."): v for k, v in state.items()},
        strict=True,
    )
    return model.to(device).eval().requires_grad_(False)


def guidance_one(parent, target, mip, root, model, device, folder, intent):
    import torch
    from cfl_gnn.experiments.pr58_guidance import (
        class_aware_gnn_assignments,
        matched_root_lp_assignments,
    )
    from cfl_gnn.graph.label_free_gurobi import build_features

    runtime = api()
    native = runtime.NativeModel(mip, "gurobi", 600)
    try:
        flow.need(
            runtime.signature(native.model) == root["mathematical_signature_sha256"],
            "root_model_signature",
        )
    finally:
        native.close()
    regions = {}
    started = time.perf_counter()
    graph, binary_order, metadata = build_features(mip, target["model_sha256"], root)
    graph_checks(graph, root, binary_order)
    logical_sha = tensor_sha(graph)
    graph_path = folder / "graph.private.pt"
    with graph_path.open("xb") as stream:
        torch.save(graph, stream)
        flow.sync(stream)
    graph_sha = flow.file_sha(graph_path)
    # Only the just-written, hash-bound trusted graph is deserialized.
    with graph_path.open("rb") as stream:
        flow.need(flow.stream_sha(stream) == graph_sha, "graph_bytes")
        stream.seek(0)
        restored = torch.load(stream, map_location="cpu", weights_only=False)
    graph_checks(restored, root, binary_order)
    flow.need(tensor_sha(restored) == logical_sha, "graph_round_trip")
    regions["features"] = time.perf_counter() - started
    started = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    graph = restored.to(device)
    edge = graph["variable", "rev_coef", "constraint"]
    torch.cuda.synchronize()
    intent()
    forward_start = time.perf_counter()
    with torch.no_grad():
        logits = model(
            x_var=graph["variable"].x,
            x_cons=graph["constraint"].x,
            edge_v2c=edge.edge_index,
            edge_attr=edge.edge_attr,
            binary_mask=graph["variable"].is_discrete.bool(),
        )
        scores = torch.sigmoid(logits)
    torch.cuda.synchronize()
    forward_seconds = time.perf_counter() - forward_start
    flow.need(
        logits.numel() == len(binary_order) and bool(torch.isfinite(logits).all()),
        "forward_shape",
    )
    probabilities = scores.cpu().reshape(-1).tolist()
    predictions = [
        dict(
            variable_name=n,
            probability=float(p),
            predicted_value=int(p >= flow.THRESHOLD),
        )
        for n, p in zip(binary_order, probabilities)
    ]
    regions["inference"] = time.perf_counter() - started
    started = time.perf_counter()
    g = class_aware_gnn_assignments(predictions, fraction=0.1, absolute_cap=20000)
    regions["assembly_gnn"] = time.perf_counter() - started
    index = {name: i for i, name in enumerate(root["variable_names"])}
    started = time.perf_counter()
    r = matched_root_lp_assignments(
        binary_order,
        [root["relaxation_vector"][index[n]] for n in binary_order],
        support=g["selected_support"],
        positive_assignments=g["positive_assignments"],
    )
    flow.validate_starts(g, r, len(binary_order))
    regions["assembly_lp"] = time.perf_counter() - started
    started = time.perf_counter()
    prediction_sha = flow.write_once(
        folder / "predictions.private.json",
        {
            "parent": parent,
            "checkpoint_sha256": flow.CHECKPOINT,
            "predictions": predictions,
        },
    )
    starts_sha = flow.write_once(
        folder / "starts.private.json", {"gnn": g, "root_lp": r}
    )
    regions["private_export"] = time.perf_counter() - started
    flow.need(flow.file_sha(mip) == target["model_sha256"], "input_changed")
    return {
        "parent": parent,
        "model_sha256": target["model_sha256"],
        "root_sha256": target["root_sha256"],
        "graph_sha256": graph_sha,
        "logical_feature_sha256": logical_sha,
        "variable_order_sha256": root["variable_order_sha256"],
        "binary_order_sha256": metadata["binary_order_sha256"],
        "prediction_sha256": prediction_sha,
        "private_starts_sha256": starts_sha,
        "M1_assignment_sha256": r["assignment_sha256"],
        "M2_assignment_sha256": g["assignment_sha256"],
        "checkpoint_sha256": flow.CHECKPOINT,
        "binary_variables": len(binary_order),
        "selected_support": g["selected_support"],
        "positive_assignments": g["positive_assignments"],
        "abstained": g["abstained"],
        "regions_seconds": regions,
        "forward_seconds_nested_in_inference": forward_seconds,
        "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "gpu_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "labels_loaded": False,
        "graph_round_trip": True,
        "forward_calls": 1,
        "optimization_calls": 0,
        "training_calls": 0,
        "scientific_reporting_eligible": False,
    }
