"""Bind bounded CPU telemetry to Gurobi callbacks; CLI preflight never optimizes.

No licensed solve or scheduler submission interface is provided here.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import subprocess
import sys
import time
from pathlib import Path

import cpu_comparison_contract as contract
import pr66_thread_pilot as screen
from publish_mvp2_baseline import PRIVATE

RAW_ROOT = Path("/raid/vrcelestino/data/cfl-gurobi-gnn/data/raw/MILPBench/CFL")
EVIDENCE_ROOT = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
SYMBOLS = (
    "MIP",
    "MIPSOL",
    "RUNTIME",
    "MIP_OBJBST",
    "MIP_OBJBND",
    "MIP_NODCNT",
    "MIPSOL_OBJBST",
    "MIPSOL_OBJBND",
    "MIPSOL_NODCNT",
)
DEPENDENCIES = (
    "gurobi_callback_adapter.py",
    "cpu_comparison_contract.py",
    "pr66_thread_pilot.py",
    "collect_class_statistics.py",
    "collect_computational_ledger.py",
    "collect_pr66_log_phases.py",
    "publish_mvp2_baseline.py",
)


def finite_bound(value, infinity):
    """Solver infinity/sentinel is unavailable; NaN and nonnumeric data fail."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("numeric_solver_bound_required")
    if math.isnan(value):
        raise ValueError("nan_solver_bound")
    return None if not math.isfinite(value) or abs(value) >= infinity else float(value)


def relative_gap(primal, dual):
    if primal is None:
        return None, "no_finite_incumbent"
    if dual is None:
        return None, "no_finite_bound"
    # Parameter/attribute documentation has different zero-objective wording.
    # Do not declare a zero-objective crossing before installed qualification.
    if primal == 0:
        return None, "zero_objective_unqualified"
    gap = abs(primal - dual) / abs(primal)
    return (
        (gap, "finite_bound_formula")
        if math.isfinite(gap)
        else (None, "unbounded_relative_gap")
    )


def callback_symbols(gp):
    symbols = {name: getattr(gp.GRB.Callback, name) for name in SYMBOLS}
    if any(type(v) is not int or v < 0 for v in symbols.values()) or len(
        set(symbols.values())
    ) != len(symbols):
        raise ValueError("invalid_callback_symbols")
    infinity = contract.number(gp.GRB.INFINITY)
    if infinity <= 0:
        raise ValueError("positive_solver_infinity_required")
    return symbols, infinity


class GurobiCallbackAdapter:
    """Observe best-known bounds, not candidate vectors or root relaxations.

    The caller owns one fresh model, closes the log and binds input/parameter
    identities. Construction and CLI preflight install/execute no callback.
    """

    def __init__(
        self, gp, telemetry, wall_clock=time.perf_counter, cpu_clock=time.process_time
    ):
        if not isinstance(telemetry, contract.Telemetry):
            raise ValueError("contract_telemetry_required")
        self.symbols, self.infinity = callback_symbols(gp)
        self.telemetry = telemetry
        self.wall_clock, self.cpu_clock = wall_clock, cpu_clock
        self.last_seen = self.last_regular = None
        self.failed = False
        self.failure_code = None
        self.termination_requested = False
        self.counters = {
            k: 0
            for k in (
                "mip_calls",
                "mipsol_calls",
                "regular_samples",
                "mipsol_samples",
                "rate_skipped",
                "missing_gap_samples",
                "zero_objective_samples",
            )
        }
        self.wall_seconds = self.cpu_seconds = 0.0
        self.finished = False

    def _fail(self, model, code):
        self.failed = True
        self.failure_code = code
        try:
            model.terminate()
            self.termination_requested = True
        except Exception:
            self.termination_requested = False
        # Never print exception messages: they may contain license/private data.

    def __call__(self, model, where):
        s = self.symbols
        if where not in (s["MIP"], s["MIPSOL"]):
            return
        if self.failed:
            return
        if self.finished:
            self._fail(model, "callback_after_finalization")
            return
        try:
            wall, cpu = (
                contract.number(self.wall_clock()),
                contract.number(self.cpu_clock()),
            )
        except Exception:
            self._fail(model, "callback_clock_failure")
            return
        try:
            runtime = contract.number(model.cbGet(s["RUNTIME"]))
            if self.last_seen is not None and runtime < self.last_seen:
                raise ValueError("nonmonotone_callback_runtime")
            self.last_seen = runtime
            incumbent_event = where == s["MIPSOL"]
            self.counters["mipsol_calls" if incumbent_event else "mip_calls"] += 1
            if (
                not incumbent_event
                and self.last_regular is not None
                and runtime - self.last_regular < 1
            ):
                self.counters["rate_skipped"] += 1
                return
            prefix = "MIPSOL" if incumbent_event else "MIP"
            # MIPSOL_OBJ is a presented candidate, not necessarily an improvement.
            # SOLCNT is a callback count, not evidence of an accepted incumbent.
            primal = finite_bound(model.cbGet(s[prefix + "_OBJBST"]), self.infinity)
            dual = finite_bound(model.cbGet(s[prefix + "_OBJBND"]), self.infinity)
            nodes = contract.number(model.cbGet(s[prefix + "_NODCNT"]))
            gap, state = relative_gap(primal, dual)
            self.telemetry.observe(runtime, primal, dual, gap, nodes)
            self.counters[
                "mipsol_samples" if incumbent_event else "regular_samples"
            ] += 1
            if gap is None:
                self.counters["missing_gap_samples"] += 1
            if state == "zero_objective_unqualified":
                self.counters["zero_objective_samples"] += 1
            if not incumbent_event:
                self.last_regular = runtime
        except Exception:
            self._fail(model, "callback_observation_failure")
        finally:
            try:
                self.wall_seconds += contract.number(self.wall_clock() - wall)
                self.cpu_seconds += contract.number(self.cpu_clock() - cpu)
            except Exception:
                self._fail(model, "callback_clock_failure")

    def finish_model(self, model):
        """Outside optimize: terminal MIPGap attribute is reported separately."""
        if self.finished:
            raise ValueError("adapter_already_finished")
        count = model.SolCount
        status = model.Status
        if type(count) is not int or count < 0 or type(status) is not int:
            raise ValueError("integer_terminal_status_and_count_required")
        runtime = contract.number(model.Runtime)
        if self.last_seen is not None and runtime < self.last_seen:
            raise ValueError("terminal_runtime_precedes_callback")
        primal = finite_bound(model.ObjVal, self.infinity) if count else None
        dual = finite_bound(model.ObjBound, self.infinity)
        nodes = contract.number(model.NodeCount)
        gap = finite_bound(model.MIPGap, self.infinity) if count else None
        if gap is not None and (gap < 0 or primal is None or dual is None):
            raise ValueError("inconsistent_terminal_gap")
        formula, state = relative_gap(primal, dual)
        if (
            gap is not None
            and formula is not None
            and not math.isclose(gap, formula, abs_tol=1e-10, rel_tol=1e-10)
        ):
            raise ValueError("terminal_gap_formula_mismatch")
        if primal == 0:
            gap = None
        stop = (
            "worker_failure"
            if self.failed
            else {9: "time_limit", 17: "memory_limit"}.get(status, "other_stop")
        )
        if (
            not self.failed
            and status == 2
            and gap is not None
            and gap <= self.telemetry.stopping_gap
        ):
            stop = "gap_target"
        result = self.telemetry.finish(stop, runtime, primal, dual, gap, nodes)
        self.finished = True
        result["gurobi_callback"] = {
            "schema_version": 1,
            "policy": "best_known_bounds_mip_at_most_once_per_second_plus_all_mipsol_and_terminal",
            "best_bound_scope": "callback_bounds_not_terminal_rounded_model_bound",
            "candidate_vectors_read": False,
            "node_relaxations_read": False,
            "algorithm_parameters_changed_by_callback": False,
            "counters": dict(self.counters),
            "callback_external_wall_seconds": self.wall_seconds,
            "callback_current_process_cpu_seconds": self.cpu_seconds,
            "overhead_subtracted_from_solver_runtime": False,
            "failed": self.failed,
            "failure_code": self.failure_code,
            "termination_requested_for_failure": self.termination_requested,
            "terminal_status": status,
            "terminal_solution_count": count,
            "terminal_gap_state": state,
            "terminal_mip_gap_attribute": finite_bound(model.MIPGap, self.infinity)
            if count
            else None,
            "zero_objective_gap_qualified": False,
            "installed_callback_execution_qualified": False,
        }
        if PRIVATE.search(contract.encoded(result).decode()):
            raise ValueError("private_marker_in_adapter_output")
        return result


def source_config(proposal, row):
    controls = proposal["controls"]
    config = {
        "gurobi_version": controls["gurobi_version"],
        "default_parameters_observed": controls["default_parameters_observed"],
        "objective_sense_policy": "historical_cfl_minimization_in_memory_only",
        "source_objective_sense": controls["source_objective_sense"],
        "effective_objective_sense": controls["effective_objective_sense"],
        "seed": row["seed"],
        "time_limit_seconds": row["optimization_limit_seconds"],
        "mip_gap_relative": row["stopping_gap_relative"],
        "soft_memory_limit_decimal_gb": controls["soft_memory_limit_decimal_gb"],
    }
    return config


def runtime_preflight(gp, proposal, raw_root):
    """Read each original once, reset/check all cap controls, never optimize."""
    if list(gp.gurobi.version()) != [13, 0, 1]:
        raise ValueError("gurobi_version_changed")
    symbols, _ = callback_symbols(gp)
    original_plan = json.loads(contract.original.public_receipts()["pilot_plan.json"])
    result = []
    for original in original_plan["models"]:
        path = screen.frozen_source(raw_root, original)
        attempts = [
            r
            for r in proposal["attempts"]
            if r["source_instance_id"] == original["source_instance_id"]
        ]
        config = source_config(proposal, attempts[0])
        with gp.Env(empty=True) as env:
            env.setParam("OutputFlag", 0)
            env.setParam("ThreadLimit", 16)
            env.start()
            with gp.read(str(path), env=env) as model:
                senses = screen.prepare_original_model(model, config)
                if not all(
                    callable(getattr(model, name, None))
                    for name in ("cbGet", "terminate", "optimize")
                ):
                    raise ValueError("callback_model_methods_missing")
                parameters = []
                for row in attempts:
                    config = source_config(proposal, row)
                    values, defaults = screen.configure_model(
                        model, config, row["threads"]
                    )
                    parameters.append(
                        {
                            "attempt_id": row["attempt_id"],
                            "effective_parameters": values,
                            "algorithm_defaults": defaults,
                        }
                    )
                result.append(
                    {
                        "source_instance_id": original["source_instance_id"],
                        "original_lp_sha256": original["original_lp_sha256"],
                        **senses,
                        "num_variables": model.NumVars,
                        "num_constraints": model.NumConstrs,
                        "configured_attempts": parameters,
                    }
                )
        if screen.digest(path) != original["original_lp_sha256"]:
            raise ValueError("source_changed_during_preflight")
    return {
        "gurobi_version": [13, 0, 1],
        "callback_symbols": symbols,
        "models": result,
        "models_read": 2,
        "parameter_configurations_checked": 10,
        "optimization_runs": 0,
    }


def qualify_host(source_sha, output):
    if sys.platform != "linux" or socket.gethostname().split(".")[0] != "dgx-dasci":
        raise ValueError("canonical_dasci_host_required")
    source = Path(__file__).resolve().parents[2]
    if not source.is_relative_to(Path("/raid/vrcelestino/data")):
        raise ValueError("physical_raid_source_required")
    cmd = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
    head = (
        subprocess.check_output([*cmd, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        .decode()
        .strip()
    )
    if head != source_sha or subprocess.check_output(
        [*cmd, "status", "--porcelain", "--untracked-files=no"],
        stderr=subprocess.DEVNULL,
    ):
        raise ValueError("pinned_clean_source_required")
    output = Path(output).absolute()
    if (
        output.exists()
        or not output.parent.resolve().is_relative_to(EVIDENCE_ROOT.resolve())
        or output.resolve().is_relative_to(source)
    ):
        raise ValueError("fresh_raid_output_outside_source_required")
    if RAW_ROOT.resolve(strict=True) != RAW_ROOT:
        raise ValueError("canonical_raw_root_required")
    return output


def preflight(source_sha, output):
    output = qualify_host(source_sha, output)
    proposal = contract.compile_proposal()
    # The proposal is immutable/disabled: checking installed symbols is not an
    # approval, live callback test, memory/affinity qualification or solve.
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema_version": 1,
        "source_commit": source_sha,
        "proposal_sha256": proposal["proposal_sha256"],
        "dependency_sha256": {
            name: screen.digest(Path(__file__).parent / name) for name in DEPENDENCIES
        },
        "host_policy": "canonical_dgx_dasci_physical_raid",
        "status": "failed",
        "failure_code": None,
        "optimization_runs": 0,
        "training_runs": 0,
        "execution_enabled": False,
        "resource_budget_approved": False,
        "installed_callback_execution_qualified": False,
        "scheduler_affinity_memory_qualified": False,
        "scientific_reporting_eligible": False,
    }
    try:
        gp = screen.licensed_runtime(proposal["controls"])
        receipt["runtime_preflight"] = runtime_preflight(gp, proposal, RAW_ROOT)
        receipt["status"] = "passed_no_optimization"
    except Exception:
        receipt["failure_code"] = "installed_runtime_preflight_failed"
    payload = contract.encoded(receipt)
    if PRIVATE.search(payload.decode()):
        raise ValueError("private_marker_in_preflight_export")
    with (output / "preflight_receipt.json").open("xb") as stream:
        stream.write(payload)
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write((contract.sha(payload) + "  preflight_receipt.json\n").encode())
    print("GUROBI_CALLBACK_PREFLIGHT=" + receipt["status"], flush=True)
    print("RECEIPT_SHA256=" + contract.sha(payload), flush=True)
    print("NO_OPTIMIZATION_NO_CALLBACK_EXECUTION_NO_SUBMISSION_NO_MERGE", flush=True)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight",))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        checked = preflight(args.source_sha, args.output)
    except Exception:
        print("PREFLIGHT_SAFETY_GATE_FAILED_NO_OPTIMIZATION", flush=True)
        sys.exit(1)
    sys.exit(0 if checked["status"] == "passed_no_optimization" else 1)
