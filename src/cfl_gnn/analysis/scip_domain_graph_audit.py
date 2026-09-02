"""Audit whether SCIP domain-only variants remain distinct as PyG graphs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file


SCHEMA_VERSION = 1
DATASET_VARIANT = "scip_domain_variant_graph_observability_audit"
PLAN_NAME = "scip_domain_graph_audit_plan.json"
REPORT_NAME = "scip_domain_graph_observability_report.json"
PER_CANDIDATE_NAME = "per_candidate_graph_audit.jsonl"
VARIABLE_FEATURE_NAMES = (
    "objective_log",
    "lower_bound_log",
    "upper_bound_log",
    "is_continuous",
    "is_binary",
    "is_integer",
    "root_lp_relaxation",
)
BOUND_FEATURE_NAMES = ("lower_bound_log", "upper_bound_log")
MAX_CHANGE_DETAILS = 100
SUPPORTED_SUFFIXES = (".lp", ".mps", ".cip")


class GraphObservabilityAuditError(RuntimeError):
    """Raised when the graph-observability contract fails closed."""


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


def _require_model_file(value: str | Path, name: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"missing or empty {name}: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"{name} must be LP, MPS, or CIP")
    return path


@dataclass(frozen=True, slots=True)
class GraphAuditPlan:
    root_mip: Path
    node_mips: tuple[Path, ...]
    output_dir: Path
    root_sha256: str
    node_sha256: tuple[str, ...]
    graph_builder_source_sha256: str

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
            "graph_builder": "cfl_gnn.graph.build_dataset.build_heterodata",
            "graph_builder_source_sha256": self.graph_builder_source_sha256,
            "variable_feature_names": list(VARIABLE_FEATURE_NAMES),
            "required_classification": "domain_distinct_same_matrix",
            "eligibility": {
                "dataset_eligible": False,
                "label_eligible": False,
            },
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        return {**self.contract_payload, "contract_sha256": self.contract_sha256}


def build_audit_plan(
    *,
    root_mip: str | Path,
    node_mips: Sequence[str | Path],
    output_dir: str | Path,
) -> GraphAuditPlan:
    root = _require_model_file(root_mip, "root_mip")
    nodes = tuple(_require_model_file(path, "node_mip") for path in node_mips)
    if not nodes:
        raise ValueError("at least one node_mip is required")
    if len(set(nodes)) != len(nodes):
        raise ValueError("node_mips must be unique")
    if root in nodes:
        raise ValueError("root_mip cannot also be a node_mip")
    return GraphAuditPlan(
        root_mip=root,
        node_mips=nodes,
        output_dir=Path(output_dir).resolve(),
        root_sha256=sha256_file(root),
        node_sha256=tuple(sha256_file(path) for path in nodes),
        graph_builder_source_sha256=sha256_file(
            Path(__file__).resolve().parents[1] / "graph" / "build_dataset.py"
        ),
    )


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
        raise GraphObservabilityAuditError(
            f"unsupported SCIP variable type: {value!r}"
        ) from error


def _bound_token(value: Any) -> float | str:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized >= 1e19:
        return "+inf"
    if normalized <= -1e19:
        return "-inf"
    return normalized


def _tensor_sha256(names: Sequence[str], feature_names: Sequence[str], array: Any) -> str:
    import numpy as np

    values = np.ascontiguousarray(array, dtype="<f4")
    digest = hashlib.sha256()
    digest.update(_canonical_sha256(list(feature_names)).encode("ascii"))
    digest.update(b"\n")
    for name in names:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
    digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def _linear_constraint_data(model: Any, constraint: Any) -> tuple[str, float, list[Any], list[float]]:
    variables = list(model.getConsVars(constraint))
    coefficients = [float(value) for value in model.getConsVals(constraint)]
    lhs = float(model.getLhs(constraint))
    rhs = float(model.getRhs(constraint))
    lhs_finite = math.isfinite(lhs) and lhs > -1e19
    rhs_finite = math.isfinite(rhs) and rhs < 1e19
    tolerance = 1e-9 * max(1.0, abs(lhs) if lhs_finite else 0.0, abs(rhs) if rhs_finite else 0.0)
    if lhs_finite and rhs_finite and abs(lhs - rhs) <= tolerance:
        return "=", rhs, variables, coefficients
    if lhs_finite and not rhs_finite:
        return ">", lhs, variables, coefficients
    if rhs_finite and not lhs_finite:
        return "<", rhs, variables, coefficients
    raise GraphObservabilityAuditError(
        f"unsupported ranged or free constraint: {constraint.name}"
    )


def _extract_graph_snapshot(path: Path) -> dict[str, Any]:
    import numpy as np
    from pyscipopt import Model

    from cfl_gnn.analysis.pyscipopt_node_subproblem import (
        formulation_fingerprints,
        model_signature,
    )
    from cfl_gnn.artifacts.schemas import (
        ConstraintFeatures,
        ModelFeatures,
        VariableFeatures,
    )
    from cfl_gnn.graph.build_dataset import build_heterodata

    model = Model()
    try:
        model.hideOutput(True)
        model.readProblem(str(path))
        if str(model.getObjectiveSense()).lower() != "minimize":
            raise GraphObservabilityAuditError("candidate objective is not minimize")

        variables = sorted(
            model.getVars(transformed=False), key=lambda variable: str(variable.name)
        )
        constraints = sorted(
            model.getConss(transformed=False),
            key=lambda constraint: str(constraint.name),
        )
        variable_names = [str(variable.name) for variable in variables]
        variable_index = {name: index for index, name in enumerate(variable_names)}
        if len(variable_index) != len(variable_names):
            raise GraphObservabilityAuditError("duplicate variable names")

        variable_types = np.asarray(
            [normalize_variable_type(variable.vtype()) for variable in variables],
            dtype="<U1",
        )
        lower_bounds = np.asarray(
            [float(variable.getLbOriginal()) for variable in variables],
            dtype=np.float64,
        )
        upper_bounds = np.asarray(
            [float(variable.getUbOriginal()) for variable in variables],
            dtype=np.float64,
        )
        objective = np.asarray(
            [float(variable.getObj()) for variable in variables],
            dtype=np.float64,
        )

        senses: list[str] = []
        rhs_values: list[float] = []
        row_norms: list[float] = []
        constraint_names: list[str] = []
        constraint_indices: list[int] = []
        variable_indices: list[int] = []
        edge_coefficients: list[float] = []
        topology_records: list[dict[str, Any]] = []
        for constraint_index, constraint in enumerate(constraints):
            sense, rhs, row_variables, coefficients = _linear_constraint_data(
                model, constraint
            )
            constraint_name = str(constraint.name)
            constraint_names.append(constraint_name)
            senses.append(sense)
            rhs_values.append(rhs)
            row_norms.append(float(np.linalg.norm(coefficients)))
            terms = []
            for variable, coefficient in zip(row_variables, coefficients):
                variable_name = str(variable.name)
                if variable_name not in variable_index:
                    raise GraphObservabilityAuditError(
                        f"constraint references unknown variable: {variable_name}"
                    )
                constraint_indices.append(constraint_index)
                variable_indices.append(variable_index[variable_name])
                edge_coefficients.append(coefficient)
                terms.append([variable_name, _bound_token(coefficient)])
            topology_records.append(
                {
                    "name": constraint_name,
                    "sense": sense,
                    "rhs": _bound_token(rhs),
                    "terms": sorted(terms, key=lambda item: item[0]),
                }
            )

        model_features = ModelFeatures(
            num_vars=len(variables),
            num_constrs=len(constraints),
            num_binary=int(np.sum(variable_types == "B")),
            num_integer=int(np.sum(variable_types == "I")),
            num_continuous=int(np.sum(variable_types == "C")),
            obj_sense="MINIMIZE",
            obj_offset=0.0,
        )
        variable_features = VariableFeatures(
            types=variable_types,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            obj_coeffs=objective,
        )
        constraint_features = ConstraintFeatures(
            senses=np.asarray(senses, dtype="<U1"),
            rhs_values=np.asarray(rhs_values, dtype=np.float64),
            row_norms=np.asarray(row_norms, dtype=np.float64),
        )
        edge_indices = np.asarray(
            [constraint_indices, variable_indices], dtype=np.int64
        )
        edge_features = np.asarray(edge_coefficients, dtype=np.float64)
        graph = build_heterodata(
            model_features,
            variable_features,
            constraint_features,
            edge_indices,
            edge_features,
            np.zeros(len(variables), dtype=np.float64),
            np.zeros(len(variables), dtype=np.float64),
            1.0,
            0.0,
            False,
            -1,
            path.stem,
            {},
        )
        if graph is None:
            raise GraphObservabilityAuditError("production graph builder returned None")

        variable_x = np.ascontiguousarray(
            graph["variable"].x.detach().cpu().numpy(), dtype=np.float32
        )
        constraint_x = np.ascontiguousarray(
            graph["constraint"].x.detach().cpu().numpy(), dtype=np.float32
        )
        if variable_x.shape != (len(variables), len(VARIABLE_FEATURE_NAMES)):
            raise GraphObservabilityAuditError(
                f"unexpected variable feature shape: {variable_x.shape}"
            )
        topology_sha256 = _canonical_sha256(topology_records)
        variable_features_sha256 = _tensor_sha256(
            variable_names, VARIABLE_FEATURE_NAMES, variable_x
        )
        constraint_features_sha256 = _tensor_sha256(
            constraint_names,
            ("rhs_log", "sense_le", "sense_eq", "sense_ge", "constant_one"),
            constraint_x,
        )
        complete_graph_sha256 = _canonical_sha256(
            {
                "topology_sha256": topology_sha256,
                "variable_features_sha256": variable_features_sha256,
                "constraint_features_sha256": constraint_features_sha256,
            }
        )
        fingerprints = formulation_fingerprints(model, transformed=False)
        return {
            "file_name": path.name,
            "artifact_sha256": sha256_file(path),
            "signature": model_signature(model, transformed=False),
            "formulation_fingerprints": fingerprints,
            "graph_fingerprints": {
                "topology_sha256": topology_sha256,
                "variable_features_sha256": variable_features_sha256,
                "constraint_features_sha256": constraint_features_sha256,
                "complete_graph_sha256": complete_graph_sha256,
            },
            "graph_feature_schema": {
                "variable": list(VARIABLE_FEATURE_NAMES),
                "constraint": [
                    "rhs_log",
                    "sense_le",
                    "sense_eq",
                    "sense_ge",
                    "constant_one",
                ],
                "edge": ["coefficient_log"],
            },
            "_variable_names": variable_names,
            "_variable_types": variable_types,
            "_lower_bounds": lower_bounds,
            "_upper_bounds": upper_bounds,
            "_variable_x": variable_x,
        }
    finally:
        try:
            model.freeProb()
        except Exception:
            pass


def _public_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if not key.startswith("_")}


def compare_graph_snapshots(
    root: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    import numpy as np

    root_names = list(root["_variable_names"])
    candidate_names = list(candidate["_variable_names"])
    names_match = root_names == candidate_names
    if not names_match:
        return {
            "file_name": candidate.get("file_name"),
            "gate_status": "failed",
            "reason_code": "variable_identity_mismatch",
            "variable_names_match": False,
            "dataset_eligible": False,
            "label_eligible": False,
        }

    root_lb = np.asarray(root["_lower_bounds"])
    root_ub = np.asarray(root["_upper_bounds"])
    candidate_lb = np.asarray(candidate["_lower_bounds"])
    candidate_ub = np.asarray(candidate["_upper_bounds"])
    root_types = np.asarray(root["_variable_types"])
    candidate_types = np.asarray(candidate["_variable_types"])
    root_x = np.asarray(root["_variable_x"])
    candidate_x = np.asarray(candidate["_variable_x"])

    lb_changed = ~np.isclose(root_lb, candidate_lb, rtol=1e-12, atol=1e-12)
    ub_changed = ~np.isclose(root_ub, candidate_ub, rtol=1e-12, atol=1e-12)
    raw_changed = lb_changed | ub_changed
    encoded_lb_changed = root_x[:, 1] != candidate_x[:, 1]
    encoded_ub_changed = root_x[:, 2] != candidate_x[:, 2]
    encoded_bound_changed = encoded_lb_changed | encoded_ub_changed
    any_feature_changed = np.any(root_x != candidate_x, axis=1)
    non_bound_feature_changed = np.any(
        root_x[:, [0, 3, 4, 5, 6]] != candidate_x[:, [0, 3, 4, 5, 6]],
        axis=1,
    )
    type_changed = root_types != candidate_types
    lost_indices = np.flatnonzero(raw_changed & ~encoded_bound_changed)
    unexpected_indices = np.flatnonzero(~raw_changed & encoded_bound_changed)

    details = []
    for index in np.flatnonzero(raw_changed)[:MAX_CHANGE_DETAILS]:
        details.append(
            {
                "variable": root_names[int(index)],
                "root_lb": _bound_token(root_lb[index]),
                "root_ub": _bound_token(root_ub[index]),
                "candidate_lb": _bound_token(candidate_lb[index]),
                "candidate_ub": _bound_token(candidate_ub[index]),
                "root_encoded_lb": float(root_x[index, 1]),
                "root_encoded_ub": float(root_x[index, 2]),
                "candidate_encoded_lb": float(candidate_x[index, 1]),
                "candidate_encoded_ub": float(candidate_x[index, 2]),
            }
        )

    root_formulation = root["formulation_fingerprints"]
    candidate_formulation = candidate["formulation_fingerprints"]
    root_graph = root["graph_fingerprints"]
    candidate_graph = candidate["graph_fingerprints"]
    matrix_same = (
        root_formulation["matrix_sha256"]
        == candidate_formulation["matrix_sha256"]
    )
    objective_same = (
        root_formulation["objective_sha256"]
        == candidate_formulation["objective_sha256"]
    )
    topology_same = (
        root_graph["topology_sha256"] == candidate_graph["topology_sha256"]
    )
    constraint_features_same = (
        root_graph["constraint_features_sha256"]
        == candidate_graph["constraint_features_sha256"]
    )
    node_features_distinct = (
        root_graph["variable_features_sha256"]
        != candidate_graph["variable_features_sha256"]
    )
    graph_distinct = (
        root_graph["complete_graph_sha256"]
        != candidate_graph["complete_graph_sha256"]
    )

    if int(np.sum(raw_changed)) == 0:
        reason = "no_raw_domain_difference"
    elif not matrix_same or not objective_same:
        reason = "candidate_is_not_domain_only"
    elif not topology_same or not constraint_features_same:
        reason = "graph_structure_changed_for_domain_only_candidate"
    elif bool(np.any(type_changed)) or bool(np.any(non_bound_feature_changed)):
        reason = "non_domain_variable_features_changed"
    elif len(lost_indices):
        reason = "raw_domain_change_lost_in_graph_encoding"
    elif len(unexpected_indices):
        reason = "graph_bound_change_without_raw_domain_change"
    elif not node_features_distinct or not graph_distinct:
        reason = "graph_does_not_observe_domain_difference"
    else:
        reason = "domain_difference_observed_in_graph_features"
    gate_status = (
        "passed" if reason == "domain_difference_observed_in_graph_features" else "failed"
    )
    return {
        "file_name": candidate.get("file_name"),
        "artifact_sha256": candidate.get("artifact_sha256"),
        "gate_status": gate_status,
        "reason_code": reason,
        "classification": "domain_distinct_same_matrix",
        "variable_names_match": names_match,
        "variable_count": len(root_names),
        "raw_bound_change_count": int(np.sum(raw_changed)),
        "raw_bound_coordinate_change_count": int(np.sum(lb_changed) + np.sum(ub_changed)),
        "encoded_bound_change_count": int(np.sum(encoded_bound_changed)),
        "encoded_bound_coordinate_change_count": int(
            np.sum(encoded_lb_changed) + np.sum(encoded_ub_changed)
        ),
        "changed_variable_feature_count": int(np.sum(any_feature_changed)),
        "non_bound_feature_change_count": int(np.sum(non_bound_feature_changed)),
        "variable_type_change_count": int(np.sum(type_changed)),
        "lost_raw_domain_change_count": len(lost_indices),
        "unexpected_encoded_bound_change_count": len(unexpected_indices),
        "change_details_truncated": int(np.sum(raw_changed)) > MAX_CHANGE_DETAILS,
        "change_details": details,
        "matrix_same_as_root": matrix_same,
        "objective_same_as_root": objective_same,
        "topology_same_as_root": topology_same,
        "constraint_features_same_as_root": constraint_features_same,
        "node_features_distinct_from_root": node_features_distinct,
        "graph_distinct_from_root": graph_distinct,
        "candidate_signature": candidate.get("signature"),
        "formulation_fingerprints": candidate_formulation,
        "graph_fingerprints": candidate_graph,
        "dataset_eligible": False,
        "label_eligible": False,
    }


def run_audit(plan: GraphAuditPlan) -> dict[str, Any]:
    root_snapshot = _extract_graph_snapshot(plan.root_mip)
    candidates = []
    for path in plan.node_mips:
        try:
            snapshot = _extract_graph_snapshot(path)
            candidates.append(compare_graph_snapshots(root_snapshot, snapshot))
        except Exception as error:
            candidates.append(
                {
                    "file_name": path.name,
                    "artifact_sha256": sha256_file(path),
                    "gate_status": "failed",
                    "reason_code": "candidate_graph_extraction_failed",
                    "error_type": type(error).__name__,
                    "dataset_eligible": False,
                    "label_eligible": False,
                }
            )
    passed = sum(item["gate_status"] == "passed" for item in candidates)
    all_passed = passed == len(candidates) and bool(candidates)
    report = {
        **plan.to_summary(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "gate_status": "passed" if all_passed else "failed",
        "root_graph": _public_snapshot(root_snapshot),
        "summary": {
            "candidates_audited": len(candidates),
            "candidates_passed": passed,
            "candidates_failed": len(candidates) - passed,
            "raw_bound_changes": sum(
                int(item.get("raw_bound_change_count", 0)) for item in candidates
            ),
            "encoded_bound_changes": sum(
                int(item.get("encoded_bound_change_count", 0)) for item in candidates
            ),
            "lost_raw_domain_changes": sum(
                int(item.get("lost_raw_domain_change_count", 0))
                for item in candidates
            ),
            "unique_graphs": len(
                {
                    item.get("graph_fingerprints", {}).get("complete_graph_sha256")
                    for item in candidates
                    if item.get("gate_status") == "passed"
                }
            ),
        },
        "decision": {
            "graph_observability_proven": all_passed,
            "all_raw_domain_changes_preserved": all_passed
            and all(
                int(item.get("lost_raw_domain_change_count", 0)) == 0
                for item in candidates
            ),
            "dataset_eligible": False,
            "label_eligible": False,
            "next_gate": (
                "independent_derived_mip_label_validation"
                if all_passed
                else "stop_or_correct_graph_observability"
            ),
            "reason_code": (
                "all_domain_variants_observable_pending_review"
                if all_passed
                else "one_or_more_domain_variants_not_observable"
            ),
        },
    }
    _write_jsonl(plan.output_dir / PER_CANDIDATE_NAME, candidates)
    return report


def failure_report(plan: GraphAuditPlan, error: Exception) -> dict[str, Any]:
    return {
        **plan.to_summary(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": False,
        "gate_status": "failed",
        "failure": {
            "error_type": type(error).__name__,
            "reason_code": "graph_observability_probe_failed",
        },
        "decision": {
            "graph_observability_proven": False,
            "dataset_eligible": False,
            "label_eligible": False,
            "next_gate": "stop_or_correct_graph_observability",
            "reason_code": "probe_failed_before_graph_comparison",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit graph observability of SCIP domain-only node MIPs."
    )
    parser.add_argument("--root_mip", type=Path, required=True)
    parser.add_argument("--node_mips", nargs="+", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = build_audit_plan(
        root_mip=args.root_mip,
        node_mips=args.node_mips,
        output_dir=args.output_dir,
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
        f"contract={plan.contract_sha256} | node_mips={len(plan.node_mips)} | "
        "dataset_eligible=false | label_eligible=false"
    )
    print(f"[INFO] Plan: {plan_path}")
    if args.dry_run:
        return 0
    try:
        report = run_audit(plan)
    except Exception as error:
        report = failure_report(plan, error)
        _write_json(report_path, report)
        print(f"[INFO] Failure report: {report_path}")
        raise
    _write_json(report_path, report)
    print(
        "[INFO] "
        f"gate={report['gate_status']} | "
        f"passed={report['summary']['candidates_passed']}/"
        f"{report['summary']['candidates_audited']} | "
        f"lost={report['summary']['lost_raw_domain_changes']}"
    )
    print(f"[INFO] Report: {report_path}")
    if report["gate_status"] != "passed":
        raise GraphObservabilityAuditError(
            "graph observability gate failed; inspect per-candidate audit"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
