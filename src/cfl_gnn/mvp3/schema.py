"""Public JSON Schema 2020-12 for MVP3 observations, with local references only."""

from . import CONTRACT_VERSION


def obj(properties, required=None, **extra):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
        **extra,
    }


def ref(name):
    return {"$ref": f"#/$defs/{name}"}


def evidence_schema():
    text = {"type": "string", "minLength": 1}
    integer = {"type": "integer", "minimum": 0}
    positive = {"type": "integer", "minimum": 1}
    number = {"type": "number"}
    nonnegative = {"type": "number", "minimum": 0}
    nullable_sha = {"anyOf": [ref("sha256"), {"type": "null"}]}
    quantity = obj(
        {
            "value": {"type": ["number", "null"]},
            "missing_reason": {"type": ["string", "null"]},
        },
        allOf=[
            {
                "if": {"properties": {"value": {"type": "null"}}},
                "then": {"properties": {"missing_reason": text}},
                "else": {"properties": {"missing_reason": {"type": "null"}}},
            }
        ],
    )
    definitions = {
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "sha1": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
        "quantity": quantity,
        "key": obj(
            {
                "parent_id": {
                    "type": "string",
                    "pattern": "^CFL_(easy|medium|hard)_instance_[0-9]+$",
                },
                "stage": {"enum": ["root_relaxation", "incumbent", "evaluation"]},
                "method": {"enum": [None, "B", "R", "G"]},
                "seed": {"const": 42},
                "attempt": {
                    "type": "string",
                    "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
                },
            }
        ),
        "clock": obj(
            {
                "name": {
                    "enum": [
                        "native_runtime",
                        "worker_elapsed",
                        "end_to_end",
                        "reuse_elapsed",
                    ]
                },
                "origin": {
                    "enum": [
                        "optimize_entry",
                        "worker_entry",
                        "pipeline_entry",
                        "scenario_entry",
                    ]
                },
                "unit": {"const": "seconds"},
            }
        ),
        "audit": obj(
            {
                "model_sha256": ref("sha256"),
                "vector_sha256": ref("sha256"),
                "status": {"enum": ["qualified", "unqualified"]},
                "row_max_violation": ref("quantity"),
                "bound_max_violation": ref("quantity"),
                "integrality_max_violation": ref("quantity"),
                "objective_residual": ref("quantity"),
                "tolerances": obj(
                    {
                        key: nonnegative
                        for key in ("row", "bound", "integrality", "objective")
                    }
                ),
            }
        ),
        "resources": obj(
            {
                "node_class": {"enum": ["intel-256", "intel-512"]},
                "tasks": {"const": 1},
                "logical_CPUs": {"const": 64},
                "physical_cores": {"const": 32},
                "memory_GiB": {"enum": [192, 384]},
                "exclusive": {"const": True},
                "requested_GPUs": {"const": 0},
                "job_limit_seconds": {"const": 43200},
            }
        ),
        "timing": obj({"clock": ref("clock"), "elapsed": ref("quantity")}),
        "root_event": obj(
            {
                "where": {"const": "MIPNODE"},
                "status": {"const": "OPTIMAL"},
                "node_count": {"const": 0},
                "ordinal": positive,
                "cut_state": {"enum": ["pre_cut", "later_cut_pass"]},
                "cut_pass": integer,
            }
        ),
        "model_identity": obj(
            {
                "model_sha256": ref("sha256"),
                "variable_order_sha256": ref("sha256"),
                "declared_sense": {"enum": ["MINIMIZE", "MAXIMIZE"]},
                "effective_sense": {"const": "MINIMIZE"},
                "variables": positive,
                "rows": integer,
                "nonzeros": integer,
                "objective_constant": number,
            }
        ),
    }
    binding = {
        "schema_version": {"const": CONTRACT_VERSION},
        "key": ref("key"),
        "run_sha256": ref("sha256"),
        "model_sha256": ref("sha256"),
    }

    def record(kind, fields):
        return obj({"kind": {"const": kind}, **binding, **fields})

    definitions["run"] = record(
        "run",
        {
            "source_commit": ref("sha1"),
            "environment_sha256": ref("sha256"),
            "audit_policy_sha256": ref("sha256"),
            "input_sha256": ref("sha256"),
            "solver_version": {"const": "14.0.0"},
            "native_defaults_sha256": ref("sha256"),
            "native_defaults_receipt_sha256": ref("sha256"),
            "native_defaults": {
                "type": "object",
                "additionalProperties": {"type": ["number", "string", "boolean"]},
            },
            "effective_parameters": {
                "type": "object",
                "additionalProperties": {"type": ["number", "string", "boolean"]},
            },
            "resources": ref("resources"),
            "mathematical_identity": ref("model_identity"),
            "native_status": obj(
                {
                    "value": {"type": ["string", "null"]},
                    "missing_reason": {"type": ["string", "null"]},
                }
            ),
            "outcome": {
                "enum": [
                    "completed",
                    "feature_captured",
                    "time_limit",
                    "memory_termination",
                    "numeric_failure",
                    "callback_failure",
                    "infrastructure_interruption",
                    "no_incumbent",
                    "feature_unavailable",
                ]
            },
            "native_Work": ref("quantity"),
            "timings": {"type": "array", "items": ref("timing"), "minItems": 1},
            "final": obj(
                {
                    **{name: ref("quantity") for name in ("primal", "dual", "gap")},
                    "vector_sha256": nullable_sha,
                    "vector_missing_reason": {"type": ["string", "null"]},
                    "audit": {"anyOf": [ref("audit"), {"type": "null"}]},
                }
            ),
            "supervision": obj(
                {
                    "native_thread_count": ref("quantity"),
                    "affinity_logical_count": ref("quantity"),
                    "peak_process_bytes": ref("quantity"),
                    "peak_job_bytes": ref("quantity"),
                    "native_thread_lines_sha256": nullable_sha,
                    "affinity_mapping_sha256": nullable_sha,
                    "scheduler_record_sha256": nullable_sha,
                    "termination_cause": text,
                }
            ),
        },
    )
    definitions["root"] = record(
        "root",
        {
            "variable_order_sha256": ref("sha256"),
            "vector_sha256": ref("sha256"),
            "variable_count": positive,
            "captured_count": positive,
            "event": ref("root_event"),
            "audit": ref("audit"),
        },
    )
    definitions["label"] = record(
        "label",
        {
            "variable_order_sha256": ref("sha256"),
            "vector_sha256": ref("sha256"),
            "origin": {"enum": ["DIRECT", "BENDERS"]},
            "conditional_release_sha256": nullable_sha,
            "equivalence_audit_sha256": nullable_sha,
            "gap": nonnegative,
            "tier": {"enum": ["terminal_target", "intermediate"]},
            "parent_role": {"enum": ["train", "validation", "test", "transfer_only"]},
            "admissible_primary_label": {"type": "boolean"},
            "audit": ref("audit"),
        },
    )
    definitions["start"] = record(
        "start",
        {
            "variable_order_sha256": ref("sha256"),
            "original_variable_count": positive,
            "binary_count": integer,
            "root_artifact_sha256": nullable_sha,
            "predictor_sha256": nullable_sha,
            "frozen_policy_sha256": nullable_sha,
            "support": {
                "type": "array",
                "items": obj(
                    {
                        "position": integer,
                        "variable_name": text,
                        "value": {"enum": [0, 1]},
                        "lower_bound": number,
                        "upper_bound": number,
                    }
                ),
            },
            "support_sha256": ref("sha256"),
            "ones_count": integer,
            "unselected_coordinates": {"const": "UNDEFINED"},
            "original_model_preserved": {"const": True},
        },
    )
    definitions["event"] = record(
        "event",
        {
            "event_ordinal": positive,
            "where": {"enum": ["MIP", "MIPSOL", "MIPNODE"]},
            "clock": ref("clock"),
            "elapsed_seconds": nonnegative,
            "primal": ref("quantity"),
            "dual": ref("quantity"),
            "gap": ref("quantity"),
            "nodes": ref("quantity"),
            "native_Work": ref("quantity"),
            "candidate_vector_sha256": nullable_sha,
            "candidate_audit": {"anyOf": [ref("audit"), {"type": "null"}]},
        },
    )
    definitions["target"] = record(
        "target",
        {
            "gap_target": {"enum": [0.1, 0.05, 0.01, 0.0001]},
            "clock": ref("clock"),
            "pairing_sha256": ref("sha256"),
            "outcome": {
                "enum": [
                    "attained",
                    "right_censored",
                    "numeric_ineligible",
                    "memory_termination",
                    "callback_failure",
                    "infrastructure_interruption",
                    "no_incumbent",
                ]
            },
            "attainment_seconds": ref("quantity"),
            "followup_seconds": nonnegative,
            "observed_gap": ref("quantity"),
            "source_event_sha256": nullable_sha,
            "candidate_vector_sha256": nullable_sha,
            "candidate_audit": {"anyOf": [ref("audit"), {"type": "null"}]},
        },
    )
    definitions["disposition"] = record(
        "disposition",
        {
            "outcome": {
                "enum": [
                    "feature_unavailable",
                    "no_incumbent",
                    "numeric_ineligible",
                    "memory_termination",
                    "callback_failure",
                    "infrastructure_interruption",
                    "right_censored",
                ]
            },
            "reason": text,
            "preserved_partial_artifacts": {
                "type": "array",
                "items": ref("sha256"),
                "uniqueItems": True,
            },
        },
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:cfl-gnn:mvp3:s1a:v1:evidence",
        "title": "MVP3 observation contracts (S1-A); not execution authority",
        "$defs": definitions,
        "oneOf": [
            ref(kind)
            for kind in (
                "run",
                "root",
                "label",
                "start",
                "event",
                "target",
                "disposition",
            )
        ],
    }
