"""Gurobi-authoritative bipartite graph construction.

The recovered pipeline creates one graph per mathematical MIP.  Incumbents are
labels and provenance records; they are never treated as graph identities.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from cfl_gnn.graph.instance_provenance import sha256_file


class GurobiGraphError(RuntimeError):
    """Raised when a Gurobi graph artifact cannot be audited safely."""


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using the repository canonical form."""
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _read_gzip_json(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, TypeError, ValueError) as error:
        raise GurobiGraphError(f"unreadable Gurobi solution: {path.name}") from error
    if not isinstance(value, dict):
        raise GurobiGraphError("Gurobi solution must be a JSON object")
    return value


def _write_gzip_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def _finite_vector(values: Any, *, expected: int, field: str) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or len(vector) != expected:
        raise GurobiGraphError(f"{field} length differs from the Gurobi model")
    if not np.isfinite(vector).all():
        raise GurobiGraphError(f"{field} contains non-finite values")
    return vector


def capture_root_relaxation(
    mip_path: str | Path,
    *,
    expected_mip_sha256: str,
    time_limit_seconds: float = 600.0,
    threads: int = 1,
    seed: int = 42,
    presolve: int = 0,
) -> dict[str, Any]:
    """Capture the first optimal root-node relaxation via passive ``MIPNODE``.

    This intentionally matches the first root observation recorded by the
    preserved Phase 1 callback.  There is no continuous-relaxation or zero
    fallback: absence of the documented callback observation fails the gate.
    """
    import gurobipy as gp
    from gurobipy import GRB

    source = Path(mip_path).resolve()
    if sha256_file(source) != expected_mip_sha256:
        raise GurobiGraphError("MIP SHA-256 changed before root capture")
    model = gp.read(str(source))
    captured: dict[str, Any] = {}
    try:
        original_sense = (
            "MINIMIZE" if int(model.ModelSense) == int(GRB.MINIMIZE) else "MAXIMIZE"
        )
        model.ModelSense = GRB.MINIMIZE
        model.Params.OutputFlag = 0
        model.Params.TimeLimit = float(time_limit_seconds)
        model.Params.NodeLimit = 1
        model.Params.Threads = int(threads)
        model.Params.Seed = int(seed)
        model.Params.Presolve = int(presolve)
        model.update()
        variables = tuple(model.getVars())
        variable_names = [str(variable.VarName) for variable in variables]

        def observer(callback_model: Any, where: int) -> None:
            if captured or where != GRB.Callback.MIPNODE:
                return
            status = int(callback_model.cbGet(GRB.Callback.MIPNODE_STATUS))
            node_count = float(callback_model.cbGet(GRB.Callback.MIPNODE_NODCNT))
            if status != int(GRB.OPTIMAL) or abs(node_count) > 1e-9:
                return
            values = callback_model.cbGetNodeRel(variables)
            vector = _finite_vector(
                values,
                expected=len(variable_names),
                field="root relaxation",
            )
            captured.update(
                {
                    "vector": vector.tolist(),
                    "node_count": node_count,
                    "objective": float(
                        callback_model.cbGet(GRB.Callback.MIPNODE_OBJBND)
                    ),
                }
            )
            callback_model.terminate()

        model.optimize(observer)
        if not captured:
            raise GurobiGraphError("no optimal root MIPNODE relaxation was observed")
        vector = _finite_vector(
            captured["vector"], expected=len(variable_names), field="root relaxation"
        )
        parameter_map = {
            "ModelSense": int(model.ModelSense),
            "NodeLimit": 1,
            "OutputFlag": 0,
            "Presolve": int(presolve),
            "Seed": int(seed),
            "Threads": int(threads),
            "TimeLimit": float(time_limit_seconds),
        }
        return {
            "schema_version": 1,
            "source_mip_sha256": expected_mip_sha256,
            "authority": "gurobi",
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "original_objective_sense": original_sense,
            "effective_objective_sense": "MINIMIZE",
            "variable_count": len(variable_names),
            "variable_order_sha256": canonical_sha256(variable_names),
            "vector_sha256": canonical_sha256(vector.tolist()),
            "node_count": captured["node_count"],
            "root_objective_bound": captured["objective"],
            "solver_parameter_map": parameter_map,
            "solver_parameter_sha256": canonical_sha256(parameter_map),
            "variable_names": variable_names,
            "relaxation_vector": vector.tolist(),
        }
    finally:
        model.dispose()


def load_legacy_root_vector(
    path: str | Path, *, expected_variables: int
) -> tuple[np.ndarray, dict[str, Any]]:
    """Load the first preserved node-zero observation for parity auditing."""
    import pyarrow.parquet as pq

    artifact = Path(path).resolve()
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise GurobiGraphError("legacy root-relaxation artifact is unavailable")
    table = pq.read_table(
        artifact,
        columns=["node", "relaxation_vector"],
        filters=[("node", "==", 0)],
    )
    if table.num_rows == 0:
        raise GurobiGraphError("legacy artifact has no node-zero observation")
    vector = _finite_vector(
        table.column("relaxation_vector")[0].as_py(),
        expected=expected_variables,
        field="legacy root relaxation",
    )
    return vector, {
        "artifact_file_name": artifact.name,
        "artifact_sha256": sha256_file(artifact),
        "observation_index": 0,
        "selection": "first_node_zero_observation",
    }


def compare_root_relaxations(
    current: Any, legacy: Any, *, tolerance: float = 1e-8
) -> dict[str, Any]:
    """Return an explicit numeric parity decision for two root vectors."""
    left = np.asarray(current, dtype=np.float64)
    right = np.asarray(legacy, dtype=np.float64)
    if left.ndim != 1 or right.ndim != 1 or left.shape != right.shape:
        return {
            "status": "failed",
            "reason_code": "root_vector_shape_mismatch",
            "vector_length": None,
            "maximum_absolute_difference": None,
            "mean_absolute_difference": None,
            "tolerance": float(tolerance),
        }
    difference = np.abs(left - right)
    maximum = float(np.max(difference)) if len(difference) else 0.0
    mean = float(np.mean(difference)) if len(difference) else 0.0
    passed = math.isfinite(maximum) and maximum <= float(tolerance)
    return {
        "status": "passed" if passed else "failed",
        "reason_code": (
            "gurobi_root_relaxation_matches_legacy"
            if passed
            else "gurobi_root_relaxation_differs_from_legacy"
        ),
        "vector_length": len(left),
        "maximum_absolute_difference": maximum,
        "mean_absolute_difference": mean,
        "tolerance": float(tolerance),
    }


def _solution_by_name(payload: Mapping[str, Any]) -> dict[str, float]:
    if payload.get("solution_source") != "independent_gurobi_optimization":
        raise GurobiGraphError("graph labels must originate from Gurobi")
    variables = payload.get("variables")
    if not isinstance(variables, list) or not variables:
        raise GurobiGraphError("Gurobi solution contains no named variables")
    result: dict[str, float] = {}
    for item in variables:
        if not isinstance(item, Mapping):
            raise GurobiGraphError("invalid named-variable record")
        name = str(item.get("name", ""))
        if not name or name in result:
            raise GurobiGraphError("invalid or duplicate solution variable")
        value = float(item["value"])
        if not math.isfinite(value):
            raise GurobiGraphError("solution contains a non-finite value")
        result[name] = value
    return result


def build_graph_artifact(
    *,
    mip_path: str | Path,
    mip_sha256: str,
    solution_path: str | Path,
    solution_sha256: str,
    root_payload: Mapping[str, Any],
    output_path: str | Path,
    sample_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build exactly one strict graph from one mathematical MIP using Gurobi."""
    import gurobipy as gp
    import torch
    from gurobipy import GRB

    from cfl_gnn.artifacts.schemas import (
        ConstraintFeatures,
        ModelFeatures,
        VariableFeatures,
    )
    from cfl_gnn.graph.build_dataset import build_heterodata

    source = Path(mip_path).resolve()
    label_path = Path(solution_path).resolve()
    destination = Path(output_path).resolve()
    if sha256_file(source) != mip_sha256:
        raise GurobiGraphError("MIP SHA-256 changed before graph construction")
    if sha256_file(label_path) != solution_sha256:
        raise GurobiGraphError("solution SHA-256 changed before graph construction")
    solution_payload = _read_gzip_json(label_path)
    solution = _solution_by_name(solution_payload)
    model = gp.read(str(source))
    try:
        original_sense = (
            "MINIMIZE" if int(model.ModelSense) == int(GRB.MINIMIZE) else "MAXIMIZE"
        )
        model.ModelSense = GRB.MINIMIZE
        model.update()
        variables = tuple(model.getVars())
        constraints = tuple(model.getConstrs())
        variable_names = [str(variable.VarName) for variable in variables]
        if len(set(variable_names)) != len(variable_names):
            raise GurobiGraphError("Gurobi model contains duplicate variable names")
        if set(variable_names) != set(solution):
            raise GurobiGraphError("Gurobi solution and MIP variable identities differ")
        if canonical_sha256(variable_names) != root_payload.get(
            "variable_order_sha256"
        ):
            raise GurobiGraphError("root and graph variable orders differ")
        root_vector = _finite_vector(
            root_payload.get("relaxation_vector"),
            expected=len(variables),
            field="root relaxation",
        )
        variable_index = {name: index for index, name in enumerate(variable_names)}
        types = np.asarray([str(variable.VType) for variable in variables], dtype="<U1")
        unsupported = sorted(set(types) - {"B", "C", "I"})
        if unsupported:
            raise GurobiGraphError(
                "unsupported Gurobi variable types: " + ",".join(unsupported)
            )
        lower = np.asarray([float(variable.LB) for variable in variables])
        upper = np.asarray([float(variable.UB) for variable in variables])
        objective = np.asarray([float(variable.Obj) for variable in variables])
        senses: list[str] = []
        rhs: list[float] = []
        row_norms: list[float] = []
        row_indices: list[int] = []
        column_indices: list[int] = []
        coefficients: list[float] = []
        for row_index, constraint in enumerate(constraints):
            senses.append(str(constraint.Sense))
            rhs.append(float(constraint.RHS))
            row = model.getRow(constraint)
            row_values: list[float] = []
            for term_index in range(row.size()):
                coefficient = float(row.getCoeff(term_index))
                name = str(row.getVar(term_index).VarName)
                row_indices.append(row_index)
                column_indices.append(variable_index[name])
                coefficients.append(coefficient)
                row_values.append(coefficient)
            row_norms.append(float(np.linalg.norm(row_values)))
        labels = np.asarray([solution[name] for name in variable_names])
        graph = build_heterodata(
            ModelFeatures(
                num_vars=len(variables),
                num_constrs=len(constraints),
                num_binary=int(np.sum(types == "B")),
                num_integer=int(np.sum(types == "I")),
                num_continuous=int(np.sum(types == "C")),
                obj_sense="MINIMIZE",
                obj_offset=float(model.ObjCon),
            ),
            VariableFeatures(
                types=types,
                lower_bounds=lower,
                upper_bounds=upper,
                obj_coeffs=objective,
            ),
            ConstraintFeatures(
                senses=np.asarray(senses, dtype="<U1"),
                rhs_values=np.asarray(rhs),
                row_norms=np.asarray(row_norms),
            ),
            np.asarray([row_indices, column_indices], dtype=np.int64),
            np.asarray(coefficients),
            labels,
            root_vector,
            float(solution_payload["mip_gap_relative"]),
            float(solution_payload["execution_time_seconds"]),
            float(solution_payload["mip_gap_relative"]) <= 1e-4,
            -1,
            str(sample_metadata["sample_id"]),
            {"complexity_class": sample_metadata["difficulty"]},
        )
        if graph is None:
            raise GurobiGraphError("production encoder rejected the graph")
        graph.sample_id = str(sample_metadata["sample_id"])
        graph.source_instance_id = str(sample_metadata["source_instance_id"])
        graph.parent_instance_id = str(
            sample_metadata.get(
                "parent_instance_id", sample_metadata["source_instance_id"]
            )
        )
        graph.category = str(sample_metadata["category"])
        graph.difficulty = str(sample_metadata["difficulty"])
        graph.instance_fold = int(sample_metadata["fold"])
        graph.role = str(sample_metadata["role"])
        graph.sampling_strategy = str(sample_metadata["sampling_strategy"])
        graph.graph_authority = "gurobi"
        graph.label_source_solver = str(
            sample_metadata.get("label_source_solver", "gurobi")
        )
        graph.root_lp_relaxation_mode = "first_optimal_root_gurobi_mipnode"
        graph.root_lp_relaxation_vector_sha256 = root_payload["vector_sha256"]
        graph.objective_sense = "MINIMIZE"
        graph.input_objective_sense = original_sense
        graph.objective_sense_override_applied = original_sense == "MAXIMIZE"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        torch.save(graph, temporary)
        temporary.replace(destination)
        restored = torch.load(destination, map_location="cpu", weights_only=False)
        encoded_root = restored["variable"].x[:, 6].detach().cpu().numpy()
        if not np.array_equal(encoded_root, root_vector.astype(np.float32)):
            raise GurobiGraphError("serialized graph changed the root-LP feature")
        return {
            "graph_file_name": destination.name,
            "graph_sha256": sha256_file(destination),
            "variables": len(variables),
            "constraints": len(constraints),
            "nonzeros": len(coefficients),
            "binary_variables": int(np.sum(types == "B")),
            "integer_variables": int(np.sum(types == "I")),
            "continuous_variables": int(np.sum(types == "C")),
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
            "root_lp_feature_exactly_encoded": True,
            "original_objective_sense": original_sense,
            "effective_objective_sense": "MINIMIZE",
        }
    finally:
        model.dispose()


def write_root_artifact(path: str | Path, payload: Mapping[str, Any]) -> str:
    """Persist a root-relaxation payload and return its SHA-256."""
    destination = Path(path).resolve()
    _write_gzip_json(destination, payload)
    return sha256_file(destination)
