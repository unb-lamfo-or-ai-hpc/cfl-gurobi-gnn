"""Independent Gurobi solve kernel with passive online incumbent capture."""

from __future__ import annotations

import gzip
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.solvers.pyscipopt_solution import (
    INCUMBENT_OBJECTIVE_TOLERANCE,
    IncumbentParquetStream,
    audit_incumbent_trace,
    canonical_sha256,
    canonical_variable_type,
    normalize_variable_type,
    runtime_environment,
    sha256_file,
)


ONLINE_GAP_AVAILABILITY = "mipsol_primal_dual_snapshot"
PERFORMANCE_FEATURE_TAGS = {
    "instance": {
        "execution_time": "execution_time_seconds",
        "mip_gap_relative": "mip_gap_relative",
        "mip_gap_percent": "mip_gap_percent",
    },
    "incumbent": {
        "objective": "incumbent_objective",
        "discovery_time": "incumbent_discovery_time_seconds",
        "mip_gap_relative_at_discovery": "incumbent_mip_gap_relative_at_discovery",
        "mip_gap_percent_at_discovery": "incumbent_mip_gap_percent_at_discovery",
    },
}


class GurobiSolveError(RuntimeError):
    """Raised when an independent Gurobi solve cannot be audited safely."""


def _write_gzip_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def _finite_or_none(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return normalized if math.isfinite(normalized) and abs(normalized) < 1e100 else None


def _gap(objective: Any, bound: Any) -> float | None:
    objective_value = _finite_or_none(objective)
    bound_value = _finite_or_none(bound)
    if objective_value is None or bound_value is None:
        return None
    return abs(objective_value - bound_value) / max(abs(objective_value), 1e-10)


def _gap_percent(relative: float | None) -> float | None:
    return None if relative is None else 100.0 * relative


def _bound_token(value: Any) -> float | str:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized >= 1e100:
        return "+inf"
    if normalized <= -1e100:
        return "-inf"
    return normalized


def _improves(
    candidate: float,
    incumbent: float,
    objective_sense: str,
    *,
    tolerance: float = INCUMBENT_OBJECTIVE_TOLERANCE,
) -> bool:
    if objective_sense == "minimize":
        return candidate < incumbent - tolerance
    return candidate > incumbent + tolerance


@dataclass(slots=True)
class GurobiIncumbentCollector:
    """Capture strict incumbent improvements at ``GRB.Callback.MIPSOL``."""

    variables: Sequence[Any]
    objective_sense: str
    callback_codes: Any
    stream: IncumbentParquetStream | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    events_seen: int = 0
    non_improving_events_ignored: int = 0

    def callback(self, model: Any, where: int) -> None:
        if where != self.callback_codes.MIPSOL:
            return
        event_index = self.events_seen
        self.events_seen += 1
        try:
            objective = _finite_or_none(model.cbGet(self.callback_codes.MIPSOL_OBJ))
            bound = _finite_or_none(model.cbGet(self.callback_codes.MIPSOL_OBJBND))
            discovery_time = _finite_or_none(model.cbGet(self.callback_codes.RUNTIME))
            if objective is None or discovery_time is None:
                raise GurobiSolveError("non-finite MIPSOL observation")
            if self.trace and not _improves(
                objective,
                float(self.trace[-1]["incumbent_objective"]),
                self.objective_sense,
            ):
                self.non_improving_events_ignored += 1
                return
            solution_vector = [
                float(value) for value in model.cbGetSolution(self.variables)
            ]
            if len(solution_vector) != len(self.variables):
                raise GurobiSolveError("MIPSOL vector length mismatch")
            relative_gap = _gap(objective, bound)
            record = {
                "incumbent_index": len(self.trace),
                "incumbent_objective": objective,
                "incumbent_discovery_time_seconds": discovery_time,
                "incumbent_best_bound_at_discovery": bound,
                "incumbent_mip_gap_relative_at_discovery": relative_gap,
                "incumbent_mip_gap_percent_at_discovery": _gap_percent(relative_gap),
                "mip_gap_at_discovery_availability": ONLINE_GAP_AVAILABILITY,
                "node_count_at_discovery": int(
                    model.cbGet(self.callback_codes.MIPSOL_NODCNT)
                ),
                "best_solution_count": int(
                    model.cbGet(self.callback_codes.MIPSOL_SOLCNT)
                ),
                "observation_method": "gurobi_mipsol_callback",
                "incumbent_discovery_time_method": "gurobi_callback_runtime",
            }
            if self.stream is not None:
                self.stream.append({**record, "solution_vector": solution_vector})
            self.trace.append(record)
        except Exception as error:
            self.errors.append(
                {
                    "event_index": event_index,
                    "error_type": type(error).__name__,
                    "reason_code": "mipsol_capture_failed",
                }
            )


def _status_name(status: int, grb: Any) -> str:
    names = {
        grb.LOADED: "loaded",
        grb.OPTIMAL: "optimal",
        grb.INFEASIBLE: "infeasible",
        grb.INF_OR_UNBD: "inf_or_unbd",
        grb.UNBOUNDED: "unbounded",
        grb.CUTOFF: "cutoff",
        grb.ITERATION_LIMIT: "iterationlimit",
        grb.NODE_LIMIT: "nodelimit",
        grb.TIME_LIMIT: "timelimit",
        grb.SOLUTION_LIMIT: "solutionlimit",
        grb.INTERRUPTED: "interrupted",
        grb.NUMERIC: "numeric",
        grb.SUBOPTIMAL: "suboptimal",
        grb.INPROGRESS: "inprogress",
        grb.USER_OBJ_LIMIT: "userobjlimit",
        grb.WORK_LIMIT: "worklimit",
        grb.MEM_LIMIT: "memlimit",
    }
    return names.get(int(status), f"status_{int(status)}")


def solve_named_mip(request: Mapping[str, Any]) -> dict[str, Any]:
    """Solve one MIP from scratch and write a named, audited Gurobi label."""
    total_started = time.perf_counter()
    import gurobipy as gp
    from gurobipy import GRB

    data_read_started = time.perf_counter()
    candidate = Path(str(request["candidate_path"]))
    solution_path = Path(str(request["solution_path"]))
    expected_sha256 = str(request["candidate_sha256"])
    if sha256_file(candidate) != expected_sha256:
        raise GurobiSolveError("candidate SHA-256 changed before solve")
    data_read_time = time.perf_counter() - data_read_started
    model_build_started = time.perf_counter()
    stream_path_value = request.get("incumbent_stream_path")
    stream = (
        IncumbentParquetStream(Path(str(stream_path_value)))
        if request.get("capture_incumbent_vectors") is True and stream_path_value
        else None
    )
    variable_order_path_value = request.get("variable_order_path")
    model = gp.read(str(candidate))
    collector: GurobiIncumbentCollector | None = None
    stream_committed = False
    try:
        original_objective_sense = (
            "minimize" if int(model.ModelSense) == int(GRB.MINIMIZE) else "maximize"
        )
        if request.get("force_minimize") is True:
            model.ModelSense = GRB.MINIMIZE
        model.Params.OutputFlag = 0
        model.Params.TimeLimit = float(request["time_limit"])
        model.Params.NodeLimit = int(request["node_limit"])
        model.Params.Threads = int(request.get("threads", 1))
        model.Params.Seed = int(request["seed"])
        model.update()
        objective_sense = (
            "minimize" if int(model.ModelSense) == int(GRB.MINIMIZE) else "maximize"
        )
        variables = tuple(model.getVars())
        variable_names = [str(variable.VarName) for variable in variables]
        variable_order_sha256 = canonical_sha256(variable_names)
        if variable_order_path_value:
            _write_gzip_json(
                Path(str(variable_order_path_value)),
                {
                    "schema_version": 1,
                    "candidate_sha256": expected_sha256,
                    "variable_count": len(variable_names),
                    "variable_order_sha256": variable_order_sha256,
                    "variable_names": variable_names,
                },
            )
        try:
            pre_solve_solution_count = int(model.SolCount)
        except Exception:
            pre_solve_solution_count = 0
        collector = GurobiIncumbentCollector(
            variables=variables,
            objective_sense=objective_sense,
            callback_codes=GRB.Callback,
            stream=stream,
        )
        solver_parameter_map = {
            "TimeLimit": float(model.Params.TimeLimit),
            "NodeLimit": float(model.Params.NodeLimit),
            "Threads": int(model.Params.Threads),
            "Seed": int(model.Params.Seed),
            "OutputFlag": int(model.Params.OutputFlag),
            "ModelSense": int(model.ModelSense),
        }
        solver_parameter_sha256 = canonical_sha256(solver_parameter_map)
        model_build_time = time.perf_counter() - model_build_started
        optimize_started = time.perf_counter()
        model.optimize(collector.callback)
        optimize_time = time.perf_counter() - optimize_started

        solution_count = int(model.SolCount)
        named_variables: list[dict[str, Any]] = []
        objective = None
        solution_objective = None
        feasibility_check = False
        max_violation = None
        if solution_count > 0:
            objective = _finite_or_none(model.ObjVal)
            solution_objective = objective
            max_violation = _finite_or_none(model.MaxVio)
            feasibility_check = max_violation is not None and max_violation <= 1e-5
            for variable in variables:
                lower = float(variable.LB)
                upper = float(variable.UB)
                named_variables.append(
                    {
                        "name": str(variable.VarName),
                        "raw_type": normalize_variable_type(variable.VType),
                        "canonical_type": canonical_variable_type(
                            variable.VType, lower, upper
                        ),
                        "lb": _bound_token(lower),
                        "ub": _bound_token(upper),
                        "value": float(variable.X),
                    }
                )
            named_variables.sort(key=lambda item: item["name"])

        best_incumbent_time = (
            float(collector.trace[-1]["incumbent_discovery_time_seconds"])
            if collector.trace
            else None
        )
        trace_audit = audit_incumbent_trace(
            collector.trace,
            objective_sense=objective_sense,
            final_objective=solution_objective,
            final_discovery_time=best_incumbent_time,
        )
        if stream is not None:
            stream.close(commit=not collector.errors)
            stream_committed = not collector.errors
        relative_gap = (
            _finite_or_none(model.MIPGap) if solution_count > 0 else None
        )
        version = ".".join(str(part) for part in gp.gurobi.version())
        total_time = time.perf_counter() - total_started
        payload = {
            "schema_version": int(request.get("schema_version", 1)),
            "contract_sha256": str(request["contract_sha256"]),
            "candidate_file_name": str(request["candidate_file_name"]),
            "candidate_sha256": expected_sha256,
            "solver_profile": "default",
            "solver_versions": {"gurobi": version, "gurobipy": version},
            "solver_parameter_map": solver_parameter_map,
            "solver_parameter_sha256": solver_parameter_sha256,
            "runtime_environment": runtime_environment(),
            "solution_source": "independent_gurobi_optimization",
            "fresh_process": True,
            "warm_start_supplied": False,
            "parent_incumbent_consumed": False,
            "original_objective_sense": original_objective_sense,
            "objective_sense": objective_sense,
            "effective_objective_sense": objective_sense,
            "pre_solve_solution_count": pre_solve_solution_count,
            "solve_status": _status_name(int(model.Status), GRB),
            "solution_count": solution_count,
            "objective": objective,
            "solution_objective": solution_objective,
            "best_bound": _finite_or_none(model.ObjBound),
            "mip_gap_relative": relative_gap,
            "mip_gap_percent": _gap_percent(relative_gap),
            "execution_time_seconds": _finite_or_none(model.Runtime),
            "time_regions": {
                "total_wall_time_seconds": total_time,
                "data_read_wall_time_seconds": data_read_time,
                "model_build_wall_time_seconds": model_build_time,
                "model_optimize_wall_time_seconds": optimize_time,
            },
            "time_region_semantics": {
                "total_wall_time_seconds": (
                    "external_wall_clock_from_worker_entry_through_outcome_extraction"
                ),
                "data_read_wall_time_seconds": (
                    "external_wall_clock_for_input_identity_and_sha256_verification"
                ),
                "model_build_wall_time_seconds": (
                    "external_wall_clock_for_model_parse_configuration_and_callback_setup"
                ),
                "model_optimize_wall_time_seconds": (
                    "external_wall_clock_around_model_optimize_only"
                ),
            },
            "work_units": _finite_or_none(model.Work),
            "nodes_current_run": int(model.NodeCount),
            "nodes_total": int(model.NodeCount),
            "best_incumbent_discovery_time_seconds": best_incumbent_time,
            "incumbent_trace": collector.trace,
            "incumbent_trace_error_count": len(collector.errors),
            "incumbent_trace_errors": collector.errors,
            "incumbent_trace_audit": trace_audit,
            "incumbent_trace_source": "gurobi_mipsol_callback",
            "incumbent_gap_at_discovery_availability": ONLINE_GAP_AVAILABILITY,
            "online_incumbent_capture": {
                "event_type": "MIPSOL",
                "handler": "gurobipy_Model.optimize_callback",
                "passive": True,
                "events_seen": collector.events_seen,
                "events_recorded": len(collector.trace),
                "non_improving_events_ignored": (
                    collector.non_improving_events_ignored
                ),
                "capture_error_count": len(collector.errors),
                "vectors_streamed": stream.rows_written if stream else 0,
                "stream_committed": stream_committed,
                "variable_order_sha256": variable_order_sha256,
            },
            "performance_feature_tags": PERFORMANCE_FEATURE_TAGS,
            "solver_feasibility_check": feasibility_check,
            "solver_feasibility_check_space": "original_model_solution_quality",
            "maximum_constraint_violation": max_violation,
            "variables": named_variables,
        }
        _write_gzip_json(solution_path, payload)
        return {
            "worker_status": "completed",
            "solution_file_name": solution_path.name,
        }
    finally:
        if stream is not None and stream.writer is not None:
            stream.close(commit=False)
        model.dispose()
