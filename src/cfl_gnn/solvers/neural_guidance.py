"""Solver-native guidance on original CFL MILPs, with fresh full-model recovery.

Restricted dual bounds are deliberately discarded. These executors do not
select policies or consume target labels; predictions must be held-out outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

from cfl_gnn.experiments.neural_guidance_policy import guidance_directives, rank_predictions
from cfl_gnn.validation.mathematical import OBJECTIVE_POLICY, common_gap, audit_gurobi_solution


def binary_names(domains):
    result = set()
    for name, lower, upper, kind in domains:
        if kind not in ("B", "I", "BINARY", "INTEGER"):
            continue
        if lower < 0 or upper > 1 or lower > upper:
            raise ValueError("guidance supports canonical binary domains only")
        result.add(name)
    return result


def _finite(value):
    return float(value) if value is not None and math.isfinite(value) and abs(value) < 1e19 else None


class NativeModel:
    def __init__(self, path, solver, budget):
        self.solver = solver
        self.env = None
        if solver == "gurobi":
            import gurobipy as gp
            self.env = gp.Env(empty=True)
            self.env.setParam("OutputFlag", 0)
            self.env.start()
            self.model = gp.read(str(path), env=self.env)
            self.original_sense = "MINIMIZE" if self.model.ModelSense == 1 else "MAXIMIZE"
            self.model.ModelSense = gp.GRB.MINIMIZE
            self.model.Params.TimeLimit = budget
            self.model.Params.Threads = 1
            self.model.Params.Seed = 42
            self.model.update()
            self.variables = {v.VarName: v for v in self.model.getVars()}
            self.domains = [(v.VarName, v.LB, v.UB, v.VType) for v in self.model.getVars()]
            self.rows = self.model.NumConstrs
        elif solver == "scip":
            from pyscipopt import Model
            self.model = Model()
            self.model.hideOutput()
            self.model.readProblem(str(path))
            self.original_sense = self.model.getObjectiveSense().upper()
            self.model.setMinimize()
            self.model.setParam("limits/time", budget)
            self.model.setParam("parallel/maxnthreads", 1)
            self.model.setParam("randomization/randomseedshift", 42)
            variables = self.model.getVars(transformed=False)
            self.variables = {v.name: v for v in variables}
            self.domains = [(v.name, v.getLbOriginal(), v.getUbOriginal(), v.vtype()) for v in variables]
            self.rows = self.model.getNConss()
        else:
            raise ValueError("unknown solver")
        self.binary = binary_names(self.domains)
        self.bounds = {d[0]: (d[1], d[2]) for d in self.domains}

    def start(self, values, partial=False):
        if self.solver == "gurobi":
            for name, value in values.items():
                self.variables[name].Start = value
        else:
            solution = self.model.createPartialSol() if partial else self.model.createSol()
            for name, value in values.items():
                self.model.setSolVal(solution, self.variables[name], value)
            self.model.addSol(solution, free=True)

    def apply(self, directive):
        method = directive["method"]
        assignments = directive["assignments"]
        values = {row["variable_name"]: row["value"] for row in assignments}
        if not set(values).issubset(self.binary):
            raise ValueError("guidance contains unknown or nonbinary variables")
        if method == "gurobi_variable_hints":
            if self.solver != "gurobi":
                raise ValueError("SCIP has no equivalent native variable-hint intervention")
            for row in assignments:
                var = self.variables[row["variable_name"]]
                var.VarHintVal, var.VarHintPri = row["value"], row["priority"]
        elif method == "partial_mip_start":
            self.start(values, partial=True)
        elif method == "confidence_partial_fixing_with_recovery":
            for name, value in values.items():
                var = self.variables[name]
                lb, ub = self.bounds[name]
                if not lb <= value <= ub:
                    raise ValueError("fixing would relax an original bound")
                if self.solver == "gurobi":
                    var.LB = var.UB = value
                else:
                    self.model.chgVarLb(var, value)
                    self.model.chgVarUb(var, value)
        elif method == "local_branching_trust_region_with_recovery":
            if set(values) != self.binary:
                raise ValueError("LB center must cover every canonical binary variable")
            if self.solver == "gurobi":
                from gurobipy import quicksum
            else:
                from pyscipopt import quicksum
            expression = quicksum(self.variables[n] if v == 0 else 1-self.variables[n]
                                  for n, v in values.items())
            if self.solver == "gurobi":
                self.model.addConstr(expression <= directive["radius"], name="neural_lb_restricted")
            else:
                self.model.addCons(expression <= directive["radius"], name="neural_lb_restricted")

    def optimize(self):
        self.gap_observations = {}
        self.callback_errors = 0
        started = perf_counter()
        def record(primal, dual):
            gap = common_gap(_finite(primal), _finite(dual))
            if gap is not None:
                for threshold in (.01, .05, .06, .1):
                    if gap <= threshold:
                        self.gap_observations.setdefault(str(threshold), perf_counter()-started)
        if self.solver == "gurobi":
            from gurobipy import GRB
            def observe(model, where):
                if where == GRB.Callback.MIP:
                    try:
                        record(model.cbGet(GRB.Callback.MIP_OBJBST), model.cbGet(GRB.Callback.MIP_OBJBND))
                    except Exception:
                        self.callback_errors += 1
            self.model.optimize(observe)
        else:
            from pyscipopt import SCIP_EVENTTYPE
            def observe(model, event):
                try:
                    record(model.getPrimalbound(), model.getDualbound())
                except Exception:
                    self.callback_errors += 1
            self.model.attachEventHandlerCallback(observe, [SCIP_EVENTTYPE.BESTSOLFOUND, SCIP_EVENTTYPE.LPSOLVED])
            self.model.optimize()
        if self.solver == "gurobi":
            m = self.model
            values = {n: v.X for n, v in self.variables.items()} if m.SolCount else None
            if values:
                record(m.ObjVal, m.ObjBound)
            return {"values": values, "primal": _finite(m.ObjVal) if values else None,
                    "dual": _finite(m.ObjBound), "native_gap": _finite(m.MIPGap) if values else None,
                    "status": str(m.Status), "right_censored": m.Status in (8, 9, 10, 11, 16, 17)}
        m = self.model
        solution = m.getBestSol()
        values = {n: m.getSolVal(solution, v) for n, v in self.variables.items()} if solution else None
        if values:
            record(m.getObjVal(), m.getDualbound())
        return {"values": values, "primal": _finite(m.getObjVal()) if values else None,
                "dual": _finite(m.getDualbound()), "native_gap": _finite(m.getGap()) if values else None,
                "status": str(m.getStatus()), "right_censored": str(m.getStatus()) in ("timelimit", "nodelimit", "stallnodelimit", "memlimit", "userinterrupt")}

    def close(self):
        if self.solver == "gurobi":
            self.model.dispose()
            self.env.dispose()
        else:
            self.model.freeProb()


def run_guidance(*, mip_path, predictions, solver, method, time_limit=3600,
                 fraction=None, radius_fraction=None, engineering_smoke=False):
    if time_limit not in (3600, 14400) and not (engineering_smoke and 0 < time_limit <= 60):
        raise ValueError("budget must be precommitted at 3600 or 14400 seconds")
    if not engineering_smoke and fraction is not None and fraction not in (.01, .05, .1):
        raise ValueError("coverage is not precommitted")
    started = perf_counter()
    read_started = perf_counter()
    path = Path(mip_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    read_time = perf_counter()-read_started
    directive = guidance_directives(predictions, method=method, fraction=fraction, radius_fraction=radius_fraction)
    binding = directive.get("recovery_required", False)
    phases, optimize_time, build_time = [], 0., 0.
    recovered_values = None
    domains = None
    for phase in (["restricted", "full_model_recovery"] if binding else ["full_model"]):
        read_started = perf_counter()
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("original MIP changed between phases")
        read_time += perf_counter()-read_started
        budget = time_limit*.2 if phase == "restricted" else max(.001, time_limit-optimize_time)
        begin = perf_counter()
        backend = NativeModel(path, solver, budget)
        try:
            original_sense = backend.original_sense
            signature = (backend.domains, backend.rows)
            if domains is None:
                domains = signature
            elif signature != domains:
                raise ValueError("fresh recovery model does not match original domains/rows")
            if phase != "full_model_recovery":
                if method != "unguided_control" and {p["variable_name"] for p in rank_predictions(predictions)} != backend.binary:
                    raise ValueError("predictions must cover exactly the original binary support")
                backend.apply(directive)
            elif recovered_values is not None:
                backend.start(recovered_values)
            build_time += perf_counter()-begin
            begin = perf_counter()
            result = backend.optimize()
            elapsed = perf_counter()-begin
            optimize_time += elapsed
            recovered_values = result.pop("values")
            phases.append({"phase": phase, "allocated_optimize_seconds": budget,
                           "first_observed_common_gap_times_seconds": backend.gap_observations,
                           "callback_error_count": backend.callback_errors,
                           "model_optimize_wall_time_seconds": elapsed, **result})
        finally:
            backend.close()
    # Gurobi is the mathematical graph/feasibility authority for both arms.
    begin = perf_counter()
    authority = NativeModel(path, "gurobi", 1.)
    try:
        feasibility = audit_gurobi_solution(authority.model, recovered_values, result["primal"]) if recovered_values else None
    finally:
        authority.close()
    audit_time = perf_counter()-begin
    total = perf_counter()-started
    allowed_statuses = {"2", "3", "8", "9", "10", "11", "16", "17"} if solver == "gurobi" else {
        "optimal", "infeasible", "timelimit", "nodelimit", "stallnodelimit", "memlimit", "userinterrupt", "gaplimit", "sollimit", "bestsollimit"}
    valid = (result["status"] in allowed_statuses
             and (recovered_values is None or feasibility["valid"])
             and all(p["callback_error_count"] == 0 for p in phases))
    directive_summary = {key: value for key, value in directive.items() if key != "assignments"}
    directive_summary["assignment_count"] = len(directive["assignments"])
    return {"schema_version": 1, "mip_sha256": digest, "solver": solver, "method": method,
            "seed": 42, "objective_policy": OBJECTIVE_POLICY,
            "original_objective_sense": original_sense, "effective_objective_sense": "MINIMIZE",
            "directive": directive_summary, "phases": phases,
            "full_model_recovery_executed": binding and len(phases) == 2,
            "restricted_dual_bounds_used_for_final_gap": False,
            "time_limit_seconds": time_limit, "timing": {
                "total_wall_time_seconds": total, "data_read_wall_time_seconds": read_time,
                "model_build_wall_time_seconds": build_time,
                "model_optimize_wall_time_seconds": optimize_time,
                "independent_audit_wall_time_seconds": audit_time,
                "other_wall_time_seconds": total-read_time-build_time-optimize_time-audit_time,
                "parser_time_region": "model_build", "prediction_inference_included": False},
            "terminal_mip_gap_relative": result["native_gap"],
            "common_mip_gap_relative": common_gap(result["primal"], result["dual"]),
            "feasible_solution": recovered_values is not None, "independent_feasibility": feasibility,
            "right_censored": result["right_censored"], "gate_status": "passed" if valid else "failed",
            "development_only": True, "scientific_reporting_eligible": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mip", type=Path, required=True)
    parser.add_argument("--mip_sha256", required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--solver", choices=("gurobi", "scip"), required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--time_limit", type=int, choices=(3600, 14400), default=3600)
    parser.add_argument("--fraction", type=float)
    parser.add_argument("--radius_fraction", type=float)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError("use a new output path; completed runs are immutable")
    import gzip
    if args.predictions.suffix == ".gz":
        with gzip.open(args.predictions, "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
    else:
        payload = json.loads(args.predictions.read_text(encoding="utf-8"))
    if payload.get("role") != "test" or payload.get("mip_sha256") != args.mip_sha256:
        raise ValueError("predictions must bind a held-out original MIP hash")
    if payload.get("sampling_strategy") != "original" or len(payload.get("checkpoint_sha256", "")) != 64:
        raise ValueError("held-out original predictions require a checkpoint identity")
    if hashlib.sha256(args.mip.read_bytes()).hexdigest() != args.mip_sha256:
        raise ValueError("original MIP hash mismatch")
    report = run_guidance(mip_path=args.mip, predictions=payload["predictions"],
                          solver=args.solver, method=args.method, time_limit=args.time_limit,
                          fraction=args.fraction, radius_fraction=args.radius_fraction)
    report["prediction_artifact_sha256"] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    report["offline_prediction_overhead"] = {
        "model_inference_wall_time_seconds": payload.get("model_inference_wall_time_seconds"),
        "root_graph_precomputation_included": False,
        "end_to_end_speedup_claim_allowed": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return 0 if report["gate_status"] == "passed" else 1
