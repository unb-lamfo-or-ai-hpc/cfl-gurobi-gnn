"""Byte-stable installed synthetic qualification; no solver or scheduler access."""

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import paired_matrix_executor as matrix  # noqa: E402

DIRECTORY = ROOT / "docs/evidence/pr75/fault-probe-c845ccd6b224"
SHA = "ca2381d4a1396f3d40b76b653bd7f81f591b830b5f38df8d77dfc12ecc1f1602"
SOURCE = "c845ccd6b2242022c05ac16cbf2f666c023b8e82"
PLAN_SHA = "c7070710417661afe838326fafc36d2c0bc0cc5af70618593f909388e9ec78ea"


class InstalledFaultReceiptTests(unittest.TestCase):
    def setUp(self):
        self.raw = (DIRECTORY / "no_solver_fault_probe.json").read_bytes()
        self.value = matrix.old.strict_payload(self.raw)

    def test_exact_imported_bytes_and_canonical_json(self):
        self.assertEqual(len(self.raw), 2037)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), SHA)
        self.assertEqual(self.raw, matrix.contract.encoded(self.value))

    def test_exact_manifest_and_member_set(self):
        raw = (DIRECTORY / "SHA256SUMS.txt").read_bytes()
        self.assertEqual(raw, (SHA + "  no_solver_fault_probe.json\n").encode())
        self.assertEqual(len(raw), 93)
        self.assertEqual(
            {p.name for p in DIRECTORY.iterdir()},
            {"no_solver_fault_probe.json", "SHA256SUMS.txt"},
        )

    def test_historical_source_and_protocol(self):
        self.assertEqual(self.value["source_commit"], SOURCE)
        self.assertEqual(self.value["schema_version"], 1)
        self.assertEqual(
            self.value["protocol_id"],
            "installed_paired_matrix_no_solver_fault_probe_v1",
        )

    def test_exact_tests_passed_with_no_skips(self):
        self.assertIs(self.value["passed_no_solver_fault_probe"], True)
        for name, expected in (
            ("tests_run", 25),
            ("failures", 0),
            ("errors", 0),
            ("skipped", 0),
        ):
            self.assertIs(type(self.value[name]), int)
            self.assertEqual(self.value[name], expected)

    def test_all_fourteen_reviewed_dependencies_remain_unchanged(self):
        expected = {
            **matrix.pins(),
            **{
                name: matrix.adapter.screen.digest(
                    ROOT / name
                    if name.startswith("tests/")
                    else ROOT / "scripts/evidence" / name
                )
                for name in (
                    "paired_matrix_no_solver_probe.py",
                    "tests/evidence/test_paired_matrix_executor.py",
                    "tests/evidence/test_isolated_attempt_worker.py",
                )
            },
        }
        self.assertEqual(len(expected), 14)
        self.assertEqual(self.value["dependency_sha256"], expected)

    def test_no_execution_export_or_scientific_promotion(self):
        for name in ("optimization_runs_added", "submissions_added"):
            self.assertIs(type(self.value[name]), int)
            self.assertEqual(self.value[name], 0)
        for name in (
            "actual_high_memory_pressure_injected",
            "kernel_ram_enforcement_in_allocation_qualified",
            "comparison_submission_ready",
            "raw_logs_included",
            "scientific_reporting_eligible",
        ):
            self.assertIs(self.value[name], False)

    def test_reported_unapproved_plan_recomputes_without_hpc_access(self):
        matrix.reviewed_evidence()
        plan = matrix.plan_for(SOURCE)
        matrix.validate_plan(plan)
        self.assertEqual(plan["plan_sha256"], PLAN_SHA)
        self.assertIs(plan["resource_budget_approved"], False)
        self.assertIs(plan["scientific_reporting_eligible"], False)
        approval = matrix.approval_template(plan)
        for gate in (
            "exact_head_four_ci_arms_reviewed",
            "installed_no_solver_fault_probe_reviewed",
            "explicit_resource_budget_and_submission_approved",
        ):
            self.assertIs(approval[gate], False)

    def test_no_private_paths_or_license_metadata(self):
        text = json.dumps(self.value)
        for forbidden in (
            "/home/",
            "/raid/",
            "gurobi.lic",
            "LICENSEID",
            "WLSACCESSID",
            "WLSSECRET",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
