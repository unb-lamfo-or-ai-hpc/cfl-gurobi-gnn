"""Isolated PySCIPOpt audit for exact node-subproblem materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 2
DATASET_VARIANT = "pyscipopt_node_subproblem_prototype"
PLAN_NAME = "pyscipopt_node_probe_plan.json"
REPORT_NAME = "pyscipopt_node_capability_report.json"
NODE_MANIFEST_NAME = "node_manifest.jsonl"
ROUNDTRIP_NAME = "roundtrip_audit.jsonl"
MAX_DETAILED_BOUND_CHANGES = 1_000
SUPPORTED_SUFFIXES = (".lp", ".lp.gz", ".mps", ".mps.gz", ".cip", ".cip.gz")
TOY_SPECIFICATION = {
    "name": "binary_cover_fractional_root_v1",
    "variables": ["x0", "x1", "x2"],
    "constraint": "2*x0 + 2*x1 + 2*x2 >= 3",
    "objective": "minimize x0 + x1 + x2",
}
OFFICIAL_REFERENCES = (
    "https://pyscipopt.readthedocs.io/en/latest/tutorials/eventhandler.html",
    "https://pyscipopt.readthedocs.io/en/latest/api/node.html",
    "https://pyscipopt.readthedocs.io/en/latest/api/variable.html",
    "https://pyscipopt.readthedocs.io/en/latest/api/model.html",
    "https://www.scipopt.org/scip/doc/html/group__GlobalProblemMethods.php",
)


class PyScipOptProbeError(RuntimeError):
    """Raised when a prototype run cannot satisfy its fail-closed contract."""


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
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


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    normalized = int(value)
    if normalized != value or normalized <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return normalized


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a nonnegative integer")
    normalized = int(value)
    if normalized != value or normalized < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return normalized


def _positive_finite(value: Any, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return normalized


def _finite_or_none(value: Any) -> float | None:
    normalized = float(value)
    return normalized if math.isfinite(normalized) and abs(normalized) < 1e19 else None


def _bound_token(value: Any) -> float | str:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized >= 1e19:
        return "+inf"
    if normalized <= -1e19:
        return "-inf"
    return normalized


def _source_id(path: Path) -> str:
    lowered = path.name.lower()
    for suffix in sorted(SUPPORTED_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(suffix):
            return path.name[: -len(suffix)]
    raise ValueError("instance must be LP, MPS, or CIP, optionally gzip-compressed")


@dataclass(frozen=True, slots=True)
class ProbePlan:
    source_kind: str
    source_id: str
    source_sha256: str
    source_file_name: str | None
    instance_path: Path | None
    output_dir: Path
    time_limit: float
    node_limit: int
    max_samples: int
    min_depth: int
    max_depth: int
    presolve: str
    seed: int

    @property
    def contract_payload(self) -> dict[str, Any]:
        source = {
            "kind": self.source_kind,
            "source_id": self.source_id,
            "sha256": self.source_sha256,
        }
        if self.source_file_name is not None:
            source["file_name"] = self.source_file_name
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "source": source,
            "objective_sense_override": "MINIMIZE",
            "parameters": {
                "time_limit": self.time_limit,
                "node_limit": self.node_limit,
                "max_samples": self.max_samples,
                "min_depth": self.min_depth,
                "max_depth": self.max_depth,
                "presolve": self.presolve,
                "threads": 1,
                "seed": self.seed,
            },
            "events": {
                "capture": "NODEFOCUSED",
                "serialization": "LPSOLVED",
            },
            "candidate_writers": ["writeMIP", "writeProblem_transformed"],
            "roundtrip_mode": "fresh_python_process",
            "eligibility": "experimental_ineligible_pending_review",
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        return {
            **self.contract_payload,
            "contract_sha256": self.contract_sha256,
            "planned_outputs": [
                REPORT_NAME,
                NODE_MANIFEST_NAME,
                ROUNDTRIP_NAME,
            ],
        }


def build_probe_plan(
    *,
    output_dir: str | Path,
    instance_path: str | Path | None = None,
    toy: bool = False,
    time_limit: float = 60.0,
    node_limit: int = 100,
    max_samples: int = 4,
    min_depth: int = 1,
    max_depth: int = 8,
    presolve: str = "off",
    seed: int = 42,
) -> ProbePlan:
    if toy == (instance_path is not None):
        raise ValueError("select exactly one of toy or instance_path")
    if presolve not in {"off", "default"}:
        raise ValueError("presolve must be 'off' or 'default'")
    minimum = _nonnegative_int(min_depth, "min_depth")
    maximum = _nonnegative_int(max_depth, "max_depth")
    if maximum < minimum:
        raise ValueError("max_depth must be greater than or equal to min_depth")
    if toy:
        source_kind = "controlled_toy"
        source_id = str(TOY_SPECIFICATION["name"])
        source_sha = _canonical_sha256(TOY_SPECIFICATION)
        source_file_name = None
        source_path = None
    else:
        source_path = Path(instance_path).resolve()  # type: ignore[arg-type]
        if not source_path.is_file() or source_path.stat().st_size == 0:
            raise FileNotFoundError(f"missing or empty instance: {source_path}")
        source_kind = "original_instance"
        source_id = _source_id(source_path)
        source_sha = sha256_file(source_path)
        source_file_name = source_path.name
    return ProbePlan(
        source_kind=source_kind,
        source_id=source_id,
        source_sha256=source_sha,
        source_file_name=source_file_name,
        instance_path=source_path,
        output_dir=Path(output_dir).resolve(),
        time_limit=_positive_finite(time_limit, "time_limit"),
        node_limit=_positive_int(node_limit, "node_limit"),
        max_samples=_positive_int(max_samples, "max_samples"),
        min_depth=minimum,
        max_depth=maximum,
        presolve=presolve,
        seed=_positive_int(seed, "seed"),
    )


def model_signature(model: Any, *, transformed: bool) -> dict[str, Any]:
    variables = list(model.getVars(transformed=transformed))
    constraints = list(model.getConss(transformed=transformed))
    variable_types = Counter(str(variable.vtype()) for variable in variables)
    nonzeros = 0
    nonzeros_exact = True
    unsupported_constraints = 0
    for constraint in constraints:
        try:
            nonzeros += int(model.getConsNVars(constraint))
        except (TypeError, ValueError, RuntimeError):
            nonzeros_exact = False
            unsupported_constraints += 1
    return {
        "rows": len(constraints),
        "columns": len(variables),
        "nonzeros": nonzeros if nonzeros_exact else None,
        "nonzeros_exact": nonzeros_exact,
        "constraints_without_linear_size": unsupported_constraints,
        "variable_types": dict(sorted(variable_types.items())),
    }


def _active_path(node: Any) -> list[Any]:
    path: list[Any] = []
    current = node
    while current is not None:
        path.append(current)
        if len(path) > 10_000:
            raise PyScipOptProbeError("node ancestry exceeds safety limit")
        current = current.getParent()
    path.reverse()
    return path


def _normalized_bound_type(direction: Any) -> str:
    normalized = str(direction).strip().lower()
    if normalized == "0" or normalized.endswith("lower"):
        return "lower"
    if normalized == "1" or normalized.endswith("upper"):
        return "upper"
    raise PyScipOptProbeError("unsupported branching bound type")


def _node_branchings(node: Any) -> list[dict[str, Any]]:
    raw_branchings = node.getParentBranchings()
    if raw_branchings is None:
        return []
    variables, bounds, directions = raw_branchings
    parent = node.getParent()
    return sorted(
        [
            {
                "at_node_number": int(node.getNumber()),
                "parent_number": (
                    int(parent.getNumber()) if parent is not None else None
                ),
                "variable": str(variable.name),
                "bound": _bound_token(bound),
                "bound_type": _normalized_bound_type(direction),
            }
            for variable, bound, direction in zip(variables, bounds, directions)
        ],
        key=lambda item: (
            item["at_node_number"],
            item["variable"],
            item["bound_type"],
            str(item["bound"]),
        ),
    )


def _constraint_descriptor(model: Any, constraint: Any) -> dict[str, Any]:
    descriptor: dict[str, Any] = {"name": str(constraint.name)}
    try:
        variables = list(model.getConsVars(constraint))
        coefficients = list(model.getConsVals(constraint))
        descriptor["linear_terms"] = sorted(
            [
                [str(variable.name), _bound_token(coefficient)]
                for variable, coefficient in zip(variables, coefficients)
            ],
            key=lambda item: item[0],
        )
        descriptor["representation"] = "linear_terms"
    except (TypeError, ValueError, RuntimeError, AttributeError):
        descriptor["representation"] = "handler_terms_unavailable"
    try:
        descriptor["lhs"] = _bound_token(model.getLhs(constraint))
        descriptor["rhs"] = _bound_token(model.getRhs(constraint))
    except (TypeError, ValueError, RuntimeError, AttributeError):
        descriptor["sides_available"] = False
    return descriptor


def _constraint_matches(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> bool:
    if str(expected.get("name")) != str(actual.get("name")):
        return False
    if expected.get("representation") == "linear_terms":
        if actual.get("representation") != "linear_terms":
            return False
        if expected.get("linear_terms") != actual.get("linear_terms"):
            return False
    for side in ("lhs", "rhs"):
        if side in expected and expected.get(side) != actual.get(side):
            return False
    return True


def capture_node_state(model: Any, node: Any, source_sha256: str) -> dict[str, Any]:
    variables = list(model.getVars(transformed=True))
    local_vector: list[list[Any]] = []
    changes: list[dict[str, Any]] = []
    local_bound_change_count = 0
    type_counts: Counter[str] = Counter()
    for variable in variables:
        name = str(variable.name)
        variable_type = str(variable.vtype())
        type_counts[variable_type] += 1
        global_lb = _bound_token(variable.getLbGlobal())
        global_ub = _bound_token(variable.getUbGlobal())
        local_lb = _bound_token(variable.getLbLocal())
        local_ub = _bound_token(variable.getUbLocal())
        local_vector.append([name, variable_type, local_lb, local_ub])
        if local_lb != global_lb or local_ub != global_ub:
            local_bound_change_count += 1
            if len(changes) < MAX_DETAILED_BOUND_CHANGES:
                changes.append(
                    {
                        "name": name,
                        "variable_type": variable_type,
                        "global_lb": global_lb,
                        "global_ub": global_ub,
                        "local_lb": local_lb,
                        "local_ub": local_ub,
                    }
                )
    local_vector.sort(key=lambda item: item[0])
    parent = node.getParent()
    active_path = _active_path(node)
    branch_path = [
        branching
        for path_node in active_path
        for branching in _node_branchings(path_node)
    ]
    branchings = _node_branchings(node)
    added_constraints = []
    for path_node in active_path:
        for constraint in path_node.getAddedConss():
            descriptor = _constraint_descriptor(model, constraint)
            descriptor["at_node_number"] = int(path_node.getNumber())
            added_constraints.append(descriptor)
    added_constraints.sort(key=lambda item: (item["at_node_number"], item["name"]))
    domain_change_counts = [int(value) for value in node.getNDomchg()]
    semantic_payload = {
        "source_sha256": source_sha256,
        "depth": int(node.getDepth()),
        "ancestry": [int(path_node.getNumber()) for path_node in active_path],
        "branch_path": branch_path,
        "local_bound_vector_sha256": _canonical_sha256(local_vector),
        "added_constraints": added_constraints,
    }
    return {
        "node_number": int(node.getNumber()),
        "parent_number": int(parent.getNumber()) if parent is not None else None,
        "depth": int(node.getDepth()),
        "node_type": str(node.getType()),
        "node_lower_bound": _finite_or_none(node.getLowerbound()),
        "ancestry": semantic_payload["ancestry"],
        "parent_branchings": branchings,
        "branch_path": branch_path,
        "domain_change_counts": {
            "branching": domain_change_counts[0],
            "constraint_propagation": domain_change_counts[1],
            "propagation": domain_change_counts[2],
        },
        "added_constraint_count": len(added_constraints),
        "added_constraints": added_constraints,
        "transformed_variable_count": len(variables),
        "transformed_variable_types": dict(sorted(type_counts.items())),
        "local_bound_change_count": local_bound_change_count,
        "detailed_bound_changes_truncated": (
            local_bound_change_count > MAX_DETAILED_BOUND_CHANGES
        ),
        "local_bound_changes": changes,
        "local_bound_vector_sha256": semantic_payload["local_bound_vector_sha256"],
        "semantic_node_sha256": _canonical_sha256(semantic_payload),
    }


def _candidate_name(sample_index: int, node_number: int, writer: str) -> str:
    normalized_writer = "mip" if writer == "writeMIP" else "transformed"
    return f"node_{sample_index:03d}_{node_number}_{normalized_writer}.cip"


def _safe_scip_stage(model: Any) -> str:
    try:
        return str(model.getStage())
    except Exception:
        return "unavailable"


def _serialization_reason(error: Exception) -> str:
    normalized = str(error).lower()
    if "stage" in normalized or "cannot be called" in normalized:
        return "writer_unavailable_at_scip_stage"
    if "write" in normalized or "file" in normalized:
        return "candidate_writer_rejected_output"
    return "candidate_serialization_failed"


class NodeProbeObserver:
    """Capture focused nodes, then serialize them only after their LP is solved."""

    def __init__(self, plan: ProbePlan) -> None:
        self.plan = plan
        self.nodefocused_events = 0
        self.lp_solved_events = 0
        self.events_outside_depth = 0
        self.samples: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self._samples_by_node: dict[int, dict[str, Any]] = {}
        self._candidate_dir = plan.output_dir / "candidates"

    def on_node_focused(self, model: Any, event: Any) -> None:
        self.nodefocused_events += 1
        if len(self.samples) >= self.plan.max_samples:
            return
        try:
            node = event.getNode() or model.getCurrentNode()
            node_number = int(node.getNumber())
            if node_number in self._samples_by_node:
                return
            depth = int(node.getDepth())
            if depth < self.plan.min_depth or depth > self.plan.max_depth:
                self.events_outside_depth += 1
                return
            sample = capture_node_state(model, node, self.plan.source_sha256)
            sample_index = len(self.samples)
            sample["sample_index"] = sample_index
            sample["focused_semantic_node_sha256"] = sample[
                "semantic_node_sha256"
            ]
            sample["state_capture_event"] = "NODEFOCUSED"
            sample["candidate_exports"] = []
            sample["serialization_event"] = None
            self.samples.append(sample)
            self._samples_by_node[node_number] = sample
        except Exception as error:
            self.errors.append(
                {
                    "event": "NODEFOCUSED",
                    "event_index": self.nodefocused_events - 1,
                    "error_type": type(error).__name__,
                    "reason_code": "node_capture_failed",
                }
            )

    def on_lp_solved(self, model: Any, event: Any) -> None:
        self.lp_solved_events += 1
        try:
            node = model.getCurrentNode()
            if node is None:
                return
            sample = self._samples_by_node.get(int(node.getNumber()))
            if sample is None or sample["candidate_exports"]:
                return
            serialization_state = capture_node_state(
                model, node, self.plan.source_sha256
            )
            sample.update(serialization_state)
            sample["state_capture_event"] = "LPSOLVED"
            sample["serialization_event"] = "LPSOLVED"
            self._candidate_dir.mkdir(parents=True, exist_ok=True)
            for writer in ("writeMIP", "writeProblem_transformed"):
                self._export_candidate(model, sample, writer)
        except Exception as error:
            self.errors.append(
                {
                    "event": "LPSOLVED",
                    "event_index": self.lp_solved_events - 1,
                    "error_type": type(error).__name__,
                    "reason_code": "node_serialization_dispatch_failed",
                }
            )

    def _export_candidate(
        self, model: Any, sample: dict[str, Any], writer: str
    ) -> None:
        filename = _candidate_name(sample["sample_index"], sample["node_number"], writer)
        path = self._candidate_dir / filename
        export = {
            "writer": writer,
            "writer_role": (
                "node_mip_candidate"
                if writer == "writeMIP"
                else "transformed_problem_control"
            ),
            "serialization_event": "LPSOLVED",
            "scip_stage": _safe_scip_stage(model),
            "file_name": filename,
            "relative_path": f"candidates/{filename}",
            "status": "failed",
        }
        try:
            if writer == "writeMIP":
                model.writeMIP(
                    str(path), genericnames=False, origobj=True, lazyconss=True
                )
            else:
                model.writeProblem(
                    str(path), trans=True, genericnames=False, verbose=False
                )
            if not path.is_file() or path.stat().st_size == 0:
                raise PyScipOptProbeError("candidate writer produced no bytes")
            export.update(
                {
                    "status": "written",
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
            self.candidates.append(
                {
                    "path": path,
                    "sample": sample,
                    "export": export,
                }
            )
        except Exception as error:
            export["error_type"] = type(error).__name__
            export["reason_code"] = _serialization_reason(error)
        sample["candidate_exports"].append(export)

    def summary(self) -> dict[str, Any]:
        writer_attempts = Counter()
        writer_successes = Counter()
        for sample in self.samples:
            for export in sample["candidate_exports"]:
                writer_attempts[export["writer"]] += 1
                if export["status"] == "written":
                    writer_successes[export["writer"]] += 1
        return {
            "nodefocused_events": self.nodefocused_events,
            "lp_solved_events": self.lp_solved_events,
            "events_outside_depth_window": self.events_outside_depth,
            "samples_recorded": len(self.samples),
            "candidate_files_written": len(self.candidates),
            "writer_attempts": dict(sorted(writer_attempts.items())),
            "writer_successes": dict(sorted(writer_successes.items())),
            "capture_error_count": len(self.errors),
            "capture_errors": list(self.errors),
        }


def evaluate_roundtrip(
    sample: Mapping[str, Any], export: Mapping[str, Any], inspection: Mapping[str, Any]
) -> dict[str, Any]:
    readable = inspection.get("status") == "readable"
    expected_types = sample.get("transformed_variable_types", {})
    actual_types = inspection.get("signature", {}).get("variable_types", {})
    integrality_preserved = readable and all(
        int(actual_types.get(key, 0)) >= int(value)
        for key, value in expected_types.items()
        if key in {"BINARY", "INTEGER", "IMPLINT"}
    )
    bounds_match = readable and bool(inspection.get("expected_local_bounds_match"))
    constraints_match = readable and bool(
        inspection.get("expected_local_constraints_match")
    )
    branch_bounds_match = readable and bool(
        inspection.get("expected_branch_bounds_match")
    )
    objective_minimize = readable and inspection.get("objective_sense") == "minimize"
    semantic_distinction = (
        int(sample.get("depth", 0)) > 0
        and (
            int(sample.get("local_bound_change_count", 0)) > 0
            or int(sample.get("added_constraint_count", 0)) > 0
            or bool(sample.get("branch_path"))
        )
    )
    writer_supports_node_mip = export["writer"] == "writeMIP"
    checks_passed = all(
        [
            readable,
            objective_minimize,
            integrality_preserved,
            bounds_match,
            constraints_match,
            branch_bounds_match,
            semantic_distinction,
        ]
    )
    if not writer_supports_node_mip:
        roundtrip_status = "transformed_problem_control_only"
    elif checks_passed:
        roundtrip_status = "candidate_passed_mechanical_checks"
    else:
        roundtrip_status = "candidate_failed_or_incomplete"
    return {
        "sample_index": sample["sample_index"],
        "node_number": sample["node_number"],
        "semantic_node_sha256": sample["semantic_node_sha256"],
        "writer": export["writer"],
        "writer_role": export["writer_role"],
        "file_name": export["file_name"],
        "artifact_sha256": export.get("sha256"),
        "fresh_process_readable": readable,
        "objective_minimize": objective_minimize,
        "integrality_preserved": integrality_preserved,
        "expected_local_bounds_match": bounds_match,
        "expected_local_constraints_match": constraints_match,
        "expected_branch_bounds_match": branch_bounds_match,
        "semantic_distinction_observed": semantic_distinction,
        "candidate_signature": inspection.get("signature"),
        "roundtrip_status": roundtrip_status,
        "dataset_eligible": False,
        "eligibility_reason": "prototype_requires_independent_scientific_review",
    }


def _branch_bound_matches(variable: Any, branching: Mapping[str, Any]) -> bool:
    expected = branching.get("bound")
    if not isinstance(expected, (int, float)) or isinstance(expected, bool):
        return False
    bound_type = branching.get("bound_type")
    tolerance = 1e-9 * max(1.0, abs(float(expected)))
    if bound_type == "lower":
        return float(variable.getLbOriginal()) + tolerance >= float(expected)
    if bound_type == "upper":
        return float(variable.getUbOriginal()) - tolerance <= float(expected)
    return False


def inspect_candidate(candidate_path: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    from pyscipopt import Model

    model = Model()
    try:
        model.hideOutput(True)
        model.readProblem(str(candidate_path))
        variables = list(model.getVars(transformed=False))
        actual_constraints = [
            _constraint_descriptor(model, constraint)
            for constraint in model.getConss(transformed=False)
        ]
        by_name = {str(variable.name): variable for variable in variables}
        mismatches: list[dict[str, Any]] = []
        for change in expected.get("local_bound_changes", []):
            variable = by_name.get(str(change["name"]))
            if variable is None:
                mismatches.append({"name": change["name"], "reason": "missing_variable"})
                continue
            actual_lb = _bound_token(variable.getLbOriginal())
            actual_ub = _bound_token(variable.getUbOriginal())
            if actual_lb != change["local_lb"] or actual_ub != change["local_ub"]:
                mismatches.append({"name": change["name"], "reason": "bound_mismatch"})
        branch_mismatches: list[dict[str, Any]] = []
        for branching in expected.get("branch_path", []):
            variable = by_name.get(str(branching["variable"]))
            if variable is None:
                branch_mismatches.append(
                    {
                        "name": branching["variable"],
                        "bound_type": branching.get("bound_type"),
                        "reason": "missing_branch_variable",
                    }
                )
            elif not _branch_bound_matches(variable, branching):
                branch_mismatches.append(
                    {
                        "name": branching["variable"],
                        "bound_type": branching.get("bound_type"),
                        "reason": "branch_bound_not_materialized",
                    }
                )
        constraint_mismatches = []
        for expected_constraint in expected.get("added_constraints", []):
            if not any(
                _constraint_matches(expected_constraint, actual_constraint)
                for actual_constraint in actual_constraints
            ):
                constraint_mismatches.append(
                    {
                        "name": str(expected_constraint.get("name")),
                        "reason": "missing_or_structurally_distinct_constraint",
                    }
                )
        return {
            "status": "readable",
            "objective_sense": str(model.getObjectiveSense()).lower(),
            "signature": model_signature(model, transformed=False),
            "expected_local_bound_count": len(expected.get("local_bound_changes", [])),
            "expected_local_bounds_match": not mismatches,
            "expected_branch_bound_count": len(expected.get("branch_path", [])),
            "expected_branch_bounds_match": not branch_mismatches,
            "expected_local_constraint_count": len(
                expected.get("added_constraints", [])
            ),
            "expected_local_constraints_match": not constraint_mismatches,
            "bound_mismatch_count": len(mismatches),
            "bound_mismatches": mismatches[:20],
            "branch_bound_mismatch_count": len(branch_mismatches),
            "branch_bound_mismatches": branch_mismatches[:20],
            "constraint_mismatch_count": len(constraint_mismatches),
            "constraint_mismatches": constraint_mismatches[:20],
        }
    finally:
        try:
            model.freeProb()
        except Exception:
            pass


def _run_roundtrip_worker(
    candidate_path: Path, expected_path: Path, output_path: Path
) -> int:
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    try:
        inspection = inspect_candidate(candidate_path, expected)
    except Exception as error:
        inspection = {
            "status": "failed",
            "error_type": type(error).__name__,
            "reason_code": "fresh_process_read_failed",
        }
    _write_json(output_path, inspection)
    return 0 if inspection["status"] == "readable" else 2


def _fresh_process_inspection(candidate: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(candidate["path"])
    expected_path = path.with_suffix(path.suffix + ".expected.json")
    output_path = path.with_suffix(path.suffix + ".inspection.json")
    expected = {
        "local_bound_changes": candidate["sample"]["local_bound_changes"],
        "branch_path": candidate["sample"]["branch_path"],
        "added_constraints": candidate["sample"]["added_constraints"],
    }
    _write_json(expected_path, expected)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cfl_gnn.cli.audit_pyscipopt_node_subproblems",
                "--inspect_candidate",
                str(path),
                "--expected_bounds",
                str(expected_path),
                "--inspection_output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if output_path.is_file():
            return json.loads(output_path.read_text(encoding="utf-8"))
        return {
            "status": "failed",
            "return_code": result.returncode,
            "reason_code": "fresh_process_produced_no_audit",
        }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "reason_code": "fresh_process_timeout"}
    finally:
        expected_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def _build_toy_model(Model: Any) -> Any:
    model = Model(str(TOY_SPECIFICATION["name"]))
    variables = [model.addVar(name=f"x{index}", vtype="B") for index in range(3)]
    model.addCons(2 * sum(variables) >= 3, name="fractional_cover")
    model.setObjective(sum(variables), sense="minimize")
    return model


def determine_gate_status(
    observations: Mapping[str, Any],
    roundtrip_by_writer: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    write_mip = roundtrip_by_writer["writeMIP"]
    if observations["capture_error_count"]:
        reason = "node_capture_failed"
    elif observations["samples_recorded"] == 0:
        reason = "no_nonroot_node_sampled"
    elif write_mip["candidates_audited"] == 0:
        reason = "write_mip_candidate_not_serialized"
    elif write_mip["fresh_process_readable"] == 0:
        reason = "write_mip_candidate_not_readable"
    elif write_mip["mechanical_checks_passed"] == 0:
        reason = "write_mip_mechanical_checks_failed"
    else:
        reason = "write_mip_mechanical_check_observed_pending_review"
    status = (
        "passed"
        if reason == "write_mip_mechanical_check_observed_pending_review"
        else "failed"
    )
    return status, reason


def run_probe(plan: ProbePlan) -> dict[str, Any]:
    import pyscipopt
    from pyscipopt import Model, SCIP_EVENTTYPE, SCIP_PARAMSETTING

    model = _build_toy_model(Model) if plan.source_kind == "controlled_toy" else Model()
    try:
        model.hideOutput(True)
        if plan.instance_path is not None:
            model.readProblem(str(plan.instance_path))
        original_sense = str(model.getObjectiveSense()).upper()
        model.setMinimize()
        source_signature = model_signature(model, transformed=False)
        model.setParam("limits/time", plan.time_limit)
        model.setParam("limits/nodes", plan.node_limit)
        model.setParam("parallel/maxnthreads", 1)
        model.setParam("randomization/randomseedshift", plan.seed)
        model.setParam("display/verblevel", 0)
        if plan.presolve == "off":
            model.setPresolve(SCIP_PARAMSETTING.OFF)
            model.setHeuristics(SCIP_PARAMSETTING.OFF)
            model.setSeparating(SCIP_PARAMSETTING.OFF)
        observer = NodeProbeObserver(plan)
        model.attachEventHandlerCallback(
            observer.on_node_focused,
            [SCIP_EVENTTYPE.NODEFOCUSED],
            name="cfl_gnn_node_capture",
            description="Passive bounded node-state capture",
        )
        model.attachEventHandlerCallback(
            observer.on_lp_solved,
            [SCIP_EVENTTYPE.LPSOLVED],
            name="cfl_gnn_node_serializer",
            description="Post-LP node-subproblem serialization probe",
        )
        model.optimize()
        roundtrips = []
        for candidate in observer.candidates:
            inspection = _fresh_process_inspection(candidate)
            roundtrips.append(
                evaluate_roundtrip(candidate["sample"], candidate["export"], inspection)
            )
        roundtrip_by_writer = {}
        for writer in ("writeMIP", "writeProblem_transformed"):
            writer_roundtrips = [
                item for item in roundtrips if item["writer"] == writer
            ]
            roundtrip_by_writer[writer] = {
                "candidates_audited": len(writer_roundtrips),
                "fresh_process_readable": sum(
                    bool(item["fresh_process_readable"])
                    for item in writer_roundtrips
                ),
                "branch_bounds_matched": sum(
                    bool(item["expected_branch_bounds_match"])
                    for item in writer_roundtrips
                ),
                "mechanical_checks_passed": sum(
                    item["roundtrip_status"]
                    == "candidate_passed_mechanical_checks"
                    for item in writer_roundtrips
                ),
            }
        observations = observer.summary()
        gate_status, gate_reason = determine_gate_status(
            observations, roundtrip_by_writer
        )
        report = {
            **plan.to_summary(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "probe_completed": True,
            "gate_status": gate_status,
            "environment": {
                "python": sys.version.split()[0],
                "pyscipopt": str(getattr(pyscipopt, "__version__", "unknown")),
                "scip": str(model.version()),
            },
            "source_model": {
                "original_objective_sense": original_sense,
                "effective_objective_sense": "MINIMIZE",
                "signature": source_signature,
            },
            "solve": {
                "status": str(model.getStatus()),
                "solving_time": float(model.getSolvingTime()),
                "total_nodes": int(model.getNTotalNodes()),
                "solutions_found": int(model.getNSolsFound()),
                "primal_bound": _finite_or_none(model.getPrimalbound()),
                "dual_bound": _finite_or_none(model.getDualbound()),
            },
            "observations": observations,
            "roundtrip": {
                "candidates_audited": len(roundtrips),
                "fresh_process_readable": sum(
                    bool(item["fresh_process_readable"]) for item in roundtrips
                ),
                "mechanical_checks_passed": sum(
                    item["roundtrip_status"] == "candidate_passed_mechanical_checks"
                    for item in roundtrips
                ),
                "by_writer": roundtrip_by_writer,
            },
            "decision": {
                "local_node_state_observed": bool(observer.samples),
                "candidate_serialization_observed": bool(observer.candidates),
                "write_mip_candidate_observed": bool(
                    roundtrip_by_writer["writeMIP"]["candidates_audited"]
                ),
                "write_mip_mechanical_check_observed": bool(
                    roundtrip_by_writer["writeMIP"]["mechanical_checks_passed"]
                ),
                "exact_node_subproblem_proven": False,
                "dataset_eligible": False,
                "reason_code": gate_reason,
            },
            "official_references": list(OFFICIAL_REFERENCES),
        }
        _write_jsonl(plan.output_dir / NODE_MANIFEST_NAME, observer.samples)
        _write_jsonl(plan.output_dir / ROUNDTRIP_NAME, roundtrips)
        return report
    finally:
        try:
            model.freeProb()
        except Exception:
            pass


def failure_report(plan: ProbePlan, error: Exception) -> dict[str, Any]:
    return {
        **plan.to_summary(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": False,
        "gate_status": "failed",
        "failure": {
            "error_type": type(error).__name__,
            "reason_code": "pyscipopt_probe_failed",
        },
        "decision": {
            "exact_node_subproblem_proven": False,
            "dataset_eligible": False,
            "reason_code": "probe_failed_before_capability_assessment",
        },
        "official_references": list(OFFICIAL_REFERENCES),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit PySCIPOpt node-local state and candidate serialization."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--toy", action="store_true")
    source.add_argument("--instance", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--time_limit", type=float, default=60.0)
    parser.add_argument("--node_limit", type=int, default=100)
    parser.add_argument("--max_samples", type=int, default=4)
    parser.add_argument("--min_depth", type=int, default=1)
    parser.add_argument("--max_depth", type=int, default=8)
    parser.add_argument("--presolve", choices=("off", "default"), default="off")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--inspect_candidate", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--expected_bounds", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--inspection_output", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = build_parser().parse_args(argv)
    if args.inspect_candidate is not None:
        if args.expected_bounds is None or args.inspection_output is None:
            raise ValueError("inspection worker requires expected bounds and output")
        return _run_roundtrip_worker(
            args.inspect_candidate, args.expected_bounds, args.inspection_output
        )
    if args.output_dir is None or (not args.toy and args.instance is None):
        raise ValueError("select --toy or --instance and provide --output_dir")
    plan = build_probe_plan(
        output_dir=args.output_dir,
        instance_path=args.instance,
        toy=args.toy,
        time_limit=args.time_limit,
        node_limit=args.node_limit,
        max_samples=args.max_samples,
        min_depth=args.min_depth,
        max_depth=args.max_depth,
        presolve=args.presolve,
        seed=args.seed,
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
        f"source={plan.source_id} | contract={plan.contract_sha256} | "
        f"depth={plan.min_depth}:{plan.max_depth} | samples={plan.max_samples}"
    )
    print("[INFO] PySCIPOpt probe is isolated; dataset_eligible=false")
    print(f"[INFO] Plan: {plan_path}")
    if args.dry_run:
        return 0
    try:
        report = run_probe(plan)
    except Exception as error:
        report = failure_report(plan, error)
        _write_json(report_path, report)
        print(f"[INFO] Failure report: {report_path}")
        raise
    _write_json(report_path, report)
    observations = report["observations"]
    print(
        "[INFO] "
        f"NODEFOCUSED={observations['nodefocused_events']} | "
        f"LPSOLVED={observations['lp_solved_events']} | "
        f"samples={observations['samples_recorded']} | "
        f"candidates={observations['candidate_files_written']}"
    )
    print(f"[INFO] Report: {report_path}")
    if report["gate_status"] != "passed":
        raise PyScipOptProbeError(
            f"prototype gate failed: {report['decision']['reason_code']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
