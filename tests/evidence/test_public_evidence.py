"""Standard-library tests; no private receipts, solvers or GPUs required.

SPDX-License-Identifier: MIT
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "evidence"


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


VERIFIER = module("verify_mvp1_closure_receipts")
PUBLISHER = module("publish_mvp2_baseline")
EVIDENCE = ROOT / "docs" / "evidence" / "mvp1"
HEADER = (
    "JobID|JobName|State|ExitCode|ElapsedRaw|TotalCPU|AllocCPUS|AllocTRES|MaxRSS|ReqMem"
)


def accounting():
    return (
        HEADER
        + "\n"
        + "\n".join(
            f"{job}|training|COMPLETED|0:0|12|00:00:10|8|cpu=8,gres/gpu=1||64G"
            for job in PUBLISHER.JOBS
        )
    )


def read(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


class IntegrityTests(unittest.TestCase):
    def test_duplicate_checksum_is_rejected(self):
        row = ("a" * 64 + "  a.json\n").encode()
        with self.assertRaises(AssertionError):
            VERIFIER.checksum_lines(row + row)

    def test_malformed_checksum_is_rejected(self):
        with self.assertRaises(AssertionError):
            VERIFIER.checksum_lines(b"not-a-hash  a.json\n")

    def test_wrong_package_is_rejected_before_tar_read(self):
        with tempfile.TemporaryDirectory() as directory:
            wrong = Path(directory) / "wrong.tar.gz"
            wrong.write_bytes(b"not the frozen receipts")
            with self.assertRaises(AssertionError):
                VERIFIER.verify(wrong)

    def test_optimized_python_cannot_bypass_integrity_checks(self):
        result = subprocess.run(
            [
                sys.executable,
                "-O",
                str(SCRIPTS / "verify_mvp1_closure_receipts.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("assertion checks enabled", result.stderr)

    def test_manifest_covers_exactly_four_summaries(self):
        checks = VERIFIER.checksum_lines((EVIDENCE / "SHA256SUMS.txt").read_bytes())
        self.assertEqual(
            set(checks),
            {
                "closure_verification.json",
                "incumbent_inventory.json",
                "hardware_allocations.json",
                "parent_coverage.json",
            },
        )
        for name, expected in checks.items():
            payload = (EVIDENCE / name).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), expected)
            self.assertLess(len(payload), 100_000)
            self.assertIsNone(PUBLISHER.PRIVATE.search(payload.decode("utf-8")))

    def test_hash_bound_evidence_preserves_bytes_across_checkouts(self):
        attributes = (ROOT / ".gitattributes").read_text()
        self.assertIn("docs/evidence/mvp1/*.json -text", attributes)
        self.assertIn("docs/evidence/mvp1/SHA256SUMS.txt text eol=lf", attributes)
        self.assertNotIn(b"\r", (EVIDENCE / "SHA256SUMS.txt").read_bytes())

    def test_archive_receipts_are_not_scientific_or_publication_certification(self):
        summary = read("closure_verification.json")
        self.assertEqual(summary["closure_package_sha256"], VERIFIER.EXPECTED)
        self.assertEqual(summary["included_files"], 8790)
        self.assertEqual(summary["archive_parts"], 26)
        self.assertEqual(summary["policy_excluded_operational_paths"], 7)
        for flag in (
            "upload_ready",
            "scientific_reporting_eligible",
            "zenodo_upload_performed",
            "large_archives_rehashed_locally",
        ):
            self.assertFalse(summary[flag])

    def test_existing_output_is_never_overwritten(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "fresh output"),
        ):
            PUBLISHER.publish(Path("missing.tar.gz"), Path(directory))

    def test_projection_is_allowlisted_not_a_copy_of_private_receipts(self):
        verification = read("closure_verification.json")
        inventory = read("incumbent_inventory.json")
        verification["incumbent_table_observations_by_path_solver"] = inventory[
            "observations_by_path_solver"
        ]
        verification["unapproved_private_path"] = "/raid/private/research"
        inventory["incumbent_tables"] = []
        inventory["unapproved_private_path"] = "/home/private/research"
        payloads = PUBLISHER.publication_payloads(verification, inventory, [])
        self.assertFalse(
            any(b"unapproved_private_path" in payload for payload in payloads.values())
        )

    def test_private_marker_in_allowed_field_is_rejected(self):
        verification = read("closure_verification.json")
        inventory = read("incumbent_inventory.json")
        verification["incumbent_table_observations_by_path_solver"] = inventory[
            "observations_by_path_solver"
        ]
        verification["scope"] = "/raid/private/research"
        inventory["incumbent_tables"] = []
        with self.assertRaisesRegex(ValueError, "prohibited private marker"):
            PUBLISHER.publication_payloads(verification, inventory, [])

    def test_private_marker_scanner_detects_supported_markers(self):
        for marker in (
            "/home/person/file",
            "/raid/data/file",
            "D:\\Downloads\\file",
            "gho_abcdef",
            "WLSSECRET=abc",
            "password: abc",
        ):
            self.assertIsNotNone(PUBLISHER.PRIVATE.search(marker))


class AccountingTests(unittest.TestCase):
    def test_parent_allocations_only(self):
        text = (
            accounting() + "\n3307.batch|worker|COMPLETED|0:0|12|00:00:10|8|cpu=8||64G"
        )
        rows = PUBLISHER.training_allocations(text)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["allocated_gpus"] == 1 for row in rows))
        self.assertTrue(all(row["gpu_utilization"] is None for row in rows))
        self.assertTrue(all(not row["ddp_execution_verified"] for row in rows))

    def test_unknown_gpu_allocation_is_not_zero(self):
        rows = PUBLISHER.training_allocations(accounting().replace(",gres/gpu=1", ""))
        self.assertTrue(all(row["allocated_gpus"] is None for row in rows))

    def test_missing_job_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            PUBLISHER.training_allocations("\n".join(accounting().splitlines()[:-1]))

    def test_duplicate_job_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            PUBLISHER.training_allocations(
                accounting() + "\n" + accounting().splitlines()[1]
            )

    def test_bad_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            PUBLISHER.training_allocations("JobID|State\n3307|COMPLETED")

    def test_historical_training_has_one_allocated_gpu(self):
        rows = read("hardware_allocations.json")["jobs"]
        self.assertEqual({row["job_id"] for row in rows}, set(PUBLISHER.JOBS))
        for row in rows:
            self.assertEqual(row["allocated_gpus"], 1)
        self.assertEqual(
            next(row["state"] for row in rows if row["job_id"] == "3422"), "TIMEOUT"
        )


class ResearchScopeTests(unittest.TestCase):
    def test_parent_inventory_is_exhaustive_not_a_solver_run_ledger(self):
        parents = read("parent_coverage.json")["parents"]
        self.assertEqual(len(parents), 90)
        self.assertEqual(len({row["parent_id"] for row in parents}), 90)
        for difficulty in ("easy", "medium", "hard"):
            self.assertEqual(
                sum(row["difficulty"] == difficulty for row in parents), 30
            )
        self.assertEqual(sum(row["in_frozen_learning_cohort"] for row in parents), 54)
        self.assertTrue(
            all(row["unique_feasible_incumbents"] is None for row in parents)
        )

    def test_footer_rows_are_not_unique_feasible_incumbents(self):
        inventory = read("incumbent_inventory.json")
        self.assertEqual(inventory["cohort_by_class"], {"easy": 30, "medium": 24})
        groups = inventory["observations_by_path_solver"]
        self.assertEqual(
            {solver: row["footer_rows"] for solver, row in groups.items()},
            {"gurobi": 7860, "scip": 119, "unattributed": 284},
        )
        self.assertIsNone(inventory["complete_gurobi_54_parent_incumbent_total"])
        self.assertIsNone(inventory["complete_scip_54_parent_incumbent_total"])

    def test_only_declared_parent_tables_are_counted(self):
        fixture = {
            "cohort": ["CFL_easy_instance_0"],
            "incumbent_tables": [
                {"parent_ids_from_path": ["CFL_easy_instance_0"]},
                {"parent_ids_from_path": ["CFL_easy_instance_0"]},
            ],
        }
        rows = PUBLISHER.parent_coverage(fixture)
        self.assertEqual(rows[0]["observed_incumbent_tables"], 2)
        self.assertEqual(rows[1]["observed_incumbent_tables"], 0)
        self.assertIsNone(rows[1]["unique_feasible_incumbents"])

    def test_planned_gpu_comparison_has_five_arms_without_execution_claims(self):
        plan = json.loads(
            (ROOT / "configs/experiments/mvp2_gpu_comparison_v1.json").read_text()
        )
        self.assertEqual(
            [(arm["execution"], arm["gpus"]) for arm in plan["arms"]],
            [("serial", 1), ("ddp", 1), ("ddp", 2), ("ddp", 4), ("ddp", 8)],
        )
        self.assertEqual(plan["pull_request_base"], "develop")
        self.assertFalse(plan["more_gpus_guarantee_higher_quality"])
        self.assertFalse(plan["test_outcomes_select_configuration"])
        self.assertEqual(plan["training_runs_executed"], 0)
        self.assertEqual(plan["solver_runs_executed"], 0)
        self.assertIn("same_effective_global_batch", plan["scaling_controls"])
        self.assertIn(
            "padding_and_duplicate_samples_accounted_for",
            plan["qualification_required"],
        )


if __name__ == "__main__":
    unittest.main()
