"""Cross-run numeric conflict is evidence to investigate, never a solver retry."""

import ast
import copy
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import audit_pr86_wave49_numeric as audit  # noqa: E402


class NumericAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = audit.q.read(audit.DEST / "public_return.json")
        cls.wave = audit.load_wave(cls.raw)
        cls.rows = audit.records(cls.wave)

    def test_real_bound_conflicts_keep_numeric_qualification_pending(self):
        report = audit.summary(self.wave, self.rows)
        self.assertEqual(report["campaign_cells_collected"], 165)
        self.assertEqual(report["previously_reviewed_cells"], 147)
        self.assertEqual(report["remaining_unexecuted_cells"], 45)
        self.assertEqual(report["reported_target_reaching_cells_in_wave"], 1)
        self.assertEqual(report["reported_censored_cells_in_wave"], 17)
        self.assertEqual(len(report["findings"]), 3)
        self.assertEqual(
            {r["bound_cell"] for r in report["findings"]}, {"M4-threads8-seed42-M2"}
        )
        self.assertAlmostEqual(
            max(r["absolute_difference"] for r in report["findings"]),
            0.004595841778280985,
        )
        self.assertTrue(report["new_wave_numeric_qualification_pending"])
        self.assertFalse(report["remaining_dispatch_admitted"])
        self.assertFalse(report["scientific_reporting_eligible"])
        self.assertFalse(report["cause_proven"])

    def test_identity_tolerance_and_no_conflict_cases(self):
        bound = next(r for r in self.rows if r["status_code"] == 2)
        candidate = min(self.rows, key=lambda r: r["primal"])
        self.assertEqual(len(audit.cross_run_findings([bound, candidate])), 1)
        different = copy.deepcopy(candidate)
        different["model_sha256"] = "f" * 64
        self.assertEqual(audit.cross_run_findings([bound, different]), [])
        near = copy.deepcopy(candidate)
        near["primal"] = bound["dual"] - 1e-8
        self.assertEqual(audit.cross_run_findings([bound, near]), [])
        self.assertEqual(audit.cross_run_findings([candidate]), [])

    def test_rounding_exposes_scaled_row_risk_without_changing_values(self):
        data = dict(
            lower=np.array([0.0, 0.0]),
            upper=np.array([1.0, 10.0]),
            types=np.array(["B", "C"]),
            objective=np.array([1.0, 0.0]),
            rows=np.array([0, 0]),
            columns=np.array([0, 1]),
            coefficients=np.array([-1e-6, 1e-12]),
            senses=np.array(["<"]),
            rhs=np.array([0.0]),
        )
        x = np.array([9e-6, 5.0])
        before = x.copy()
        report = audit.array_diagnostics(data, x, 9e-6)
        self.assertTrue(report["stored"]["valid"])
        self.assertTrue(report["rounded_in_memory_only"]["valid"])
        self.assertEqual(report["integer_values_changed_by_rounding"], 1)
        self.assertGreater(
            report["rounded_in_memory_only"][
                "max_row_violation_divided_by_max_abs_row_coefficient"
            ],
            1e-6,
        )
        self.assertEqual(
            report["rounded_in_memory_only"][
                "rows_above_1e_minus6_after_row_normalization"
            ],
            1,
        )
        self.assertFalse(
            report["stored"]["extended_precision"]["exact_arithmetic_certificate"]
        )
        np.testing.assert_array_equal(x, before)

    def test_hash_tampering_and_reproducible_outputs(self):
        with self.assertRaisesRegex(ValueError, "wave49_return_hash"):
            audit.load_wave(self.raw + b" ")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            audit.publish(folder)
            audit.publish(folder)
            for name in ("numeric_screen.json", "wave_results.csv", "manifest.json"):
                self.assertEqual(
                    audit.q.read(folder / name), audit.q.read(audit.DEST / name)
                )

    def test_no_optimization_submission_or_scheduler_calls_in_auditor(self):
        source = Path(audit.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {
            n.func.attr
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        self.assertTrue(
            called.isdisjoint({"optimize", "submit", "command", "run", "Popen"})
        )
        self.assertIn("newly_observed_private_hashes_are_not_historical_seals", source)
        self.assertIn("sealed_solver_log", source)
        self.assertIn("16 * 2**30", source)

    def binding_fixture(self, folder):
        row = self.rows[0]
        group = folder / "group-0"
        admission = group / "admission"
        admission.mkdir(parents=True)
        frozen = self.wave["plan"]["groups"][0]
        requests = []
        for i, cell in enumerate(frozen["cells"]):
            name = f"bundle-{i}.json"
            value = {
                "cell": cell,
                "context": frozen["context"],
                "private_mip_path": "private-model",
            }
            digest = audit.q.write(admission / name, value)
            requests.append({"file": name, "sha256": digest})
        audit.q.write(group / "requests.json", requests)
        return row, group, requests

    def test_installed_bindings_require_historical_seals_and_canonical_names(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            row, group, requests = self.binding_fixture(folder)
            sealed = {"bundle_sha256": [r["sha256"] for r in requests]}
            with patch.object(audit.f0, "member", return_value=sealed):
                value = audit.installed_bundle(self.wave, row, folder)
                self.assertEqual(value["cell"]["cell_id"], row["cell_id"])
                bad = copy.deepcopy(requests)
                bad[0]["file"] = "../bundle-0.json"
                with (
                    patch.object(audit.q, "read", return_value=audit.q.encoded(bad)),
                    self.assertRaisesRegex(ValueError, "historical_bundle_seals"),
                ):
                    audit.installed_bundle(self.wave, row, folder)
                changed = copy.deepcopy(requests)
                changed[0]["sha256"] = "f" * 64
                with (
                    patch.object(
                        audit.q, "read", return_value=audit.q.encoded(changed)
                    ),
                    self.assertRaisesRegex(ValueError, "historical_bundle_seals"),
                ):
                    audit.installed_bundle(self.wave, row, folder)

    def test_installed_bundle_checks_complete_cell_and_context(self):
        for field in ("cell", "context"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                row, _, requests = self.binding_fixture(folder)
                frozen = self.wave["plan"]["groups"][0]
                bundle = {
                    "cell": copy.deepcopy(frozen["cells"][0]),
                    "context": copy.deepcopy(frozen["context"]),
                }
                if field == "cell":
                    bundle["cell"]["threads"] = 99
                else:
                    bundle["context"]["source_commit"] = "f" * 40
                raw = audit.q.encoded(bundle)
                requests[0]["sha256"] = audit.q.digest(raw)
                sealed = {"bundle_sha256": [r["sha256"] for r in requests]}
                with (
                    patch.object(audit.f0, "member", return_value=sealed),
                    patch.object(
                        audit.q, "read", side_effect=[audit.q.encoded(requests), raw]
                    ),
                    self.assertRaisesRegex(ValueError, "installed_cell_and_context"),
                ):
                    audit.installed_bundle(self.wave, row, folder)

    def test_private_paths_and_public_stdout_remain_scoped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "safe.json"
            audit.q.write(file, {})
            self.assertEqual(audit.scoped_regular_file(file, root), file)
            with self.assertRaisesRegex(ValueError, "scoped_regular_file"):
                audit.scoped_regular_file(file, root / "other")
            with (
                patch.object(Path, "is_symlink", return_value=True),
                self.assertRaisesRegex(ValueError, "scoped_regular_file"),
            ):
                audit.scoped_regular_file(file, root)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                audit.print_receipt("a" * 64)
                with (
                    patch.object(audit.platform, "system", return_value="Windows"),
                    patch.object(
                        sys,
                        "argv",
                        ["audit", "--installed-output", str(root / "output")],
                    ),
                ):
                    self.assertEqual(audit.main(), 2)
            self.assertNotIn(str(root), stdout.getvalue())
            self.assertIn("execution_host", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
