"""Independently solve and validate labels for SCIP-derived node MIPs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file


SCHEMA_VERSION = 2
DATASET_VARIANT = "scip_derived_mip_independent_label_audit"
PLAN_NAME = "scip_derived_label_audit_plan.json"
REPORT_NAME = "scip_derived_label_validation_report.json"
PER_CANDIDATE_NAME = "per_candidate_label_audit.jsonl"
SOLUTION_DIR_NAME = "candidate_solutions"
SUPPORTED_SUFFIXES = (".lp", ".mps", ".cip")
MAX_MISMATCH_DETAILS = 100
DEFAULT_MAX_PARALLEL = 4
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


class DerivedLabelAuditError(RuntimeError):
    """Raised when independent label validation fails closed."""


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def _write_gzip_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise DerivedLabelAuditError(f"expected JSON object: {path.name}")
    return loaded


def _read_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        loaded = json.load(stream)
    if not isinstance(loaded, dict):
        raise DerivedLabelAuditError(f"expected compressed JSON object: {path.name}")
    return loaded


def _require_model_file(value: str | Path, name: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"missing or empty {name}: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"{name} must be LP, MPS, or CIP")
    return path


def _positive_finite(value: Any, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return normalized


def _nonnegative_finite(value: Any, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be nonnegative and finite")
    return normalized


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    normalized = int(value)
    if normalized != value or normalized <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return normalized


def _finite_or_none(value: Any) -> float | None:
    normalized = float(value)
    return normalized if math.isfinite(normalized) and abs(normalized) < 1e19 else None


def _gap_percent(relative_gap: float | None) -> float | None:
    return None if relative_gap is None else 100.0 * relative_gap


def _bound_token(value: Any) -> float | str:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized >= 1e19:
        return "+inf"
    if normalized <= -1e19:
        return "-inf"
    return normalized


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
        raise DerivedLabelAuditError(
            f"unsupported SCIP variable type: {value!r}"
        ) from error


def canonical_root_type(raw_type: Any, lower: float, upper: float) -> str:
    """Recover binary semantics lost when SCIP writeMIP emits bounded integers."""

    normalized = normalize_variable_type(raw_type)
    if normalized == "I" and lower >= -1e-9 and upper <= 1.0 + 1e-9:
        return "B"
    return normalized


@dataclass(frozen=True, slots=True)
class LabelAuditPlan:
    root_mip: Path
    node_mips: tuple[Path, ...]
    output_dir: Path
    graph_audit_report: Path
    root_sha256: str
    node_sha256: tuple[str, ...]
    graph_audit_report_sha256: str
    graph_audit_contract_sha256: str
    time_limit: float
    node_limit: int
    seed: int
    max_parallel: int
    feasibility_tolerance: float
    optimality_tolerance: float

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "root_mip": {
                "file_name": self.root_mip.name,
                "sha256": self.root_sha256,
            },
            "node_mips": [
                {"file_name": path.name, "sha256": digest}
                for path, digest in zip(self.node_mips, self.node_sha256)
            ],
            "upstream_graph_audit": {
                "file_name": self.graph_audit_report.name,
                "sha256": self.graph_audit_report_sha256,
                "contract_sha256": self.graph_audit_contract_sha256,
                "required_gate_status": "passed",
            },
            "solve_contract": {
                "solver_interface": "PySCIPOpt",
                "objective_sense": "MINIMIZE",
                "fresh_process_per_candidate": True,
                "threads": 1,
                "time_limit": self.time_limit,
                "node_limit": self.node_limit,
                "seed": self.seed,
                "max_parallel_candidates": self.max_parallel,
                "warm_start_supplied": False,
                "parent_incumbent_consumed": False,
            },
            "validation": {
                "require_optimal_status": True,
                "require_zero_pre_solve_solutions": True,
                "require_solver_feasibility_check": True,
                "require_candidate_domain_subset_of_root": True,
                "require_strict_domain_restriction": True,
                "canonical_type_policy": "root_bounded_integer_0_1_as_binary",
                "feasibility_tolerance": self.feasibility_tolerance,
                "optimality_tolerance": self.optimality_tolerance,
            },
            "performance_feature_tags": PERFORMANCE_FEATURE_TAGS,
            "eligibility": {
                "dataset_eligible": False,
                "scientific_reporting_eligible": False,
            },
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        return {**self.contract_payload, "contract_sha256": self.contract_sha256}


def _artifact_map(report: Mapping[str, Any], key: str) -> dict[str, str]:
    values = report.get(key)
    if not isinstance(values, list):
        raise DerivedLabelAuditError(f"upstream graph audit has invalid {key}")
    result: dict[str, str] = {}
    for value in values:
        if not isinstance(value, Mapping):
            raise DerivedLabelAuditError(f"upstream graph audit has invalid {key}")
        name = str(value.get("file_name", ""))
        digest = str(value.get("sha256", ""))
        if not name or len(digest) != 64 or name in result:
            raise DerivedLabelAuditError(f"upstream graph audit has invalid {key}")
        result[name] = digest
    return result


def build_audit_plan(
    *,
    root_mip: str | Path,
    node_mips: Sequence[str | Path],
    graph_audit_report: str | Path,
    output_dir: str | Path,
    time_limit: float = 3600.0,
    node_limit: int = 1_000_000,
    seed: int = 42,
    max_parallel: int = DEFAULT_MAX_PARALLEL,
    feasibility_tolerance: float = 1e-6,
    optimality_tolerance: float = 1e-8,
) -> LabelAuditPlan:
    root = _require_model_file(root_mip, "root_mip")
    nodes = tuple(
        sorted(
            (_require_model_file(path, "node_mip") for path in node_mips),
            key=lambda path: path.name,
        )
    )
    if not nodes:
        raise ValueError("at least one node_mip is required")
    if len(set(nodes)) != len(nodes):
        raise ValueError("node_mips must be unique")
    if root in nodes:
        raise ValueError("root_mip cannot also be a node_mip")

    graph_report_path = Path(graph_audit_report).resolve()
    if not graph_report_path.is_file() or graph_report_path.stat().st_size == 0:
        raise FileNotFoundError("missing or empty graph_audit_report")
    graph_report = _read_json(graph_report_path)
    if graph_report.get("gate_status") != "passed":
        raise DerivedLabelAuditError("upstream graph observability gate did not pass")
    decision = graph_report.get("decision", {})
    if not isinstance(decision, Mapping) or not decision.get(
        "graph_observability_proven", False
    ):
        raise DerivedLabelAuditError("upstream graph observability is not proven")

    root_record = graph_report.get("root_mip")
    if not isinstance(root_record, Mapping):
        raise DerivedLabelAuditError("upstream graph audit has invalid root_mip")
    root_digest = sha256_file(root)
    if root_record.get("file_name") != root.name or root_record.get("sha256") != root_digest:
        raise DerivedLabelAuditError("root MIP does not match upstream graph audit")

    expected_nodes = _artifact_map(graph_report, "node_mips")
    actual_nodes = {path.name: sha256_file(path) for path in nodes}
    if actual_nodes != expected_nodes:
        raise DerivedLabelAuditError("node MIPs do not exactly match upstream graph audit")

    graph_contract = str(graph_report.get("contract_sha256", ""))
    if len(graph_contract) != 64:
        raise DerivedLabelAuditError("upstream graph audit contract is missing")
    return LabelAuditPlan(
        root_mip=root,
        node_mips=nodes,
        output_dir=Path(output_dir).resolve(),
        graph_audit_report=graph_report_path,
        root_sha256=root_digest,
        node_sha256=tuple(actual_nodes[path.name] for path in nodes),
        graph_audit_report_sha256=sha256_file(graph_report_path),
        graph_audit_contract_sha256=graph_contract,
        time_limit=_positive_finite(time_limit, "time_limit"),
        node_limit=_positive_int(node_limit, "node_limit"),
        seed=_positive_int(seed, "seed"),
        max_parallel=_positive_int(max_parallel, "max_parallel"),
        feasibility_tolerance=_nonnegative_finite(
            feasibility_tolerance, "feasibility_tolerance"
        ),
        optimality_tolerance=_nonnegative_finite(
            optimality_tolerance, "optimality_tolerance"
        ),
    )


def _model_domain_records(path: Path) -> list[dict[str, Any]]:
    from pyscipopt import Model

    model = Model()
    try:
        model.hideOutput(True)
        model.readProblem(str(path))
        records = []
        for variable in model.getVars(transformed=False):
            lower = float(variable.getLbOriginal())
            upper = float(variable.getUbOriginal())
            records.append(
                {
                    "name": str(variable.name),
                    "raw_type": normalize_variable_type(variable.vtype()),
                    "canonical_type": canonical_root_type(
                        variable.vtype(), lower, upper
                    ),
                    "lb": _bound_token(lower),
                    "ub": _bound_token(upper),
                }
            )
        return sorted(records, key=lambda record: record["name"])
    finally:
        try:
            model.freeProb()
        except Exception:
            pass


def _numeric_bound(value: float | str) -> float:
    if value == "+inf":
        return math.inf
    if value == "-inf":
        return -math.inf
    return float(value)


def validate_solution_vector(
    root_domains: Sequence[Mapping[str, Any]],
    candidate_variables: Sequence[Mapping[str, Any]],
    *,
    tolerance: float,
) -> dict[str, Any]:
    root = {str(record["name"]): record for record in root_domains}
    candidate = {str(record["name"]): record for record in candidate_variables}
    mismatches: list[dict[str, Any]] = []
    restriction_count = 0
    bound_violation_count = 0
    integrality_violation_count = 0

    if len(root) != len(root_domains) or len(candidate) != len(candidate_variables):
        mismatches.append({"reason_code": "duplicate_variable_name"})
    missing = sorted(set(root) - set(candidate))
    extra = sorted(set(candidate) - set(root))
    for name in missing[:MAX_MISMATCH_DETAILS]:
        mismatches.append({"name": name, "reason_code": "missing_candidate_variable"})
    for name in extra[: max(0, MAX_MISMATCH_DETAILS - len(mismatches))]:
        mismatches.append({"name": name, "reason_code": "unexpected_candidate_variable"})

    for name in sorted(set(root) & set(candidate)):
        expected = root[name]
        actual = candidate[name]
        root_type = str(expected["canonical_type"])
        candidate_raw_type = normalize_variable_type(actual["raw_type"])
        lower = _numeric_bound(actual["lb"])
        upper = _numeric_bound(actual["ub"])
        root_lower = _numeric_bound(expected["lb"])
        root_upper = _numeric_bound(expected["ub"])
        value = float(actual["value"])

        type_ok = (
            candidate_raw_type in {"B", "I"}
            if root_type in {"B", "I"}
            else candidate_raw_type == "C"
        )
        if not type_ok:
            mismatches.append({"name": name, "reason_code": "variable_type_changed"})
        actual["canonical_type"] = root_type
        if lower < root_lower - tolerance or upper > root_upper + tolerance:
            mismatches.append({"name": name, "reason_code": "domain_not_subset_of_root"})
        if lower > root_lower + tolerance or upper < root_upper - tolerance:
            restriction_count += 1
        if value < lower - tolerance or value > upper + tolerance:
            bound_violation_count += 1
            mismatches.append({"name": name, "reason_code": "solution_outside_candidate_bounds"})
        if root_type in {"B", "I"} and abs(value - round(value)) > tolerance:
            integrality_violation_count += 1
            mismatches.append({"name": name, "reason_code": "integrality_violation"})
        if root_type == "B" and (value < -tolerance or value > 1.0 + tolerance):
            bound_violation_count += 1
            mismatches.append({"name": name, "reason_code": "binary_value_out_of_range"})
        if len(mismatches) >= MAX_MISMATCH_DETAILS:
            break

    return {
        "variable_sets_match": not missing and not extra,
        "canonical_types_preserved": not any(
            item.get("reason_code") == "variable_type_changed" for item in mismatches
        ),
        "candidate_domain_subset_of_root": not any(
            item.get("reason_code") == "domain_not_subset_of_root" for item in mismatches
        ),
        "strict_domain_restriction_count": restriction_count,
        "solution_within_candidate_bounds": bound_violation_count == 0,
        "integrality_preserved": integrality_violation_count == 0,
        "bound_violation_count": bound_violation_count,
        "integrality_violation_count": integrality_violation_count,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "mismatch_details_truncated": len(mismatches) >= MAX_MISMATCH_DETAILS,
    }


def _worker_request(
    candidate: Path,
    solution_path: Path,
    plan: LabelAuditPlan,
) -> dict[str, Any]:
    return {
        "contract_sha256": plan.contract_sha256,
        "candidate_path": str(candidate),
        "candidate_file_name": candidate.name,
        "candidate_sha256": sha256_file(candidate),
        "solution_path": str(solution_path),
        "time_limit": plan.time_limit,
        "node_limit": plan.node_limit,
        "seed": plan.seed,
    }


def _solve_worker(request: Mapping[str, Any]) -> dict[str, Any]:
    from pyscipopt import Model, SCIP_EVENTTYPE

    candidate = Path(str(request["candidate_path"]))
    solution_path = Path(str(request["solution_path"]))
    model = Model()
    incumbent_trace: list[dict[str, Any]] = []
    incumbent_trace_errors = 0

    def observe_best_solution(observed_model: Any, _event: Any) -> None:
        nonlocal incumbent_trace_errors
        try:
            relative_gap = _finite_or_none(observed_model.getGap())
            incumbent_trace.append(
                {
                    "incumbent_index": len(incumbent_trace),
                    "incumbent_objective": _finite_or_none(
                        observed_model.getObjVal()
                    ),
                    "incumbent_discovery_time_seconds": _finite_or_none(
                        observed_model.getSolvingTime()
                    ),
                    "incumbent_mip_gap_relative_at_discovery": relative_gap,
                    "incumbent_mip_gap_percent_at_discovery": _gap_percent(
                        relative_gap
                    ),
                    "dual_bound_at_discovery": _finite_or_none(
                        observed_model.getDualbound()
                    ),
                    "nodes_total_at_discovery": int(
                        observed_model.getNTotalNodes()
                    ),
                }
            )
        except Exception:
            incumbent_trace_errors += 1

    try:
        model.hideOutput(True)
        model.readProblem(str(candidate))
        objective_sense = str(model.getObjectiveSense()).lower()
        pre_solve_solution_count = int(model.getNSols())
        model.setParam("limits/time", float(request["time_limit"]))
        model.setParam("limits/nodes", int(request["node_limit"]))
        model.setParam("parallel/maxnthreads", 1)
        model.setParam("randomization/randomseedshift", int(request["seed"]))
        model.setParam("display/verblevel", 0)
        model.attachEventHandlerCallback(
            observe_best_solution,
            [SCIP_EVENTTYPE.BESTSOLFOUND],
            name="cfl_gnn_incumbent_metrics",
            description="Record incumbent objective, gap, and execution time",
        )
        model.optimize()

        status = str(model.getStatus()).lower()
        solution_count = int(model.getNSols())
        best_solution = model.getBestSol() if solution_count > 0 else None
        variables: list[dict[str, Any]] = []
        solver_feasibility_check = False
        objective = None
        solution_objective = None
        best_incumbent_discovery_time = None
        if best_solution is not None:
            solver_feasibility_check = bool(
                model.checkSol(
                    best_solution,
                    printreason=False,
                    completely=True,
                )
            )
            objective = _finite_or_none(model.getObjVal())
            try:
                solution_objective = _finite_or_none(
                    model.getSolObjVal(best_solution, original=True)
                )
            except (AttributeError, TypeError):
                solution_objective = objective
            try:
                best_incumbent_discovery_time = _finite_or_none(
                    model.getSolTime(best_solution)
                )
            except (AttributeError, TypeError):
                best_incumbent_discovery_time = None
            for variable in model.getVars(transformed=False):
                variables.append(
                    {
                        "name": str(variable.name),
                        "raw_type": normalize_variable_type(variable.vtype()),
                        "lb": _bound_token(variable.getLbOriginal()),
                        "ub": _bound_token(variable.getUbOriginal()),
                        "value": float(model.getSolVal(best_solution, variable)),
                    }
                )
            variables.sort(key=lambda record: record["name"])

        relative_gap = _finite_or_none(model.getGap())
        execution_time = _finite_or_none(model.getSolvingTime())
        payload = {
            "schema_version": SCHEMA_VERSION,
            "contract_sha256": str(request["contract_sha256"]),
            "candidate_file_name": str(request["candidate_file_name"]),
            "candidate_sha256": str(request["candidate_sha256"]),
            "solution_source": "independent_pyscipopt_optimization",
            "fresh_process": True,
            "warm_start_supplied": False,
            "parent_incumbent_consumed": False,
            "objective_sense": objective_sense,
            "pre_solve_solution_count": pre_solve_solution_count,
            "solve_status": status,
            "solution_count": solution_count,
            "objective": objective,
            "solution_objective": solution_objective,
            "best_bound": _finite_or_none(model.getDualbound()),
            "mip_gap_relative": relative_gap,
            "mip_gap_percent": _gap_percent(relative_gap),
            "execution_time_seconds": execution_time,
            "reading_time_seconds": _finite_or_none(model.getReadingTime()),
            "presolving_time_seconds": _finite_or_none(
                model.getPresolvingTime()
            ),
            "nodes_current_run": int(model.getNNodes()),
            "nodes_total": int(model.getNTotalNodes()),
            "best_incumbent_discovery_time_seconds": (
                best_incumbent_discovery_time
            ),
            "incumbent_trace": incumbent_trace,
            "incumbent_trace_error_count": incumbent_trace_errors,
            "performance_feature_tags": PERFORMANCE_FEATURE_TAGS,
            "solver_feasibility_check": solver_feasibility_check,
            "variables": variables,
        }
        _write_gzip_json(solution_path, payload)
        return {
            "worker_status": "completed",
            "solution_file_name": solution_path.name,
        }
    finally:
        try:
            model.freeProb()
        except Exception:
            pass


def _run_worker(
    request_path: Path,
    worker_result_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "cfl_gnn.cli.audit_scip_derived_labels",
            "--_worker_request",
            str(request_path),
            "--_worker_result",
            str(worker_result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise DerivedLabelAuditError(
            "fresh candidate worker failed: "
            f"{completed.stderr.strip()[-500:]}"
        )


def evaluate_candidate_label(
    worker_payload: Mapping[str, Any],
    domain_audit: Mapping[str, Any],
    *,
    solution_file_name: str,
    solution_sha256: str,
    optimality_tolerance: float,
) -> dict[str, Any]:
    objective = worker_payload.get("objective")
    solution_objective = worker_payload.get("solution_objective")
    objective_consistent = (
        objective is not None
        and solution_objective is not None
        and math.isclose(
            float(objective),
            float(solution_objective),
            rel_tol=optimality_tolerance,
            abs_tol=optimality_tolerance,
        )
    )
    gap = worker_payload.get("mip_gap_relative")
    optimal_gap = gap is not None and float(gap) <= optimality_tolerance
    checks = {
        "fresh_process": worker_payload.get("fresh_process") is True,
        "zero_pre_solve_solutions": worker_payload.get("pre_solve_solution_count") == 0,
        "no_warm_start": worker_payload.get("warm_start_supplied") is False,
        "no_parent_incumbent": worker_payload.get("parent_incumbent_consumed") is False,
        "objective_minimize": worker_payload.get("objective_sense") == "minimize",
        "optimal_status": worker_payload.get("solve_status") == "optimal",
        "solution_present": int(worker_payload.get("solution_count", 0)) > 0,
        "solver_feasibility_check": worker_payload.get("solver_feasibility_check") is True,
        "objective_consistent": objective_consistent,
        "optimal_gap": optimal_gap,
        "variable_sets_match": domain_audit.get("variable_sets_match") is True,
        "canonical_types_preserved": domain_audit.get("canonical_types_preserved") is True,
        "candidate_domain_subset_of_root": domain_audit.get(
            "candidate_domain_subset_of_root"
        )
        is True,
        "strict_domain_restriction": int(
            domain_audit.get("strict_domain_restriction_count", 0)
        )
        > 0,
        "solution_within_candidate_bounds": domain_audit.get(
            "solution_within_candidate_bounds"
        )
        is True,
        "integrality_preserved": domain_audit.get("integrality_preserved") is True,
    }
    evidence_checks = {
        key: value
        for key, value in checks.items()
        if key not in {"optimal_status", "optimal_gap"}
    }
    feasible_solution_evidence = all(evidence_checks.values())
    label_eligible = feasible_solution_evidence and all(
        checks[key] for key in ("optimal_status", "optimal_gap")
    )
    solve_status = str(worker_payload.get("solve_status", "unknown"))
    if label_eligible:
        gate_status = "passed"
        optimality_status = "proven_optimal"
        reason_code = "independent_optimal_label_validated"
    elif feasible_solution_evidence:
        gate_status = "inconclusive"
        optimality_status = f"not_proven_{solve_status}"
        reason_code = f"feasible_nonoptimal_{solve_status}"
    else:
        gate_status = "failed"
        optimality_status = "not_proven_invalid_or_absent_solution"
        reason_code = "independent_solution_evidence_failed"

    relative_gap = worker_payload.get("mip_gap_relative")
    incumbent_trace = worker_payload.get("incumbent_trace", [])
    best_incumbent_trace = (
        incumbent_trace[-1] if isinstance(incumbent_trace, list) and incumbent_trace else {}
    )
    performance_features = {
        "solver": "SCIP",
        "feature_tags": PERFORMANCE_FEATURE_TAGS,
        "instance": {
            "execution_time_seconds": worker_payload.get(
                "execution_time_seconds"
            ),
            "mip_gap_relative": relative_gap,
            "mip_gap_percent": worker_payload.get("mip_gap_percent"),
        },
        "best_incumbent": {
            "incumbent_objective": objective,
            "incumbent_discovery_time_seconds": worker_payload.get(
                "best_incumbent_discovery_time_seconds"
            ),
            "incumbent_mip_gap_relative_at_discovery": (
                best_incumbent_trace.get(
                    "incumbent_mip_gap_relative_at_discovery"
                )
            ),
            "incumbent_mip_gap_percent_at_discovery": (
                best_incumbent_trace.get(
                    "incumbent_mip_gap_percent_at_discovery"
                )
            ),
            "terminal_mip_gap_relative": relative_gap,
            "terminal_mip_gap_percent": worker_payload.get("mip_gap_percent"),
        },
        "incumbent_trace_count": len(incumbent_trace),
        "incumbent_trace_error_count": worker_payload.get(
            "incumbent_trace_error_count"
        ),
    }
    return {
        "candidate_file_name": worker_payload.get("candidate_file_name"),
        "candidate_sha256": worker_payload.get("candidate_sha256"),
        "solution_source": worker_payload.get("solution_source"),
        "label_source": (
            worker_payload.get("solution_source") if label_eligible else None
        ),
        "execution_status": "completed",
        "solution_evidence_status": (
            "validated_feasible"
            if feasible_solution_evidence
            else "invalid_or_absent"
        ),
        "optimality_status": optimality_status,
        "gate_status": gate_status,
        "solve": {
            key: worker_payload.get(key)
            for key in (
                "solve_status",
                "solution_count",
                "objective",
                "solution_objective",
                "best_bound",
                "mip_gap_relative",
                "mip_gap_percent",
                "execution_time_seconds",
                "reading_time_seconds",
                "presolving_time_seconds",
                "nodes_current_run",
                "nodes_total",
            )
        },
        "performance_features": performance_features,
        "independence": {
            "fresh_process": worker_payload.get("fresh_process"),
            "pre_solve_solution_count": worker_payload.get(
                "pre_solve_solution_count"
            ),
            "warm_start_supplied": worker_payload.get("warm_start_supplied"),
            "parent_incumbent_consumed": worker_payload.get(
                "parent_incumbent_consumed"
            ),
        },
        "domain_and_solution_audit": dict(domain_audit),
        "checks": checks,
        "feasible_solution_evidence": feasible_solution_evidence,
        "solution_artifact": {
            "file_name": solution_file_name,
            "sha256": solution_sha256,
        },
        "label_eligible": label_eligible,
        "dataset_eligible": False,
        "scientific_reporting_eligible": False,
        "reason_code": reason_code,
    }


def summarize_candidate_results(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = sum(record.get("label_eligible") is True for record in records)
    feasible_evidence = sum(
        record.get("feasible_solution_evidence") is True for record in records
    )
    passed = bool(records) and eligible == len(records)
    inconclusive = (
        bool(records)
        and not passed
        and feasible_evidence == len(records)
        and all(record.get("gate_status") == "inconclusive" for record in records)
    )
    gate_status = "passed" if passed else "inconclusive" if inconclusive else "failed"
    return {
        "candidates_audited": len(records),
        "candidate_execution_completed": sum(
            record.get("execution_status") == "completed" for record in records
        ),
        "feasible_solution_evidence": feasible_evidence,
        "labels_validated": eligible,
        "labels_rejected": len(records) - eligible,
        "all_independently_optimal": all(
            record.get("checks", {}).get("optimal_status") is True
            for record in records
        ),
        "all_feasible": all(
            record.get("checks", {}).get("solver_feasibility_check") is True
            for record in records
        ),
        "all_domain_valid": all(
            record.get("checks", {}).get("candidate_domain_subset_of_root") is True
            and record.get("checks", {}).get("strict_domain_restriction") is True
            for record in records
        ),
        "gate_status": gate_status,
        "gate_passed": passed,
    }


def _load_reusable_worker_payload(
    solution_path: Path,
    candidate: Path,
    plan: LabelAuditPlan,
) -> dict[str, Any] | None:
    if not solution_path.is_file() or solution_path.stat().st_size == 0:
        return None
    try:
        payload = _read_gzip_json(solution_path)
    except (OSError, json.JSONDecodeError, DerivedLabelAuditError):
        return None
    expected = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "candidate_file_name": candidate.name,
        "candidate_sha256": sha256_file(candidate),
        "fresh_process": True,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        return None
    return payload


def _solve_and_evaluate_candidate(
    index: int,
    candidate: Path,
    root_domains: Sequence[Mapping[str, Any]],
    plan: LabelAuditPlan,
    *,
    reuse_existing: bool,
) -> tuple[int, dict[str, Any]]:
    solution_dir = plan.output_dir / SOLUTION_DIR_NAME
    solution_path = solution_dir / f"{candidate.stem}.solution.json.gz"
    payload = (
        _load_reusable_worker_payload(solution_path, candidate, plan)
        if reuse_existing
        else None
    )
    reused = payload is not None
    if payload is None:
        request_path = plan.output_dir / f".worker_request_{index:03d}.json"
        worker_result_path = plan.output_dir / f".worker_result_{index:03d}.json"
        _write_json(request_path, _worker_request(candidate, solution_path, plan))
        try:
            _run_worker(request_path, worker_result_path)
            worker_result = _read_json(worker_result_path)
            if worker_result.get("worker_status") != "completed":
                raise DerivedLabelAuditError("candidate worker did not complete")
            payload = _read_gzip_json(solution_path)
        finally:
            request_path.unlink(missing_ok=True)
            worker_result_path.unlink(missing_ok=True)

    variables = payload.get("variables")
    if not isinstance(variables, list):
        raise DerivedLabelAuditError("candidate worker omitted solution vector")
    domain_audit = validate_solution_vector(
        root_domains,
        variables,
        tolerance=plan.feasibility_tolerance,
    )
    payload["variables"] = variables
    payload["canonical_type_policy"] = "root_bounded_integer_0_1_as_binary"
    payload["contract_sha256"] = plan.contract_sha256
    _write_gzip_json(solution_path, payload)
    record = evaluate_candidate_label(
        payload,
        domain_audit,
        solution_file_name=solution_path.name,
        solution_sha256=sha256_file(solution_path),
        optimality_tolerance=plan.optimality_tolerance,
    )
    record["worker_result_reused"] = reused
    return index, record


def run_audit(
    plan: LabelAuditPlan,
    *,
    reuse_existing: bool = True,
) -> dict[str, Any]:
    root_domains = _model_domain_records(plan.root_mip)
    solution_dir = plan.output_dir / SOLUTION_DIR_NAME
    solution_dir.mkdir(parents=True, exist_ok=True)
    records_by_index: dict[int, dict[str, Any]] = {}
    workers = min(plan.max_parallel, len(plan.node_mips))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _solve_and_evaluate_candidate,
                index,
                candidate,
                root_domains,
                plan,
                reuse_existing=reuse_existing,
            ): index
            for index, candidate in enumerate(plan.node_mips)
        }
        for future in as_completed(futures):
            index, record = future.result()
            records_by_index[index] = record
            partial = [records_by_index[key] for key in sorted(records_by_index)]
            _write_jsonl(plan.output_dir / PER_CANDIDATE_NAME, partial)

    records = [records_by_index[index] for index in range(len(plan.node_mips))]
    _write_jsonl(plan.output_dir / PER_CANDIDATE_NAME, records)

    summary = summarize_candidate_results(records)
    gate_passed = summary["gate_passed"]
    gate_status = summary["gate_status"]
    reused_workers = sum(record["worker_result_reused"] for record in records)
    execution = {
        "status": "completed",
        "mode": "parallel_fresh_processes",
        "max_parallel_candidates": plan.max_parallel,
        "workers_used": workers,
        "worker_results_reused": reused_workers,
        "worker_results_executed": len(records) - reused_workers,
    }
    if gate_status == "passed":
        reason_code = "all_derived_mip_labels_independently_validated_pending_review"
        next_gate = "grouped_parent_dataset_contract_and_sampling_policy"
    elif gate_status == "inconclusive":
        reason_code = "feasible_independent_solutions_optimality_not_proven"
        next_gate = "increase_compute_or_controlled_solver_experiment"
    else:
        reason_code = "derived_mip_solution_evidence_failed"
        next_gate = "stop_or_correct_independent_label_validation"
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "execution": execution,
        "gate_status": gate_status,
        "upstream_graph_audit": plan.contract_payload["upstream_graph_audit"],
        "performance_feature_tags": PERFORMANCE_FEATURE_TAGS,
        "summary": summary,
        "eligibility": {
            "label_eligible": gate_passed,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "independent_labels_validated": gate_passed,
            "label_eligible": gate_passed,
            "dataset_eligible": False,
            "feasible_solution_evidence_validated": (
                summary["feasible_solution_evidence"] == len(records)
            ),
            "reason_code": reason_code,
            "next_gate": next_gate,
        },
    }


def failure_report(plan: LabelAuditPlan, error: Exception) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": False,
        "execution": {"status": "failed"},
        "gate_status": "failed",
        "failure": {
            "error_type": type(error).__name__,
            "reason_code": "independent_label_audit_execution_failed",
        },
        "eligibility": {
            "label_eligible": False,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently validate labels for graph-audited SCIP node MIPs."
    )
    parser.add_argument("--root_mip")
    parser.add_argument("--node_mips", nargs="+")
    parser.add_argument("--graph_audit_report")
    parser.add_argument("--output_dir")
    parser.add_argument("--time_limit", type=float, default=3600.0)
    parser.add_argument("--node_limit", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_parallel", type=int, default=DEFAULT_MAX_PARALLEL)
    parser.add_argument("--feasibility_tolerance", type=float, default=1e-6)
    parser.add_argument("--optimality_tolerance", type=float, default=1e-8)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--_worker_request", help=argparse.SUPPRESS)
    parser.add_argument("--_worker_result", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args._worker_request or args._worker_result:
        if not args._worker_request or not args._worker_result:
            raise ValueError("worker request and result must be supplied together")
        result = _solve_worker(_read_json(Path(args._worker_request)))
        _write_json(Path(args._worker_result), result)
        return 0
    required = {
        "root_mip": args.root_mip,
        "node_mips": args.node_mips,
        "graph_audit_report": args.graph_audit_report,
        "output_dir": args.output_dir,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("missing required arguments: " + ", ".join(missing))
    plan = build_audit_plan(
        root_mip=args.root_mip,
        node_mips=args.node_mips,
        graph_audit_report=args.graph_audit_report,
        output_dir=args.output_dir,
        time_limit=args.time_limit,
        node_limit=args.node_limit,
        seed=args.seed,
        max_parallel=args.max_parallel,
        feasibility_tolerance=args.feasibility_tolerance,
        optimality_tolerance=args.optimality_tolerance,
    )
    plan_path = plan.output_dir / PLAN_NAME
    report_path = plan.output_dir / REPORT_NAME
    if not args.overwrite and (
        report_path.exists() or (args.dry_run and plan_path.exists())
    ):
        raise FileExistsError("output exists; choose another directory or use --overwrite")
    _write_json(plan_path, plan.to_summary())
    print(
        "[INFO] "
        f"contract={plan.contract_sha256} | candidates={len(plan.node_mips)} | "
        "fresh_process=true | dataset_eligible=false"
    )
    print(f"[INFO] Plan: {plan_path}")
    if args.dry_run:
        return 0
    try:
        report = run_audit(plan, reuse_existing=not args.overwrite)
    except Exception as error:
        report = failure_report(plan, error)
        _write_json(report_path, report)
        print(f"[INFO] Failure report: {report_path}")
        raise
    _write_json(report_path, report)
    print(
        "[INFO] "
        f"gate={report['gate_status']} | "
        f"validated={report['summary']['labels_validated']}/"
        f"{report['summary']['candidates_audited']} | "
        "dataset_eligible=false"
    )
    print(f"[INFO] Report: {report_path}")
    if report["gate_status"] == "failed":
        raise DerivedLabelAuditError(
            "independent solution evidence failed; inspect per-candidate audit"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
