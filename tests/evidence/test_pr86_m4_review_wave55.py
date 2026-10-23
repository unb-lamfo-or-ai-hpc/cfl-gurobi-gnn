"""Preserve M4 numeric limits while testing six unchanged future groups offline."""

import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_wave55 as f  # noqa: E402
import test_pr86_main_first_group as fixtures  # noqa: E402
import test_pr86_six_job_queue as wave_tests  # noqa: E402

q, review = f.q, f.reviewed


class NumericReview(unittest.TestCase):
    def test_four_vectors_including_zero_gap_fail_rounding_not_original_tolerances(
        self,
    ):
        rows, report = review.review(q.read(review.DEST / "numeric_audit.json"))
        self.assertEqual(len(rows), 4)
        self.assertEqual(report["rounded_vectors_violating_original_unit_rows"], 4)
        self.assertTrue(report["reported_zero_gap_vector_also_fails_rounding"])
        self.assertFalse(report["cause_of_cross_run_conflict_proven"])
        self.assertFalse(report["exact_optimality_certified"])
        self.assertFalse(report["main_performance_promotion"])
        self.assertFalse(report["remaining_dispatch_admitted_by_diagnostic"])
        self.assertTrue(all(r["normalized_rows_above_1e_minus6"] == 0 for r in rows))
        self.assertEqual(
            [r["integer_values_changed_by_rounding"] for r in rows], [2, 19, 25, 1]
        )
        self.assertGreater(
            min(r["rounded_residual_over_existing_tolerance"] for r in rows), 99
        )
        self.assertLess(
            max(abs(r["objective_change_after_rounding"]) for r in rows), 1e-6
        )

    def test_collected_prefix_is_not_blanket_performance_promotion(self):
        rows, inventory = review.campaign()
        self.assertEqual(len(rows), 165)
        self.assertEqual(inventory["previously_scoped_reviewed_cells"], 147)
        self.assertEqual(inventory["numerically_sensitive_cells"], 18)
        self.assertEqual(inventory["remaining_cells"], 45)
        sensitive = [r for r in rows if r["numerical_scope"].startswith("M4_sensitive")]
        self.assertEqual(len(sensitive), 18)
        self.assertEqual({r["alias"] for r in sensitive}, {"M4"})
        self.assertEqual(sum(not r["right_censored"] for r in sensitive), 1)
        self.assertFalse(inventory["scientific_reporting_eligible"])
        self.assertEqual(inventory["author_decision"], review.AUTHOR_DECISION)

    def test_tampering_scope_and_exact_certificate_are_rejected(self):
        raw = q.read(review.DEST / "numeric_audit.json")
        with self.assertRaisesRegex(ValueError, "m4_numeric_hash"):
            review.review(raw + b" ")
        for mutate, code in (
            (
                lambda v: v.update(collector_source_commit="f" * 40),
                "m4_numeric_identity",
            ),
            (lambda v: v.update(optimization_runs_added=1), "read_only_scope"),
            (
                lambda v: v["solutions"][0].update(child_sha256="f" * 64),
                "numeric_cell_and_sealed_log",
            ),
            (
                lambda v: v["solutions"][0]["diagnostics"]["stored"][
                    "extended_precision"
                ].update(exact_arithmetic_certificate=True),
                "diagnostic_not_certificate",
            ),
            (
                lambda v: v["solutions"][0]["diagnostics"][
                    "rounded_in_memory_only"
                ].update(valid=True),
                "rounded_row_failure",
            ),
        ):
            with self.subTest(code=code):
                value = q.first.executor.existing.review.flow.meta.strict_json(raw)
                mutate(value)
                changed = q.encoded(value)
                with (
                    patch.object(review, "SHA", q.digest(changed)),
                    self.assertRaisesRegex(ValueError, code),
                ):
                    review.review(changed)

    def test_reproducible_derived_assets_and_original_receipt_bytes(self):
        raw = q.read(review.DEST / "numeric_audit.json")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp).resolve()
            review.publish(folder)
            review.publish(folder)
            for name in (
                "review.json",
                "diagnostics.csv",
                "campaign_results.csv",
                "campaign_inventory.json",
                "manifest.json",
            ):
                self.assertEqual(q.read(folder / name), q.read(review.DEST / name))
        self.assertEqual(
            q.digest(q.read(review.DEST / "numeric_audit.json")), review.SHA
        )
        self.assertEqual(q.read(review.DEST / "numeric_audit.json"), raw)


class Wave55(unittest.TestCase):
    def test_frozen_positions_budgets_and_two_parent_binding(self):
        frozen = f.plan("a" * 40)
        original, cells = q.first.executor.proposal.build()
        groups = frozen["groups"]
        self.assertEqual([g["group"] for g in groups], original["groups"][55:61])
        self.assertEqual(
            [(g["group"]["threads"], g["group"]["seed"]) for g in groups],
            [(16, 42), (1, 42), (1, 43), (1, 44), (2, 42), (4, 42)],
        )
        self.assertEqual(groups[0]["group"]["parent"], "CFL_medium_instance_4")
        self.assertTrue(
            all(g["group"]["parent"] == "CFL_medium_instance_7" for g in groups[1:])
        )
        for g in groups:
            self.assertEqual(
                g["cells"],
                [c for c in cells if c["group_id"] == g["group"]["group_id"]],
            )
            self.assertEqual(g["start_binding"]["selected_support"], 20000)
        self.assertNotEqual(
            groups[0]["start_binding"]["private_starts_sha256"],
            groups[1]["start_binding"]["private_starts_sha256"],
        )
        self.assertEqual(frozen["maximum_physical_core_hours"], 100)
        self.assertEqual(frozen["campaign_completed_calls_before_this_wave"], 165)
        self.assertEqual(frozen["maximum_solver_seconds"], 64800)
        self.assertEqual(frozen["maximum_serial_reservation_seconds"], 86400)
        self.assertEqual(frozen["first_review"]["numeric_audit_sha256"], review.SHA)
        self.assertEqual(
            frozen["first_review"]["author_decision"], review.AUTHOR_DECISION
        )
        self.assertFalse(frozen["scientific_reporting_eligible"])
        self.assertFalse(frozen["dispatch_after_this_wave"])

    def test_submit_caches_two_parents_and_rejects_repeat(self):
        self.frozen = f.plan("a" * 40)
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp).resolve()
            calls = wave_tests.SixJobs.submit_fixture(self, stage, stack)
            policy = copy.copy(f.POLICY)
            policy.claim = stage / "claim"
            policy.installed_review = lambda: self.frozen["first_review"]
            private = stack.enter_context(
                patch.object(
                    q.first,
                    "private_inputs",
                    side_effect=lambda g: (
                        Path(g["group"]["parent"]),
                        Path(g["group"]["parent"] + "-starts"),
                    ),
                )
            )
            bundles = stack.enter_context(patch.object(q.first, "bundles"))
            result = q.submit(stage, q.digest(q.encoded(self.frozen)), policy)
            self.assertEqual(private.call_count, 2)
            self.assertEqual(bundles.call_count, 6)
            for call, group in zip(bundles.call_args_list, self.frozen["groups"]):
                self.assertEqual(call.args[2], Path(group["group"]["parent"]))
                self.assertEqual(
                    call.args[3], Path(group["group"]["parent"] + "-starts")
                )
            self.assertTrue(
                all(
                    c[-3].endswith("operate_pr86_wave55.sh")
                    for c in calls
                    if c[0] == "sbatch"
                )
            )
            self.assertEqual(q.admitted(stage, self.frozen, policy), result["job_ids"])
            with self.assertRaises(FileExistsError):
                q.submit(stage, q.digest(q.encoded(self.frozen)), policy)

    def test_real_admissions_for_eighteen_frozen_cells(self):
        self.frozen = f.plan("a" * 40)
        wave_tests.SixJobs.test_real_admission_for_all_six_caps_and_seeds(self)

    def test_synthetic_nested_returns_bind_mixed_parents_and_serial_dependencies(self):
        frozen = f.plan("a" * 40)
        with tempfile.TemporaryDirectory() as temp:
            value = {
                "protocol_id": f.POLICY.protocol,
                "plan": frozen,
                "plan_sha256": q.digest(q.encoded(frozen)),
                "returns": [],
                "launch": [],
                "scientific_reporting_eligible": False,
                "raw_logs_included": False,
            }
            helper = fixtures.MainFirst()
            for i, group in enumerate(frozen["groups"]):
                folder = Path(temp).resolve() / str(i)
                folder.mkdir()
                helper.frozen = group
                job, prev = str(900 + i), str(899 + i) if i else None
                value["returns"].append(helper.make_return(folder, job=job))
                value["launch"].append(
                    {
                        "job_id": job,
                        "held_profile": q.profile(
                            wave_tests.held(job, group["group"]["threads"], prev),
                            job,
                            group["group"]["threads"],
                            prev,
                        ),
                    }
                )
            self.assertEqual(
                q.validate_return(q.encoded(value), f.POLICY)["complete_groups"], 6
            )
            bad = copy.deepcopy(value)
            bad["returns"][1]["plan"]["start_binding"]["model_sha256"] = "f" * 64
            with self.assertRaises(ValueError):
                q.validate_return(q.encoded(bad), f.POLICY)
            bad = copy.deepcopy(value)
            bad["launch"][1]["held_profile"]["dependency"] = "afterany:900"
            with self.assertRaisesRegex(ValueError, "serial_dependency"):
                q.validate_return(q.encoded(bad), f.POLICY)


if __name__ == "__main__":
    unittest.main()
