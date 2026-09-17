"""Audited two-method Gurobi solves; reuse the native model/start adapter."""
from __future__ import annotations

import math
import platform
import hashlib
import gzip
import json
from time import perf_counter

from cfl_gnn.solvers.neural_guidance import NativeModel, _finite
from cfl_gnn.experiments.neural_guidance_policy import guidance_directives, rank_predictions
from cfl_gnn.graph.gurobi_graph_artifact import canonical_sha256
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.validation.mathematical import audit_gurobi_solution, common_gap

METHODS = ("unguided_control", "partial_mip_start")
GAPS = (.01, .05, .06, .1)


def mathematical_signature(model):
    """Hash the linear formulation, excluding starts and solver guidance."""
    import numpy as np
    variables, constraints = model.getVars(), model.getConstrs()
    digest = hashlib.sha256()
    digest.update(canonical_sha256([v.VarName for v in variables]).encode())
    digest.update(canonical_sha256([v.VType for v in variables]).encode())
    digest.update(canonical_sha256([c.Sense for c in constraints]).encode())
    for values in ([model.ModelSense, model.ObjCon], [v.LB for v in variables],
                   [v.UB for v in variables], [v.Obj for v in variables], [c.RHS for c in constraints]):
        digest.update(np.asarray(values, dtype="<f8").tobytes())
    matrix = model.getA().tocsr()
    for values, dtype in ((matrix.indptr, "<i8"), (matrix.indices, "<i8"), (matrix.data, "<f8")):
        digest.update(np.asarray(values, dtype=dtype).tobytes())
    return digest.hexdigest()


def start_evidence(messages, submitted):
    """Do not interpret 'no new incumbent' as proof of infeasibility."""
    if not submitted:
        return {"status": "not_submitted", "accepted": None, "completed": None}
    if any("Loaded user MIP start with objective" in s for s in messages):
        return {"status": "accepted", "accepted": True, "completed": True}
    if any("User MIP start produced solution with objective" in s for s in messages):
        return {"status": "completion_observed_acceptance_unknown", "accepted": None, "completed": True}
    if any("User MIP start did not produce a new incumbent solution" in s for s in messages):
        return {"status": "no_new_incumbent", "accepted": False, "completed": None}
    return {"status": "submitted_outcome_unknown", "accepted": None, "completed": None}


def solve(mip_path, expected_hash, predictions, method, budget=3600, engineering_smoke=False, solution_path=None):
    import gurobipy as gp
    from gurobipy import GRB
    if method not in METHODS or (budget != 3600 and not (engineering_smoke and 0 < budget <= 30)):
        raise ValueError("unsupported method or optimization budget")
    start = perf_counter()
    t = perf_counter()
    if sha256_file(mip_path) != expected_hash:
        raise ValueError("source MIP changed")
    read_seconds = perf_counter()-t
    t = perf_counter()
    backend = NativeModel(mip_path, "gurobi", budget)
    values = None
    try:
        m = backend.model
        if m.NumQNZs or m.NumQConstrs or m.NumGenConstrs or m.NumSOS:
            raise ValueError("linear model required")
        before = mathematical_signature(m)
        model_fingerprint = int(m.Fingerprint)
        if m.SolCount != 0 or m.NumStart != 0:
            raise ValueError("fresh model contains prior solution or start")
        if not backend.binary:
            raise ValueError("binary support required")
        rows = [] if method == METHODS[0] else rank_predictions(predictions)
        if method == METHODS[1] and {r["variable_name"] for r in rows} != backend.binary:
            raise ValueError("predictions must cover exactly the original binary support")
        directive = guidance_directives(rows, method=method, fraction=.1)
        backend.apply(directive)
        m.update()
        assignments = directive["assignments"]
        selected = {a["variable_name"]: a["value"] for a in assignments}
        if any(not backend.bounds[n][0] <= v <= backend.bounds[n][1] for n, v in selected.items()):
            raise ValueError("predicted start violates an original variable bound")
        after = mathematical_signature(m)
        if before != after:
            raise ValueError("start changed the mathematical model")
        if selected:
            if m.NumStart != 1 or any(v.Start != selected[n] if n in selected else v.Start != GRB.UNDEFINED
                                      for n, v in backend.variables.items()):
                raise ValueError("partial start support differs from submitted assignments")
        elif m.NumStart != 0:
            raise ValueError("control contains a MIP start")
        # Enable solver messages only after model loading; never write license,
        # host or input-path banners into shareable artifacts.
        m.Params.OutputFlag = 1
        m.Params.LogToConsole = 0
        m.Params.MIPGap = 1e-4
        params = {k: getattr(m.Params, k) for k in (
            "Threads", "Seed", "TimeLimit", "MIPGap", "MIPGapAbs", "Presolve", "Heuristics",
            "Cuts", "MIPFocus", "Method", "StartNodeLimit", "SubMIPNodes", "FeasibilityTol", "IntFeasTol")}
        build_seconds = perf_counter()-t
        messages, trajectory, observed, callback_errors = [], [], {}, []
        first_feasible = None
        optimize_start = perf_counter()
        last_record = -30.

        def record(primal, dual, event, force=False):
            nonlocal first_feasible, last_record
            seconds = perf_counter()-optimize_start
            p, d = _finite(primal), _finite(dual)
            if p is not None and first_feasible is None:
                first_feasible = seconds
            gap = common_gap(p, d)
            if gap is not None:
                for threshold in GAPS:
                    if gap <= threshold:
                        observed.setdefault(str(threshold), seconds)
            if force or event == "MIPSOL" or seconds-last_record >= 30:
                trajectory.append(dict(seconds=seconds, primal=p, dual=d, common_gap_relative=gap, event=event))
                last_record = seconds

        def callback(model, where):
            try:
                if where == GRB.Callback.MESSAGE:
                    message = model.cbGet(GRB.Callback.MSG_STRING).strip()
                    # Store only exact, numeric solver evidence; exclude names,
                    # general solver logs and potential confidential paths.
                    prefixes = ("Loaded user MIP start with objective", "User MIP start produced solution with objective",
                                "User MIP start did not produce a new incumbent solution")
                    if message.startswith(prefixes) and len(messages) < 50:
                        messages.append(message)
                elif where == GRB.Callback.MIP:
                    record(model.cbGet(GRB.Callback.MIP_OBJBST), model.cbGet(GRB.Callback.MIP_OBJBND), "MIP")
                elif where == GRB.Callback.MIPSOL:
                    record(min(model.cbGet(GRB.Callback.MIPSOL_OBJ), model.cbGet(GRB.Callback.MIPSOL_OBJBST)),
                           model.cbGet(GRB.Callback.MIPSOL_OBJBND), "MIPSOL")
            except Exception as error:
                if len(callback_errors) < 10:
                    callback_errors.append(type(error).__name__)

        m.optimize(callback)
        optimize_seconds = perf_counter()-optimize_start
        primal = _finite(m.ObjVal) if m.SolCount else None
        dual = _finite(m.ObjBound)
        record(primal, dual, "terminal", True)
        # Include terminal fallback only when no earlier qualifying observation
        # exists; these are first-observed times, not exact hitting times.
        values = {n: v.X for n, v in backend.variables.items()} if m.SolCount else None
        status = int(m.Status)
        result = dict(solve_status_code=status, primal=primal, dual=dual,
                      terminal_mip_gap_relative=_finite(m.MIPGap) if m.SolCount else None,
                      common_mip_gap_relative=common_gap(primal, dual),
                      node_count=float(m.NodeCount), solver_runtime_seconds=float(m.Runtime),
                      right_censored=status in (8, 9, 10, 11, 16, 17), feasible_solution=values is not None,
                      first_observed_feasible_seconds=first_feasible,
                      first_observed_gap_times_seconds={str(g): observed.get(str(g)) for g in GAPS})
        original_sense = backend.original_sense
    finally:
        backend.close()
    t = perf_counter()
    with gp.Env(params={"OutputFlag": 0}) as env, gp.read(str(mip_path), env=env) as authority:
        authority.ModelSense = GRB.MINIMIZE
        authority.update()
        audit = audit_gurobi_solution(authority, values, primal) if values is not None else None
        if mathematical_signature(authority) != before:
            raise ValueError("independent audit model differs from solved model")
    audit_seconds = perf_counter()-t
    t = perf_counter()
    solution_artifact = None
    if values is not None and solution_path is not None:
        with gzip.open(solution_path, "xt", encoding="utf-8") as stream:
            json.dump(dict(mip_sha256=expected_hash, objective_sense="MINIMIZE", objective=primal,
                           variables=values, independent_feasibility=audit), stream, allow_nan=False)
        solution_artifact = dict(file_name=solution_path.name, sha256=sha256_file(solution_path))
    export_seconds = perf_counter()-t
    total = perf_counter()-start
    valid = status in (2, 3, 8, 9, 10, 16, 17) and not callback_errors and (values is None or audit["valid"])
    return dict(schema_version=1, gate_status="passed" if valid else "failed", method=method,
        mip_sha256=expected_hash, model_fingerprint=model_fingerprint, mathematical_signature_sha256=before,
        solution_artifact=solution_artifact, effective_objective_sense="MINIMIZE",
        original_objective_sense=original_sense, fresh_model=True, mathematical_model_unchanged=True,
        solver_version=list(gp.gurobi.version()), python_version=platform.python_version(),
        parameters=params, parameter_sha256=canonical_sha256(params), solve=result,
        start={**start_evidence(messages, bool(selected)), "submitted_assignments": len(selected),
               "binary_variables": len(backend.binary), "actual_coverage": len(selected)/len(backend.binary),
               "positive_assignments": sum(selected.values()), "negative_assignments": len(selected)-sum(selected.values()),
               "assignment_sha256": canonical_sha256(assignments), "solver_messages": messages,
               "unselected_starts_undefined": True},
        independent_feasibility=audit, callback_errors=callback_errors, trajectory=trajectory,
        timing=dict(total_wall_time_seconds=total, data_read_wall_time_seconds=read_seconds,
                    model_build_wall_time_seconds=build_seconds, model_optimize_wall_time_seconds=optimize_seconds,
                    independent_audit_wall_time_seconds=audit_seconds,
                    solution_export_wall_time_seconds=export_seconds,
                    other_wall_time_seconds=total-read_seconds-build_seconds-optimize_seconds-audit_seconds,
                    parser_time_region="model_build", prediction_preparation_included=False),
        development_only=True, scientific_reporting_eligible=False)
