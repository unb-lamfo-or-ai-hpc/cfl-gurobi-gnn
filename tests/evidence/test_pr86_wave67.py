"""M12 installed review and final three-job workflow; synthetic scheduler only."""

import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_wave67 as f  # noqa: E402
import test_pr86_main_first_group as fixtures  # noqa: E402
import test_pr86_six_job_queue as wave_tests  # noqa: E402

q, review = f.q, f.reviewed


class Wave67(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = q.read(review.DEST / "numeric_audit.json")
        cls.rows, cls.report = review.review(cls.raw)
        cls.ledger, cls.inventory = review.campaign()
        with patch.object(review, "campaign", return_value=(cls.ledger, cls.inventory)):
            cls.frozen = f.plan("a" * 40)

    def test_six_real_diagnostics_are_not_the_m4_outcome(self):
        self.assertEqual(q.digest(self.raw), review.SHA)
        self.assertEqual(len(self.rows), 6)
        gnn = [r for r in self.rows if r["method"] == "M2"]
        controls = [r for r in self.rows if r["method"] != "M2"]
        self.assertEqual(len(gnn), 4)
        self.assertTrue(
            all(
                r["rounded_original_unit_feasible"]
                and r["stored_max_integrality_residual"]
                == r["rounded_max_row_residual"]
                == 0
                for r in gnn
            )
        )
        self.assertTrue(
            all(
                not r["rounded_original_unit_feasible"]
                and 41 < r["rounded_residual_over_existing_tolerance"] < 42
                for r in controls
            )
        )
        self.assertFalse(self.report["cause_of_cross_run_discrepancy_proven"])
        self.assertFalse(self.report["exact_optimality_certified"])
        self.assertFalse(self.report["main_performance_promotion"])
        self.assertTrue(self.report["diagnostic_summary_eligible"])
        self.assertEqual(len(self.ledger), 201)
        self.assertEqual(self.inventory["M4_sensitive_cells"], 21)
        self.assertEqual(self.inventory["M12_sensitive_cells"], 12)
        self.assertEqual(self.inventory["scoped_review_non_M4_M12_cells"], 168)
        self.assertEqual(
            self.inventory["author_decisions"]["M12"], review.AUTHOR_DECISION
        )
        with self.assertRaisesRegex(ValueError, "m12_numeric_hash"):
            review.review(self.raw + b" ")

    def test_real_audit_rejects_scope_and_result_tampering(self):
        original = q.first.executor.existing.review.flow.meta.strict_json(self.raw)
        for mutate in (
            lambda v: v.update(remaining_dispatch_admitted=True),
            lambda v: v.update(optimization_runs_added=1),
            lambda v: v["solutions"][2]["diagnostics"]["rounded_in_memory_only"].update(
                valid=False
            ),
        ):
            value = copy.deepcopy(original)
            mutate(value)
            raw = q.encoded(value)
            with (
                patch.object(review, "SHA", q.digest(raw)),
                self.assertRaises(ValueError),
            ):
                review.review(raw)

    def test_frozen_tail_and_full_campaign_reservation_budget(self):
        original, cells = q.first.executor.proposal.build()
        groups = self.frozen["groups"]
        self.assertEqual([g["group"] for g in groups], original["groups"][67:70])
        self.assertEqual([c for g in groups for c in g["cells"]], cells[201:210])
        self.assertEqual(
            [
                (g["group"]["parent"], g["group"]["threads"], g["group"]["seed"])
                for g in groups
            ],
            [("CFL_medium_instance_12", t, 42) for t in (4, 8, 16)],
        )
        self.assertEqual(self.frozen["maximum_submissions"], 3)
        self.assertEqual(self.frozen["maximum_optimization_calls"], 9)
        self.assertEqual(self.frozen["maximum_solver_seconds"], 32400)
        self.assertEqual(self.frozen["maximum_serial_reservation_seconds"], 43200)
        self.assertEqual(self.frozen["maximum_physical_core_hours"], 112)
        self.assertEqual(
            self.frozen["campaign_completed_calls_before_this_wave"] + 9, 210
        )
        self.assertEqual(sum(g["threads"] * 4 for g in original["groups"]), 1320)
        self.assertFalse(self.frozen["dispatch_after_this_wave"])

    def test_three_jobs_held_before_reverse_release_and_no_repeat(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp).resolve()
            calls = wave_tests.SixJobs.submit_fixture(self, stage, stack)
            policy = copy.copy(f.POLICY)
            policy.claim = stage / "claim"
            policy.installed_review = lambda: self.frozen["first_review"]
            result = q.submit(stage, q.digest(q.encoded(self.frozen)), policy)
            self.assertEqual(result["job_ids"], ["900", "901", "902"])
            self.assertEqual(result["submission"], "three_serial_jobs_released")
            self.assertEqual(
                calls[-3:], [["scontrol", "release", j] for j in ("902", "901", "900")]
            )
            self.assertTrue(
                all(
                    c[-3].endswith("operate_pr86_wave67.sh")
                    for c in calls
                    if c[0] == "sbatch"
                )
            )
            self.assertEqual(q.admitted(stage, self.frozen, policy), result["job_ids"])
            self.assertFalse((stage / "group-3").exists())
            self.assertEqual(
                q.parsed(stage / "approval.json")["maximum_optimization_calls"], 9
            )
            before = len(calls)
            with self.assertRaises(FileExistsError):
                q.submit(stage, q.digest(q.encoded(self.frozen)), policy)
            self.assertEqual(len(calls), before)

    def test_partial_submission_and_release_never_retry_or_release_root(self):
        for failure in ("submit", "release"):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as temp,
                ExitStack() as stack,
            ):
                stage = Path(temp).resolve()
                calls = wave_tests.SixJobs.submit_fixture(
                    self,
                    stage,
                    stack,
                    fail_submit=1 if failure == "submit" else None,
                    fail_release="901" if failure == "release" else None,
                )
                policy = copy.copy(f.POLICY)
                policy.claim = stage / "claim"
                policy.installed_review = lambda: self.frozen["first_review"]
                with self.assertRaises(RuntimeError):
                    q.submit(stage, q.digest(q.encoded(self.frozen)), policy)
                self.assertNotIn(["scontrol", "release", "900"], calls)
                if failure == "submit":
                    self.assertFalse(any(c[1] == "release" for c in calls))

    def test_real_admissions_for_all_nine_frozen_cells(self):
        wave_tests.SixJobs.test_real_admission_for_all_six_caps_and_seeds(self)

    def test_nested_three_group_return_and_fail_closed_identity(self):
        value = {
            "protocol_id": f.POLICY.protocol,
            "plan": self.frozen,
            "plan_sha256": q.digest(q.encoded(self.frozen)),
            "returns": [],
            "launch": [],
            "scientific_reporting_eligible": False,
            "raw_logs_included": False,
        }
        with tempfile.TemporaryDirectory() as temp:
            helper = fixtures.MainFirst()
            for i, group in enumerate(self.frozen["groups"]):
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
            policy = copy.copy(f.POLICY)
            policy.plan = lambda _: self.frozen
            self.assertEqual(
                q.validate_return(q.encoded(value), policy)["complete_groups"], 3
            )
            for kind in ("extra", "dependency", "member"):
                bad = copy.deepcopy(value)
                if kind == "extra":
                    bad["returns"].append(bad["returns"][0])
                elif kind == "dependency":
                    bad["launch"][1]["held_profile"]["dependency"] = "afterany:900"
                else:
                    bad["returns"][0]["members"].pop("run/attempt-2/child.json")
                with self.assertRaises(ValueError):
                    q.validate_return(q.encoded(bad), policy)

    def test_status_collect_and_budget_fail_closed(self):
        policy = copy.copy(f.POLICY)
        policy.plan = lambda _: self.frozen
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(q, "load", return_value=self.frozen),
            patch.object(q, "admitted", return_value=["900", "901", "902"]),
        ):
            stage = Path(temp).resolve()
            self.assertEqual(len(q.status(stage, policy)["jobs"]), 3)
            self.assertFalse(q.status(stage, policy)["terminal"])
            with self.assertRaisesRegex(ValueError, "not_terminal_no_wait"):
                q.collect(stage, policy)
            for index in (-1, 3, 6):
                with self.assertRaisesRegex(ValueError, "group_index"):
                    q.run(stage, index, policy)
        for key, replacement in (
            ("maximum_optimization_calls", 18),
            ("campaign_completed_calls_before_this_wave", 204),
        ):
            bad = copy.deepcopy(self.frozen)
            bad[key] = replacement
            with self.assertRaisesRegex(ValueError, "wave_budget"):
                q.wave_size(bad)

    def test_receiver_batch_scope_and_reproducible_assets(self):
        text = (q.ROOT / "scripts/evidence/receive_pr86_wave67.ps1").read_text()
        self.assertIn("../../outputs/pr86-next67-", text)
        self.assertEqual(text.count("& scp "), 1)
        self.assertIn(
            "^[0-2]$", (q.ROOT / "scripts/evidence/operate_pr86_wave67.sh").read_text()
        )
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(review, "review", return_value=(self.rows, self.report)),
            patch.object(
                review, "campaign", return_value=(self.ledger, self.inventory)
            ),
        ):
            folder = Path(temp).resolve()
            review.publish(folder)
            review.publish(folder)
            for name in (
                "diagnostics.csv",
                "review.json",
                "campaign_results.csv",
                "campaign_inventory.json",
                "manifest.json",
            ):
                self.assertEqual(q.read(folder / name), q.read(review.DEST / name))
        self.assertEqual(q.read(review.DEST / "numeric_audit.json"), self.raw)


if __name__ == "__main__":
    unittest.main()
