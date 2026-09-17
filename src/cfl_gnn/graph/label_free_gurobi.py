"""Inference-only Gurobi features using the same encoder as training.

No target solution file or solver label is accepted by this interface. Temporary
encoder placeholders are removed before the graph is returned or serialized.
"""
from __future__ import annotations

import math
import numpy as np

from cfl_gnn.graph.gurobi_graph_artifact import canonical_sha256
from cfl_gnn.graph.instance_provenance import sha256_file


def prediction_rows(names, probabilities, threshold):
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("invalid easy-validation threshold")
    if not names or len(set(names)) != len(names) or len(names) != len(probabilities):
        raise ValueError("prediction identity or length mismatch")
    rows = []
    for name, probability in zip(names, probabilities):
        p = float(probability)
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("non-finite or invalid prediction")
        # Scores are weighted-BCE outputs, not calibrated probabilities. Preserve
        # the existing confidence convention without fitting on medium targets.
        confidence = max(p, 1-p)
        rows.append(dict(variable_name=name, probability=p,
                         predicted_value=int(p >= threshold), confidence=confidence,
                         priority=int(round(100*confidence))))
    return rows


def build_features(mip_path, mip_sha256, root):
    import gurobipy as gp
    from cfl_gnn.artifacts.schemas import ModelFeatures, VariableFeatures, ConstraintFeatures
    from cfl_gnn.graph.build_dataset import build_heterodata
    from cfl_gnn.solvers.neural_guidance import binary_names

    if sha256_file(mip_path) != mip_sha256 or root.get("source_mip_sha256") != mip_sha256:
        raise ValueError("feature source hash mismatch")
    if root.get("capture_method") != "first_optimal_root_gurobi_mipnode" or root.get("effective_objective_sense") != "MINIMIZE":
        raise ValueError("real MINIMIZE root observation required")
    with gp.Env(params={"OutputFlag": 0}) as env, gp.read(str(mip_path), env=env) as model:
        model.ModelSense = gp.GRB.MINIMIZE
        model.update()
        if model.NumQNZs or model.NumQConstrs or model.NumGenConstrs or model.NumSOS:
            raise ValueError("only linear CFL models are supported")
        variables, constraints = model.getVars(), model.getConstrs()
        names = [v.VarName for v in variables]
        domains = [(v.VarName, v.LB, v.UB, v.VType) for v in variables]
        binaries = binary_names(domains)
        if len(set(names)) != len(names) or not binaries:
            raise ValueError("unique names and binary support are required")
        if root["variable_names"] != names or root["variable_order_sha256"] != canonical_sha256(names):
            raise ValueError("root variable order mismatch")
        vector = np.asarray(root["relaxation_vector"], dtype=np.float64)
        if vector.shape != (len(names),) or not np.isfinite(vector).all() or canonical_sha256(vector.tolist()) != root["vector_sha256"]:
            raise ValueError("invalid root vector")
        matrix = model.getA().tocoo()
        types = np.array([v.VType for v in variables])
        graph = build_heterodata(
            ModelFeatures(num_vars=len(variables), num_constrs=len(constraints),
                          num_binary=int(sum(types == "B")), num_integer=int(sum(types == "I")),
                          num_continuous=int(sum(types == "C")), obj_sense="MINIMIZE", obj_offset=model.ObjCon),
            VariableFeatures(types=types, lower_bounds=np.array([v.LB for v in variables]),
                             upper_bounds=np.array([v.UB for v in variables]), obj_coeffs=np.array([v.Obj for v in variables])),
            ConstraintFeatures(senses=np.array([c.Sense for c in constraints]), rhs_values=np.array([c.RHS for c in constraints]),
                               row_norms=np.sqrt(np.bincount(matrix.row, weights=matrix.data**2, minlength=len(constraints)))),
            np.array([matrix.row, matrix.col]), matrix.data, np.zeros(len(names)), vector,
            0., 0., False, -1, "unlabelled_medium_features", {}, strict=True, edge_layout="constraint_variable")
        if graph is None:
            raise ValueError("feature encoder rejected input")
        del graph["variable"].y
        for key in ("mip_gap", "exec_time", "is_optimal", "incumbent_node"):
            del graph[key]
        if not np.array_equal(graph["variable"].x[:, 6].numpy(), vector.astype(np.float32)):
            raise ValueError("root feature changed during encoding")
        binary_order = [n for n in names if n in binaries]
        if int(graph["variable"].is_discrete.sum()) != len(binary_order):
            raise ValueError("graph discrete support differs from solver binary support")
        return graph, binary_order, {"variables": len(names), "constraints": len(constraints),
            "nonzeros": len(matrix.data), "binary_variables": len(binary_order),
            "variable_order_sha256": canonical_sha256(names), "binary_order_sha256": canonical_sha256(binary_order),
            "root_lp_feature_exactly_encoded": True, "target_labels_loaded": False}


def predict(graph, binary_order, checkpoint, architecture, threshold, device_name):
    import torch
    from cfl_gnn.models.versioning import model_class
    if "y" in graph["variable"]:
        raise ValueError("target-labelled graphs are prohibited")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise ValueError("requested CUDA device unavailable")
    device = torch.device(device_name)
    graph = graph.to(device)
    edge = graph["variable", "rev_coef", "constraint"]
    model = model_class(architecture["model_version"])(
        var_in_dim=7, cons_in_dim=5, edge_dim=1,
        hidden_dim=architecture["hidden_dim"], num_layers=architecture["num_layers"]).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    model.eval()
    with torch.inference_mode():
        logits = model(x_var=graph["variable"].x, x_cons=graph["constraint"].x,
                       edge_v2c=edge.edge_index, edge_attr=edge.edge_attr,
                       binary_mask=graph["variable"].is_discrete.bool())
        probabilities = torch.sigmoid(logits).detach().cpu().reshape(-1).tolist()
    # CPU transfer synchronizes CUDA. No prenorm fitting or training is allowed.
    return prediction_rows(binary_order, probabilities, threshold)
