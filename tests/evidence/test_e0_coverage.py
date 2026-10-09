"""Offline E0 scope, sanitization and reconciliation regression tests."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import reconcile_e0_coverage as e0  # noqa: E402


class E0Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "data"
        for group in e0.GROUPS:
            (self.root / group).mkdir(parents=True)

    def fixture(self, name=None, value=None):
        row = {
            "source_instance_id": "CFL_easy_instance_0",
            "method": e0.METHODS[0],
            "role": "test",
            "gate_status": "passed",
            "parameters": {"Threads": 1, "Seed": 42},
            "solve": {"primal": 5.0, "right_censored": True},
            "contract_sha256": "a" * 64,
            "reason_detail": "SECRET LICENSE /private/path",
        }
        row["parameter_sha256"] = e0.digest(e0.canonical(row["parameters"]).encode())
        path = self.root / "analysis" / (name or f"{e0.METHODS[0]}.json")
        path.write_text(json.dumps(row if value is None else value), encoding="utf-8")
        return path

    def test_population(self):
        rows = e0.population()
        self.assertEqual(len(rows), 48)
        self.assertEqual(sum(int(r["published_records"]) for r in rows), 24)
        self.assertEqual(
            len({r["parent"] for r in rows if r["published_records"] == "0"}), 8
        )

    def test_collect_sanitizes_and_never_admits(self):
        self.fixture()
        receipt = e0.collect(self.root)
        self.assertNotIn("SECRET", json.dumps(receipt))
        row = receipt["candidates"][0]
        self.assertTrue(row["parameter_digest_matches"])
        self.assertEqual(row["outcomes"]["primal"], 5.0)
        self.assertFalse(row["reuse_admitted"])
        self.assertFalse(receipt["solver_execution_admitted"])

    def test_missing_not_absence_proof(self):
        receipt = e0.collect(self.root)
        self.assertTrue(receipt["recognized_metadata_scan_complete"])
        self.assertFalse(receipt["absence_proven"])
        self.assertEqual(
            e0.coverage(receipt)[0]["state"], "not_found_in_recognized_scope"
        )

    def test_missing_group_is_incomplete(self):
        (self.root / "models").rmdir()
        self.assertFalse(e0.collect(self.root)["recognized_metadata_scan_complete"])

    def test_aggregate_not_promoted_to_method(self):
        self.fixture(
            "per_method_outcomes.json",
            {
                "records": [
                    {
                        "source_instance_id": "CFL_medium_instance_13",
                        "method": e0.METHODS[0],
                        "role": "test",
                        "primal": 3,
                    }
                ]
            },
        )
        rows = e0.coverage(e0.collect(self.root))
        row = next(
            r
            for r in rows
            if r["parent"] == "CFL_medium_instance_13" and r["method"] == e0.METHODS[0]
        )
        self.assertEqual(row["state"], "aggregate_only")
        self.assertEqual(row["canonical_role"], "train")
        self.assertEqual(
            row["evaluation_stratum"], "label_excluded_historically_exposed"
        )
        self.assertTrue(row["role_disagreement"])

    def test_duplicate_bytes_not_new_observation(self):
        path = self.fixture()
        copy = self.root / "models" / path.name
        copy.write_bytes(path.read_bytes())
        row = e0.coverage(e0.collect(self.root))[0]
        self.assertEqual(row["distinct_method_metadata"], 1)

    def test_ignores_raw_logs_and_unrelated_files(self):
        self.fixture("console.log", {"secret": "not read"})
        self.fixture("unknown.json", {"secret": "not read"})
        (self.root / "analysis/secrets").mkdir()
        (self.root / "analysis/secrets/per_method_outcomes.json").write_bytes(
            b"invalid"
        )
        receipt = e0.collect(self.root)
        self.assertEqual(receipt["bytes_read"], 0)

    def test_bad_json_is_recorded_not_exported(self):
        path = self.fixture()
        path.write_bytes(b'{"secret":1,"secret":2}')
        receipt = e0.collect(self.root)
        self.assertEqual(len(receipt["failures"]), 1)
        self.assertFalse(receipt["recognized_metadata_scan_complete"])
        self.assertNotIn("secret", json.dumps(receipt))

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            e0.strict_json('{"value":NaN}')

    def test_bounded_scan(self):
        self.fixture()
        with self.assertRaises(ValueError):
            e0.collect(self.root, max_entries=0)

    def test_plan_digest(self):
        plan = {"policy": {}, "checkpoint_sha256": "b" * 64}
        plan["contract_sha256"] = e0.digest(e0.canonical(plan).encode())
        plan["contract_valid"] = True
        self.fixture("pr59_heldout_guidance_plan.json", plan)
        receipt = e0.collect(self.root)
        self.assertTrue(receipt["plans"][0]["contract_digest_matches"])

    def test_cli_hash_and_preservation(self):
        self.fixture()
        output = Path(self.temp.name) / "receipt.json"
        with contextlib.redirect_stdout(io.StringIO()):
            e0.main(["collect", "--data-root", str(self.root), "--output", str(output)])
        data = output.read_bytes()
        with self.assertRaises(ValueError):
            e0.main(["collect", "--data-root", str(self.root), "--output", str(output)])
        self.assertEqual(output.read_bytes(), data)
        dest = Path(self.temp.name) / "review"
        with self.assertRaises(ValueError):
            e0.main(
                [
                    "review",
                    "--receipt",
                    str(output),
                    "--expected-sha256",
                    "0" * 64,
                    "--output-directory",
                    str(dest),
                ]
            )
        self.assertFalse(dest.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            e0.main(
                [
                    "review",
                    "--receipt",
                    str(output),
                    "--expected-sha256",
                    e0.digest(data),
                    "--output-directory",
                    str(dest),
                ]
            )
        proposal = json.loads((dest / "proposal.json").read_text())
        self.assertFalse(proposal["execution_admitted"])
        self.assertEqual(len(proposal["rows"]), 48)

    def test_output_inside_data_rejected(self):
        with self.assertRaises(ValueError):
            e0.main(
                [
                    "collect",
                    "--data-root",
                    str(self.root),
                    "--output",
                    str(self.root / "result.json"),
                ]
            )

    def test_no_side_effect_imports(self):
        import ast

        tree = ast.parse(Path(e0.__file__).read_text())
        imported = {
            n.names[0].name.split(".")[0]
            for n in ast.walk(tree)
            if isinstance(n, ast.Import)
        }
        self.assertFalse(imported & {"torch", "gurobipy", "subprocess", "pickle"})


if __name__ == "__main__":
    unittest.main()
