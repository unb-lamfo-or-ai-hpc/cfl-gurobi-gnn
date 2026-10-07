"""Actual CLI regression and offline sealed-return analysis; no solver/network."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import review_pr79_sprint_b as review  # noqa: E402


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = review.build_report()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pr79 CLI spaces ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        review.unpack_public(review.EVIDENCE, self.directory)
        self.return_file = self.directory / "public_return.json"

    def cli(self, sha=review.RETURN_SHA):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/evidence/pr78_medium_workflow.py"),
                "validate-return",
                "--directory",
                str(self.directory),
                "--return-file",
                str(self.return_file),
                "--expected-sha",
                sha,
            ],
            cwd=self.directory,
            capture_output=True,
            check=False,
            timeout=60,
        )

    def test_actual_cli_valid_return_with_string_arguments_and_spaces(self):
        before = review.flow.digest(self.return_file)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        value = json.loads(result.stdout)
        self.assertTrue(value["ready_for_independent_review"])
        self.assertEqual(len(value["attempts"]), 5)
        self.assertEqual(before, review.flow.digest(self.return_file))
        self.assertFalse((self.directory / "STOP.json").exists())

    def test_wrong_hash_reports_local_failure_not_hpc_stop(self):
        result = self.cli("0" * 64)
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            b"PR79_LOCAL_RETURN_VALIDATION_FAILED_NO_HPC_ACTION", result.stderr
        )
        self.assertNotIn(b"PR78_MEDIUM_STOPPED", result.stderr)
        self.assertNotIn(str(self.directory).encode(), result.stderr)

    def test_nested_tampering_with_updated_outer_hash_rejected(self):
        value = review.flow.load(self.return_file)
        value["attempts"]["medium-seed42-threads1"]["receipt"]["child"][
            "optimization_calls"
        ] = 2
        self.return_file.write_bytes(review.flow.contract.encoded(value))
        result = self.cli(review.flow.digest(self.return_file))
        self.assertEqual(result.returncode, 2)

    def test_missing_predecessor_rejected(self):
        (self.directory / "predecessor/easy/accounting.json").unlink()
        self.assertEqual(self.cli().returncode, 2)

    def test_legacy_admission_does_not_weaken_execution_plan(self):
        value = review.flow.load(self.return_file)
        with self.assertRaises(ValueError):
            review.flow.validate_plan(value["plan"], self.directory)
        review.flow.validate_plan(
            value["plan"], self.directory, historical_read_only=True
        )
        value["plan"]["dependency_sha256"]["pr78_medium_workflow.py"] = "0" * 64
        with self.assertRaises(ValueError):
            review.flow.validate_plan(
                value["plan"], self.directory, historical_read_only=True
            )

    def test_other_dependency_tampering_rejected(self):
        value = review.flow.load(self.return_file)
        value["plan"]["dependency_sha256"][review.flow.BATCH] = "0" * 64
        with self.assertRaises(ValueError):
            review.flow.validate_public(value, self.directory)

    def test_ten_attempts_and_historical_interruption_retained(self):
        self.assertEqual(len(self.report["comparison_rows"]), 10)
        self.assertEqual(
            sum(r["optimization_calls"] for r in self.report["comparison_rows"]), 10
        )
        self.assertIsNone(self.report["job3490_optimization_calls"])
        self.assertEqual(
            [r["job_id"] for r in self.report["allocation_rows"]],
            ["3489", "3490", "3494"],
        )
        self.assertFalse(self.report["scientific_reporting_eligible"])

    def test_censored_and_missing_times_never_manufacture_speedup(self):
        rows = copy.deepcopy(self.report["comparison_rows"])
        for row in rows:
            row["first_observed_target_seconds"] = None
        self.assertTrue(
            all(
                r["observed_target_speedup_vs_1"] is None
                for r in review.comparison(rows)
            )
        )
        medium = [r for r in self.report["comparison_rows"] if r["parent"] == "medium"]
        self.assertEqual(
            sum(r["observed_target_speedup_vs_1"] is not None for r in medium), 2
        )

    def test_different_targets_do_not_share_baseline(self):
        rows = copy.deepcopy(
            [r for r in self.report["comparison_rows"] if r["parent"] == "medium"]
        )
        for row in rows:
            if row["threads"] == 2:
                row["target_gap_relative"] = 0.01
        result = review.comparison(rows)
        self.assertIsNone(
            next(r for r in result if r["threads"] == 2)["observed_target_speedup_vs_1"]
        )

    def test_allocation_dedup_and_no_step_cpu_double_count(self):
        value = review.flow.load(self.return_file)["accounting"]
        rows = review.allocation_rows([value, value])
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["scheduler_total_cpu_seconds"], 13 * 3600 + 40 * 60 + 12
        )
        changed = copy.deepcopy(value)
        changed["rows"][0]["TotalCPU"] = "00:00:01"
        with self.assertRaises(ValueError):
            review.allocation_rows([value, changed])

    def test_strict_frontier_keeps_ties_and_rejects_dominated(self):
        rows = [
            dict(
                parent="p",
                threads=t,
                stop="gap_target",
                first_observed_target_seconds=x,
                process_cpu_seconds=x,
                sampled_cgroup_peak_bytes=x,
            )
            for t, x in [(1, 10), (2, 10), (4, 20)]
        ]
        value = review.profile(rows)
        self.assertEqual(value["strict_pareto_threads"], [1, 2])
        self.assertEqual(value["selected_development_threads"], 1)
        self.assertIsNone(review.profile([])["selected_development_threads"])

    def test_report_reproducible(self):
        self.assertEqual(self.report, review.build_report())

    def test_committed_report_matches_recomputed_values(self):
        self.assertEqual(
            self.report,
            json.loads(
                (review.EVIDENCE / "pr79-sprint-b-review.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        self.assertEqual(
            review.markdown(self.report),
            (review.EVIDENCE / "pr79-sprint-b-review.md").read_text(encoding="utf-8"),
        )

    def test_analysis_cli_writes_report_without_solver_or_network(self):
        output = self.directory / "new review"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/evidence/review_pr79_sprint_b.py"),
                "--output-directory",
                str(output),
            ],
            cwd=self.directory,
            capture_output=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout)["validated_attempts"], 10)
        self.assertEqual(
            json.loads(
                (output / "pr79-sprint-b-review.json").read_text(encoding="utf-8")
            ),
            self.report,
        )


if __name__ == "__main__":
    unittest.main()
