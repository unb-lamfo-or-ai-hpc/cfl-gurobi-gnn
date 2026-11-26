"""Schema and cross-record checks. This module contains no solver operations."""

import math

from .contract import CLOCKS, ContractError, canonical_bytes, digest, require
from .schema import evidence_schema


def check_schema(schema):
    from jsonschema import Draft202012Validator

    require(
        canonical_bytes(schema) == canonical_bytes(evidence_schema()),
        "Evidence schema differs from versioned source",
    )
    Draft202012Validator.check_schema(schema)


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), "Nonfinite JSON number")
    elif isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            finite_json(item)


def missing_semantics(value):
    if isinstance(value, dict):
        if set(value) == {"value", "missing_reason"}:
            reason = value["missing_reason"]
            if value["value"] is None:
                require(
                    isinstance(reason, str) and bool(reason.strip()),
                    "Missing value requires a reason",
                )
            else:
                require(reason is None, "Observed value cannot have a missing reason")
        for item in value.values():
            missing_semantics(item)
    elif isinstance(value, list):
        for item in value:
            missing_semantics(item)


def validate_clock(clock):
    require(CLOCKS.get(clock["name"]) == clock["origin"], "Clock origin mismatch")


def relative_gap(primal, dual):
    """Native relative-gap convention without JSON Infinity or fabricated values."""
    if primal is None:
        return {"value": None, "missing_reason": "no_incumbent"}
    if dual is None:
        return {"value": None, "missing_reason": "dual_unavailable"}
    finite_json([primal, dual])
    require(
        type(primal) in (int, float) and type(dual) in (int, float),
        "Gap inputs must be real numbers",
    )
    if primal == 0:
        if dual == 0:
            return {"value": 0, "missing_reason": None}
        return {"value": None, "missing_reason": "native_infinite_gap_zero_primal"}
    value = abs(primal - dual) / abs(primal)
    require(math.isfinite(value), "Computed gap exceeds finite numeric range")
    return {"value": value, "missing_reason": None}


def run_identity(run):
    return digest(
        {
            key: run[key]
            for key in (
                "schema_version",
                "key",
                "model_sha256",
                "source_commit",
                "environment_sha256",
                "audit_policy_sha256",
                "input_sha256",
                "solver_version",
                "effective_parameters",
                "native_defaults_sha256",
                "native_defaults_receipt_sha256",
                "resources",
                "mathematical_identity",
            )
        }
    )


def pairing_identity(run):
    """Same native comparison contract; intentionally excludes method and attempt."""
    return digest(
        {
            key: run[key]
            for key in (
                "model_sha256",
                "source_commit",
                "environment_sha256",
                "audit_policy_sha256",
                "input_sha256",
                "solver_version",
                "effective_parameters",
                "native_defaults_sha256",
                "native_defaults_receipt_sha256",
                "resources",
                "mathematical_identity",
            )
        }
    )


def validate_audit(audit, model_sha256, vector_sha256, *, continuous=False):
    require(
        audit["model_sha256"] == model_sha256,
        "Audit refers to another mathematical model",
    )
    require(audit["vector_sha256"] == vector_sha256, "Audit refers to another vector")
    for name in ("row", "bound", "integrality", "objective"):
        key = "objective_residual" if name == "objective" else f"{name}_max_violation"
        value = audit[key]["value"]
        require(value is None or value >= 0, "Negative audit residual")
        if audit["status"] == "qualified" and not (
            continuous
            and (name == "integrality" or (name == "objective" and value is None))
        ):
            require(
                value is not None and value <= audit["tolerances"][name],
                f"Unqualified {name} residual",
            )
    if continuous:
        require(
            audit["integrality_max_violation"]["value"] is None,
            "Continuous root audit is not an integrality audit",
        )


def validate_record(record, bundle):
    from jsonschema import Draft202012Validator

    finite_json(record)
    kind = record.get("kind") if isinstance(record, dict) else None
    require(
        kind in ("run", "root", "label", "start", "event", "target", "disposition"),
        "Unknown evidence record kind",
    )
    selected = dict(bundle["schema"])
    selected.pop("oneOf")
    selected["$ref"] = f"#/$defs/{kind}"
    errors = list(Draft202012Validator(selected).iter_errors(record))
    if errors:
        error = errors[0]
        raise ContractError(
            f"Evidence schema: {kind} at {list(error.absolute_path)} violates {error.validator}"
        )
    missing_semantics(record)
    key = record["key"]
    parent_map = {
        parent["original_id"]: parent for parent in bundle["parents"]["parents"]
    }
    require(key["parent_id"] in parent_map, "Parent is outside the frozen population")
    parent = parent_map[key["parent_id"]]
    if key["stage"] == "evaluation":
        require(key["method"] in ("B", "R", "G"), "Evaluation method is required")
        require(
            parent["role"] in ("test", "transfer_only"),
            "Evaluation parent is not held out",
        )
    else:
        require(key["method"] is None, "Preparation is not a B/R/G evaluation")
    kind = record["kind"]
    required_stage = {
        "root": "root_relaxation",
        "label": "incumbent",
        "start": "evaluation",
        "target": "evaluation",
    }.get(kind)
    if required_stage:
        require(key["stage"] == required_stage, f"Wrong stage for {kind}")
    if kind == "run":
        _validate_run(record, bundle, parent)
    elif kind == "root":
        require(
            record["captured_count"] == record["variable_count"],
            "Incomplete root vector",
        )
        event = record["event"]
        if event["cut_state"] == "pre_cut":
            require(
                event["ordinal"] == 1 and event["cut_pass"] == 0,
                "Pre-cut provenance contradicts root ordinal",
            )
        else:
            require(
                event["ordinal"] > 1 and event["cut_pass"] > 0,
                "Later root pass needs its actual provenance",
            )
        validate_audit(
            record["audit"],
            record["model_sha256"],
            record["vector_sha256"],
            continuous=True,
        )
        require(
            record["audit"]["status"] == "qualified",
            "Root is not numerically qualified",
        )
    elif kind == "label":
        _validate_label(record, parent)
    elif kind == "start":
        _validate_start(record)
    elif kind in ("event", "target"):
        validate_clock(record["clock"])
        vector, audit = record["candidate_vector_sha256"], record["candidate_audit"]
        if audit is not None:
            require(vector is not None, "Candidate audit needs its exact vector")
            validate_audit(audit, record["model_sha256"], vector)
        if kind == "event":
            for name in ("gap", "nodes", "native_Work"):
                require(
                    record[name]["value"] is None or record[name]["value"] >= 0,
                    f"Negative event {name}",
                )
            _check_gap(record["primal"], record["dual"], record["gap"])
        else:
            _validate_target(record)
    return record


def _check_gap(primal, dual, gap):
    expected = relative_gap(primal["value"], dual["value"])
    value = gap["value"]
    if expected["value"] is None:
        require(
            value is None, "Gap cannot be numeric without finite primal/dual evidence"
        )
    else:
        require(
            value is not None
            and math.isclose(value, expected["value"], rel_tol=1e-10, abs_tol=1e-12),
            "Gap inconsistent with primal/dual",
        )


def _validate_run(record, bundle, parent):
    contract = bundle["contract"]
    expected = contract["solver"]["profiles"][record["key"]["stage"]]
    require(
        record["native_defaults_sha256"] == digest(record["native_defaults"]),
        "Native-default inventory digest mismatch",
    )
    require(
        set(expected) <= set(record["native_defaults"]),
        "Native-default inventory is incomplete for the explicit profile",
    )
    expected_map = {**record["native_defaults"], **expected}
    actual_map = record["effective_parameters"]
    require(
        set(actual_map) == set(expected_map)
        and all(
            _parameter_equal(actual_map[name], value)
            for name, value in expected_map.items()
        ),
        "Effective parameters differ from recorded defaults plus approved overrides",
    )
    for name, value in expected.items():
        actual = record["effective_parameters"].get(name)
        require(
            _parameter_equal(actual, value),
            f"Effective solver parameter drift: {name}",
        )
    require(
        record["resources"]
        == contract["resources"]["solver_profiles"][parent["family"]],
        "Resource profile drift",
    )
    inputs = {row["original_id"]: row for row in bundle["catalogue"]["parents"]}
    require(
        record["input_sha256"] == inputs[parent["original_id"]]["stored_sha256"],
        "Stored input identity drift",
    )
    require(
        record["model_sha256"] == record["mathematical_identity"]["model_sha256"],
        "Mathematical identity binding mismatch",
    )
    require(record["run_sha256"] == run_identity(record), "Run identity mismatch")
    names = [item["clock"]["name"] for item in record["timings"]]
    require(len(set(names)) == len(names), "Duplicate timing clock")
    require(
        {"native_runtime", "worker_elapsed"} <= set(names),
        "Missing native/process clocks",
    )
    for item in record["timings"]:
        validate_clock(item["clock"])
        value = item["elapsed"]["value"]
        require(value is None or value >= 0, "Negative elapsed time")
    for quantity in [record["native_Work"], *record["supervision"].values()]:
        if isinstance(quantity, dict):
            value = quantity["value"]
            require(value is None or value >= 0, "Negative work/resource observation")
    if record["outcome"] == "feature_captured":
        require(
            record["key"]["stage"] == "root_relaxation",
            "Feature capture belongs to root preparation",
        )
    if record["outcome"] == "no_incumbent":
        require(
            record["final"]["primal"]["value"] is None,
            "No-incumbent outcome contains a primal",
        )
    final = record["final"]
    if final["vector_sha256"] is None:
        require(
            isinstance(final["vector_missing_reason"], str)
            and bool(final["vector_missing_reason"].strip()),
            "Missing final vector needs a reason",
        )
        require(final["audit"] is None, "Final audit has no retained vector")
    else:
        require(
            final["primal"]["value"] is not None
            and final["vector_missing_reason"] is None,
            "Final vector/primal availability mismatch",
        )
        if final["audit"] is not None:
            validate_audit(
                final["audit"], record["model_sha256"], final["vector_sha256"]
            )
            require(
                digest(final["audit"]["tolerances"]) == record["audit_policy_sha256"],
                "Final audit policy differs from run binding",
            )
    _check_gap(
        record["final"]["primal"], record["final"]["dual"], record["final"]["gap"]
    )


def _parameter_equal(actual, expected):
    if type(expected) in (int, float):
        return type(actual) in (int, float) and actual == expected
    return type(actual) is type(expected) and actual == expected


def _validate_label(record, parent):
    validate_audit(record["audit"], record["model_sha256"], record["vector_sha256"])
    require(record["parent_role"] == parent["role"], "Label partition drift")
    terminal = record["gap"] <= 0.0001
    require(
        record["tier"] == ("terminal_target" if terminal else "intermediate"),
        "Label quality tier contradicts gap",
    )
    eligible = (
        terminal
        and record["audit"]["status"] == "qualified"
        and parent["family"] != "hard"
    )
    require(
        record["admissible_primary_label"] == eligible,
        "Primary-label eligibility mismatch",
    )
    if record["origin"] == "BENDERS":
        require(parent["family"] == "hard", "Benders provenance is hard-only")
        require(
            record["conditional_release_sha256"] is not None
            and record["equivalence_audit_sha256"] is not None,
            "Benders needs separate release and equivalence evidence",
        )
    else:
        require(
            record["conditional_release_sha256"] is None
            and record["equivalence_audit_sha256"] is None,
            "DIRECT label has Benders-only references",
        )


def _validate_start(record):
    support = record["support"]
    method = record["key"]["method"]
    require(
        record["binary_count"] <= record["original_variable_count"],
        "Too many binary variables",
    )
    require(
        len(support) <= record["binary_count"] // 10,
        "Start exceeds the 10% binary support cap",
    )
    names = [item["variable_name"] for item in support]
    positions = [item["position"] for item in support]
    require(
        len(set(names)) == len(names) and len(set(positions)) == len(positions),
        "Duplicate Start coordinate",
    )
    for item in support:
        require(
            type(item["value"]) is int, "Start assignments must be integer 0/1 values"
        )
        require(
            item["position"] < record["original_variable_count"],
            "Start position outside original model",
        )
        require(
            item["lower_bound"] <= item["value"] <= item["upper_bound"],
            "Start violates selected-variable bounds",
        )
    assignments = [
        {key: item[key] for key in ("position", "variable_name", "value")}
        for item in support
    ]
    require(
        record["support_sha256"] == digest(assignments), "Start support digest mismatch"
    )
    require(
        record["ones_count"] == sum(item["value"] for item in support),
        "Start ones count mismatch",
    )
    if method == "B":
        require(
            not support
            and all(
                record[name] is None
                for name in (
                    "root_artifact_sha256",
                    "predictor_sha256",
                    "frozen_policy_sha256",
                )
            ),
            "B must have an empty external Start",
        )
    else:
        require(
            record["root_artifact_sha256"] is not None
            and record["frozen_policy_sha256"] is not None,
            "R/G guidance provenance missing",
        )
        require(
            (record["predictor_sha256"] is not None) == (method == "G"),
            "R must be independent of a G predictor",
        )


def _validate_target(record):
    attained = record["outcome"] == "attained"
    time = record["attainment_seconds"]["value"]
    if attained:
        require(
            time is not None and 0 <= time <= record["followup_seconds"],
            "Invalid observed attainment time",
        )
        gap = record["observed_gap"]["value"]
        require(
            gap is not None and 0 <= gap <= record["gap_target"],
            "Attainment lacks the specified gap",
        )
        require(
            record["candidate_audit"] is not None
            and record["candidate_audit"]["status"] == "qualified",
            "Attainment lacks a qualified point-specific audit",
        )
        require(
            record["source_event_sha256"] is not None,
            "Attainment lacks its observed source event",
        )
    else:
        require(
            time is None,
            "Nonattainment must not substitute a censoring endpoint for a target time",
        )
        require(
            record["source_event_sha256"] is None,
            "Nonattainment cannot cite an attainment event",
        )
        if record["outcome"] == "right_censored":
            gap = record["observed_gap"]["value"]
            require(
                gap is None or gap > record["gap_target"],
                "Censored record reports an attained gap",
            )


def validate_records(records, bundle):
    """Validate a collection, including immutable run and point-specific links."""
    for record in records:
        validate_record(record, bundle)
    runs = {}
    keys = set()
    unique = set()
    events = {}
    event_keys = set()
    for record in records:
        kind = record["kind"]
        identity = (
            kind,
            record["run_sha256"],
            record.get("gap_target"),
            record.get("event_ordinal"),
            digest(record.get("clock")),
        )
        require(
            identity not in unique, "Duplicate record for run/kind/target/event/clock"
        )
        unique.add(identity)
        if kind == "run":
            key = canonical_bytes(record["key"])
            require(key not in keys, "Attempt key reused by another run")
            keys.add(key)
            runs[record["run_sha256"]] = record
        elif kind == "event":
            event_key = (record["run_sha256"], record["event_ordinal"])
            require(event_key not in event_keys, "Duplicate run event ordinal")
            event_keys.add(event_key)
            events[digest(record)] = record
    last_time = {}
    for event in sorted(
        events.values(), key=lambda item: (item["run_sha256"], item["event_ordinal"])
    ):
        clock_key = (event["run_sha256"], event["clock"]["name"])
        require(
            event["elapsed_seconds"] >= last_time.get(clock_key, 0),
            "Nonmonotone event clock",
        )
        last_time[clock_key] = event["elapsed_seconds"]
    for record in records:
        if record["kind"] == "run":
            continue
        require(record["run_sha256"] in runs, "Missing source run")
        run = runs[record["run_sha256"]]
        require(
            record["key"] == run["key"]
            and record["model_sha256"] == run["model_sha256"],
            "Cross-run artifact binding mismatch",
        )
        audit = record.get("audit", record.get("candidate_audit"))
        if audit is not None:
            require(
                digest(audit["tolerances"]) == run["audit_policy_sha256"],
                "Artifact audit policy differs from run binding",
            )
        if "variable_order_sha256" in record:
            require(
                record["variable_order_sha256"]
                == run["mathematical_identity"]["variable_order_sha256"],
                "Artifact variable order differs from source run",
            )
        if record["kind"] == "root":
            require(
                record["variable_count"] == run["mathematical_identity"]["variables"],
                "Root count differs from original model",
            )
            require(
                run["outcome"] == "feature_captured",
                "Qualified root lacks a successful feature-capture receipt",
            )
        if record["kind"] == "label":
            require(
                record["vector_sha256"] == run["final"]["vector_sha256"]
                and record["audit"] == run["final"]["audit"]
                and record["gap"] == run["final"]["gap"]["value"],
                "Label differs from the audited source incumbent",
            )
        if record["kind"] in ("event", "target"):
            clock = record["clock"]
            timings = {item["clock"]["name"]: item for item in run["timings"]}
            require(clock["name"] in timings, "Source run lacks this observation clock")
            endpoint = timings[clock["name"]]["elapsed"]["value"]
            observed = (
                record["elapsed_seconds"]
                if record["kind"] == "event"
                else record["followup_seconds"]
            )
            require(
                endpoint is not None and observed <= endpoint,
                "Observation exceeds recorded follow-up",
            )
        if record["kind"] == "target":
            require(
                record["pairing_sha256"] == pairing_identity(run),
                "Target pairing contract mismatch",
            )
            if record["outcome"] == "right_censored":
                require(
                    run["outcome"] in ("completed", "time_limit"),
                    "Invalid interruption recast as valid censoring",
                )
            attained_events = [
                event
                for event in events.values()
                if event["run_sha256"] == record["run_sha256"]
                and event["clock"] == record["clock"]
                and event["elapsed_seconds"] <= record["followup_seconds"]
                and event["gap"]["value"] is not None
                and event["gap"]["value"] <= record["gap_target"]
                and event["candidate_audit"] is not None
                and event["candidate_audit"]["status"] == "qualified"
            ]
            if record["outcome"] == "right_censored":
                require(
                    not attained_events,
                    "Censoring contradicts a qualified retained attainment event",
                )
                final = run["final"]
                if (
                    record["followup_seconds"] == endpoint
                    and final["gap"]["value"] is not None
                    and final["audit"] is not None
                    and final["audit"]["status"] == "qualified"
                ):
                    require(
                        final["gap"]["value"] > record["gap_target"],
                        "Censoring contradicts the qualified final gap",
                    )
            if record["outcome"] == "attained":
                event_sha256 = record["source_event_sha256"]
                require(event_sha256 in events, "Target source event is absent")
                event = events[event_sha256]
                require(
                    event["run_sha256"] == record["run_sha256"]
                    and event["clock"] == record["clock"]
                    and event["elapsed_seconds"]
                    == record["attainment_seconds"]["value"]
                    and event["gap"] == record["observed_gap"]
                    and event["candidate_vector_sha256"]
                    == record["candidate_vector_sha256"]
                    and event["candidate_audit"] == record["candidate_audit"],
                    "Target does not match its audited source event",
                )
                require(
                    record["attainment_seconds"]["value"]
                    == min(item["elapsed_seconds"] for item in attained_events),
                    "Target is not the first qualified observed attainment",
                )
    return {"records": len(records), "runs": len(runs), "events": len(events)}


def paired_time_factor(comparator, guidance, bundle, source_records):
    """One qualified paired factor, never a cohort aggregate or imputed time."""
    validate_records([*source_records, comparator, guidance], bundle)
    require(
        comparator["kind"] == guidance["kind"] == "target", "Expected target records"
    )
    result = {"ratio": None, "signed_saving_seconds": None, "eligibility_reason": None}
    if (
        comparator["key"]["method"] not in ("B", "R")
        or guidance["key"]["method"] != "G"
    ):
        reason = "wrong_method_orientation"
    elif comparator["key"]["parent_id"] != guidance["key"]["parent_id"]:
        reason = "different_parent"
    elif comparator["gap_target"] != guidance["gap_target"]:
        reason = "different_target"
    elif comparator["clock"] != guidance["clock"]:
        reason = "different_clock"
    elif comparator["pairing_sha256"] != guidance["pairing_sha256"]:
        reason = "different_pairing_contract"
    elif comparator["outcome"] != "attained" or guidance["outcome"] != "attained":
        reason = "no_common_qualified_attainment"
    else:
        first, second = (
            comparator["attainment_seconds"]["value"],
            guidance["attainment_seconds"]["value"],
        )
        if first <= 0 or second <= 0:
            reason = "nonpositive_observed_time"
        else:
            result["ratio"] = first / second
            result["signed_saving_seconds"] = first - second
            finite_json(result)
            reason = None
    result["eligibility_reason"] = reason
    return result
