"""Offline immutable evidence, ledger and budget tests; no HPC or solver."""

import copy
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import review_pr86_job3521 as review  # noqa: E402


class GuidanceReview(unittest.TestCase):
    def setUp(self):
        self.raw = (review.DESTINATION / "public_return.json").read_bytes()
        self.value, self.rows, self.report = review.review(self.raw)

    def test_pinned_bytes_and_original_false_flags(self):
        self.assertEqual(len(self.rows), 10)
        self.assertEqual(self.report["forward_calls"], 10)
        self.assertEqual(self.report["optimization_calls"], 0)
        self.assertFalse(self.report["main_comparison_admitted"])
        self.assertFalse(self.value["scientific_reporting_eligible"])
        with self.assertRaisesRegex(ValueError, "immutable_return_hash"):
            review.review(self.raw + b" ")

    def test_old_tree_not_recomputed(self):
        with patch.object(
            review.guidance, "plan", side_effect=AssertionError("new tree")
        ):
            review.review(self.raw)

    def test_ledger_is_disjoint_and_does_not_add_nested_forward(self):
        components = self.report["disjoint_campaign_components_seconds"]
        self.assertTrue(
            math.isclose(
                sum(components.values()),
                self.report["combined_instrumented_preparation_seconds"],
                abs_tol=1e-8,
            )
        )
        self.assertNotIn("forward", components)
        for row in self.rows:
            self.assertGreaterEqual(
                row["inference_seconds"], row["forward_seconds_nested_in_inference"]
            )
            self.assertAlmostEqual(
                row["M1_scoped_dependency_seconds"]
                - row["M2_scoped_dependency_seconds"],
                row["assembly_lp_seconds"],
            )

    def test_allocated_scenario_is_not_observed_cold_time(self):
        self.assertFalse(self.report["standalone_cold_preparation_measured"])
        self.assertFalse(self.report["whole_job_end_to_end_qualified"])
        self.assertTrue(
            self.report["allocation_is_modeled_not_observed_standalone_cold_cost"]
        )
        self.assertAlmostEqual(
            sum(r["M1_allocated_preparation_scenario_seconds"] for r in self.rows),
            self.report["combined_instrumented_preparation_seconds"],
        )
        for row in self.rows:
            for method in ("M1", "M2"):
                self.assertAlmostEqual(
                    row[method + "_allocated_scenario_per_seven_uses_seconds"] * 7,
                    row[method + "_allocated_preparation_scenario_seconds"],
                )

    def test_mutated_semantics_rejected_beneath_hash_gate(self):
        roots = review.roots.review(
            (review.roots.DESTINATION / "public_return.json").read_bytes()
        )
        for key, bad, error in (
            ("root_sha256", "a" * 64, "root_identity"),
            ("model_sha256", "a" * 64, "model_identity"),
            ("effective_objective_sense", "MAXIMIZE", "sense"),
            ("selected_support", 20001, "support_policy"),
            ("optimization_calls", 1, "calls"),
        ):
            value = copy.deepcopy(self.value)
            value["child"]["rows"][0][key] = bad
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, error):
                review.summarize(value, *roots)

    def test_timing_and_failure_rejected(self):
        roots = review.roots.review(
            (review.roots.DESTINATION / "public_return.json").read_bytes()
        )
        for change in (
            lambda v: v["child"].update(complete=False),
            lambda v: v["child"].update(child_observed_wall_seconds=0),
            lambda v: v["supervision"].update(guard_stop="memory_limit"),
            lambda v: v["child"]["rows"][0]["regions_seconds"].update(
                features=float("nan")
            ),
        ):
            value = copy.deepcopy(self.value)
            change(value)
            with self.assertRaises(ValueError):
                review.summarize(value, *roots)

    def test_budget_counts_existing_preparation_zero_new_calls(self):
        budget = review.budget(self.report)
        self.assertEqual(budget["main_optimization_calls_maximum"], 210)
        self.assertEqual(budget["submissions_maximum"], 70)
        self.assertEqual(budget["solver_seconds_maximum"] / 3600, 210)
        self.assertEqual(budget["sequential_reserved_wall_seconds_maximum"] / 3600, 280)
        self.assertEqual(budget["reserved_physical_core_seconds_maximum"] / 3600, 1320)
        self.assertEqual(
            budget["solver_capacity_physical_core_seconds_maximum"] / 3600, 990
        )
        self.assertEqual(
            budget["new_root_calls"] + budget["new_forwards"] + budget["training_runs"],
            0,
        )
        self.assertFalse(budget["resource_budget_approved"])
        self.assertFalse(budget["solver_execution_admitted"])
        self.assertTrue(budget["first_group_is_part_of_210_not_additional_pilot"])

    def test_svg_has_ten_rows_and_sixty_segments(self):
        svg = ElementTree.fromstring(review.figure(self.rows))
        ns = {"s": "http://www.w3.org/2000/svg"}
        bars = svg.findall(".//s:rect/s:title", ns)
        self.assertEqual(len(bars), 60)
        self.assertIn("F0", "".join(svg.itertext()))
        self.assertIn("M12", "".join(svg.itertext()))

    def test_regeneration_is_byte_identical_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            review.produce(review.DESTINATION / "public_return.json", output)
            for p in output.iterdir():
                self.assertEqual(
                    p.read_bytes(), (review.DESTINATION / p.name).read_bytes()
                )
            with self.assertRaises(FileExistsError):
                review.produce(review.DESTINATION / "public_return.json", output)


if __name__ == "__main__":
    unittest.main()
