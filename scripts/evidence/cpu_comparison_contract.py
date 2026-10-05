"""Compile a disabled CPU comparison proposal and validate bounded telemetry.

No solver imports, optimizer calls, scheduler queries or submission interface.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from contextlib import contextmanager
from pathlib import Path

import collect_pr66_log_phases as original
from publish_mvp2_baseline import PRIVATE

PROTOCOL = "sprint_b_same_pair_defaults_comparison_proposal_v1"
CAPS = (1, 2, 4, 8, 16)
TARGETS = (0.1, 0.05, 0.01)
MODEL_IDS = ("CFL_easy_instance_17", "CFL_medium_instance_1")
STOPS = {"gap_target", "time_limit", "memory_limit", "worker_failure", "other_stop"}
MAX_SAMPLES = 10000
MAX_LOG_BYTES = 64 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def number(value, nonnegative=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("finite_numeric_observation_required")
    if not math.isfinite(value) or (nonnegative and value < 0):
        raise ValueError("finite_numeric_observation_required")
    return float(value)


def compile_proposal():
    """Derive cohort identities from pinned original receipts, never outcomes."""
    payloads = original.public_receipts()
    plan = json.loads(payloads["pilot_plan.json"])
    if tuple(row["source_instance_id"] for row in plan["models"]) != MODEL_IDS or any(
        row["role"] != "train" for row in plan["models"]
    ):
        raise ValueError("original_pilot_cohort_changed")
    models, attempts = [], []
    for source in plan["models"]:
        parent = source["source_instance_id"]
        difficulty = source["difficulty"]
        # Versioned SHA256 ordering avoids depending on a Python RNG version.
        # Freeze every resulting order, including any accidental ascending one.
        order = sorted(
            CAPS, key=lambda cap: sha(f"{PROTOCOL}|{parent}|42|{cap}".encode())
        )
        models.append(
            {
                key: source[key]
                for key in (
                    "source_instance_id",
                    "difficulty",
                    "role",
                    "original_lp_sha256",
                )
            }
        )
        for ordinal, cap in enumerate(order):
            attempts.append(
                {
                    "attempt_id": f"{difficulty}-seed42-threads{cap}",
                    "source_instance_id": parent,
                    "original_lp_sha256": source["original_lp_sha256"],
                    "seed": 42,
                    "threads": cap,
                    "within_parent_order": ordinal,
                    "optimization_limit_seconds": 3600,
                    "stopping_gap_relative": 0.01 if difficulty == "easy" else 0.1,
                }
            )
    proposal = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "stage": "prospective_development_comparison_not_population_scaling",
        "execution_enabled": False,
        "resource_budget_approved": False,
        "licensed_worker_adapter_implemented": False,
        "merged_code_is_not_submission_authorization": True,
        "original_screen_plan_sha256": original.PLAN_SHA,
        "original_role_plan_sha256": plan["role_plan_sha256"],
        "original_role_contract_sha256": plan["role_plan_contract_sha256"],
        "models": models,
        "attempts": attempts,
        "controls": {
            "cluster": "dgx-dasci",
            "shared_node": True,
            "requested_physical_cores": 16,
            "scheduler_memory_gib": 64,
            "soft_memory_limit_decimal_gb": 48,
            "thread_limit": 16,
            "gurobi_version": [13, 0, 1],
            "algorithm_policy": plan["config"]["algorithm_policy"],
            "default_parameters_observed": plan["config"][
                "default_parameters_observed"
            ],
            "source_objective_sense": "MAXIMIZE",
            "effective_objective_sense": "MINIMIZE",
            "stored_lp_modified": False,
            "warm_start": False,
            "gpu": False,
            "exclusive": False,
            "concurrent_attempts": 1,
            "fresh_model_and_environment": True,
        },
        "order_policy": "ascending_sha256_protocol_parent_seed_cap_within_parent",
        "parent_block_order": list(MODEL_IDS),
        "outcomes": {
            "primary": [
                "first_sampled_time_to_gap_10pct",
                "terminal_gap_at_actual_stop",
                "allocated_logical_cpu_hours",
                "reported_cpu_hours",
                "worker_peak_rss_bytes",
            ],
            "secondary_gap_targets": list(TARGETS[1:]),
            "fixed_budget_terminal_quality_comparison": False,
            "time_to_target_clock": "solver_runtime_observation",
            "true_continuous_first_crossing_known": False,
            "parent_is_independent_unit": True,
            "seed_replications_executed": False,
            "callback_sampling_proposal": "at_most_one_regular_sample_per_solver_second_plus_new_incumbent_and_terminal_events",
        },
        "prospective_budget": {
            "attempts": 10,
            "maximum_optimization_seconds": 36000,
            "configured_cap_optimization_hour_ceiling": 62,
            "scheduler_layout": "two_parent_blocks_five_serial_attempts_each",
            "proposed_jobs": 2,
            "proposed_minutes_per_job": 330,
            "proposed_child_timeout_seconds": 3780,
            "parent_block_other_overhead_allowance_seconds": 900,
            "physical_core_reservation_hour_ceiling_if_16_allocated": 176,
            "logical_cpu_hour_ceiling_if_32_allocated": 352,
            "actual_alloccpus_not_yet_observed": True,
            "actual_cost_unknown": True,
        },
        "required_gates": [
            "exact_head_four_arm_ci_and_independent_review",
            "explicit_resource_budget_and_submission_approval",
            "licensed_hpc_worker_callback_and_fault_qualification",
            "scheduler_walltime_and_affinity_support",
            "original_role_and_lp_hash_revalidation",
            "runtime_load_and_higher_budget_memory_safety_review",
        ],
        "followup_seeds": {
            "proposed": [43, 44],
            "enabled": False,
            "separate_budget_required": True,
            "review_not_conditioned_on_favourable_effect": True,
        },
        "scientific_reporting_eligible": False,
        "optimization_runs": 0,
        "training_runs": 0,
        "compiler_sha256": sha(Path(__file__).read_bytes()),
    }
    proposal["proposal_sha256"] = sha(encoded(proposal))
    return proposal


class Telemetry:
    """Caller-supplied observations with separate clocks, not a Gurobi adapter.

    No callback is installed here. A future licensed worker must normalize
    unavailable/sentinel values, bind provenance and qualify callback overhead.
    """

    def __init__(self, budget_seconds, stopping_gap, max_samples=MAX_SAMPLES):
        self.budget = number(budget_seconds)
        self.stopping_gap = number(stopping_gap)
        if self.budget <= 0 or self.stopping_gap not in TARGETS:
            raise ValueError("unsupported_observation_contract")
        if (
            isinstance(max_samples, bool)
            or not isinstance(max_samples, int)
            or not 1 <= max_samples <= MAX_SAMPLES
        ):
            raise ValueError("bounded_sample_limit_required")
        self.max_samples = max_samples
        self.samples = []
        self.crossings = {}
        self.dropped_samples = 0
        self.phases = []
        self.active = None
        self.finished = False
        self.last_runtime = None

    def observe(
        self, runtime, primal=None, dual=None, gap=None, nodes=None, terminal=False
    ):
        if self.finished:
            raise ValueError("telemetry_already_finished")
        runtime = number(runtime)
        if self.last_runtime is not None and runtime < self.last_runtime:
            raise ValueError("nonmonotone_solver_runtime")
        if type(terminal) is not bool:
            raise ValueError("boolean_terminal_flag_required")
        value = {"solver_runtime_seconds": runtime, "terminal": terminal}
        for key, raw in (
            ("primal", primal),
            ("dual", dual),
            ("gap_relative", gap),
            ("node_count", nodes),
        ):
            value[key] = (
                None if raw is None else number(raw, key not in {"primal", "dual"})
            )
        if gap is not None and (primal is None or dual is None):
            raise ValueError("gap_requires_finite_primal_and_dual")
        if gap is not None:
            for target in TARGETS:
                if gap <= target and target not in self.crossings:
                    self.crossings[target] = {
                        "solver_runtime_seconds": runtime,
                        "previous_sample_runtime_seconds": self.last_runtime,
                        "observed_within_budget": runtime <= self.budget,
                    }
        self.last_runtime = runtime
        if len(self.samples) < self.max_samples:
            self.samples.append(value)
        else:
            self.dropped_samples += 1
        return value

    @contextmanager
    def phase(self, name, wall_clock=time.perf_counter, cpu_clock=time.process_time):
        if (
            self.finished
            or self.active is not None
            or name not in {"read_setup", "optimization", "cleanup"}
            or any(row["phase"] == name for row in self.phases)
        ):
            raise ValueError("disjoint_unique_phase_required")
        wall, cpu = number(wall_clock()), number(cpu_clock())
        self.active = name
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            self.active = None
            self.phases.append(
                {
                    "phase": name,
                    "external_wall_seconds": number(wall_clock() - wall),
                    "process_cpu_seconds": number(cpu_clock() - cpu),
                    "call_failed": failed,
                }
            )

    def finish(self, stop, runtime, primal=None, dual=None, gap=None, nodes=None):
        if self.active is not None or stop not in STOPS:
            raise ValueError("supported_terminal_stop_required")
        if stop == "gap_target" and (gap is None or number(gap) > self.stopping_gap):
            raise ValueError("terminal_gap_stop_inconsistent")
        terminal = self.observe(runtime, primal, dual, gap, nodes, terminal=True)
        result = []
        for target in TARGETS:
            observed = self.crossings.get(target)
            if observed is not None:
                row = {"state": "observed", **observed}
            else:
                state = {
                    "time_limit": "right_censored",
                    "gap_target": "not_observed_before_planned_gap_stop",
                    "memory_limit": "resource_stop",
                    "worker_failure": "worker_failure",
                    "other_stop": "other_stop",
                }[stop]
                row = {
                    "state": state,
                    "solver_runtime_seconds": None,
                    "observation_end_runtime_seconds": terminal[
                        "solver_runtime_seconds"
                    ],
                }
            result.append({"target_gap_relative": target, **row})
        self.finished = True
        return {
            "schema_version": 1,
            "stop": stop,
            "terminal": terminal,
            "optimization_budget_seconds": self.budget,
            "stopping_gap_relative": self.stopping_gap,
            "time_limit_overshoot_seconds": max(0, runtime - self.budget),
            "first_sampled_gap_observations": result,
            "samples": list(self.samples),
            "dropped_sample_count": self.dropped_samples,
            "sampling_policy": "caller_supplied_events_not_continuous_monitoring",
            "true_first_crossings_qualified": False,
            "phases": list(self.phases),
            "root_tree_phase_costs_qualified": False,
            "process_cpu_scope": "current_process_only_not_scheduler_aggregate",
            "primal_integral_qualified": False,
            "scientific_reporting_eligible": False,
        }


def paired_speedup(baseline, comparison, threads):
    """Only qualified same-parent/seed/profile/target observations are paired."""
    for row in (baseline, comparison):
        if (
            row.get("state") != "observed"
            or row.get("observed_within_budget") is not True
        ):
            return {
                "speedup": None,
                "parallel_efficiency": None,
                "reason": "target_not_observed_within_budget",
            }
        number(row["solver_runtime_seconds"])
        budget = number(row["optimization_budget_seconds"])
        if budget <= 0 or row["solver_runtime_seconds"] > budget:
            raise ValueError("observed_within_budget_flag_inconsistent")
        if (
            type(row.get("seed")) is not int
            or row["seed"] < 0
            or row.get("target_gap_relative") not in TARGETS
        ):
            raise ValueError("qualified_seed_and_target_required")
        for key in ("original_lp_sha256", "comparison_profile_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", row.get(key, "")):
                raise ValueError("qualified_pair_identity_required")
    keys = (
        "original_lp_sha256",
        "comparison_profile_sha256",
        "seed",
        "target_gap_relative",
        "optimization_budget_seconds",
    )
    if any(baseline.get(k) is None or baseline[k] != comparison.get(k) for k in keys):
        raise ValueError("mismatched_paired_observations")
    if (
        type(threads) is not int
        or threads not in CAPS
        or type(baseline.get("threads")) is not int
        or type(comparison.get("threads")) is not int
        or baseline.get("threads") != 1
        or comparison.get("threads") != threads
    ):
        raise ValueError("paired_thread_caps_required")
    first, other = (
        baseline["solver_runtime_seconds"],
        comparison["solver_runtime_seconds"],
    )
    if first <= 0 or other <= 0:
        return {
            "speedup": None,
            "parallel_efficiency": None,
            "reason": "positive_observed_durations_required",
        }
    speedup = first / other
    return {
        "speedup": speedup,
        "parallel_efficiency": speedup / threads,
        "reason": "sampled_same_parent_seed_profile_target_pair",
    }


def seal_closed_log(path):
    """Caller closes the writer first; read bounded bytes, export only a digest.

    A hash is an execution-receipt binding, not a signed authenticity certificate.
    A future worker must persist this immediately in its own attempt receipt.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("regular_closed_log_required")
    before = path.stat()
    if before.st_size > MAX_LOG_BYTES:
        raise ValueError("log_above_bound")
    digest, total = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while chunk := stream.read(min(1024 * 1024, MAX_LOG_BYTES + 1 - total)):
            total += len(chunk)
            if total > MAX_LOG_BYTES:
                raise ValueError("log_grew_above_bound")
            digest.update(chunk)
    after = path.stat()
    if (
        path.is_symlink()
        or (before.st_size, before.st_mtime_ns, before.st_ino)
        != (after.st_size, after.st_mtime_ns, after.st_ino)
        or total != after.st_size
    ):
        raise ValueError("log_changed_during_sealing")
    return {
        "log_sha256": digest.hexdigest(),
        "log_size_bytes": total,
        "private_log_text_included": False,
        "hash_scope": "bytes_after_caller_closed_writer",
    }


def export_proposal(output):
    output = Path(output).absolute()
    source = Path(__file__).resolve().parents[2]
    if output.exists() or output.resolve().is_relative_to(source):
        raise ValueError("fresh_output_outside_source_checkout_required")
    value = compile_proposal()
    payload = encoded(value)
    if PRIVATE.search(payload.decode()):
        raise ValueError("private_marker_in_proposal")
    output.mkdir(parents=True, exist_ok=False)
    with (output / "comparison_proposal.json").open("xb") as stream:
        stream.write(payload)
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write((sha(payload) + "  comparison_proposal.json\n").encode())
    print("CPU_COMPARISON_PROPOSAL_ONLY_NO_OPTIMIZATION_NO_SUBMISSION")
    print("PROPOSAL_SHA256=" + value["proposal_sha256"])
    print("FILE_SHA256=" + sha(payload))
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_proposal(args.output)
