"""Invented tiny evidence for contract tests; never research observations."""

import copy
from functools import lru_cache
from pathlib import Path

from cfl_gnn.mvp3 import CONTRACT_VERSION
from cfl_gnn.mvp3.contract import CLOCKS, digest, load_bundle
from cfl_gnn.mvp3.identity import model_identity
from cfl_gnn.mvp3.records import pairing_identity, run_identity

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def bundle():
    return load_bundle(ROOT / "configs/mvp3/v1")


def quantity(value, reason=None):
    return {"value": value, "missing_reason": reason}


def clock(name="native_runtime"):
    return {"name": name, "origin": CLOCKS[name], "unit": "seconds"}


def model():
    return {
        "declared_sense": "MAXIMIZE",
        "effective_sense": "MINIMIZE",
        "objective_constant": 0,
        "variables": [
            {"name": f"x{index}", "domain": "B", "lower": 0, "upper": 1, "objective": 1}
            for index in range(20)
        ],
        "rows": [
            {
                "name": "capacity",
                "sense": ">=",
                "rhs": 20,
                "terms": [[index, 1] for index in range(20)],
            }
        ],
    }


def audit(model_sha256, vector_sha256, *, continuous=False):
    return {
        "model_sha256": model_sha256,
        "vector_sha256": vector_sha256,
        "status": "qualified",
        "row_max_violation": quantity(0),
        "bound_max_violation": quantity(0),
        "integrality_max_violation": quantity(None, "continuous_relaxation")
        if continuous
        else quantity(0),
        "objective_residual": quantity(0),
        "tolerances": {
            "row": 1e-6,
            "bound": 1e-6,
            "integrality": 1e-5,
            "objective": 1e-8,
        },
    }


def run(method="G", *, parent_id=None, stage="evaluation", attempt="synthetic-1"):
    data = bundle()
    parent = (
        next(
            row for row in data["parents"]["parents"] if row["original_id"] == parent_id
        )
        if parent_id
        else next(row for row in data["parents"]["parents"] if row["role"] == "test")
    )
    input_row = next(
        row
        for row in data["catalogue"]["parents"]
        if row["original_id"] == parent["original_id"]
    )
    mathematical = model_identity(model())
    vector = digest([1] * 20)
    defaults = {**data["contract"]["solver"]["profiles"]["incumbent"], "Cuts": -1}
    record = {
        "schema_version": CONTRACT_VERSION,
        "kind": "run",
        "key": {
            "parent_id": parent["original_id"],
            "stage": stage,
            "method": method if stage == "evaluation" else None,
            "seed": 42,
            "attempt": attempt,
        },
        "run_sha256": "0" * 64,
        "model_sha256": mathematical["model_sha256"],
        "source_commit": "1" * 40,
        "environment_sha256": "2" * 64,
        "audit_policy_sha256": digest(
            audit(mathematical["model_sha256"], vector)["tolerances"]
        ),
        "input_sha256": input_row["stored_sha256"],
        "solver_version": "14.0.0",
        "native_defaults": defaults,
        "native_defaults_sha256": digest(defaults),
        "native_defaults_receipt_sha256": "3" * 64,
        "effective_parameters": {
            **defaults,
            **data["contract"]["solver"]["profiles"][stage],
        },
        "resources": copy.deepcopy(
            data["contract"]["resources"]["solver_profiles"][parent["family"]]
        ),
        "mathematical_identity": mathematical,
        "native_status": quantity("OPTIMAL"),
        "outcome": "completed",
        "native_Work": quantity(1.5),
        "timings": [
            {"clock": clock(name), "elapsed": quantity(300)} for name in CLOCKS
        ],
        "final": {
            "primal": quantity(20),
            "dual": quantity(20),
            "gap": quantity(0),
            "vector_sha256": vector,
            "vector_missing_reason": None,
            "audit": audit(mathematical["model_sha256"], vector),
        },
        "supervision": {
            "native_thread_count": quantity(32),
            "affinity_logical_count": quantity(64),
            "peak_process_bytes": quantity(1000000),
            "peak_job_bytes": quantity(2000000),
            "native_thread_lines_sha256": "4" * 64,
            "affinity_mapping_sha256": "5" * 64,
            "scheduler_record_sha256": "6" * 64,
            "termination_cause": "native_optimal",
        },
    }
    record["run_sha256"] = run_identity(record)
    return record


def binding(source, kind):
    return {
        name: copy.deepcopy(source[name])
        for name in ("schema_version", "key", "run_sha256", "model_sha256")
    } | {"kind": kind}


def event(source, seconds=120, *, name="native_runtime", ordinal=1):
    record = binding(source, "event")
    vector = source["final"]["vector_sha256"]
    record.update(
        {
            "event_ordinal": ordinal,
            "where": "MIPSOL",
            "clock": clock(name),
            "elapsed_seconds": seconds,
            "primal": quantity(20),
            "dual": quantity(18),
            "gap": quantity(0.1),
            "nodes": quantity(1),
            "native_Work": quantity(0.5),
            "candidate_vector_sha256": vector,
            "candidate_audit": audit(source["model_sha256"], vector),
        }
    )
    return record


def target(source, source_event=None, *, outcome="attained"):
    if source_event is None:
        source_event = event(source)
    record = binding(source, "target")
    record.update(
        {
            "gap_target": 0.1,
            "clock": copy.deepcopy(source_event["clock"]),
            "pairing_sha256": pairing_identity(source),
            "outcome": outcome,
            "attainment_seconds": quantity(source_event["elapsed_seconds"])
            if outcome == "attained"
            else quantity(None, outcome),
            "followup_seconds": 300,
            "observed_gap": copy.deepcopy(source_event["gap"]),
            "source_event_sha256": digest(source_event)
            if outcome == "attained"
            else None,
            "candidate_vector_sha256": source_event["candidate_vector_sha256"],
            "candidate_audit": copy.deepcopy(source_event["candidate_audit"]),
        }
    )
    return record


def root(source):
    record = binding(source, "root")
    vector = digest([1] * 20)
    record.update(
        {
            "variable_order_sha256": source["mathematical_identity"][
                "variable_order_sha256"
            ],
            "vector_sha256": vector,
            "variable_count": 20,
            "captured_count": 20,
            "event": {
                "where": "MIPNODE",
                "status": "OPTIMAL",
                "node_count": 0,
                "ordinal": 1,
                "cut_state": "pre_cut",
                "cut_pass": 0,
            },
            "audit": audit(source["model_sha256"], vector, continuous=True),
        }
    )
    return record


def label(source, role):
    record = binding(source, "label")
    record.update(
        {
            "variable_order_sha256": source["mathematical_identity"][
                "variable_order_sha256"
            ],
            "vector_sha256": source["final"]["vector_sha256"],
            "origin": "DIRECT",
            "conditional_release_sha256": None,
            "equivalence_audit_sha256": None,
            "gap": 0,
            "tier": "terminal_target",
            "parent_role": role,
            "admissible_primary_label": role != "transfer_only",
            "audit": copy.deepcopy(source["final"]["audit"]),
        }
    )
    return record


def start(source, size=2):
    record = binding(source, "start")
    method = source["key"]["method"]
    support = [
        {
            "position": index,
            "variable_name": f"x{index}",
            "value": index % 2,
            "lower_bound": 0,
            "upper_bound": 1,
        }
        for index in range(0 if method == "B" else size)
    ]
    assignments = [
        {key: item[key] for key in ("position", "variable_name", "value")}
        for item in support
    ]
    record.update(
        {
            "variable_order_sha256": source["mathematical_identity"][
                "variable_order_sha256"
            ],
            "original_variable_count": 20,
            "binary_count": 20,
            "root_artifact_sha256": None if method == "B" else "7" * 64,
            "predictor_sha256": "8" * 64 if method == "G" else None,
            "frozen_policy_sha256": None if method == "B" else "9" * 64,
            "support": support,
            "support_sha256": digest(assignments),
            "ones_count": sum(item["value"] for item in support),
            "unselected_coordinates": "UNDEFINED",
            "original_model_preserved": True,
        }
    )
    return record
