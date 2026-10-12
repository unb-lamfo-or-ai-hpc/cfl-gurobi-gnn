"""Cost arithmetic with synthetic clocks, never solver or GPU calls."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_cost_accounting as costs  # noqa: E402


class CostTests(unittest.TestCase):
    def test_disjoint_adapter_does_not_double_count_export(self):
        timing = dict(
            total_wall_time_seconds=25,
            data_read_wall_time_seconds=1,
            model_build_wall_time_seconds=2,
            model_optimize_wall_time_seconds=10,
            independent_audit_wall_time_seconds=3,
            solution_export_wall_time_seconds=4,
            other_wall_time_seconds=9,
        )
        result = costs.execution_costs(timing)
        self.assertEqual(result["other"], 5)
        self.assertEqual(sum(result.values()), 25)
        timing["solution_export_wall_time_seconds"] = 10
        with self.assertRaises(ValueError):
            costs.execution_costs(timing)

    def test_lp_matching_charges_gnn_and_campaign_shares_once(self):
        prep = dict(root=10, features=2, inference=3, assembly_lp=1, assembly_gnn=2)
        execution = dict.fromkeys(costs.EXECUTION, 1)
        lp = costs.end_to_end("M1", prep, execution, uses=7, worker_overhead=0)
        gnn = costs.end_to_end("M2", prep, execution, uses=7, worker_overhead=0)
        self.assertEqual(lp["preparation_seconds"], 18)
        self.assertEqual(gnn["preparation_seconds"], 17)
        self.assertEqual(lp["cold_end_to_end_seconds"], 24)
        self.assertAlmostEqual(lp["amortized_end_to_end_seconds"], 6 + 18 / 7)
        self.assertEqual(costs.campaign_preparation(prep)["seconds"], 18)

    def test_unknown_is_not_zero_and_control_needs_no_guidance(self):
        execution = dict.fromkeys(costs.EXECUTION, 1)
        for method in ("M1", "M2"):
            value = costs.end_to_end(method, {}, execution)
            self.assertIsNone(value["cold_end_to_end_seconds"])
            self.assertIsNone(value["amortized_end_to_end_seconds"])
            self.assertIn("inference", value["missing_preparation_regions"])
        self.assertEqual(
            costs.end_to_end("M0", {}, execution, worker_overhead=0)[
                "cold_end_to_end_seconds"
            ],
            6,
        )
        self.assertIsNone(
            costs.end_to_end("M0", {}, execution)["cold_end_to_end_seconds"]
        )
        self.assertIsNone(costs.campaign_preparation({})["seconds"])

    def test_historical_missing_list_cannot_compute_numeric_cost(self):
        execution = dict.fromkeys(costs.EXECUTION, 1)
        old = costs.end_to_end("M1", {}, execution, historical_missing_regions=True)
        self.assertIsNone(old["preparation_seconds"])
        self.assertNotIn("assembly_gnn", old["missing_preparation_regions"])
        new = costs.end_to_end("M1", {}, execution)
        self.assertIn("assembly_gnn", new["missing_preparation_regions"])
        for prep, overhead in (({"root": 1}, None), ({}, 0)):
            with self.assertRaisesRegex(ValueError, "historical_missing_regions_only"):
                costs.end_to_end(
                    "M1",
                    prep,
                    execution,
                    worker_overhead=overhead,
                    historical_missing_regions=True,
                )

    def test_clock_synchronizes_and_rejects_overlap_and_duplicates(self):
        samples, sync = iter((10, 12)), []
        clock = costs.StageClock(lambda: next(samples))
        with (
            clock.measure("inference", synchronize=lambda: sync.append(1)),
            self.assertRaises(ValueError),
            clock.measure("root"),
        ):
            pass
        self.assertEqual(sync, [1, 1])
        self.assertEqual(
            clock.records["inference"], {"seconds": 2.0, "state": "complete"}
        )
        with self.assertRaises(ValueError), clock.measure("inference"):
            pass

    def test_failed_region_is_missing_not_successful_zero(self):
        clock = costs.StageClock(lambda: 1)
        with self.assertRaises(RuntimeError), clock.measure("root"):
            raise RuntimeError("synthetic")
        self.assertEqual(
            clock.records["root"], {"seconds": None, "state": "failed_or_incomplete"}
        )
        self.assertFalse(clock.active)

    def test_invalid_durations_and_inconsistent_total_rejected(self):
        for value in (True, -1, float("nan"), float("inf"), None):
            with self.assertRaises(ValueError):
                costs.seconds(value)
        for uses in (0, True, 1.5):
            with self.assertRaises(ValueError):
                costs.end_to_end("M0", {}, dict.fromkeys(costs.EXECUTION, 1), uses)


if __name__ == "__main__":
    unittest.main()
