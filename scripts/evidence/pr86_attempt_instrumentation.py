"""Prospective attempt instrumentation, not an HPC submission/admission interface.

The dispatcher is supplied by the future admission-checked operator. There is
deliberately no default process launcher or CLI. Tests supply synthetic dispatchers.
Historical receipts and the qualified memory watchdog are never modified here.
"""

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

import pr86_cost_accounting as costs
import pr86_supervised_costs as supervised

PROTOCOL = "pr86_prospective_attempt_measurement_v1"
PARENTS = {"easy": (0, 3, 6, 14, 27, 29), "medium": (0, 4, 7, 12)}
STOPS = {
    "memory_guard_stop",
    "memory_observation_lost",
    "child_deadline_exceeded",
    "unexpected_process_group_survivor",
}


def require(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_once(path, value):
    raw = encoded(value)
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def parameters(cell):
    """Explicit supported cells, not implicit legacy Threads=1/Seed=42."""
    require(cell["method"] in ("M0", "M1", "M2"), "method")
    threads, seed = cell["threads"], cell["seed"]
    require(type(threads) is int and threads in (1, 2, 4, 8, 16), "thread_cap")
    require(type(seed) is int and seed in (42, 43, 44), "seed")
    require(threads == 1 or seed == 42, "unplanned_repeat")
    match = re.fullmatch(r"CFL_(easy|medium)_instance_([0-9]+)", cell["parent"])
    require(match is not None, "parent")
    difficulty, number = match.groups()
    require(int(number) in PARENTS[difficulty] and str(int(number)) == number, "parent")
    alias = ("F" if difficulty == "easy" else "M") + number
    require(
        cell["cell_id"] == f"{alias}-threads{threads}-seed{seed}-{cell['method']}",
        "cell_id",
    )
    require(cell["effective_objective_sense"] == "MINIMIZE", "objective_sense")
    require(
        type(cell["time_limit_seconds"]) in (int, float)
        and cell["time_limit_seconds"] == 3600,
        "time_limit",
    )
    require(
        type(cell["mip_gap_fraction"]) in (int, float)
        and cell["mip_gap_fraction"] == 1e-4,
        "gap",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", cell["model_sha256"]) is not None, "model_hash"
    )
    return dict(
        Threads=threads, Seed=seed, TimeLimit=3600, MIPGap=1e-4, SoftMemLimit=48
    )


def validate_result(cell, result):
    require(
        type(result["optimization_calls"]) is int and result["optimization_calls"] == 1,
        "optimization_calls",
    )
    require(result["method"] == cell["method"], "result_method")
    require(result["mip_sha256"] == cell["model_sha256"], "result_model")
    require(result["solver_version"] == [13, 0, 1], "result_solver")
    require(result["effective_objective_sense"] == "MINIMIZE", "result_sense")
    require(
        result["fresh_model"] is True
        and result["mathematical_model_unchanged"] is True,
        "result_model_identity",
    )
    require(
        all(
            result["parameters"][key] == value
            for key, value in parameters(cell).items()
        ),
        "result_parameters",
    )
    require(result["gate_status"] in ("passed", "failed"), "result_gate")
    require(result["scientific_reporting_eligible"] is False, "scientific_gate")


def reconcile(cell, supervision, result):
    """Stops must be resolved BEFORE a successful-cost label is calculated."""
    parameters(cell)
    reason = supervision["guard_stop"]
    require(reason is None or reason in STOPS, "unknown_guard_stop")
    require(type(supervision["child_exit_code"]) is int, "child_exit_code")
    if reason is None and (supervision["child_exit_code"] != 0 or result is None):
        reason = "child_failed"
    if result is not None:
        validate_result(cell, result)
        status = result["solve"]["solve_status_code"]
        require(
            type(status) is int and status in (2, 3, 8, 9, 10, 11, 16, 17),
            "solve_status",
        )
        if reason is None and status == 17:
            reason = "solver_soft_memory_stop"
        if reason is None and result["gate_status"] != "passed":
            reason = "result_validation_failed"
    # Do not promote a valid but SoftMemLimit-interrupted return as completed.
    normalized = {**supervision, "guard_stop": reason}
    measurement = supervised.reconcile(normalized, result, cell["method"])
    return reason, measurement


def observe_attempt(output, cell, context, *, dispatch=None, clock=time.perf_counter):
    """Wrap a future isolated dispatcher and durably preserve failure measurements.

    dispatch(output, claim) returns (supervision, sanitized_child_result). It
    must use the existing job-scoped memory watchdog and validate admission,
    affinity, preparation, environment and logs. No such launcher is exposed yet.
    claim must be called from the child immediately before its sole optimize.
    """
    parameters(cell)
    require(callable(dispatch), "installed_execution_adapter_not_admitted")
    require(
        set(context) == {"source_commit", "plan_sha256", "binding_sha256"},
        "context_fields",
    )
    for field, value in context.items():
        width = 40 if field == "source_commit" else 64
        require(
            isinstance(value, str)
            and re.fullmatch(r"[0-9a-f]{" + str(width) + "}", value) is not None,
            "context_hash",
        )
    output = Path(output)
    # mkdir is the durable one-attempt reservation. Never resume or reuse it.
    output.mkdir(exist_ok=False)
    started = clock()
    identity = json.loads(
        encoded(dict(protocol_id=PROTOCOL, cell=cell, context=context))
    )
    write_once(output / "attempt.started.json", identity)
    cell_hash = digest(encoded(cell))

    def claim():
        write_once(
            output / "optimize.intent.json",
            {
                "cell_sha256": cell_hash,
                "maximum_calls": 1,
            },
        )

    observed, result, measurement, reason = None, None, None, None
    dispatch_seconds = None
    error = None
    claimed = False
    try:
        dispatch_started = clock()
        try:
            observed, result = dispatch(output, claim)
        finally:
            dispatch_seconds = costs.seconds(clock() - dispatch_started)
        claimed = (output / "optimize.intent.json").exists()
        if claimed:
            require(
                (output / "optimize.intent.json").read_bytes()
                == encoded({"cell_sha256": cell_hash, "maximum_calls": 1}),
                "optimization_intent_binding",
            )
        require(digest(encoded(cell)) == cell_hash, "cell_mutated")
        require(context == identity["context"], "context_mutated")
        require(claimed or result is None, "result_without_optimization_intent")
        reason, measurement = reconcile(cell, observed, result)
        require(
            measurement["supervisor_wall_seconds"] <= dispatch_seconds,
            "dispatch_shorter_than_supervisor",
        )
    except BaseException as exc:
        # Exception messages/paths/logs never enter the public receipt. Preserve
        # even KeyboardInterrupt/SystemExit; no replacement attempt is allowed.
        reason = "instrumentation_or_dispatch_failed"
        error = (
            type(exc).__name__
            if type(exc)
            in (ValueError, OSError, RuntimeError, KeyboardInterrupt, SystemExit)
            else "other"
        )
        measurement = None
    before_export = costs.seconds(clock() - started)
    require(
        dispatch_seconds is None or dispatch_seconds <= before_export, "attempt_clock"
    )
    report = {
        **identity,
        "dispatch_wall_seconds": dispatch_seconds,
        "attempt_before_receipt_export_seconds": before_export,
        "outside_dispatch_before_export_seconds": None
        if dispatch_seconds is None
        else before_export - dispatch_seconds,
        "optimization_intent_present": (output / "optimize.intent.json").exists(),
        "exact_optimization_call_count": 1
        if result is not None and claimed and error is None
        else None,
        "child_result_sha256": digest(encoded(result))
        if result is not None and error is None
        else None,
        "supervision": None
        if measurement is None
        else {
            k: observed[k]
            for k in ("supervisor_wall_seconds", "child_exit_code", "guard_stop")
        },
        "measurement": measurement,
        "stop_code": reason,
        "exception_type": error,
        "pause_remaining_matrix": reason is not None,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
        "whole_job_end_to_end_qualified": False,
    }
    export_started = clock()
    report_sha = write_once(output / "attempt.json", report)
    export_seconds = costs.seconds(clock() - export_started)
    total = costs.seconds(clock() - started)
    # The tail cannot measure its own write: explicitly leave that outside scope.
    require(total >= before_export + export_seconds, "export_clock")
    write_once(
        output / "timing_tail.json",
        {
            "attempt_sha256": report_sha,
            "attempt_receipt_export_seconds": export_seconds,
            "observed_attempt_through_receipt_export_seconds": total,
            "between_export_measurements_seconds": total
            - before_export
            - export_seconds,
            "excludes": [
                "timing_tail_write",
                "scheduler_queue",
                "batch_setup_teardown",
                "preparation_in_other_processes",
            ],
            "whole_job_end_to_end_qualified": False,
        },
    )
    return report


def validate_timing_files(output):
    """Read-only reconciliation of the immutable receipt and separate export tail."""
    output = Path(output)
    raw = (output / "attempt.json").read_bytes()
    report = json.loads(raw)
    tail = json.loads((output / "timing_tail.json").read_bytes())
    require(tail["attempt_sha256"] == digest(raw), "attempt_hash")
    identity = json.loads((output / "attempt.started.json").read_bytes())
    require(
        identity == {key: report[key] for key in ("protocol_id", "cell", "context")},
        "attempt_identity",
    )
    require(
        report["protocol_id"] == PROTOCOL
        and report["scientific_reporting_eligible"] is False,
        "report_scope",
    )
    require(
        report["whole_job_end_to_end_qualified"] is False
        and tail["whole_job_end_to_end_qualified"] is False,
        "measurement_scope",
    )
    before = costs.seconds(report["attempt_before_receipt_export_seconds"])
    export = costs.seconds(tail["attempt_receipt_export_seconds"])
    other = costs.seconds(tail["between_export_measurements_seconds"])
    total = costs.seconds(tail["observed_attempt_through_receipt_export_seconds"])
    require(
        math.isclose(before + export + other, total, abs_tol=1e-6, rel_tol=1e-8),
        "export_reconciliation",
    )
    return report, tail
