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
SCHEMA_VERSION = 1
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
            "event": "NODEFOCUSED",
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


def _ancestry(node: Any) -> list[int]:
    ancestry: list[int] = []
    current = node
    while current is not None:
        ancestry.append(int(current.getNumber()))
        if len(ancestry) > 10_000:
            raise PyScipOptProbeError("node ancestry exceeds safety limit")
        current = current.getParent()
    ancestry.reverse()
    return ancestry


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
    branch_variables, branch_bounds, branch_directions = node.getParentBranchings()
    branchings = sorted(
        [
            {
                "variable": str(variable.name),
                "bound": _bound_token(bound),
                "direction": str(direction),
            }
            for variable, bound, direction in zip(
                branch_variables, branch_bounds, branch_directions
            )
        ],
        key=lambda item: (item["variable"], str(item["direction"]), str(item["bound"])),
    )
    added_constraints = sorted(
        [_constraint_descriptor(model, constraint) for constraint in node.getAddedConss()],
        key=lambda item: item["name"],
    )
    domain_change_counts = [int(value) for value in node.getNDomchg()]
    semantic_payload = {
        "source_sha256": source_sha256,
        "depth": int(node.getDepth()),
        "ancestry": _ancestry(node),
        "parent_branchings": branchings,
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


class NodeProbeObserver:
    """Bounded passive observer attached to SCIP's NODEFOCUSED event."""

    def __init__(self, plan: ProbePlan) -> None:
        self.plan = plan
        self.events_seen = 0
        self.events_outside_depth = 0
        self.samples: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self._candidate_dir = plan.output_dir / "candidates"

    def __call__(self, model: Any, event: Any) -> None:
        self.events_seen += 1
        if len(self.samples) >= self.plan.max_samples:
            return
        try:
            node = event.getNode() or model.getCurrentNode()
            depth = int(node.getDepth())
            if depth < self.plan.min_depth or depth > self.plan.max_depth:
                self.events_outside_depth += 1
                return
            sample = capture_node_state(model, node, self.plan.source_sha256)
            sample_index = len(self.samples)
            sample["sample_index"] = sample_index
            sample["candidate_exports"] = []
            self._candidate_dir.mkdir(parents=True, exist_ok=True)
            for writer in ("writeMIP", "writeProblem_transformed"):
                filename = _candidate_name(sample_index, sample["node_number"], writer)
                path = self._candidate_dir / filename
                export = {
                    "writer": writer,
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
                    export["reason_code"] = "candidate_serialization_failed"
                sample["candidate_exports"].append(export)
            self.samples.append(sample)
        except Exception as error:
            self.errors.append(
                {
                    "event_index": self.events_seen - 1,
                    "error_type": type(error).__name__,
                    "reason_code": "node_capture_failed",
                }
            )

    def summary(self) -> dict[str, Any]:
        return {
            "nodefocused_events": self.events_seen,
            "events_outside_depth_window": self.events_outside_depth,
            "samples_recorded": len(self.samples),
            "candidate_files_written": len(self.candidates),
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
    objective_minimize = readable and inspection.get("objective_sense") == "minimize"
    semantic_distinction = (
        int(sample.get("depth", 0)) > 0
        and (
            int(sample.get("local_bound_change_count", 0)) > 0
            or int(sample.get("added_constraint_count", 0)) > 0
            or bool(sample.get("parent_branchings"))
        )
    )
    return {
        "sample_index": sample["sample_index"],
        "node_number": sample["node_number"],
        "semantic_node_sha256": sample["semantic_node_sha256"],
        "writer": export["writer"],
        "file_name": export["file_name"],
        "artifact_sha256": export.get("sha256"),
        "fresh_process_readable": readable,
        "objective_minimize": objective_minimize,
        "integrality_preserved": integrality_preserved,
        "expected_local_bounds_match": bounds_match,
        "expected_local_constraints_match": constraints_match,
        "semantic_distinction_observed": semantic_distinction,
        "candidate_signature": inspection.get("signature"),
        "roundtrip_status": (
            "candidate_passed_mechanical_checks"
            if all(
                [
                    readable,
                    objective_minimize,
                    integrality_preserved,
                    bounds_match,
                    constraints_match,
                    semantic_distinction,
                ]
            )
            else "candidate_failed_or_incomplete"
        ),
        "dataset_eligible": False,
        "eligibility_reason": "prototype_requires_independent_scientific_review",
    }


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
            "expected_local_constraint_count": len(
                expected.get("added_constraints", [])
            ),
            "expected_local_constraints_match": not constraint_mismatches,
            "bound_mismatch_count": len(mismatches),
            "bound_mismatches": mismatches[:20],
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
            observer,
            [SCIP_EVENTTYPE.NODEFOCUSED],
            name="cfl_gnn_node_probe",
            description="Passive bounded node-subproblem feasibility audit",
        )
        model.optimize()
        roundtrips = []
        for candidate in observer.candidates:
            inspection = _fresh_process_inspection(candidate)
            roundtrips.append(
                evaluate_roundtrip(candidate["sample"], candidate["export"], inspection)
            )
        report = {
            **plan.to_summary(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "probe_completed": True,
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
            "observations": observer.summary(),
            "roundtrip": {
                "candidates_audited": len(roundtrips),
                "fresh_process_readable": sum(
                    bool(item["fresh_process_readable"]) for item in roundtrips
                ),
                "mechanical_checks_passed": sum(
                    item["roundtrip_status"] == "candidate_passed_mechanical_checks"
                    for item in roundtrips
                ),
            },
            "decision": {
                "local_node_state_observed": bool(observer.samples),
                "candidate_serialization_observed": bool(observer.candidates),
                "exact_node_subproblem_proven": False,
                "dataset_eligible": False,
                "reason_code": "prototype_requires_independent_scientific_review",
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
        f"samples={observations['samples_recorded']} | "
        f"candidates={observations['candidate_files_written']}"
    )
    print(f"[INFO] Report: {report_path}")
    if observations["capture_error_count"]:
        raise PyScipOptProbeError("one or more node captures failed")
    if observations["samples_recorded"] == 0:
        raise PyScipOptProbeError("no node in the requested depth window was sampled")
    if report["roundtrip"]["fresh_process_readable"] == 0:
        raise PyScipOptProbeError("no candidate passed fresh-process deserialization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
