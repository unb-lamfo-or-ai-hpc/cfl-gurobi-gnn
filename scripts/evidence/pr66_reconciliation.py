"""Explicit, conservative qualification primitives for historical CFL evidence.

These functions do not discover private sources, optimize, or certify an entire
cohort. Each caller must provide hash-bound provenance and complete coverage.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import math
import re
import struct

from collect_computational_ledger import HEX, identity


def provenance(sha):
    if not isinstance(sha, str) or not HEX.fullmatch(sha):
        raise ValueError("qualified_source_sha256_required")
    return sha


def finite(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError("finite_numeric_value_required")
    return value


def artifact_aliases(observations):
    """Same report bytes imply artifact aliases, not equivalent solver attempts."""
    groups, seen = {}, set()
    for row in observations:
        ref = provenance(row["artifact_id"])
        sha = provenance(row["report_sha256"])
        if ref in seen:
            raise ValueError("duplicate_artifact_identity")
        seen.add(ref)
        groups.setdefault(sha, []).append(ref)
    return [
        {
            "report_sha256": sha,
            "artifact_ids": sorted(refs),
            "execution_identity_qualified": False,
        }
        for sha, refs in sorted(groups.items())
    ]


def adapt_parent_report(value, report_sha, solver):
    """Named v1 adapter. Unsupported legacy schemas remain unsupported, not zero."""
    provenance(report_sha)
    if solver not in {"gurobi", "scip"}:
        raise ValueError("unsupported_solver")
    parent, solve = value.get("parent"), value.get("solve")
    if not isinstance(parent, dict) or not isinstance(solve, dict):
        raise ValueError("unsupported_parent_solve_v1_schema")
    name = identity(parent.get("source_instance_id"))
    if not name:
        raise ValueError("invalid_parent_identity")
    sense = solve.get("objective_sense")
    sense = sense.upper() if isinstance(sense, str) else None
    if sense not in {None, "MINIMIZE", "MAXIMIZE"}:
        raise ValueError("unsupported_objective_sense")
    return {
        "adapter": "parent_solve_v1",
        "report_sha256": report_sha,
        "source_instance_id": name,
        "solver": solver,
        "original_lp_sha256": provenance(parent["sha256"]),
        "effective_objective_sense": sense,
        "execution_identity": None,
        "unique_feasible_incumbents": None,
    }


def seconds(text):
    """Slurm TotalCPU duration, including days and fractional seconds."""
    if text in {None, ""}:
        return None
    match = re.fullmatch(r"(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError("unsupported_slurm_cpu_duration")
    days, hours, minutes, sec = match.groups()
    if int(minutes) >= 60 or float(sec) >= 60:
        raise ValueError("invalid_slurm_cpu_duration")
    return (
        int(days or 0) * 86400 + int(hours or 0) * 3600 + int(minutes) * 60 + float(sec)
    )


def attributed_cost(jobs, edges):
    """Count each concrete allocation once, even if it contains several solves."""
    allocations = {}
    for row in jobs:
        job = row["job_id"]
        if not re.fullmatch(r"\d+(?:_\d+)?(?:\.[a-zA-Z0-9]+)?", job):
            raise ValueError("concrete_job_id_required")
        if "." in job:
            continue
        if job in allocations:
            raise ValueError("duplicate_allocation")
        allocations[job] = row
    matched, seen = set(), set()
    for edge in edges:
        provenance(edge["receipt_sha256"])
        key = (edge["attempt_id"], edge["job_id"])
        if key in seen:
            raise ValueError("duplicate_attempt_job_edge")
        seen.add(key)
        if edge["join_state"] == "matched":
            if edge["job_id"] not in allocations:
                raise ValueError("matched_allocation_missing")
            matched.add(edge["job_id"])
        elif edge["join_state"] not in {"ambiguous", "unmatched"}:
            raise ValueError("invalid_job_join_state")
    result = []
    for job, row in sorted(allocations.items()):
        cpus = finite(row["allocated_cpus"])
        elapsed = finite(row["elapsed_seconds"])
        if cpus <= 0 or int(cpus) != cpus or elapsed < 0:
            raise ValueError("invalid_allocation_resources")
        cpu = seconds(row.get("reported_total_cpu_time"))
        result.append(
            {
                "job_id": job,
                "attributed_to_cfl": job in matched,
                "allocated_cpu_hours": cpus * elapsed / 3600,
                "reported_cpu_hours": cpu / 3600 if cpu is not None else None,
                "phase_costs_qualified": False,
            }
        )
    return result


def variable_order_sha(names):
    if (
        not names
        or len(set(names)) != len(names)
        or not all(isinstance(n, str) for n in names)
    ):
        raise ValueError("unique_complete_variable_order_required")
    return hashlib.sha256("\n".join(names).encode()).hexdigest()


def audit_vector(model, vector, expected_order_sha):
    """Evaluate a complete original linear-model vector without solver calls.

    model is a qualified adapter projection, not a pickle/checkpoint. Constraints
    are sparse (index, coefficient) pairs. Tolerances apply to unrounded values;
    uniqueness is exact full-vector float64 identity, not a binary projection.
    """
    provenance(model["original_lp_sha256"])
    provenance(model["adapter_source_sha256"])
    if model["effective_objective_sense"] != "MINIMIZE":
        raise ValueError("effective_minimization_not_qualified")
    names = model["variable_names"]
    if variable_order_sha(names) != provenance(expected_order_sha):
        raise ValueError("variable_order_mismatch")
    n = len(names)
    values = [finite(x) for x in vector]
    if len(values) != n or any(
        len(model[k]) != n for k in ("lb", "ub", "types", "objective")
    ):
        raise ValueError("incomplete_vector_or_model")
    feasibility_tol = finite(model["feasibility_tol"])
    integer_tol = finite(model["integer_tol"])
    if not 0 < feasibility_tol <= 1e-4 or not 0 < integer_tol <= 1e-4:
        raise ValueError("invalid_frozen_tolerances")
    violations = set()
    for i, value in enumerate(values):
        lb, ub = model["lb"][i], model["ub"][i]
        if math.isnan(lb) or math.isnan(ub) or lb > ub:
            raise ValueError("invalid_variable_bounds")
        kind = model["types"][i]
        if kind not in {"B", "I", "C"}:
            raise ValueError("unsupported_variable_domain")
        if value < lb - feasibility_tol or value > ub + feasibility_tol:
            violations.add("bounds")
        if kind in {"B", "I"} and abs(value - round(value)) > integer_tol:
            violations.add("integrality")
        if kind == "B" and (value < -integer_tol or value > 1 + integer_tol):
            violations.add("binary_domain")
    for constraint in model["constraints"]:
        seen = set()
        terms = []
        for index, coefficient in constraint["terms"]:
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or not 0 <= index < n
                or index in seen
            ):
                raise ValueError("invalid_sparse_constraint_mapping")
            seen.add(index)
            terms.append(values[index] * finite(coefficient))
        residual = math.fsum(terms) - finite(constraint["rhs"])
        sense = constraint["sense"]
        if sense not in {"<", ">", "="}:
            raise ValueError("invalid_constraint_sense")
        if (
            (sense == "<" and residual > feasibility_tol)
            or (sense == ">" and residual < -feasibility_tol)
            or (sense == "=" and abs(residual) > feasibility_tol)
        ):
            violations.add("constraints")
    objective = math.fsum(
        x * finite(c) for x, c in zip(values, model["objective"])
    ) + finite(model["objective_constant"])
    finite(objective)
    fingerprint = hashlib.sha256(
        b"".join(struct.pack("<d", 0.0 if x == 0 else x) for x in values)
    ).hexdigest()
    return {
        "feasible_at_declared_tolerances": not violations,
        "violations": sorted(violations),
        "objective": objective,
        "full_vector_sha256": fingerprint,
        "gap_qualified": None,
    }


def derivative_usage(record):
    """Generation/plan membership are not proof of actual optimizer consumption."""
    provenance(record["lineage_source_sha256"])
    planned = record.get("planned_role")
    parent_role = record.get("parent_role")
    if planned not in {None, "train", "validation", "test"} or parent_role not in {
        "train",
        "validation",
        "test",
    }:
        raise ValueError("invalid_lineage_roles")
    if planned is not None and planned != parent_role:
        raise ValueError("derivative_parent_role_leakage")
    event = record.get("fitting_event")
    if event is None:
        return {
            "fitting_consumption": "unknown",
            "complete_training_usage_verified": False,
        }
    provenance(event["receipt_sha256"])
    provenance(event["dataset_sha256"])
    if (
        parent_role != "train"
        or planned != "train"
        or event["derivative_id"] != record["derivative_id"]
    ):
        raise ValueError("fitting_identity_or_role_mismatch")
    updates = finite(event["optimizer_updates_observed"])
    if updates <= 0 or int(updates) != updates:
        raise ValueError("positive_optimizer_update_evidence_required")
    return {
        "fitting_consumption": "observed_in_explicit_update_receipt",
        "complete_training_usage_verified": False,
    }
