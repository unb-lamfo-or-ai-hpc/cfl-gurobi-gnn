"""Frozen fresh 60-cell CPU12h proposal, reusing reviewed PR86 preparation."""

import base64
import copy
import re
from functools import lru_cache

import build_pr88_methodology as methodology
import pr86_main_first_group as previous
import pr89_cpu_temporal as temporal
from pr89_cpu_temporal import Recorder  # noqa: F401

require, read, parsed, write = (
    previous.require,
    previous.read,
    previous.parsed,
    previous.write,
)
encoded, digest = previous.encoded, previous.digest
ROOT = previous.ROOT
PROTOCOL = "fresh_cpu12h_seed42_sixty_single_solve_jobs_v1"
BUDGET = {
    "jobs": 60,
    "optimization_calls": 60,
    "solver_hours": 720,
    "serial_reserved_hours": 780,
    "physical_solver_core_hours": 4464,
    "physical_reserved_core_hours": 4836,
    "gpus": 0,
    "memory_mib_per_job": 65536,
}
CHILD_DEADLINE = 45000  # 30min loading/audit/export margin beyond 12h optimize.
JOB_WALL = 46800  # another30min for parent validation/collection/teardown.
THRESHOLDS = temporal.THRESHOLDS


@lru_cache(maxsize=1)
def baseline_parameters():
    raw = read(ROOT / "docs/evidence/pr86/job3522/public_return.json")
    require(
        digest(raw)
        == "dd1a553b453289b23dbed3d52bd4bd7e0ac93eb2b4283597b788e406fcab6825",
        "historical_parameter_source",
    )
    archive = previous.executor.existing.review.flow.meta.strict_json(raw)
    member = archive["members"]["run/attempt-0/child.json"]
    decoded = base64.b64decode(member["base64"], validate=True)
    require(digest(decoded) == member["sha256"], "historical_parameter_member")
    return previous.executor.existing.review.flow.meta.strict_json(decoded)["result"][
        "parameters"
    ]


def parameters(cell):
    old = {**cell, "time_limit_seconds": 3600}
    requested = previous.executor.metered.parameters(old)
    require(
        cell["seed"] == 42
        and cell["parent"]
        in {
            "CFL_medium_instance_0",
            "CFL_medium_instance_4",
            "CFL_medium_instance_7",
            "CFL_medium_instance_12",
        },
        "cpu12h_parent_seed",
    )
    require(cell["time_limit_seconds"] == 43200, "cpu12h_limit")
    return {**baseline_parameters(), **requested, "TimeLimit": 43200}


def plan(commit):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "source_commit")
    original, old_cells = previous.executor.proposal.build()
    matrix, _ = methodology.cpu_package()
    bases, cells = {}, []
    for proposed in matrix:
        parent, cap, method = (
            proposed["parent"],
            proposed["threads"],
            proposed["method"],
        )
        if parent not in bases:
            index = next(
                i
                for i, g in enumerate(original["groups"])
                if g["parent"] == parent and g["seed"] == 42
            )
            bases[parent] = previous.plan_for_group(commit, index)
        cell = copy.deepcopy(
            next(
                c
                for c in old_cells
                if c["parent"] == parent
                and c["threads"] == cap
                and c["seed"] == 42
                and c["method"] == method
            )
        )
        cell["time_limit_seconds"] = 43200
        parameters(cell)
        cells.append(cell)
    return {
        "protocol_id": PROTOCOL,
        "source_commit": commit,
        "author_decision_sha256": digest(
            read(ROOT / "docs/evidence/pr89/cpu_author_decision.json")
        ),
        "source_sha256_lf": previous.executor.existing.dependencies(),
        "formulation_contract": previous.executor.FORMULATION_CONTRACT,
        "cells": cells,
        "parents": bases,
        "budget": BUDGET,
        "child_deadline_seconds": CHILD_DEADLINE,
        "job_wall_seconds": JOB_WALL,
        "resource_budget_approved": False,
        "automatic_retry": False,
        "resume": False,
        "new_preparation_calls": 0,
        "numerical_scope_by_alias": {
            "M0": "original_tolerance_review_required",
            "M4": "sensitive_no_exact_optimum_or_certified_speedup",
            "M7": "original_tolerance_review_required",
            "M12": "sensitive_no_exact_optimum_or_certified_speedup",
        },
        "scientific_reporting_eligible": False,
    }


def validate_result(cell, value):
    # Reuse the complete old result validator with ONLY the admitted time limit
    # normalized. The original value and parameter hash are never modified.
    normalized = copy.deepcopy(value)
    normalized["parameters"]["TimeLimit"] = 3600
    previous.executor.metered.validate_result(
        {**cell, "time_limit_seconds": 3600}, normalized
    )
    require(
        all(value["parameters"][k] == v for k, v in parameters(cell).items()),
        "cpu12h_parameters",
    )
    from cfl_gnn.graph.gurobi_graph_artifact import canonical_sha256

    require(
        value["parameter_sha256"] == canonical_sha256(value["parameters"]),
        "parameter_hash",
    )
    temporal.validate(value["temporal_evidence"])
    require(
        value["gate_status"] == "passed" and not value["callback_errors"],
        "child_validation",
    )
    require(value["solve"]["solve_status_code"] != 17, "solver_soft_memory_stop")
    require(
        value["solve"]["solve_status_code"] in {2, 3, 8, 9, 10, 16},
        "unexpected_solver_stop",
    )
    solve = value["solve"]
    if solve["feasible_solution"]:
        require(
            value["independent_feasibility"]["valid"] is True, "independent_feasibility"
        )
    terminal = value["temporal_evidence"]["terminal"]
    require(
        terminal["primal"] == solve["primal"] and terminal["dual"] == solve["dual"],
        "terminal_result_parity",
    )
    require(value["scientific_reporting_eligible"] is False, "scientific_scope")


def authorization(frozen, decision):
    require(
        isinstance(decision, str) and 1 <= len(decision) <= 200, "decision_reference"
    )
    return {
        "protocol_id": PROTOCOL,
        "plan_sha256": digest(encoded(frozen)),
        "source_commit": frozen["source_commit"],
        "author_decision_sha256": frozen["author_decision_sha256"],
        "explicit_user_authorization": True,
        "decision_reference": decision,
        "budget": BUDGET,
        "m4_m12_numerical_limits_preserved": True,
        "calendar_ceiling_32_5_days_plus_queues_acknowledged": True,
        "automatic_retry": False,
    }


def validate_authorization(frozen, value):
    require(
        value == authorization(frozen, value.get("decision_reference")),
        "separate_specific_cpu_authorization_required",
    )
