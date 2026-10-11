"""Installed receipt and supervised timing regressions; no solver execution."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_supervised_costs as costs  # noqa: E402
import review_pr86_installed_bindings as review  # noqa: E402


class InstalledReviewTests(unittest.TestCase):
    def test_ten_parents_cap_and_historical_exposure(self):
        rows = review.review((review.DESTINATION / "binding.json").read_bytes())
        self.assertEqual(
            [r["alias"] for r in rows],
            ["F0", "F3", "F6", "F14", "F27", "F29", "M0", "M4", "M7", "M12"],
        )
        for row in rows:
            self.assertTrue(row["historically_exposed"])
            self.assertFalse(row["full_solution_feasibility_qualified"])
            self.assertFalse(row["solver_acceptance_observed"])
            if row["difficulty"] == "medium":
                self.assertEqual(row["selected_support_per_guided_method"], 20000)
                self.assertLess(row["coverage_fraction"], 0.018)
            else:
                self.assertEqual(row["coverage_fraction"], 0.1)

    def test_byte_changes_and_different_source_rejected(self):
        raw = (review.DESTINATION / "binding.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "binding_hash"):
            review.review(raw + b" ")
        value = json.loads(raw)
        value["source_commit"] = "0" * 40
        with self.assertRaises(ValueError):
            review.review(review.binding.proposal.encoded(value))

    def test_outputs_reproduce_and_preserve_receipt(self):
        source = review.DESTINATION / "binding.json"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            report = review.produce(source, output)
            self.assertFalse(report["solver_execution_admitted"])
            self.assertEqual(report["historical_attempt_timings_reconciled"], 18)
            for file in output.iterdir():
                self.assertEqual(
                    file.read_bytes(), (review.DESTINATION / file.name).read_bytes()
                )
            with self.assertRaises(FileExistsError):
                review.produce(source, output)

    def test_historical_costs_do_not_create_new_results(self):
        rows = review.historical_cost_rows()
        self.assertEqual(len(rows), 18)
        for row in rows:
            self.assertFalse(row["prospective_pr86_result"])
            self.assertFalse(row["whole_job_end_to_end_qualified"])
            self.assertGreaterEqual(row["outside_solver_function_seconds"], 0)
            self.assertAlmostEqual(
                row["supervisor_wall_seconds"],
                row["solver_function_seconds"] + row["outside_solver_function_seconds"],
            )
            if row["method"] != "M0":
                self.assertIsNone(row["cold_attempt_seconds"])


class SupervisedCostsTests(unittest.TestCase):
    def setUp(self):
        self.supervision = dict(
            supervisor_wall_seconds=30, child_exit_code=0, guard_stop=None
        )
        self.result = dict(
            gate_status="passed",
            timing=dict(
                total_wall_time_seconds=25,
                data_read_wall_time_seconds=1,
                model_build_wall_time_seconds=2,
                model_optimize_wall_time_seconds=10,
                independent_audit_wall_time_seconds=3,
                solution_export_wall_time_seconds=4,
                other_wall_time_seconds=9,
            ),
        )

    def test_disjoint_supervisor_and_export_scopes(self):
        value = costs.reconcile(self.supervision, self.result, "M0")
        self.assertEqual(value["outside_solver_function_seconds"], 5)
        self.assertEqual(value["execution_regions_seconds"]["other"], 5)
        self.assertEqual(value["cold_attempt_seconds"], 30)
        self.assertFalse(value["whole_job_end_to_end_qualified"])

    def test_failures_preserve_wall_without_completed_cost(self):
        for patch, child in (
            (dict(child_exit_code=2), self.result),
            (dict(guard_stop="memory_guard_stop"), self.result),
            ({}, None),
            ({}, dict(gate_status="failed")),
        ):
            value = costs.reconcile({**self.supervision, **patch}, child, "M2")
            self.assertEqual(value["supervisor_wall_seconds"], 30)
            self.assertFalse(value["complete_attempt"])
            self.assertIsNone(value["cold_attempt_seconds"])

    def test_inconsistent_wall_and_boolean_exit_rejected(self):
        for patch in (
            dict(supervisor_wall_seconds=24),
            dict(child_exit_code=False),
            dict(supervisor_wall_seconds=float("nan")),
        ):
            with self.assertRaises(ValueError):
                costs.reconcile({**self.supervision, **patch}, self.result, "M0")

    def test_guidance_unknown_and_measured_preparation(self):
        self.assertIsNone(
            costs.reconcile(self.supervision, self.result, "M1")["cold_attempt_seconds"]
        )
        prep = dict(root=10, features=2, inference=3, assembly_lp=1, assembly_gnn=2)
        value = costs.reconcile(self.supervision, self.result, "M1", prep)
        self.assertEqual(value["cold_attempt_seconds"], 46)
        self.assertAlmostEqual(value["amortized_attempt_seconds"], 30 + 16 / 7)


if __name__ == "__main__":
    unittest.main()
