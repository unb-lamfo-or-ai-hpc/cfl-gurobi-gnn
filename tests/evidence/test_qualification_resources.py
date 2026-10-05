"""Resource scopes, immutable imported bytes, and sanitized read-only queries."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import review_qualification_resources as review  # noqa: E402


class ResourceReviewTests(unittest.TestCase):
    def test_archived_resource_review_hash_and_cost_scope(self):
        path = ROOT / "docs/evidence/pr74/job3479"
        raw = (path / "job3479_resource_review.json").read_bytes()
        sha = review.digest(raw)
        self.assertEqual(
            sha, "9d89915872dfd0fa35e113cbf73683de02cbd7c0fbdc48ddce5bccc3ba1e1b10"
        )
        self.assertEqual(
            (path / "SHA256SUMS.txt").read_bytes(),
            (sha + "  job3479_resource_review.json\n").encode(),
        )
        value = json.loads(raw)
        self.assertEqual(value["private_review_sha256"], review.AUDIT_SHA)
        self.assertEqual(value["package_sha256"], review.PACKAGE_SHA)
        self.assertEqual(value["allocation_cost"]["logical_allocation_cpu_hours"], 0.56)
        self.assertFalse(value["comparison_submission_ready"])

    def audit(self):
        return review.audit_bytes(
            (
                ROOT / "docs/evidence/pr73/job3479/job3479_private_review.json"
            ).read_bytes()
        )

    def fixture(self):
        audit = self.audit()
        root = {
            "JobID": "3479",
            "State": "COMPLETED",
            "ExitCode": "0:0",
            "ElapsedRaw": 63,
            "AllocCPUS": 32,
            "TotalCPU": "01:01.286",
        }
        step = {**root, "JobID": "3479.0", "MaxRSS": audit["slurm_step_max_rss"]}
        outer = {
            "accounting": {
                "job_id": "3479",
                "terminal": True,
                "state": "COMPLETED",
                "rows": [root, step],
            },
            "approval_sha256": audit["approval_sha256"],
            "plan_sha256": audit["plan_sha256"],
        }
        request = {
            "source_commit": audit["source_commit"],
            "approval_record_sha256": audit["approval_sha256"],
        }
        receipt = {
            "status": "completed",
            "supervisor_wall_seconds": 62,
            "console_log": {"log_sha256": audit["console_log_sha256"]},
            "child": {
                "slurm_job_id": "3479",
                "optimization_calls": 1,
                "gurobi_log": {"log_sha256": audit["gurobi_log_sha256"]},
                "peak_rss_bytes": audit["worker_ru_maxrss_bytes"],
                "current_process_cpu_seconds": 61,
                "phases": [],
                "result": {
                    "terminal": {"solver_runtime_seconds": 60},
                    "gurobi_callback": {
                        "callback_external_wall_seconds": 0.02,
                        "callback_current_process_cpu_seconds": 0.01,
                        "counters": {
                            "mip_calls": audit["callback_mip_calls"],
                            "mipsol_calls": audit["callback_mipsol_calls"],
                        },
                    },
                },
            },
        }
        return outer, request, receipt, audit

    def test_original_receipt_and_manifest_bytes(self):
        path = ROOT / "docs/evidence/pr73/job3479"
        self.audit()
        self.assertEqual(
            (path / "SHA256SUMS.txt").read_bytes(),
            (review.AUDIT_SHA + "  job3479_private_review.json\n").encode(),
        )
        with self.assertRaises(ValueError):
            review.audit_bytes(
                (path / "job3479_private_review.json").read_bytes() + b" "
            )

    def test_no_allocation_step_double_counting_or_speedup_claim(self):
        value = review.projection(*self.fixture())
        cost = value["allocation_cost"]
        self.assertEqual(cost["logical_allocation_cpu_hours"], 0.56)
        self.assertEqual(cost["reported_total_cpu_seconds"], 61.286)
        self.assertFalse(cost["step_rows_added_to_allocation"])
        callback = value["callback_instrumentation"]
        self.assertAlmostEqual(
            callback["external_wall_fraction_of_solver_runtime"], 0.02 / 60
        )
        self.assertFalse(callback["counterfactual_slowdown_qualified"])
        self.assertFalse(value["comparison_submission_ready"])
        self.assertFalse(value["scientific_reporting_eligible"])
        self.assertFalse(value["memory_observations"]["metrics_reconciled"])

    def test_changed_provenance_log_counter_memory_and_duplicate_root_fail(self):
        for section, key, value in (
            (3, "source_commit", "0" * 40),
            (3, "plan_sha256", "0" * 64),
            (3, "gurobi_log_sha256", "0" * 64),
            (3, "callback_mip_calls", 0),
            (3, "worker_ru_maxrss_bytes", 0),
            (3, "memory_metrics_reconciled", True),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                args = copy.deepcopy(self.fixture())
                args[section][key] = value
                review.projection(*args)
        args = self.fixture()
        args[0]["accounting"]["rows"].append(args[0]["accounting"]["rows"][0])
        with self.assertRaises(ValueError):
            review.projection(*args)

    def test_unrecognized_configuration_never_leaks_raw_values(self):
        raw = b"PrivateLicense = SECRET\nJobAcctGatherParams = SECRET\nJobAcctGatherType = jobacct_gather/cgroup\nTaskPlugin = task/cgroup,task/affinity\nJobAcctGatherFrequency = task=30,energy=10\n"
        result = review.config_projection(raw)
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertIsNone(result["allowlisted_configuration"]["JobAcctGatherParams"])
        self.assertEqual(
            result["allowlisted_configuration"]["JobAcctGatherFrequency"],
            {"task": 30, "energy": 10},
        )

    def test_duplicate_field_and_bad_frequency_fail_closed(self):
        with self.assertRaises(ValueError):
            review.config_projection(
                b"TaskPlugin = task/cgroup\nTaskPlugin = task/affinity\n"
            )
        for raw in ("task=30,task=10", "task=SECRET", "-1", "10000000"):
            self.assertIsNone(review.config_value("JobAcctGatherFrequency", raw))
        self.assertEqual(
            review.config_value("JobAcctGatherFrequency", "30"), {"task": 30}
        )

    def test_exactly_two_one_shot_queries_no_historical_promotion(self):
        with patch.object(
            review,
            "query",
            side_effect=[
                b"slurm 23.02.6\n",
                b"JobAcctGatherType = jobacct_gather/linux\n",
            ],
        ) as query:
            value = review.current_site("a" * 40)
        self.assertEqual(query.call_args_list[0].args[0], ["scontrol", "--version"])
        self.assertEqual(
            query.call_args_list[1].args[0], ["scontrol", "show", "config"]
        )
        self.assertEqual(query.call_count, 2)
        self.assertEqual(value["slurm_version"], "23.02.6")
        self.assertFalse(value["historical_job3479_configuration_verified"])
        self.assertFalse(value["higher_budget_memory_safety_qualified"])
        self.assertEqual(value["optimization_runs_added"], 0)
        self.assertEqual(value["submissions_added"], 0)

    def test_timeout_and_failed_query_do_not_emit_stderr_or_retry(self):
        with patch.object(
            review.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("scontrol", 20, stderr=b"SECRET"),
        ) as run:
            self.assertIsNone(review.query(["scontrol", "show", "config"]))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 20)
        with patch.object(review, "query", return_value=None) as query:
            value = review.current_site("a" * 40)
        self.assertEqual(query.call_count, 2)
        self.assertFalse(value["configuration_query_succeeded"])
        self.assertFalse(value["comparison_submission_ready"])

    def test_fresh_output_and_manifest_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fresh"
            sha = review.write_fresh(
                path, "receipt.json", {"optimization_runs_added": 0}
            )
            self.assertEqual(review.digest((path / "receipt.json").read_bytes()), sha)
            self.assertEqual(
                (path / "SHA256SUMS.txt").read_bytes(),
                (sha + "  receipt.json\n").encode(),
            )
            with self.assertRaises(ValueError):
                review.write_fresh(path, "receipt.json", {})


if __name__ == "__main__":
    unittest.main()
