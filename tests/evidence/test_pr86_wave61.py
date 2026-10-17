"""Review wave55 and unchanged M7/M12 continuation, using synthetic schedulers."""

import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_wave61 as f  # noqa: E402
import test_pr86_main_first_group as fixtures  # noqa: E402
import test_pr86_six_job_queue as wave_tests  # noqa: E402

q, review = f.q, f.reviewed


class Wave61(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = q.read(review.DEST / "public_return.json")
        cls.rows, cls.report = review.review(cls.raw)
        cls.frozen = f.plan("a" * 40)

    def test_observed_prefix_scientific_limits_and_tamper_rejection(self):
        self.assertEqual(q.digest(self.raw), review.SHA)
        self.assertEqual(len(self.rows), 183)
        self.assertEqual(self.report["completed_groups"], 61)
        self.assertEqual(self.report["remaining_cells"], 27)
        self.assertEqual(self.report["numerically_sensitive_cells"], 21)
        self.assertEqual(self.report["scoped_review_non_M4_cells"], 162)
        self.assertEqual(self.report["right_censored_cells"], 55)
        self.assertFalse(self.report["M4_exact_optimality_or_speedup_qualified"])
        self.assertFalse(self.report["scientific_reporting_eligible"])
        self.assertTrue(self.report["next_fixed_wave_review_passed"])
        self.assertEqual(self.report["new_parent_cross_run_findings"], [])
        self.assertEqual(len(self.report["cross_run_findings"]), 4)
        with self.assertRaisesRegex(ValueError, "wave55_return_hash"):
            review.review_wave(self.raw + b" ")

    def test_new_parent_conflict_blocks_next_wave(self):
        changed = copy.deepcopy(self.report)
        changed["next_fixed_wave_review_passed"] = False
        with (
            patch.object(review, "review", return_value=(self.rows, changed)),
            self.assertRaisesRegex(ValueError, "new_parent_numeric_conflict"),
        ):
            f.predecessor(self.raw)

    def test_assets_preserve_censoring_warning_and_original_bytes(self):
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
                "m4_gap_cpu.svg",
                "m4_memory_cpu.svg",
                "m7_gap_cpu.svg",
                "m7_memory_cpu.svg",
            ):
                self.assertEqual(q.read(folder / name), q.read(review.DEST / name))
            self.assertIn(b"no certifica", q.read(folder / "m4_gap_cpu.svg"))
            self.assertIn(b"pendientes", q.read(folder / "m7_gap_cpu.svg"))
        self.assertEqual(q.read(review.DEST / "public_return.json"), self.raw)

    def test_frozen_groups_budget_and_predecessor(self):
        groups = self.frozen["groups"]
        original, cells = q.first.executor.proposal.build()
        self.assertEqual([g["group"] for g in groups], original["groups"][61:67])
        self.assertEqual(
            [(g["group"]["threads"], g["group"]["seed"]) for g in groups],
            [(8, 42), (16, 42), (1, 42), (1, 43), (1, 44), (2, 42)],
        )
        self.assertEqual(
            [g["group"]["parent"] for g in groups],
            ["CFL_medium_instance_7"] * 2 + ["CFL_medium_instance_12"] * 4,
        )
        for g in groups:
            self.assertEqual(
                g["cells"],
                [c for c in cells if c["group_id"] == g["group"]["group_id"]],
            )
            self.assertEqual(g["start_binding"]["selected_support"], 20000)
        self.assertEqual(self.frozen["maximum_physical_core_hours"], 116)
        self.assertEqual(self.frozen["maximum_optimization_calls"], 18)
        self.assertEqual(self.frozen["maximum_serial_reservation_seconds"], 86400)
        self.assertEqual(self.frozen["campaign_completed_calls_before_this_wave"], 183)
        self.assertEqual(
            self.frozen["first_review"]["numeric_audit_sha256"], f.previous.reviewed.SHA
        )
        self.assertFalse(self.frozen["dispatch_after_this_wave"])

    def test_submit_binds_two_parents_and_rejects_repeat(self):
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
            self.assertTrue(
                all(
                    c[-3].endswith("operate_pr86_wave61.sh")
                    for c in calls
                    if c[0] == "sbatch"
                )
            )
            self.assertEqual(q.admitted(stage, self.frozen, policy), result["job_ids"])
            with self.assertRaises(FileExistsError):
                q.submit(stage, q.digest(q.encoded(self.frozen)), policy)

    def test_real_admission_for_all_eighteen_cells(self):
        wave_tests.SixJobs.test_real_admission_for_all_six_caps_and_seeds(self)

    def test_synthetic_nested_two_parent_returns_and_dependencies(self):
        frozen = self.frozen
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
            # Plan rebuilding is tested separately against the real pinned prefix.
            policy = copy.copy(f.POLICY)
            policy.plan = lambda _: frozen
            self.assertEqual(
                q.validate_return(q.encoded(value), policy)["complete_groups"], 6
            )
            bad = copy.deepcopy(value)
            bad["returns"][2]["plan"]["start_binding"]["model_sha256"] = "f" * 64
            with self.assertRaises(ValueError):
                q.validate_return(q.encoded(bad), policy)
            bad = copy.deepcopy(value)
            bad["launch"][1]["held_profile"]["dependency"] = "afterany:900"
            with self.assertRaisesRegex(ValueError, "serial_dependency"):
                q.validate_return(q.encoded(bad), policy)

    def test_receivers_label_the_correct_wave_and_use_one_scp(self):
        for number in (55, 61):
            text = (
                q.ROOT / f"scripts/evidence/receive_pr86_wave{number}.ps1"
            ).read_text()
            self.assertIn(f"../../outputs/pr86-next{number}-", text)
            self.assertEqual(text.count("& scp "), 1)


if __name__ == "__main__":
    unittest.main()
