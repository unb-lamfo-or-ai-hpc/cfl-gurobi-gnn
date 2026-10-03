"""Integrity regression tests for CPU pilot evidence, without licensed execution.

SPDX-License-Identifier: MIT
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import package_pr66_pilot as packaging  # noqa: E402
import pr66_thread_pilot as pilot  # noqa: E402
import test_pr66_thread_pilot  # noqa: E402
from collect_computational_ledger import digest, write_json  # noqa: E402


class PackageTests(unittest.TestCase):
    def fixture(self, root):
        _, plan_dir, sha = test_pr66_thread_pilot.PilotTests().simulated_plan(root)
        plan = pilot.strict_json(plan_dir / "pilot_plan.json")
        executions = []
        for cap in pilot.CAPS:
            for model in plan["models"]:
                name = f"{model['difficulty']}-threads{cap}"
                out = plan_dir / name
                out.mkdir()
                params = {
                    "Threads": cap,
                    "Seed": 42,
                    "TimeLimit": 300,
                    "MIPGap": 0.1,
                    "SoftMemLimit": 48,
                }
                report = {
                    **model,
                    "plan_sha256": sha,
                    "parameters": params,
                    "parameters_sha256": hashlib.sha256(
                        pilot.canonical(params).encode()
                    ).hexdigest(),
                    "algorithm_defaults": {
                        k: {"effective": -1, "version_default": -1}
                        for k in plan["config"]["default_parameters_observed"]
                    },
                    "source_objective_sense": "MAXIMIZE",
                    "effective_objective_sense": "MINIMIZE",
                    "objective_sense_override_applied": True,
                    "gurobi_version": [13, 0, 1],
                    "model_unchanged_after_execution": True,
                    "scientific_reporting_eligible": False,
                    "affinity": {"physical_cores": 16},
                    "optimize_wall_seconds": 300,
                    "process_cpu_seconds": 320,
                    "process_peak_rss_bytes": 1000,
                    "mip_gap_relative": 0.3,
                    "primal": 10,
                    "dual": 7,
                    "termination": "time_limit",
                    "solver_status": 9,
                }
                write_json(out / "attempt_report.json", report)
                executions.append(
                    {
                        "attempt": name,
                        "exit_code": 0,
                        "report_sha256": digest(out / "attempt_report.json"),
                    }
                )
        execution = {
            "plan_sha256": sha,
            "executions": executions,
            "failure_type": None,
            "scientific_reporting_eligible": False,
        }
        write_json(plan_dir / "pilot_execution_report.json", execution)
        return plan_dir, sha

    def test_complete_package_has_no_raw_or_private_logs_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory, sha = self.fixture(root)
            (directory / "secret.private.log").write_text("/home/private")
            output = root / "evidence.tar.gz"
            packaging.package(directory, sha, output)
            with packaging.tarfile.open(output) as archive:
                self.assertEqual(len(archive.getmembers()), 15)
                receipt = json.load(archive.extractfile("verification.json"))
                self.assertTrue(receipt["complete_matrix"])
                self.assertFalse(receipt["scientific_reporting_eligible"])
            with self.assertRaisesRegex(ValueError, "fresh_package"):
                packaging.package(directory, sha, output)

    def test_tampered_attempt_not_rehashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory, sha = self.fixture(root)
            (directory / "easy-threads1/attempt_report.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash_mismatch"):
                packaging.package(directory, sha, root / "evidence.tar.gz")
            self.assertFalse((root / "evidence.tar.gz").exists())

    def test_partial_execution_is_explicit_and_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory, sha = self.fixture(Path(tmp))
            path = directory / "pilot_execution_report.json"
            execution = pilot.strict_json(path)
            execution["executions"] = execution["executions"][:1]
            execution["failure_type"] = "TimeoutExpired"
            write_json(path, execution)
            rows, _, complete = packaging.verify(directory, sha)
            self.assertEqual(len(rows), 1)
            self.assertFalse(complete)

    def test_wrong_plan_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory, _ = self.fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError, "plan_hash_mismatch"):
                packaging.verify(directory, "0" * 64)

    def test_objective_normalization_claim_is_checked_even_after_rehashing(self):
        for field, value in (
            ("source_objective_sense", "MINIMIZE"),
            ("effective_objective_sense", "MAXIMIZE"),
            ("objective_sense_override_applied", False),
            ("objective_sense_override_applied", 1),
        ):
            with (
                self.subTest(field=field, value=value),
                tempfile.TemporaryDirectory() as tmp,
            ):
                directory, sha = self.fixture(Path(tmp))
                path = directory / "easy-threads1/attempt_report.json"
                report = pilot.strict_json(path)
                report[field] = value
                write_json(path, report)
                execution_path = directory / "pilot_execution_report.json"
                execution = pilot.strict_json(execution_path)
                execution["executions"][0]["report_sha256"] = digest(path)
                write_json(execution_path, execution)
                with self.assertRaisesRegex(ValueError, "contract_mismatch"):
                    packaging.verify(directory, sha)


if __name__ == "__main__":
    unittest.main()
