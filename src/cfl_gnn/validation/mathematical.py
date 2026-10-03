"""Solver-independent feasibility checks and explicitly scaled gap metrics."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


OBJECTIVE_POLICY = "milpbench_cfl_force_minimize_v1"


def common_gap(primal: float | None, dual: float | None) -> float | None:
    """Return |P-D|/|P|, retaining undefined/infinite cases as JSON null."""
    if primal is None or dual is None:
        return None
    if not math.isfinite(primal) or not math.isfinite(dual):
        return None
    if primal == dual:
        return 0.0
    return abs(primal - dual) / abs(primal) if primal else None


def validate_linear_solution(
    *, values: Any, lower: Any, upper: Any, types: Any, objective: Any,
    rows: Any, columns: Any, coefficients: Any, senses: Any, rhs: Any,
    objective_offset: float = 0.0, reported_objective: float | None = None,
    feasibility_tolerance: float = 1e-6, integrality_tolerance: float = 1e-5,
) -> dict[str, Any]:
    """Check a named-and-aligned solution independently of solver status.

    Row residuals are absolute, in original model units. Callers must first
    verify exact variable identity, not infer it from vector length.
    """
    x, lb, ub, cost = [np.asarray(a, dtype=np.float64) for a in
                       (values, lower, upper, objective)]
    kinds, directions = np.asarray(types), np.asarray(senses)
    b, a = np.asarray(rhs, dtype=np.float64), np.asarray(coefficients, dtype=np.float64)
    r, c = np.asarray(rows, dtype=np.int64), np.asarray(columns, dtype=np.int64)
    if (x.ndim != 1 or not len(x) or any(v.shape != x.shape for v in (lb, ub, cost, kinds))
            or b.ndim != 1 or directions.shape != b.shape
            or r.ndim != 1 or not (r.shape == c.shape == a.shape)
            or np.isnan(lb).any() or np.isnan(ub).any() or (lb > ub).any()
            or not all(np.isfinite(v).all() for v in (x, cost, b, a))
            or not math.isfinite(objective_offset)
            or not set(kinds).issubset({"B", "I", "C"})
            or not set(directions).issubset({"<", "=", ">"})
            or (len(r) and (r.min() < 0 or r.max() >= len(b) or c.min() < 0 or c.max() >= len(x)))):
        raise ValueError("invalid linear-model validation arrays")
    if not (0 < feasibility_tolerance < 1 and 0 < integrality_tolerance < 1):
        raise ValueError("invalid validation tolerances")
    activity = np.bincount(r, weights=a * x[c], minlength=len(b))
    violation = np.where(directions == "<", np.maximum(activity-b, 0),
                         np.where(directions == ">", np.maximum(b-activity, 0), abs(activity-b)))
    integer = kinds != "C"
    binary = kinds == "B"
    bound_residual = max(float(np.maximum(lb-x, 0).max(initial=0)),
                         float(np.maximum(x-ub, 0).max(initial=0)),
                         float(np.maximum(-x[binary], 0).max(initial=0)),
                         float(np.maximum(x[binary]-1, 0).max(initial=0)))
    int_residual = float(abs(x[integer]-np.rint(x[integer])).max(initial=0))
    row_residual = float(violation.max(initial=0))
    obj = float(cost @ x + objective_offset)
    obj_match = reported_objective is None or (
        math.isfinite(reported_objective)
        and math.isclose(obj, reported_objective, rel_tol=1e-8, abs_tol=1e-6))
    checks = {"bounds": bound_residual <= feasibility_tolerance,
              "integrality": int_residual <= integrality_tolerance,
              "rows": row_residual <= feasibility_tolerance,
              "objective": obj_match}
    return {"valid": all(checks.values()), "checks": checks,
            "max_bound_residual": bound_residual, "max_integrality_residual": int_residual,
            "max_row_residual": row_residual, "recomputed_objective": obj,
            "feasibility_tolerance": feasibility_tolerance,
            "integrality_tolerance": integrality_tolerance}


def audit_gurobi_solution(model: Any, named_values: dict[str, float],
                          reported_objective: float | None = None) -> dict[str, Any]:
    """Extract the original linear model; never run optimize or modify bounds."""
    variables, constraints = model.getVars(), model.getConstrs()
    names = [v.VarName for v in variables]
    if len(names) != len(set(names)) or set(names) != set(named_values):
        raise ValueError("solution variable identities differ from the model")
    if model.NumQConstrs or model.NumGenConstrs or model.NumQNZs:
        raise ValueError("only linear CFL models are supported")
    matrix = model.getA().tocoo()
    return validate_linear_solution(
        values=[named_values[n] for n in names], lower=[v.LB for v in variables],
        upper=[v.UB for v in variables], types=[v.VType for v in variables],
        objective=[v.Obj for v in variables], objective_offset=model.ObjCon,
        rows=matrix.row, columns=matrix.col, coefficients=matrix.data,
        senses=[c.Sense for c in constraints], rhs=[c.RHS for c in constraints],
        reported_objective=reported_objective)
