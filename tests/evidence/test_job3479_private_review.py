"""Synthetic private footer cases; no solver, license, or scheduler calls."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import collect_pr66_log_phases as phases  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "job3479_private", SCRIPTS / "review_installed_job3479.py"
)
private = importlib.util.module_from_spec(spec)
spec.loader.exec_module(private)


class InstalledReviewTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "source_commit": private.HEAD,
            "approval_record_sha256": private.APPROVAL_SHA,
        }
        self.receipt = {
            "status": "completed",
            "optimization_calls_known": 1,
            "installed_callback_execution_qualified": False,
            "console_log": {"log_sha256": "b" * 64},
            "child": {
                "slurm_job_id": "3479",
                "optimization_calls": 1,
                "failure_code": None,
                "effective_parameters": {
                    "Threads": 1,
                    "Seed": 42,
                    "TimeLimit": 60,
                    "MIPGap": 0.01,
                    "SoftMemLimit": 48,
                },
                "gurobi_log": {"log_sha256": "a" * 64},
                "peak_rss_bytes": 270479360,
                "result": {
                    "stop": "time_limit",
                    "dropped_sample_count": 0,
                    "gurobi_callback": {
                        "failed": False,
                        "counters": {"mip_calls": 1098, "mipsol_calls": 62},
                    },
                    "terminal": {
                        "primal": 5.109543784909757,
                        "dual": 4.653854724579171,
                        "node_count": 1041,
                        "solver_runtime_seconds": 60.020081996917725,
                        "gap_relative": 0.08918390359554078,
                    },
                },
            },
        }
        self.outer = {
            "plan_sha256": private.PLAN_SHA,
            "approval_sha256": private.APPROVAL_SHA,
            "scientific_reporting_eligible": False,
            "accounting": {
                "job_id": "3479",
                "state": "COMPLETED",
                "rows": [{"JobID": "3479.0", "MaxRSS": "200152K"}],
            },
        }
        self.log = (
            "Gurobi Optimizer version 13.0.1\n"
            "Threads 1\nSeed 42\nTimeLimit 60\nMIPGap 0.01\nSoftMemLimit 48\n"
            "Presolve time: 0.10s\n"
            "Root relaxation: objective 4.50, 10 iterations, 0.20 seconds\n"
            "Explored 1041 nodes (1200 simplex iterations) in 60.02 seconds\n"
            "Best objective 5.109543784909757, best bound 4.653854724579171, "
            "gap 8.9184%\n"
        )

    def review(self, text=None):
        return private.sanitized_review(
            None,
            phases,
            self.outer,
            self.request,
            self.receipt,
            self.log if text is None else text,
        )

    def test_consistent_display_is_limited_observation(self):
        value = self.review()
        self.assertEqual(value["log_state"], "receipt_consistent_observations")
        self.assertTrue(value["terminal_numeric_parity_supported"])
        self.assertTrue(value["installed_callback_observation_supported"])
        self.assertEqual(value["presolve_display_seconds"], 0.10)
        self.assertEqual(value["root_relaxation_display_seconds"], 0.20)
        self.assertFalse(value["memory_metrics_reconciled"])
        self.assertFalse(value["scientific_reporting_eligible"])
        self.assertFalse(value["raw_logs_included"])
        self.assertNotIn(self.log, str(value))

    def test_mismatched_terminal_bound_fails_closed(self):
        value = self.review(
            self.log.replace("best bound 4.653854724579171", "best bound 4.0")
        )
        self.assertEqual(value["log_state"], "unqualified")
        self.assertFalse(value["terminal_numeric_parity_supported"])
        self.assertFalse(value["installed_callback_observation_supported"])

    def test_duplicate_header_fails_closed(self):
        value = self.review("Gurobi Optimizer version 13.0.1\n" + self.log)
        self.assertEqual(value["log_state"], "unqualified")
        self.assertFalse(value["terminal_numeric_parity_supported"])

    def test_wrong_identity_stops_before_parsing(self):
        self.request["source_commit"] = "0" * 40
        with self.assertRaises(ValueError):
            self.review()

    def test_callback_failure_stops_before_parsing(self):
        self.receipt["child"]["result"]["gurobi_callback"]["failed"] = True
        with self.assertRaises(ValueError):
            self.review()

    def test_zero_callback_events_cannot_support_installed_observation(self):
        self.receipt["child"]["result"]["gurobi_callback"]["counters"]["mip_calls"] = 0
        value = self.review()
        self.assertTrue(value["terminal_numeric_parity_supported"])
        self.assertFalse(value["installed_callback_observation_supported"])


if __name__ == "__main__":
    unittest.main()
