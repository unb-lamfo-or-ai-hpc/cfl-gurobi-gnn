"""Real 201-cell screen, bounded six-vector selection and synthetic diagnostics."""

import ast
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import audit_pr86_wave61_numeric as audit  # noqa: E402
import pr86_wave61 as prior_wave  # noqa: E402
import review_pr86_wave61 as review  # noqa: E402

q = review.q


class Wave61Review(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = q.read(review.DEST / "public_return.json")
        cls.rows, cls.report = review.review(cls.raw)
        cls.wave = q.first.executor.existing.review.flow.meta.strict_json(cls.raw)

    def test_real_hash_prefix_and_numeric_denominators(self):
        self.assertEqual(q.digest(self.raw), review.SHA)
        self.assertEqual(len(self.rows), 201)
        self.assertEqual(self.report["completed_groups"], 67)
        self.assertEqual(self.report["remaining_cells"], 9)
        self.assertEqual(self.report["scoped_review_non_M4_cells"], 168)
        self.assertEqual(self.report["numerically_sensitive_cells"], 21)
        self.assertEqual(
            self.report["new_parent_numeric_qualification_pending_cells"], 12
        )
        self.assertEqual(self.report["distinct_historically_exposed_parents"], 10)
        self.assertEqual(self.report["reported_target_met_cells"], 132)
        self.assertEqual(self.report["right_censored_cells"], 69)
        self.assertFalse(self.report["next_fixed_wave_review_passed"])
        self.assertFalse(self.report["scientific_reporting_eligible"])
        self.assertFalse(self.report["M4_exact_optimality_or_speedup_qualified"])
        self.assertFalse(self.report["M12_exact_optimality_or_speedup_qualified"])
        with self.assertRaisesRegex(ValueError, "wave61_return_hash"):
            review.review_wave(self.raw + b" ")

    def test_eight_findings_select_exactly_six_vectors(self):
        selected = audit.selected_records(self.wave)
        self.assertEqual(len(selected), 6)
        self.assertEqual({r["cell_id"] for r in selected}, audit.EXPECTED)
        self.assertEqual({r["model_sha256"] for r in selected}, {audit.MODEL})
        findings = self.report["new_parent_cross_run_findings"]
        self.assertEqual(len(findings), 8)
        self.assertTrue(all(not f["exact_feasibility_proven"] for f in findings))
        self.assertLess(max(f["relative_difference"] for f in findings), 1e-4)
        self.assertGreater(max(f["absolute_difference"] for f in findings), 1e-6)
        self.assertEqual(len(self.report["cross_run_findings"]), 12)

    def test_original_hash_and_no_result_based_continuation(self):
        # The actual successor predecessor gate consumes this field; it is closed.
        self.assertFalse(self.report["next_fixed_wave_review_passed"])
        self.assertEqual(
            self.report["author_decision"], prior_wave.previous.reviewed.AUTHOR_DECISION
        )
        changed = copy.deepcopy(self.wave)
        changed["returns"][2]["members"]["run/attempt-0/child.json"]["sha256"] = (
            "f" * 64
        )
        with self.assertRaisesRegex(ValueError, "member_hash"):
            audit.selected_records(changed)

    def test_reproducible_assets_and_partial_or_sensitive_labels(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(review, "review", return_value=(self.rows, self.report)),
        ):
            folder = Path(temp).resolve()
            review.publish(folder)
            review.publish(folder)
            for name in (
                "campaign_results.csv",
                "review.json",
                "manifest.json",
                "m7_gap_cpu.svg",
                "m7_memory_cpu.svg",
                "m12_gap_cpu.svg",
                "m12_memory_cpu.svg",
            ):
                self.assertEqual(q.read(folder / name), q.read(review.DEST / name))
            self.assertIn(b"numerica pendiente", q.read(folder / "m12_gap_cpu.svg"))
            self.assertIn(b"M12", q.read(folder / "m12_gap_cpu.svg"))
            self.assertNotIn(b"pendientes", q.read(folder / "m7_gap_cpu.svg"))
        self.assertEqual(q.read(review.DEST / "public_return.json"), self.raw)

    def synthetic_receipt(self):
        # Tiny tolerance-feasible vector: rounded copy violates an original row.
        data = dict(
            lower=np.array([0.0]),
            upper=np.array([1.0]),
            types=np.array(["B"]),
            objective=np.array([1.0]),
            rows=np.array([0]),
            columns=np.array([0]),
            coefficients=np.array([1000.0]),
            senses=np.array([">"]),
            rhs=np.array([0.001]),
        )
        diag = audit.array_diagnostics(data, np.array([1e-6]), 1e-6)
        selected = audit.selected_records(self.wave)
        solutions = []
        for row in selected:
            data["objective"] = np.array([row["primal"] / 1e-6])
            diag = audit.array_diagnostics(data, np.array([1e-6]), row["primal"])
            child = audit.old.f0.member(
                self.wave["returns"][row["group_index"]],
                f"run/attempt-{row['attempt_index']}/child.json",
            )
            solutions.append(
                {
                    "cell_id": row["cell_id"],
                    "private_solution_sha256_observed_now": "b" * 64,
                    "child_sha256": row["child_sha256"],
                    "reported_primal": row["primal"],
                    "reported_dual": row["dual"],
                    "sealed_log_sha256": child["gurobi_log"]["log_sha256"],
                    "diagnostics": copy.deepcopy(diag),
                }
            )
        return {
            "protocol_id": audit.PROTOCOL,
            "source_commit": review.COMMIT,
            "collector_source_commit": "a" * 40,
            "return_sha256": review.SHA,
            "collector_source_sha256_lf": q.digest(
                Path(audit.__file__).read_bytes().replace(b"\r\n", b"\n")
            ),
            "diagnostic_helper_sha256_lf": q.digest(
                Path(audit.old.__file__).read_bytes().replace(b"\r\n", b"\n")
            ),
            "optimization_runs_added": 0,
            "scheduler_queries": 0,
            "submissions_added": 0,
            "raw_logs_or_variable_values_included": False,
            "mathematical_model_or_solver_parameters_changed": False,
            "rounded_values_persisted_or_used_as_start": False,
            "cause_proven": False,
            "remaining_dispatch_admitted": False,
            "scientific_reporting_eligible": False,
            "original_solution_hashes_were_not_exported_in_historical_return": True,
            "newly_observed_private_hashes_are_not_historical_seals": True,
            "model": {
                "sha256": audit.MODEL,
                "mathematical_signature_sha256": selected[0][
                    "mathematical_signature_sha256"
                ],
            },
            "solutions": solutions,
        }

    def test_synthetic_receipt_allows_negative_diagnostic_not_scientific_promotion(
        self,
    ):
        value = self.synthetic_receipt()
        self.assertTrue(value["solutions"][0]["diagnostics"]["stored"]["valid"])
        self.assertFalse(
            value["solutions"][0]["diagnostics"]["rounded_in_memory_only"]["valid"]
        )
        raw = q.encoded(value)
        with patch.object(review, "review_wave", return_value=self.wave):
            report = audit.validate_numeric(raw, q.digest(raw), "a" * 40)
        self.assertEqual(report["solutions_read"], 6)
        self.assertFalse(report["remaining_dispatch_admitted"])

    def test_receipt_tampering_and_scope_expansion_rejected(self):
        original = self.synthetic_receipt()
        for key, replacement in (
            ("collector_source_commit", "c" * 40),
            ("submissions_added", 1),
            ("remaining_dispatch_admitted", True),
            ("collector_source_sha256_lf", "d" * 64),
        ):
            changed = copy.deepcopy(original)
            changed[key] = replacement
            raw = q.encoded(changed)
            with (
                self.subTest(key=key),
                patch.object(review, "review_wave", return_value=self.wave),
                self.assertRaises(ValueError),
            ):
                audit.validate_numeric(raw, q.digest(raw), "a" * 40)
        with self.assertRaisesRegex(ValueError, "numeric_return_hash"):
            audit.validate_numeric(q.encoded(original), "f" * 64, "a" * 40)

    def test_objective_parity_preserves_original_absolute_tolerance(self):
        value = self.synthetic_receipt()
        stored = value["solutions"][0]["diagnostics"]["stored"]
        stored["recomputed_objective"] = value["solutions"][0]["reported_primal"] + 5e-7
        raw = q.encoded(value)
        with patch.object(review, "review_wave", return_value=self.wave):
            self.assertEqual(
                audit.validate_numeric(raw, q.digest(raw), "a" * 40)["solutions_read"],
                6,
            )
        stored["recomputed_objective"] += 2e-6
        raw = q.encoded(value)
        with (
            patch.object(review, "review_wave", return_value=self.wave),
            self.assertRaisesRegex(ValueError, "recomputed_objective_parity"),
        ):
            audit.validate_numeric(raw, q.digest(raw), "a" * 40)

    def test_installed_host_gate_precedes_imports_or_writes(self):
        with (
            patch.object(audit.platform, "system", return_value="Windows"),
            self.assertRaisesRegex(ValueError, "execution_host"),
        ):
            audit.installed(Path("not-created"))
        tree = ast.parse(Path(audit.__file__).read_text())
        self.assertFalse(
            any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("optimize", "optimizeAsync")
                for n in ast.walk(tree)
            )
        )
        text = (q.ROOT / "scripts/evidence/receive_pr86_m12_numeric.ps1").read_text()
        self.assertEqual(text.count("& scp "), 1)
        self.assertNotIn("sbatch", Path(audit.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
