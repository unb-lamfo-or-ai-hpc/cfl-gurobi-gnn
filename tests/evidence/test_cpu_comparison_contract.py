"""Offline proposal and telemetry tests; no optimizer, license or scheduler."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import cpu_comparison_contract as contract  # noqa: E402


class ProposalTests(unittest.TestCase):
    def test_original_pair_and_roles_not_outcome_selected(self):
        proposal = contract.compile_proposal()
        self.assertEqual(
            tuple(row["source_instance_id"] for row in proposal["models"]),
            contract.MODEL_IDS,
        )
        self.assertTrue(all(row["role"] == "train" for row in proposal["models"]))
        self.assertFalse(any("relative_path" in row for row in proposal["models"]))

    def test_proposal_is_disabled_and_does_not_authorize_replication(self):
        proposal = contract.compile_proposal()
        for name in (
            "execution_enabled",
            "resource_budget_approved",
            "scientific_reporting_eligible",
        ):
            self.assertIs(proposal[name], False)
        self.assertEqual(proposal["optimization_runs"], 0)
        self.assertFalse(proposal["followup_seeds"]["enabled"])
        self.assertEqual(proposal["followup_seeds"]["proposed"], [43, 44])

    def test_same_profile_and_complete_frozen_matrix(self):
        proposal = contract.compile_proposal()
        attempts = proposal["attempts"]
        self.assertEqual(len(attempts), 10)
        self.assertEqual(len({row["attempt_id"] for row in attempts}), 10)
        for parent in contract.MODEL_IDS:
            block = [row for row in attempts if row["source_instance_id"] == parent]
            self.assertEqual({row["threads"] for row in block}, set(contract.CAPS))
            self.assertEqual(
                [row["within_parent_order"] for row in block], list(range(5))
            )
            self.assertTrue(
                all(
                    row["seed"] == 42 and row["optimization_limit_seconds"] == 3600
                    for row in block
                )
            )
        self.assertEqual({row["stopping_gap_relative"] for row in attempts[:5]}, {0.01})
        self.assertEqual({row["stopping_gap_relative"] for row in attempts[5:]}, {0.1})

    def test_sha_order_reproducible_and_proposal_digest(self):
        proposal = contract.compile_proposal()
        self.assertEqual(proposal, contract.compile_proposal())
        for parent in contract.MODEL_IDS:
            actual = [
                row["threads"]
                for row in proposal["attempts"]
                if row["source_instance_id"] == parent
            ]
            expected = sorted(
                contract.CAPS,
                key=lambda t: hashlib.sha256(
                    f"{contract.PROTOCOL}|{parent}|42|{t}".encode()
                ).hexdigest(),
            )
            self.assertEqual(actual, expected)
        digest = proposal.pop("proposal_sha256")
        self.assertEqual(digest, contract.sha(contract.encoded(proposal)))

    def test_declared_budget_arithmetic_and_clock_units(self):
        proposal = contract.compile_proposal()
        budget = proposal["prospective_budget"]
        self.assertEqual(
            sum(row["optimization_limit_seconds"] for row in proposal["attempts"]),
            budget["maximum_optimization_seconds"],
        )
        self.assertEqual(
            sum(
                row["threads"] * row["optimization_limit_seconds"]
                for row in proposal["attempts"]
            )
            / 3600,
            62,
        )
        job_seconds = budget["proposed_minutes_per_job"] * 60
        self.assertEqual(
            job_seconds,
            5 * budget["proposed_child_timeout_seconds"]
            + budget["parent_block_other_overhead_allowance_seconds"],
        )
        self.assertEqual(2 * 32 * job_seconds / 3600, 352)
        self.assertEqual(2 * 16 * job_seconds / 3600, 176)
        self.assertTrue(budget["actual_cost_unknown"])
        self.assertFalse(
            proposal["outcomes"]["fixed_budget_terminal_quality_comparison"]
        )

    def test_changed_original_cohort_rejected(self):
        payloads = contract.original.public_receipts()
        plan = json.loads(payloads["pilot_plan.json"])
        plan["models"][0]["role"] = "test"
        payloads["pilot_plan.json"] = json.dumps(plan).encode()
        with (
            patch.object(contract.original, "public_receipts", return_value=payloads),
            self.assertRaisesRegex(ValueError, "cohort_changed"),
        ):
            contract.compile_proposal()

    def test_export_fresh_outside_checkout_and_internal_hash(self):
        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / "proposal"
            expected = contract.export_proposal(output)
            data = (output / "comparison_proposal.json").read_bytes()
            self.assertEqual(json.loads(data), expected)
            self.assertEqual(
                (output / "SHA256SUMS.txt").read_text(),
                contract.sha(data) + "  comparison_proposal.json\n",
            )
            self.assertEqual(
                {row.name for row in output.iterdir()},
                {"comparison_proposal.json", "SHA256SUMS.txt"},
            )
            with self.assertRaisesRegex(ValueError, "fresh_output"):
                contract.export_proposal(output)
        root = Path(contract.__file__).resolve().parents[2]
        with self.assertRaisesRegex(ValueError, "fresh_output"):
            contract.export_proposal(root / "test-must-not-exist")


class TelemetryTests(unittest.TestCase):
    def telemetry(self, **kwargs):
        return contract.Telemetry(3600, 0.1, **kwargs)

    def test_missing_incumbent_is_missing_gap_not_zero(self):
        trace = self.telemetry()
        sample = trace.observe(0, dual=2, nodes=0)
        self.assertIsNone(sample["gap_relative"])
        self.assertEqual(trace.crossings, {})

    def test_first_sampled_crossing_retained(self):
        trace = self.telemetry()
        trace.observe(4, 10, 7, 0.3)
        trace.observe(9, 10, 9.1, 0.09)
        trace.observe(12, 10, 9.9, 0.01)
        result = trace.finish("gap_target", 13, 10, 9.95, 0.005)
        self.assertEqual(
            result["first_sampled_gap_observations"][0]["solver_runtime_seconds"], 9
        )
        self.assertEqual(
            result["first_sampled_gap_observations"][0][
                "previous_sample_runtime_seconds"
            ],
            4,
        )
        self.assertFalse(result["true_first_crossings_qualified"])

    def test_timeout_is_censored_never_an_observed_target(self):
        result = self.telemetry().finish("time_limit", 3600.2, 10, 1, 0.9)
        first = result["first_sampled_gap_observations"][0]
        self.assertEqual(first["state"], "right_censored")
        self.assertIsNone(first["solver_runtime_seconds"])
        self.assertAlmostEqual(result["time_limit_overshoot_seconds"], 0.2)

    def test_memory_failure_not_a_successful_timeout(self):
        for stop in ("memory_limit", "worker_failure", "other_stop"):
            result = self.telemetry().finish(stop, 10)
            self.assertNotEqual(
                result["first_sampled_gap_observations"][0]["state"], "right_censored"
            )

    def test_planned_gap_stop_does_not_impute_stricter_crossings(self):
        result = self.telemetry().finish("gap_target", 12, 10, 9.1, 0.09)
        self.assertEqual(
            result["first_sampled_gap_observations"][0]["state"], "observed"
        )
        self.assertEqual(
            result["first_sampled_gap_observations"][1]["state"],
            "not_observed_before_planned_gap_stop",
        )

    def test_late_target_is_observed_but_outside_budget(self):
        result = self.telemetry().finish("gap_target", 3600.3, 10, 9.1, 0.09)
        self.assertFalse(
            result["first_sampled_gap_observations"][0]["observed_within_budget"]
        )

    def test_bad_numbers_gap_and_nonmonotone_clock_rejected(self):
        for invalid in (True, "1", float("nan"), float("inf"), -1):
            with self.assertRaises(ValueError):
                self.telemetry().observe(invalid)
        with self.assertRaisesRegex(ValueError, "finite_primal_and_dual"):
            self.telemetry().observe(1, gap=0.01)
        trace = self.telemetry()
        trace.observe(2)
        with self.assertRaisesRegex(ValueError, "nonmonotone"):
            trace.observe(1)

    def test_sample_storage_bounded_crossings_still_tracked(self):
        trace = self.telemetry(max_samples=1)
        trace.observe(0)
        trace.observe(10, 10, 9.1, 0.09)
        result = trace.finish("gap_target", 12, 10, 9.1, 0.09)
        self.assertEqual(len(result["samples"]), 1)
        self.assertEqual(result["dropped_sample_count"], 2)
        self.assertTrue(result["terminal"]["terminal"])
        self.assertEqual(
            result["first_sampled_gap_observations"][0]["solver_runtime_seconds"], 10
        )

    def test_invalid_contract_and_sample_cap_rejected(self):
        for value in (0, True, -1, contract.MAX_SAMPLES + 1):
            with self.assertRaises(ValueError):
                self.telemetry(max_samples=value)
        for budget, target in ((0, 0.1), (3600, 0.2)):
            with self.assertRaises(ValueError):
                contract.Telemetry(budget, target)

    def test_disjoint_wall_and_cpu_clocks_no_addition(self):
        trace = self.telemetry()
        with trace.phase(
            "optimization",
            wall_clock=iter([10, 12]).__next__,
            cpu_clock=iter([20, 29]).__next__,
        ):
            pass
        (row,) = trace.phases
        self.assertEqual(row["external_wall_seconds"], 2)
        self.assertEqual(row["process_cpu_seconds"], 9)
        self.assertFalse(row["call_failed"])

    def test_nested_and_duplicate_phases_rejected(self):
        trace = self.telemetry()
        with (
            trace.phase("read_setup"),
            self.assertRaisesRegex(ValueError, "disjoint_unique"),
            trace.phase("optimization"),
        ):
            pass
        with (
            self.assertRaisesRegex(ValueError, "disjoint_unique"),
            trace.phase("read_setup"),
        ):
            pass

    def test_failure_phase_preserved_without_exception_text(self):
        trace = self.telemetry()
        with self.assertRaises(RuntimeError), trace.phase("optimization"):
            raise RuntimeError("PRIVATE_TEST_MESSAGE")
        self.assertTrue(trace.phases[0]["call_failed"])
        self.assertNotIn("PRIVATE_TEST_MESSAGE", json.dumps(trace.phases))
        self.assertIsNone(trace.active)

    def test_finish_one_time_no_sampling_or_phase_after_terminal(self):
        trace = self.telemetry()
        trace.finish("time_limit", 3600)
        with self.assertRaisesRegex(ValueError, "already_finished"):
            trace.observe(3601)
        with self.assertRaises(ValueError), trace.phase("cleanup"):
            pass

    def test_inconsistent_stop_and_active_phase_rejected(self):
        trace = self.telemetry()
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            trace.finish("gap_target", 1, 10, 1, 0.9)
        with trace.phase("optimization"), self.assertRaises(ValueError):
            trace.finish("time_limit", 3600)

    def test_terminal_flag_requires_boolean(self):
        with self.assertRaisesRegex(ValueError, "boolean_terminal"):
            self.telemetry().observe(1, terminal="false")

    def test_failed_initial_clock_does_not_leave_phase_active(self):
        trace = self.telemetry()
        with (
            self.assertRaises(ValueError),
            trace.phase("optimization", wall_clock=lambda: float("nan")),
        ):
            pass
        self.assertIsNone(trace.active)

    def test_bad_phase_end_clock_is_not_a_qualified_measurement(self):
        trace = self.telemetry()
        with (
            self.assertRaises(ValueError),
            trace.phase("optimization", wall_clock=iter([2, 1]).__next__),
        ):
            pass
        self.assertIsNone(trace.active)
        self.assertEqual(trace.phases, [])


class PairAndLogTests(unittest.TestCase):
    def pair(self, seconds, threads=1):
        return {
            "state": "observed",
            "observed_within_budget": True,
            "solver_runtime_seconds": seconds,
            "original_lp_sha256": "a" * 64,
            "comparison_profile_sha256": "b" * 64,
            "seed": 42,
            "target_gap_relative": 0.1,
            "optimization_budget_seconds": 3600,
            "threads": threads,
        }

    def test_paired_speedup_and_efficiency(self):
        result = contract.paired_speedup(self.pair(100), self.pair(40, 4), 4)
        self.assertEqual(result["speedup"], 2.5)
        self.assertEqual(result["parallel_efficiency"], 0.625)

    def test_censored_or_late_pair_never_imputed(self):
        for changed in ({"state": "right_censored"}, {"observed_within_budget": False}):
            result = contract.paired_speedup(
                self.pair(100), {**self.pair(3600, 4), **changed}, 4
            )
            self.assertIsNone(result["speedup"])

    def test_mismatched_or_unqualified_pairs_rejected(self):
        for changed in (
            {"seed": 43},
            {"target_gap_relative": 0.01},
            {"original_lp_sha256": "c" * 64},
            {"comparison_profile_sha256": "x"},
            {"threads": 8},
            {"optimization_budget_seconds": 300},
        ):
            with self.assertRaises(ValueError):
                contract.paired_speedup(
                    self.pair(100), {**self.pair(40, 4), **changed}, 4
                )

    def test_zero_duration_not_infinite_speedup(self):
        self.assertIsNone(
            contract.paired_speedup(self.pair(0), self.pair(1, 2), 2)["speedup"]
        )

    def test_false_within_budget_flag_rejected(self):
        with self.assertRaisesRegex(ValueError, "flag_inconsistent"):
            contract.paired_speedup(self.pair(100), self.pair(3601, 4), 4)

    def test_boolean_seed_or_thread_not_integer_identity(self):
        for changed in (
            {"seed": True},
            {"threads": True},
            {"target_gap_relative": True},
        ):
            with self.assertRaises(ValueError):
                contract.paired_speedup(
                    {**self.pair(100), **changed}, self.pair(40, 4), 4
                )

    def test_closed_log_digest_only_source_preserved(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "private.log"
            data = b"PRIVATE_LOG_TEXT_TEST\n"
            path.write_bytes(data)
            result = contract.seal_closed_log(path)
            self.assertEqual(result["log_sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(result["log_size_bytes"], len(data))
            self.assertFalse(result["private_log_text_included"])
            self.assertNotIn("PRIVATE_LOG_TEXT_TEST", json.dumps(result))
            self.assertEqual(path.read_bytes(), data)

    def test_missing_and_oversized_log_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "private.log"
            with self.assertRaises(ValueError):
                contract.seal_closed_log(path)
            path.write_bytes(b"abcd")
            with (
                patch.object(contract, "MAX_LOG_BYTES", 3),
                self.assertRaisesRegex(ValueError, "above_bound"),
            ):
                contract.seal_closed_log(path)

    def test_log_changed_during_sealing_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "private.log"
            path.write_bytes(b"abc")
            # A changed file length cannot pass readback even if initial metadata
            # stays cached; use real overwrite immediately after stream closes.
            original_stat = Path.stat
            calls = 0

            def changing_stat(p, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 4:
                    p.write_bytes(b"abcd")
                return original_stat(p, *args, **kwargs)

            with (
                patch.object(Path, "stat", changing_stat),
                self.assertRaisesRegex(ValueError, "changed_during"),
            ):
                contract.seal_closed_log(path)


if __name__ == "__main__":
    unittest.main()
