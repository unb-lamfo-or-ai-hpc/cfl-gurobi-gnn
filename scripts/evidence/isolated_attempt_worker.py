"""One authorized qualification child; sealed receipts, no submission CLI.

The public CLI only validates/exports existing receipts. A future reviewed
operator workflow must supply an explicitly approved, hash-bound single-solve
request to supervise_one. This module never creates that authorization.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tarfile
import time
from contextlib import ExitStack
from pathlib import Path

import gurobi_callback_adapter as adapter

contract = adapter.contract
PROTOCOL = "single_attempt_callback_qualification_v1"
PREFLIGHT_SHA = "f8077c9c2abcb77ca3b1bf36133bb07b5bfe43b05bea9395da6e39908956fb00"
DEPENDENCIES = (*adapter.DEPENDENCIES, "isolated_attempt_worker.py")
PUBLIC = ("request.json", "attempt_receipt.json", "SHA256SUMS.txt")
MAX_JSON = 8 * 1024 * 1024
GRACE_SECONDS = 10
DEFAULTS = {
    "ConcurrentMIP": 1,
    "Crossover": -1,
    "Cuts": -1,
    "FeasibilityTol": 1e-6,
    "Heuristics": 0.05,
    "IntFeasTol": 1e-5,
    "MIPFocus": 0,
    "MIPGapAbs": 1e-10,
    "Method": -1,
    "NodeLimit": "positive_infinity",
    "NodeMethod": -1,
    "OptimalityTol": 1e-6,
    "Presolve": -1,
}


def require(condition):
    if not condition:
        raise ValueError("isolated_attempt_contract_failed")


def keys(value, names):
    require(isinstance(value, dict) and set(value) == set(names.split()))


def integer(value, minimum=0, maximum=None):
    require(type(value) is int and value >= minimum)
    require(maximum is None or value <= maximum)
    return value


def hexadecimal(value, length=64):
    require(isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value))


def strict_payload(raw):
    require(len(raw) <= MAX_JSON)

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result)
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("nonfinite_json")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    require(contract.encoded(value) == raw)
    require(not adapter.PRIVATE.search(raw.decode()))
    require(
        not any(
            marker in raw.lower()
            for marker in (
                b"/home/",
                b"/raid/",
                b"licenseid",
                b"wlssecret",
                b"gurobi.lic",
            )
        )
    )
    return value


def read_bytes(path, limit=MAX_JSON):
    path = Path(path)
    require(not path.is_symlink() and path.is_file())
    before = path.stat()
    require(before.st_size <= limit)
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    after = path.stat()
    require(len(raw) <= limit and len(raw) == after.st_size)
    require(
        (before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_ino, after.st_size, after.st_mtime_ns)
    )
    return raw


def write_json(path, value):
    payload = contract.encoded(value)
    strict_payload(payload)
    with Path(path).open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def dependency_hashes():
    return {
        name: adapter.screen.digest(Path(__file__).parent / name)
        for name in DEPENDENCIES
    }


def validate_request(request):
    keys(
        request,
        "schema_version protocol_id explicitly_approved approval_record_sha256 "
        "source_commit dependency_sha256 proposal_sha256 installed_preflight_receipt_sha256 "
        "attempt_id optimization_limit_seconds child_deadline_seconds "
        "maximum_optimization_calls scientific_reporting_eligible",
    )
    require(integer(request["schema_version"]) == 1)
    require(
        request["protocol_id"] == PROTOCOL and request["explicitly_approved"] is True
    )
    hexadecimal(request["approval_record_sha256"])
    require(request["approval_record_sha256"] != "0" * 64)
    hexadecimal(request["source_commit"], 40)
    require(request["dependency_sha256"] == dependency_hashes())
    require(request["installed_preflight_receipt_sha256"] == PREFLIGHT_SHA)
    proposal = contract.compile_proposal()
    require(request["proposal_sha256"] == proposal["proposal_sha256"])
    matches = [
        r for r in proposal["attempts"] if r["attempt_id"] == request["attempt_id"]
    ]
    require(len(matches) == 1)
    # Qualification is a separate, explicitly budgeted experiment, not the
    # disabled 3600-second comparison. There is no comparison execution here.
    limit = integer(request["optimization_limit_seconds"], 1, 300)
    require(integer(request["child_deadline_seconds"]) == limit + 180)
    require(integer(request["maximum_optimization_calls"]) == 1)
    require(request["scientific_reporting_eligible"] is False)
    strict_payload(contract.encoded(request))
    return proposal, matches[0]


def expected_parameters(request, row):
    return {
        "Threads": row["threads"],
        "Seed": row["seed"],
        "TimeLimit": request["optimization_limit_seconds"],
        "MIPGap": row["stopping_gap_relative"],
        "SoftMemLimit": 48,
    }


def qualify_execution(request, output, fresh):
    validate_request(request)
    require(
        sys.platform == "linux" and socket.gethostname().split(".")[0] == "dgx-dasci"
    )
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env")
    require(os.environ.get("SLURM_CPUS_PER_TASK") == "16")
    require(re.fullmatch(r"[0-9]+", os.environ.get("SLURM_JOB_ID", "")))
    require(os.environ.get("SLURM_MEM_PER_NODE") == "65536")
    require(os.environ.get("SLURM_JOB_NUM_NODES") == "1")
    require(
        not os.environ.get("SLURM_JOB_GPUS") and not os.environ.get("SLURM_STEP_GPUS")
    )
    source = Path(__file__).resolve().parents[2]
    require(
        source.resolve() == source
        and source.is_relative_to(Path("/raid/vrcelestino/data"))
    )
    cmd = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
    require(
        subprocess.check_output([*cmd, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        .decode()
        .strip()
        == request["source_commit"]
    )
    require(
        not subprocess.check_output(
            [*cmd, "status", "--porcelain", "--untracked-files=all"],
            stderr=subprocess.DEVNULL,
        )
    )
    output = Path(output).absolute()
    require(
        output.resolve() == output
        and output.parent.resolve().is_relative_to(adapter.EVIDENCE_ROOT)
    )
    require(not output.is_relative_to(source) and not source.is_relative_to(output))
    require((not output.exists()) if fresh else output.is_dir())
    require(adapter.RAW_ROOT.resolve(strict=True) == adapter.RAW_ROOT)
    return output


def claim_authorization(request, output):
    """Global persistent claim prevents reusing one approval at another path."""
    root = adapter.EVIDENCE_ROOT / "isolated-attempt-locks"
    require(root.parent.resolve(strict=True) == adapter.EVIDENCE_ROOT)
    root.mkdir(mode=0o700, exist_ok=True)
    require(root.resolve() == root and not root.is_symlink())
    claimed = root / request["approval_record_sha256"]
    claimed.mkdir(mode=0o700, exist_ok=False)
    write_json(claimed / "request.json", request)
    write_json(
        claimed / "target.json",
        {
            "output_directory_sha256": contract.sha(
                str(Path(output).absolute()).encode()
            )
        },
    )
    return claimed


def validate_claim(request, output):
    root = (
        adapter.EVIDENCE_ROOT
        / "isolated-attempt-locks"
        / request["approval_record_sha256"]
    )
    require(root.resolve() == root)
    require(read_bytes(root / "request.json") == contract.encoded(request))
    target = strict_payload(read_bytes(root / "target.json"))
    require(
        target
        == {
            "output_directory_sha256": contract.sha(
                str(Path(output).absolute()).encode()
            )
        }
    )


def run_child(request, output):
    """One fresh model/environment. Caller must isolate this function in a process."""
    output = qualify_execution(request, output, fresh=False)
    validate_claim(request, output)
    require(
        read_bytes(output / "child.started", 64)
        == contract.sha(contract.encoded(request)).encode()
    )
    with (output / "worker.started").open("xb") as stream:
        stream.write(contract.sha(contract.encoded(request)).encode())
    proposal, row = validate_request(request)
    telemetry = contract.Telemetry(
        request["optimization_limit_seconds"], row["stopping_gap_relative"]
    )
    # Callback finalization occurs while the model still exists. Independent
    # phase recorder remains open through disposal after telemetry is finished.
    phase_clock = contract.Telemetry(
        request["optimization_limit_seconds"], row["stopping_gap_relative"]
    )
    affinity = adapter.screen.qualify_affinity()
    import resource

    original = next(
        r
        for r in json.loads(contract.original.public_receipts()["pilot_plan.json"])[
            "models"
        ]
        if r["source_instance_id"] == row["source_instance_id"]
    )
    source = adapter.screen.frozen_source(adapter.RAW_ROOT, original)
    log = Path(output) / "gurobi.private.log"
    value = {
        "request_sha256": contract.sha(contract.encoded(request)),
        "optimization_calls": 0,
        "failure_code": None,
        "result": None,
        "effective_parameters": None,
        "algorithm_defaults": None,
        "original_lp_unchanged": False,
        "gurobi_log": None,
        "affinity": affinity,
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "peak_rss_bytes": None,
        "current_process_cpu_seconds": None,
        "phases": [],
    }
    stage = "read_setup"
    stack = ExitStack()
    try:
        with phase_clock.phase("read_setup"):
            gp = adapter.screen.licensed_runtime(proposal["controls"])
            env = stack.enter_context(gp.Env(empty=True))
            env.setParam("OutputFlag", 0)
            env.setParam("ThreadLimit", 16)
            env.start()
            model = stack.enter_context(gp.read(str(source), env=env))
            config = adapter.source_config(proposal, row)
            config["time_limit_seconds"] = request["optimization_limit_seconds"]
            adapter.screen.prepare_original_model(model, config)
            parameters, defaults = adapter.screen.configure_model(
                model, config, row["threads"], log
            )
            value.update(effective_parameters=parameters, algorithm_defaults=defaults)
            require(
                defaults
                == {
                    name: {"effective": value, "version_default": value}
                    for name, value in DEFAULTS.items()
                }
            )
            callback = adapter.GurobiCallbackAdapter(gp, telemetry)
        stage = "optimization"
        with phase_clock.phase("optimization"):
            value["optimization_calls"] = 1
            model.optimize(callback)
        # Final attributes outside the timed optimize call and before disposal.
        stage = "terminal_inspection"
        value["result"] = callback.finish_model(model)
    except Exception:
        value["failure_code"] = "worker_" + stage + "_failed"
    finally:
        try:
            with phase_clock.phase("cleanup"):
                stack.close()
        except Exception:
            value["failure_code"] = "worker_cleanup_failed"
    # Both model and environment writers have now been disposed. A disposal
    # failure cannot certify a closed log and never receives a sealed digest.
    if value["failure_code"] != "worker_cleanup_failed" and log.exists():
        try:
            value["gurobi_log"] = contract.seal_closed_log(log)
        except Exception:
            value["failure_code"] = "worker_log_seal_failed"
    value["original_lp_unchanged"] = (
        adapter.screen.digest(source) == row["original_lp_sha256"]
    )
    if not value["original_lp_unchanged"]:
        value["failure_code"] = "worker_source_changed"
    value["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    value["current_process_cpu_seconds"] = time.process_time()
    value["phases"] = list(phase_clock.phases)
    if value["result"] is not None:
        value["result"]["phases"] = list(phase_clock.phases)
    write_json(Path(output) / "child.private.json", value)


def internal_child(directory, request_sha):
    """Private dispatch only; no request/approval creation or retry capability."""
    try:
        output = Path(directory)
        raw = read_bytes(output / "request.private.json")
        require(contract.sha(raw) == request_sha)
        request = strict_payload(raw)
        qualify_execution(request, output, fresh=False)
        validate_claim(request, output)
        # Persistent one-shot claim. A second child cannot enter the solver.
        with (output / "child.started").open("xb") as stream:
            stream.write(request_sha.encode())
        run_child(request, output)
    except Exception:
        print("ISOLATED_CHILD_FAILED_PRESERVE_PRIVATE_OUTPUT", flush=True)
        raise SystemExit(2) from None


def log_binding(value):
    keys(value, "log_sha256 log_size_bytes private_log_text_included hash_scope")
    hexadecimal(value["log_sha256"])
    integer(value["log_size_bytes"], 0, contract.MAX_LOG_BYTES)
    require(value["private_log_text_included"] is False)
    require(value["hash_scope"] == "bytes_after_caller_closed_writer")


def validate_phases(phases):
    require(isinstance(phases, list) and 1 <= len(phases) <= 3)
    order = ["read_setup", "optimization", "cleanup"]
    names = []
    for phase in phases:
        keys(phase, "phase external_wall_seconds process_cpu_seconds call_failed")
        require(phase["phase"] in order and phase["phase"] not in names)
        names.append(phase["phase"])
        contract.number(phase["external_wall_seconds"])
        contract.number(phase["process_cpu_seconds"])
        require(type(phase["call_failed"]) is bool)
    require(names == sorted(names, key=order.index) and names[-1] == "cleanup")


def validate_result(result, request, row):
    keys(
        result,
        "schema_version stop terminal optimization_budget_seconds stopping_gap_relative "
        "time_limit_overshoot_seconds first_sampled_gap_observations samples dropped_sample_count "
        "sampling_policy true_first_crossings_qualified phases root_tree_phase_costs_qualified "
        "process_cpu_scope primal_integral_qualified scientific_reporting_eligible gurobi_callback",
    )
    require(integer(result["schema_version"]) == 1)
    require(
        result["optimization_budget_seconds"] == request["optimization_limit_seconds"]
    )
    require(result["stopping_gap_relative"] == row["stopping_gap_relative"])
    for flag in (
        "true_first_crossings_qualified",
        "root_tree_phase_costs_qualified",
        "primal_integral_qualified",
        "scientific_reporting_eligible",
    ):
        require(result[flag] is False)
    require(
        result["sampling_policy"] == "caller_supplied_events_not_continuous_monitoring"
    )
    require(
        result["process_cpu_scope"] == "current_process_only_not_scheduler_aggregate"
    )
    cb = result["gurobi_callback"]
    keys(
        cb,
        "schema_version policy best_bound_scope candidate_vectors_read node_relaxations_read "
        "algorithm_parameters_changed_by_callback counters callback_external_wall_seconds "
        "callback_current_process_cpu_seconds overhead_subtracted_from_solver_runtime failed "
        "failure_code termination_requested_for_failure terminal_status terminal_solution_count "
        "terminal_gap_state terminal_mip_gap_attribute zero_objective_gap_qualified installed_callback_execution_qualified",
    )
    require(integer(cb["schema_version"]) == 1)
    require(
        cb["policy"]
        == "best_known_bounds_mip_at_most_once_per_second_plus_all_mipsol_and_terminal"
    )
    require(
        cb["best_bound_scope"] == "callback_bounds_not_terminal_rounded_model_bound"
    )
    for flag in (
        "candidate_vectors_read",
        "node_relaxations_read",
        "algorithm_parameters_changed_by_callback",
        "overhead_subtracted_from_solver_runtime",
        "zero_objective_gap_qualified",
        "installed_callback_execution_qualified",
    ):
        require(cb[flag] is False)
    require(
        type(cb["failed"]) is bool
        and type(cb["termination_requested_for_failure"]) is bool
    )
    require(
        cb["failure_code"]
        in {
            None,
            "callback_after_finalization",
            "callback_clock_failure",
            "callback_observation_failure",
        }
    )
    require(cb["failed"] == (cb["failure_code"] is not None))
    require(cb["failed"] or not cb["termination_requested_for_failure"])
    integer(cb["terminal_solution_count"])
    integer(cb["terminal_status"])
    contract.number(cb["callback_external_wall_seconds"])
    contract.number(cb["callback_current_process_cpu_seconds"])
    keys(
        cb["counters"],
        "mip_calls mipsol_calls regular_samples mipsol_samples rate_skipped missing_gap_samples zero_objective_samples",
    )
    counts = cb["counters"]
    for value in counts.values():
        integer(value)
    require(counts["regular_samples"] + counts["rate_skipped"] <= counts["mip_calls"])
    require(counts["mipsol_samples"] <= counts["mipsol_calls"])
    require(
        counts["missing_gap_samples"]
        <= counts["regular_samples"] + counts["mipsol_samples"]
    )
    require(counts["zero_objective_samples"] <= counts["missing_gap_samples"])
    terminal = result["terminal"]
    keys(
        terminal, "solver_runtime_seconds terminal primal dual gap_relative node_count"
    )
    require(terminal["terminal"] is True)
    contract.number(terminal["node_count"])
    gap, state = adapter.relative_gap(terminal["primal"], terminal["dual"])
    require(cb["terminal_gap_state"] == state)
    attribute = cb["terminal_mip_gap_attribute"]
    if attribute is not None:
        contract.number(attribute)
        require(cb["terminal_solution_count"] > 0)
    if cb["terminal_solution_count"] == 0:
        require(terminal["primal"] is None and terminal["gap_relative"] is None)
    if terminal["primal"] == 0:
        require(terminal["gap_relative"] is None)
    else:
        require(terminal["gap_relative"] == attribute)
    if gap is not None and attribute is not None:
        require(abs(gap - attribute) <= 1e-10 * max(1, abs(gap)))
    stop = (
        "worker_failure"
        if cb["failed"]
        else {9: "time_limit", 17: "memory_limit"}.get(
            cb["terminal_status"], "other_stop"
        )
    )
    if (
        not cb["failed"]
        and cb["terminal_status"] == 2
        and terminal["gap_relative"] is not None
        and terminal["gap_relative"] <= row["stopping_gap_relative"]
    ):
        stop = "gap_target"
    require(result["stop"] == stop)
    samples = result["samples"]
    require(isinstance(samples, list) and 1 <= len(samples) <= contract.MAX_SAMPLES)
    # Full exports are fail-closed on storage exhaustion: the missing tail
    # cannot be independently reconstructed from an aggregate claim.
    require(integer(result["dropped_sample_count"]) == 0)
    require(
        samples[-1] == terminal
        and len(samples) == counts["regular_samples"] + counts["mipsol_samples"] + 1
    )
    rebuilt = contract.Telemetry(
        request["optimization_limit_seconds"], row["stopping_gap_relative"]
    )
    for sample in samples[:-1]:
        keys(
            sample,
            "solver_runtime_seconds terminal primal dual gap_relative node_count",
        )
        require(sample["terminal"] is False)
        formula, _ = adapter.relative_gap(sample["primal"], sample["dual"])
        require(sample["gap_relative"] == formula)
        rebuilt.observe(
            sample["solver_runtime_seconds"],
            sample["primal"],
            sample["dual"],
            sample["gap_relative"],
            sample["node_count"],
        )
    calculated = rebuilt.finish(
        stop,
        terminal["solver_runtime_seconds"],
        terminal["primal"],
        terminal["dual"],
        terminal["gap_relative"],
        terminal["node_count"],
    )
    require(all(result[k] == calculated[k] for k in calculated if k != "phases"))
    validate_phases(result["phases"])


def validate_child(child, request):
    keys(
        child,
        "request_sha256 optimization_calls failure_code result effective_parameters "
        "algorithm_defaults original_lp_unchanged gurobi_log affinity peak_rss_bytes "
        "current_process_cpu_seconds phases slurm_job_id",
    )
    proposal, row = validate_request(request)
    require(child["request_sha256"] == contract.sha(contract.encoded(request)))
    calls = integer(child["optimization_calls"], 0, 1)
    require(
        child["failure_code"]
        in {
            None,
            "worker_read_setup_failed",
            "worker_optimization_failed",
            "worker_terminal_inspection_failed",
            "worker_cleanup_failed",
            "worker_log_seal_failed",
            "worker_source_changed",
        }
    )
    require(type(child["original_lp_unchanged"]) is bool)
    require(
        isinstance(child["slurm_job_id"], str)
        and re.fullmatch(r"[0-9]{1,20}", child["slurm_job_id"])
    )
    keys(child["affinity"], "observed_cpu_ids bound_cpu_ids physical_cores")
    affinity = child["affinity"]
    require(integer(affinity["physical_cores"]) == 16)
    for name in ("observed_cpu_ids", "bound_cpu_ids"):
        values = affinity[name]
        require(isinstance(values, list) and values == sorted(set(values)))
        for value in values:
            integer(value)
    require(
        len(affinity["bound_cpu_ids"]) == 16
        and set(affinity["bound_cpu_ids"]) <= set(affinity["observed_cpu_ids"])
    )
    integer(child["peak_rss_bytes"])
    contract.number(child["current_process_cpu_seconds"])
    validate_phases(child["phases"])
    require(
        sum(p["process_cpu_seconds"] for p in child["phases"])
        <= child["current_process_cpu_seconds"] + 1e-9
    )
    if child["effective_parameters"] is not None:
        require(child["effective_parameters"] == expected_parameters(request, row))
        require(
            all(type(v) in (int, float) for v in child["effective_parameters"].values())
        )
        defaults = child["algorithm_defaults"]
        require(
            isinstance(defaults, dict)
            and set(defaults)
            == set(proposal["controls"]["default_parameters_observed"])
        )
        require(set(DEFAULTS) == set(defaults))
        for name, values in defaults.items():
            keys(values, "effective version_default")
            require(values["effective"] == values["version_default"] == DEFAULTS[name])
            for value in values.values():
                if value != "positive_infinity":
                    contract.number(value, nonnegative=False)
    else:
        require(child["algorithm_defaults"] is None and calls == 0)
    if child["gurobi_log"] is not None:
        log_binding(child["gurobi_log"])
    if child["result"] is not None:
        require(calls == 1)
        validate_result(child["result"], request, row)
        require(child["result"]["phases"] == child["phases"])
    if child["failure_code"] is None:
        require(child["original_lp_unchanged"] and calls == 1)
        require(child["result"] is not None and child["gurobi_log"] is not None)
        require(
            [p["phase"] for p in child["phases"]]
            == ["read_setup", "optimization", "cleanup"]
        )
        require(not any(p["call_failed"] for p in child["phases"]))
    strict_payload(contract.encoded(child))


def supervise_process(command, console, deadline):
    """Wait only in the allocated batch task; never an interactive status loop."""
    with Path(console).open("xb") as stream:
        process = subprocess.Popen(
            command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
        )
        watchdog = False
        try:
            code = process.wait(timeout=deadline)
        except subprocess.TimeoutExpired:
            watchdog = True
            # Child PID is also its fresh process-group ID, never the caller's.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                code = process.wait(timeout=GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                code = process.wait(timeout=GRACE_SECONDS)
        except BaseException:
            # A Python-level interruption must not leave an unbounded child.
            # An OS kill of the supervisor itself may leave no final receipt;
            # retained claims prohibit retry and require external reconciliation.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=GRACE_SECONDS)
            raise
        stream.flush()
        os.fsync(stream.fileno())
    return code, watchdog


def supervise_one(request, output):
    """Future approved operator workflow entry: exactly one persistent attempt."""
    output = qualify_execution(request, output, fresh=True)
    claim_authorization(request, output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_json(output / "request.private.json", request)
    request_sha = contract.sha(contract.encoded(request))
    command = [
        sys.executable,
        "-B",
        "-c",
        "import sys;sys.path.insert(0,sys.argv[1]);import isolated_attempt_worker as w;w.internal_child(*sys.argv[2:])",
        str(Path(__file__).parent),
        str(output),
        request_sha,
    ]
    started = time.perf_counter()
    child = None
    receipt = {
        "schema_version": 1,
        "request_sha256": request_sha,
        "status": "process_failure",
        "failure_code": "child_process_failed",
        "child_exit_code": None,
        "watchdog_triggered": False,
        "supervisor_wall_seconds": 0,
        "console_log": None,
        "child_report_sha256": None,
        "child": None,
        "optimization_calls_known": None,
        "maximum_authorized_optimization_calls": 1,
        "pause_remaining_matrix": True,
        "log_text_included": False,
        "installed_callback_execution_qualified": False,
        "scheduler_affinity_memory_qualified": False,
        "scientific_reporting_eligible": False,
    }
    try:
        code, timed_out = supervise_process(
            command, output / "console.private.log", request["child_deadline_seconds"]
        )
        receipt.update(child_exit_code=code, watchdog_triggered=timed_out)
        receipt["console_log"] = contract.seal_closed_log(
            output / "console.private.log"
        )
        if timed_out:
            receipt.update(
                status="watchdog_timeout", failure_code="child_deadline_exceeded"
            )
        elif code == 0:
            raw = read_bytes(output / "child.private.json")
            child = strict_payload(raw)
            validate_child(child, request)
            if child["gurobi_log"] is not None:
                require(
                    contract.seal_closed_log(output / "gurobi.private.log")
                    == child["gurobi_log"]
                )
            receipt.update(
                child=child,
                child_report_sha256=contract.sha(raw),
                optimization_calls_known=child["optimization_calls"],
            )
            success = child["failure_code"] is None and child["result"]["stop"] in {
                "gap_target",
                "time_limit",
            }
            receipt.update(
                status="completed" if success else "worker_stopped",
                failure_code=None if success else "worker_or_resource_stop",
                pause_remaining_matrix=not success,
            )
    except Exception:
        receipt.update(
            status="process_failure",
            failure_code="supervisor_or_receipt_validation_failed",
            child=None,
            child_report_sha256=None,
            optimization_calls_known=None,
            pause_remaining_matrix=True,
        )
    receipt["supervisor_wall_seconds"] = time.perf_counter() - started
    validate_receipt(receipt, request)
    write_json(output / "request.json", request)
    write_json(output / "attempt_receipt.json", receipt)
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        for name in PUBLIC[:2]:
            stream.write(
                (adapter.screen.digest(output / name) + "  " + name + "\n").encode()
            )
        stream.flush()
        os.fsync(stream.fileno())
    return receipt


def validate_receipt(receipt, request):
    keys(
        receipt,
        "schema_version request_sha256 status failure_code child_exit_code watchdog_triggered "
        "supervisor_wall_seconds console_log child_report_sha256 child optimization_calls_known "
        "maximum_authorized_optimization_calls pause_remaining_matrix log_text_included "
        "installed_callback_execution_qualified scheduler_affinity_memory_qualified scientific_reporting_eligible",
    )
    validate_request(request)
    require(integer(receipt["schema_version"]) == 1)
    require(receipt["request_sha256"] == contract.sha(contract.encoded(request)))
    require(integer(receipt["maximum_authorized_optimization_calls"]) == 1)
    for flag in (
        "log_text_included",
        "installed_callback_execution_qualified",
        "scheduler_affinity_memory_qualified",
        "scientific_reporting_eligible",
    ):
        require(receipt[flag] is False)
    require(
        type(receipt["pause_remaining_matrix"]) is bool
        and type(receipt["watchdog_triggered"]) is bool
    )
    code = receipt["child_exit_code"]
    require(code is None or type(code) is int)
    contract.number(receipt["supervisor_wall_seconds"])
    if receipt["console_log"] is not None:
        log_binding(receipt["console_log"])
    status = receipt["status"]
    require(
        status in {"completed", "worker_stopped", "watchdog_timeout", "process_failure"}
    )
    if status in {"completed", "worker_stopped"}:
        require(
            code == 0
            and not receipt["watchdog_triggered"]
            and receipt["console_log"] is not None
        )
        child = receipt["child"]
        validate_child(child, request)
        require(receipt["child_report_sha256"] == contract.sha(contract.encoded(child)))
        require(receipt["optimization_calls_known"] == child["optimization_calls"])
        success = child["failure_code"] is None and child["result"]["stop"] in {
            "gap_target",
            "time_limit",
        }
        require((status == "completed") == success)
        require(receipt["pause_remaining_matrix"] is not success)
        require(
            receipt["failure_code"] == (None if success else "worker_or_resource_stop")
        )
    else:
        require(receipt["pause_remaining_matrix"])
        require(receipt["child"] is None and receipt["child_report_sha256"] is None)
        require(receipt["optimization_calls_known"] is None)
        if status == "watchdog_timeout":
            require(receipt["watchdog_triggered"] and type(code) is int)
            require(receipt["failure_code"] == "child_deadline_exceeded")
        else:
            require(
                receipt["failure_code"]
                in {"child_process_failed", "supervisor_or_receipt_validation_failed"}
            )
    strict_payload(contract.encoded(receipt))


def validate_public_payloads(payloads):
    require(set(payloads) == set(PUBLIC))
    manifest = "".join(
        contract.sha(payloads[n]) + "  " + n + "\n" for n in PUBLIC[:2]
    ).encode()
    require(payloads["SHA256SUMS.txt"] == manifest)
    request, receipt = (strict_payload(payloads[n]) for n in PUBLIC[:2])
    validate_receipt(receipt, request)
    return receipt


def validate_directory(directory, private=False):
    directory = Path(directory)
    payloads = {name: read_bytes(directory / name) for name in PUBLIC}
    receipt = validate_public_payloads(payloads)
    if private:
        if receipt["console_log"] is not None:
            require(
                contract.seal_closed_log(directory / "console.private.log")
                == receipt["console_log"]
            )
        if receipt["child"] is not None:
            require(
                read_bytes(directory / "child.private.json")
                == contract.encoded(receipt["child"])
            )
            if receipt["child"]["gurobi_log"] is not None:
                require(
                    contract.seal_closed_log(directory / "gurobi.private.log")
                    == receipt["child"]["gurobi_log"]
                )
    return payloads, receipt


def validate_archive(package, expected_sha):
    """Review an externally hash-pinned, allowlisted archive without extraction."""
    hexadecimal(expected_sha)
    raw = read_bytes(package, 16 * 1024 * 1024)
    require(contract.sha(raw) == expected_sha)
    limit = len(PUBLIC) * MAX_JSON + 64 * 1024
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded = stream.read(limit + 1)
    require(len(decoded) <= limit)
    payloads = {}
    end = 0
    with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:") as stream:
        for member in stream:
            require(member.name in PUBLIC and member.name not in payloads)
            require(member.isfile() and not member.issym() and not member.islnk())
            require(
                0 <= member.size <= MAX_JSON
                and not member.sparse
                and not member.pax_headers
            )
            payloads[member.name] = stream.extractfile(member).read(MAX_JSON + 1)
            require(len(payloads[member.name]) == member.size)
            end = member.offset_data + ((member.size + 511) // 512) * 512
    require(len(decoded) >= end + 1024 and not any(decoded[end:]))
    return validate_public_payloads(payloads)


def export_receipt(directory, output):
    # Export only from the retained private attempt, re-sealing its closed logs.
    # No raw log, LP, vector, license string or process exception enters archive.
    payloads, receipt = validate_directory(directory, private=True)
    output = Path(output).absolute()
    source = Path(__file__).resolve().parents[2]
    require(not output.exists() and not output.resolve().is_relative_to(source))
    require(not output.resolve().is_relative_to(Path(directory).resolve()))
    if socket.gethostname().split(".")[0] == "dgx-dasci":
        require(
            output.resolve() == output
            and output.parent.resolve().is_relative_to(adapter.EVIDENCE_ROOT)
        )
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive = output / "isolated_attempt_evidence.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        for name in PUBLIC:
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(payloads[name]), 0o600, 0
            stream.addfile(info, io.BytesIO(payloads[name]))
    with (output / "PACKAGE_SHA256.txt").open("xb") as stream:
        stream.write(
            (adapter.screen.digest(archive) + "  " + archive.name + "\n").encode()
        )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "export"))
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--directory", type=Path)
    inputs.add_argument("--package", type=Path)
    parser.add_argument("--expected-package-sha")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "export":
            require(
                args.output is not None
                and args.directory is not None
                and args.expected_package_sha is None
            )
            checked = export_receipt(args.directory, args.output)
        else:
            require(args.output is None)
            if args.package is not None:
                checked = validate_archive(args.package, args.expected_package_sha)
            else:
                require(args.expected_package_sha is None)
                _, checked = validate_directory(args.directory)
        print("ISOLATED_ATTEMPT_RECEIPT=" + checked["status"], flush=True)
        print("NO_NEW_OPTIMIZATION_NO_SUBMISSION_NO_MERGE", flush=True)
    except Exception:
        print("ISOLATED_ATTEMPT_VALIDATION_FAILED_PRESERVE_INPUT", flush=True)
        raise SystemExit(1) from None
