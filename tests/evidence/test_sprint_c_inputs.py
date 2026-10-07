"""Metadata scope, leakage and real CLI regression tests; no solver imports."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts/evidence/audit_sprint_c_inputs.py"
)
SPEC = importlib.util.spec_from_file_location("sprint_c_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def seal(plan):
    plan["contract_sha256"] = audit.digest(
        audit.canonical({k: v for k, v in plan.items() if k not in audit.IGNORED})
    )
    return plan


def fixture():
    rows = []
    for i, role in enumerate(audit.ROLES):
        rows.append(
            {
                "parent_instance_id": f"CFL_easy_instance_{i}",
                "sample_id": str(i),
                "role": role,
                "label_mip_gap_relative": 0.01,
                "sampling_strategy": "original",
                "graph_authority": "gurobi",
                "label_solver": "gurobi",
                **{
                    k: str(i + 1) * 64
                    for k in (
                        "mip_sha256",
                        "graph_sha256",
                        "root_sha256",
                        "label_sha256",
                        "label_contract_sha256",
                    )
                },
            }
        )
    return seal(
        {
            "schema_version": 1,
            "records": rows,
            "graph_manifest_sha256": audit.digest(b"{}\n"),
            "partition_counts": dict.fromkeys(audit.ROLES, 1),
            "parent_ids_by_role": {
                r: [f"CFL_easy_instance_{i}"] for i, r in enumerate(audit.ROLES)
            },
        }
    )


class PlanAuditTests(unittest.TestCase):
    def test_valid_metadata_is_not_feasibility(self):
        result = audit.plan_summary(fixture())
        self.assertTrue(result["metadata_consistent"])
        self.assertNotIn("training_admitted", result)

    def test_changed_contract_rejected(self):
        plan = fixture()
        plan["records"][0]["label_mip_gap_relative"] = 0.02
        self.assertIn("contract_hash_mismatch", audit.plan_summary(plan)["issues"])

    def test_parent_leakage(self):
        plan = fixture()
        plan["records"][1]["parent_instance_id"] = "CFL_easy_instance_0"
        self.assertIn("parent_role_leakage", audit.plan_summary(seal(plan))["issues"])

    def test_same_mip_across_roles(self):
        plan = fixture()
        plan["records"][1]["mip_sha256"] = plan["records"][0]["mip_sha256"]
        self.assertIn(
            "mip_identity_role_leakage", audit.plan_summary(seal(plan))["issues"]
        )

    def test_invalid_gaps(self):
        for gap in (None, -0.1, 0.1001, True, "0.01"):
            with self.subTest(gap=gap):
                plan = fixture()
                plan["records"][0]["label_mip_gap_relative"] = gap
                self.assertIn(
                    "missing_or_ineligible_label_gap",
                    audit.plan_summary(seal(plan))["issues"],
                )

    def test_duplicate_samples(self):
        plan = fixture()
        plan["records"].append(copy.deepcopy(plan["records"][0]))
        self.assertIn(
            "missing_or_duplicate_sample", audit.plan_summary(seal(plan))["issues"]
        )

    def test_untrusted_text_not_exported(self):
        plan = fixture()
        plan["secret"] = "SENSITIVE_SENTINEL"
        plan["records"][0]["graph_relative_path"] = "/private/SENSITIVE_SENTINEL"
        self.assertNotIn(
            "SENSITIVE_SENTINEL", json.dumps(audit.plan_summary(seal(plan)))
        )

    def test_strict_json(self):
        for value in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(ValueError):
                audit.strict_json(value)

    def test_missing_role(self):
        plan = fixture()
        plan["records"].pop()
        self.assertIn("missing_role", audit.plan_summary(seal(plan))["issues"])


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "data"
        self.models = self.root / "models"
        self.models.mkdir(parents=True)
        self.plan = self.models / "gasse_training_plan.json"
        self.plan.write_text(json.dumps(fixture()), encoding="utf-8")

    def test_collect_and_match_manifest(self):
        (self.models / "gurobi_graph_manifest.jsonl").write_bytes(b"{}\n")
        result = audit.collect(self.root)
        self.assertTrue(result["plans"][0]["graph_manifest_bytes_observed"])
        self.assertTrue(result["inventory_complete"])
        self.assertFalse(result["training_admitted"])
        self.assertEqual(result["optimization_runs_added"], 0)
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_no_metadata_is_not_admission(self):
        self.plan.unlink()
        result = audit.collect(self.root)
        self.assertFalse(result["metadata_candidates_present"])
        self.assertFalse(result["training_admitted"])

    def test_invalid_report_preserved_not_exposed(self):
        self.plan.write_bytes(b"SENSITIVE_SENTINEL")
        result = audit.collect(self.root)
        self.assertFalse(result["inventory_complete"])
        self.assertEqual(len(result["failures"]), 1)
        self.assertNotIn("SENSITIVE_SENTINEL", json.dumps(result))
        self.assertEqual(self.plan.read_bytes(), b"SENSITIVE_SENTINEL")

    def test_scan_limits(self):
        with self.assertRaises(ValueError):
            audit.collect(self.root, max_entries=0)
        with self.assertRaises(ValueError):
            audit.collect(self.root, seconds=-1)
        self.assertFalse(audit.collect(self.root, max_bytes=1)["inventory_complete"])

    def test_symlink_not_followed(self):
        link = self.models / "linked"
        try:
            link.symlink_to(self.base, target_is_directory=True)
        except OSError:
            self.skipTest("symlink privilege unavailable")
        result = audit.collect(self.root)
        self.assertEqual(result["symlinks_skipped"], 1)
        self.assertEqual(len(result["plans"]), 1)

    def test_cli_bytes_and_no_overwrite(self):
        output = self.base / "receipt.json"
        before = self.plan.read_bytes()
        command = [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--data-root",
            str(self.root),
            "--output",
            str(output),
        ]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(
            json.loads(first.stdout)["receipt_sha256"],
            audit.digest(output.read_bytes()),
        )
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(self.plan.read_bytes(), before)

    def test_cli_output_inside_dataset_rejected(self):
        output = self.root / "receipt.json"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "--data-root",
                str(self.root),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
