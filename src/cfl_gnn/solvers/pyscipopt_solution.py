"""Shared PySCIPOpt solve kernel with passive online incumbent capture."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


ONLINE_GAP_AVAILABILITY = "bestsolfound_primal_dual_snapshot"
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


class PyScipOptSolveError(RuntimeError):
    """Raised when a named SCIP solution cannot be captured safely."""


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    return normalized if math.isfinite(normalized) and abs(normalized) < 1e19 else None


def _gap(objective: Any, bound: Any) -> float | None:
    objective_value = _finite_or_none(objective)
    bound_value = _finite_or_none(bound)
    if objective_value is None or bound_value is None:
        return None
    return abs(objective_value - bound_value) / max(abs(objective_value), 1e-10)


def _gap_percent(relative: float | None) -> float | None:
    return None if relative is None else 100.0 * relative


def normalize_variable_type(value: Any) -> str:
    normalized = str(value).strip().upper()
    mapping = {
        "B": "B",
        "BINARY": "B",
        "I": "I",
        "INTEGER": "I",
        "IMPLINT": "I",
        "IMPLICIT_INTEGER": "I",
        "C": "C",
        "CONTINUOUS": "C",
    }
    try:
        return mapping[normalized]
    except KeyError as error:
        raise PyScipOptSolveError(f"unsupported SCIP variable type: {value!r}") from error


def canonical_variable_type(raw_type: Any, lower: float, upper: float) -> str:
    normalized = normalize_variable_type(raw_type)
    if normalized == "I" and lower >= -1e-9 and upper <= 1.0 + 1e-9:
        return "B"
    return normalized


def _bound_token(value: Any) -> float | str:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized >= 1e19:
        return "+inf"
    if normalized <= -1e19:
        return "-inf"
    return normalized


def _normalized_parameter_map(parameters: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in sorted(parameters.items()):
        if isinstance(value, (bool, int, str)) or value is None:
            normalized[str(key)] = value
        elif isinstance(value, float) and math.isfinite(value):
            normalized[str(key)] = value
        else:
            normalized[str(key)] = str(value)
    return normalized


def _apply_profile(model: Any, profile_id: str) -> None:
    if profile_id not in {"default", "feasibility", "optimality"}:
        raise ValueError(f"unsupported solver profile: {profile_id}")
    if profile_id == "default":
        return
    from pyscipopt import SCIP_PARAMEMPHASIS

    emphasis = {
        "feasibility": SCIP_PARAMEMPHASIS.FEASIBILITY,
        "optimality": SCIP_PARAMEMPHASIS.OPTIMALITY,
    }[profile_id]
    model.setEmphasis(emphasis)


class IncumbentParquetStream:
    """Incrementally persist full incumbent vectors without retaining them."""

    def __init__(self, path: Path, *, buffer_limit: int = 8) -> None:
        self.path = path
        self.temporary = path.with_suffix(path.suffix + ".tmp")
        self.buffer_limit = buffer_limit
        self.buffer: list[dict[str, Any]] = []
        self.writer: Any = None
        self.rows_written = 0

    def append(self, record: Mapping[str, Any]) -> None:
        self.buffer.append(dict(record))
        if len(self.buffer) >= self.buffer_limit:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as error:
            raise PyScipOptSolveError(
                "pyarrow is required for SCIP incumbent streaming"
            ) from error
        self.path.parent.mkdir(parents=True, exist_ok=True)
        schema = pa.schema(
            [
                ("incumbent_index", pa.int64()),
                ("incumbent_objective", pa.float64()),
                ("incumbent_discovery_time_seconds", pa.float64()),
                ("incumbent_best_bound_at_discovery", pa.float64()),
                ("incumbent_mip_gap_relative_at_discovery", pa.float64()),
                ("incumbent_mip_gap_percent_at_discovery", pa.float64()),
                ("mip_gap_at_discovery_availability", pa.string()),
                ("node_count_at_discovery", pa.int64()),
                ("best_solution_count", pa.int64()),
                ("observation_method", pa.string()),
                ("incumbent_discovery_time_method", pa.string()),
                ("solution_vector", pa.list_(pa.float64())),
            ]
        )
        table = pa.Table.from_pylist(self.buffer, schema=schema)
        if self.writer is None:
            self.writer = pq.ParquetWriter(
                self.temporary,
                table.schema,
                compression="snappy",
            )
        self.writer.write_table(table)
        self.rows_written += len(self.buffer)
        self.buffer.clear()

    def close(self, *, commit: bool) -> None:
        try:
            self.flush()
        finally:
            if self.writer is not None:
                self.writer.close()
                self.writer = None
        if commit and self.temporary.is_file():
            self.temporary.replace(self.path)
        elif self.temporary.exists():
            self.temporary.unlink()


@dataclass(slots=True)
class OnlineIncumbentCollector:
    """Stateful callback target for ``SCIP_EVENTTYPE.BESTSOLFOUND``."""

    variables: Sequence[Any]
    objective_sense: str
    stream: IncumbentParquetStream | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def callback(self, model: Any, event: Any) -> None:
        event_index = len(self.trace) + len(self.errors)
        try:
            solution = model.getBestSol()
            if solution is None:
                raise PyScipOptSolveError("BESTSOLFOUND has no best solution")
            objective = _finite_or_none(model.getSolObjVal(solution, original=True))
            # Use SCIP's timestamp attached to the solution itself.  Reading the
            # solver clock here can differ slightly from ``getSolTime`` after
            # optimization, which would make a correct trace fail round-trip
            # validation.
            try:
                discovery_time = _finite_or_none(model.getSolTime(solution))
                discovery_time_method = "pyscipopt_getSolTime"
            except Exception:
                discovery_time = _finite_or_none(model.getSolvingTime())
                discovery_time_method = "pyscipopt_solver_clock_fallback"
            bound = _finite_or_none(model.getDualbound())
            if objective is None or discovery_time is None:
                raise PyScipOptSolveError("non-finite BESTSOLFOUND observation")
            relative_gap = _gap(objective, bound)
            record = {
                "incumbent_index": len(self.trace),
                "incumbent_objective": objective,
                "incumbent_discovery_time_seconds": discovery_time,
                "incumbent_best_bound_at_discovery": bound,
                "incumbent_mip_gap_relative_at_discovery": relative_gap,
                "incumbent_mip_gap_percent_at_discovery": _gap_percent(relative_gap),
                "mip_gap_at_discovery_availability": ONLINE_GAP_AVAILABILITY,
                "node_count_at_discovery": int(model.getNNodes()),
                "best_solution_count": int(model.getNBestSolsFound()),
                "observation_method": "pyscipopt_bestsolfound_event",
                "incumbent_discovery_time_method": discovery_time_method,
            }
            if self.stream is not None:
                self.stream.append(
                    {
                        **record,
                        "solution_vector": [
                            float(model.getSolVal(solution, variable))
                            for variable in self.variables
                        ],
                    }
                )
            self.trace.append(record)
        except Exception as error:
            self.errors.append(
                {
                    "event_index": event_index,
                    "error_type": type(error).__name__,
                    "reason_code": "bestsolfound_capture_failed",
                }
            )


def audit_incumbent_trace(
    trace: Sequence[Mapping[str, Any]],
    *,
    objective_sense: str,
    final_objective: float | None,
    final_discovery_time: float | None,
    tolerance: float = 1e-8,
) -> dict[str, Any]:
    times = [float(item["incumbent_discovery_time_seconds"]) for item in trace]
    objectives = [float(item["incumbent_objective"]) for item in trace]
    times_monotonic = all(
        later + tolerance >= earlier for earlier, later in zip(times, times[1:])
    )
    if objective_sense == "minimize":
        objectives_monotonic = all(
            later < earlier - tolerance
            for earlier, later in zip(objectives, objectives[1:])
        )
    elif objective_sense == "maximize":
        objectives_monotonic = all(
            later > earlier + tolerance
            for earlier, later in zip(objectives, objectives[1:])
        )
    else:
        objectives_monotonic = False
    final_objective_matches = bool(trace) and final_objective is not None and math.isclose(
        objectives[-1], float(final_objective), rel_tol=tolerance, abs_tol=tolerance
    )
    final_time_matches = (
        bool(trace)
        and final_discovery_time is not None
        and math.isclose(
            times[-1],
            float(final_discovery_time),
            rel_tol=1e-5,
            abs_tol=1e-5,
        )
    )
    gaps_consistent = True
    for record in trace:
        relative = record.get("incumbent_mip_gap_relative_at_discovery")
        percent = record.get("incumbent_mip_gap_percent_at_discovery")
        if relative is None or percent is None:
            gaps_consistent = gaps_consistent and relative is None and percent is None
        else:
            gaps_consistent = gaps_consistent and math.isclose(
                float(percent), 100.0 * float(relative), rel_tol=1e-9, abs_tol=1e-9
            )
    return {
        "incumbent_trace_present": bool(trace),
        "incumbent_times_monotonic": times_monotonic,
        "incumbent_objectives_monotonic": objectives_monotonic,
        "final_incumbent_objective_matches": final_objective_matches,
        "final_incumbent_discovery_time_matches": final_time_matches,
        "incumbent_gap_semantics_explicit": gaps_consistent,
        "incumbent_trace_consistent": all(
            (
                bool(trace),
                times_monotonic,
                objectives_monotonic,
                final_objective_matches,
                final_time_matches,
                gaps_consistent,
            )
        ),
    }


def solve_named_mip(request: Mapping[str, Any]) -> dict[str, Any]:
    """Solve one MIP and emit a named final solution plus online incumbents."""
    import pyscipopt
    from pyscipopt import Model, SCIP_EVENTTYPE

    candidate = Path(str(request["candidate_path"]))
    solution_path = Path(str(request["solution_path"]))
    expected_sha256 = str(request["candidate_sha256"])
    if sha256_file(candidate) != expected_sha256:
        raise PyScipOptSolveError("candidate SHA-256 changed before solve")
    stream_path_value = request.get("incumbent_stream_path")
    stream = (
        IncumbentParquetStream(Path(str(stream_path_value)))
        if request.get("capture_incumbent_vectors") is True and stream_path_value
        else None
    )
    variable_order_path_value = request.get("variable_order_path")
    model = Model()
    collector: OnlineIncumbentCollector | None = None
    stream_committed = False
    try:
        model.hideOutput(True)
        model.readProblem(str(candidate))
        original_objective_sense = str(model.getObjectiveSense()).lower()
        if request.get("force_minimize") is True:
            model.setMinimize()
        objective_sense = str(model.getObjectiveSense()).lower()
        pre_solve_solution_count = int(model.getNSols())
        solver_profile = str(request.get("solver_profile", "default"))
        _apply_profile(model, solver_profile)
        model.setParam("limits/time", float(request["time_limit"]))
        model.setParam("limits/nodes", int(request["node_limit"]))
        model.setParam("parallel/maxnthreads", int(request.get("threads", 1)))
        model.setParam("randomization/randomseedshift", int(request["seed"]))
        model.setParam("display/verblevel", 0)
        variables = tuple(model.getVars(transformed=False))
        variable_names = [str(variable.name) for variable in variables]
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
        collector = OnlineIncumbentCollector(
            variables=variables,
            objective_sense=objective_sense,
            stream=stream,
        )
        model.attachEventHandlerCallback(
            collector.callback,
            [SCIP_EVENTTYPE.BESTSOLFOUND],
            name="cfl_gnn_bestsolfound",
            description="Passive online incumbent capture for the CFL MVP",
        )
        solver_parameter_map = _normalized_parameter_map(model.getParams())
        solver_parameter_sha256 = canonical_sha256(solver_parameter_map)
        scip_version = ".".join(
            str(component)
            for component in (
                model.getMajorVersion(),
                model.getMinorVersion(),
                model.getTechVersion(),
            )
        )
        model.optimize()

        status = str(model.getStatus()).lower()
        solution_count = int(model.getNSols())
        best_solution = model.getBestSol() if solution_count > 0 else None
        named_variables: list[dict[str, Any]] = []
        feasibility_check = False
        objective = None
        solution_objective = None
        best_incumbent_time = None
        if best_solution is not None:
            feasibility_check = bool(
                model.checkSol(best_solution, printreason=False, completely=True)
            )
            objective = _finite_or_none(model.getObjVal())
            solution_objective = _finite_or_none(
                model.getSolObjVal(best_solution, original=True)
            )
            best_incumbent_time = _finite_or_none(model.getSolTime(best_solution))
            for variable in variables:
                lower = float(variable.getLbOriginal())
                upper = float(variable.getUbOriginal())
                named_variables.append(
                    {
                        "name": str(variable.name),
                        "raw_type": normalize_variable_type(variable.vtype()),
                        "canonical_type": canonical_variable_type(
                            variable.vtype(), lower, upper
                        ),
                        "lb": _bound_token(lower),
                        "ub": _bound_token(upper),
                        "value": float(model.getSolVal(best_solution, variable)),
                    }
                )
            named_variables.sort(key=lambda record: record["name"])

        trace_audit = audit_incumbent_trace(
            collector.trace,
            objective_sense=objective_sense,
            final_objective=solution_objective,
            final_discovery_time=best_incumbent_time,
        )
        if stream is not None:
            stream.close(commit=not collector.errors)
            stream_committed = not collector.errors
        relative_gap = _finite_or_none(model.getGap())
        payload = {
            "schema_version": int(request.get("schema_version", 3)),
            "contract_sha256": str(request["contract_sha256"]),
            "candidate_file_name": str(request["candidate_file_name"]),
            "candidate_sha256": expected_sha256,
            "solver_profile": solver_profile,
            "solver_versions": {
                "scip": scip_version,
                "pyscipopt": str(getattr(pyscipopt, "__version__", "unknown")),
            },
            "solver_parameter_map": solver_parameter_map,
            "solver_parameter_sha256": solver_parameter_sha256,
            "solution_source": "independent_pyscipopt_optimization",
            "fresh_process": True,
            "warm_start_supplied": False,
            "parent_incumbent_consumed": False,
            "original_objective_sense": original_objective_sense,
            "objective_sense": objective_sense,
            "effective_objective_sense": objective_sense,
            "pre_solve_solution_count": pre_solve_solution_count,
            "solve_status": status,
            "solution_count": solution_count,
            "objective": objective,
            "solution_objective": solution_objective,
            "best_bound": _finite_or_none(model.getDualbound()),
            "mip_gap_relative": relative_gap,
            "mip_gap_percent": _gap_percent(relative_gap),
            "execution_time_seconds": _finite_or_none(model.getSolvingTime()),
            "reading_time_seconds": _finite_or_none(model.getReadingTime()),
            "presolving_time_seconds": _finite_or_none(model.getPresolvingTime()),
            "nodes_current_run": int(model.getNNodes()),
            "nodes_total": int(model.getNTotalNodes()),
            "best_incumbent_discovery_time_seconds": best_incumbent_time,
            "incumbent_trace": collector.trace,
            "incumbent_trace_error_count": len(collector.errors),
            "incumbent_trace_errors": collector.errors,
            "incumbent_trace_audit": trace_audit,
            "incumbent_trace_source": "pyscipopt_bestsolfound_event",
            "incumbent_gap_at_discovery_availability": ONLINE_GAP_AVAILABILITY,
            "online_incumbent_capture": {
                "event_type": "BESTSOLFOUND",
                "handler": "Model.attachEventHandlerCallback",
                "passive": True,
                "events_recorded": len(collector.trace),
                "capture_error_count": len(collector.errors),
                "vectors_streamed": stream.rows_written if stream else 0,
                "stream_committed": stream_committed,
                "variable_order_sha256": variable_order_sha256,
            },
            "performance_feature_tags": PERFORMANCE_FEATURE_TAGS,
            "solver_feasibility_check": feasibility_check,
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
        try:
            model.freeProb()
        except Exception:
            pass

