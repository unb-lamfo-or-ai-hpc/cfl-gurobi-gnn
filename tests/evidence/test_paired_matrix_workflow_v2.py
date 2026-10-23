"""Slurm singleton ranges, staged failures and preserved v1 recovery checks."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import paired_matrix_workflow_v2 as flow  # noqa: E402
import recover_pr78_job3481 as recovery  # noqa: E402
import test_paired_matrix_workflow as fixtures  # noqa: E402


class SuccessorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.binding = patch.object(fixtures, "flow", flow)
        self.binding.start()
        self.addCleanup(self.binding.stop)
        self.fixture = fixtures.OperatorWorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.site = patch.object(
            flow,
            "site_profile",
            return_value={"physical_cores": 40, "logical_cpus": 80},
        )
        self.site.start()
        self.addCleanup(self.site.stop)
        flow.write(
            self.fixture.directory.parent / "recovery.json",
            {
                "successor_operator_plan_sha256": self.fixture.plan[
                    "operator_plan_sha256"
                ],
                "successor_operator_approval_sha256": self.fixture.sha,
                "predecessor_cancelled_job": "3481",
                "prior_authorization_sha256": recovery.AUTH_SHA,
                "predecessor_no_start_verified": True,
            },
        )

    def test_equal_node_cpu_ranges_release_once_and_preserve_observed_values(self):
        original = self.fixture.scheduler

        def scheduler(args, **kwargs):
            if args[:3] == ["scontrol", "show", "job"]:
                return (
                    fixtures.held()
                    .replace("NumNodes=1", "NumNodes=1-1")
                    .replace("NumCPUs=32", "NumCPUs=32-32")
                )
            return original(args, **kwargs)

        self.fixture.command.side_effect = scheduler
        result = self.fixture.submit()
        self.assertEqual(result["submission"], "released")
        observed = flow.load(
            flow.state_for(self.fixture.directory, "easy") / "held_profile.json"
        )
        self.assertEqual(observed["NumNodes"], "1-1")
        flow.validate_held(observed, "99")
        self.assertEqual(
            sum(args[:2] == ["scontrol", "release"] for args, _ in self.fixture.calls),
            1,
        )

    def test_actual_multinode_is_stopped_with_job_and_field_before_release(self):
        original = self.fixture.scheduler
        self.fixture.command.side_effect = lambda args, **kw: (
            fixtures.held().replace("NumNodes=1", "NumNodes=2")
            if args[:3] == ["scontrol", "show", "job"]
            else original(args, **kw)
        )
        with self.assertRaises(flow.SubmissionError) as raised:
            self.fixture.submit()
        report = raised.exception.report
        self.assertEqual(report["job_id"], "99")
        self.assertEqual(report["stage"], "validate_held_profile")
        self.assertEqual(report["resource_difference"]["field"], "NumNodes")
        state = flow.state_for(self.fixture.directory, "easy")
        self.assertEqual(flow.load(state / "submission_failure.json"), report)
        self.assertFalse((state / "release.started").exists())
        self.assertTrue((flow.root_for(self.fixture.sha) / "STOP.json").exists())
        with self.assertRaises(FileExistsError):
            self.fixture.submit()
        self.assertEqual(sum(args[0] == "sbatch" for args, _ in self.fixture.calls), 1)

    def test_non_singleton_ranges_gpus_and_whole_node_are_rejected(self):
        for before, after in (
            ("NumNodes=1", "NumNodes=1-2"),
            ("NumCPUs=32", "NumCPUs=16-32"),
            ("NumCPUs=32", "NumCPUs=80"),
            ("billing=32", "gres/gpu=1"),
            ("OverSubscribe=OK", "OverSubscribe=YES"),
        ):
            with self.subTest(after=after), self.assertRaises(ValueError):
                flow.held_profile(fixtures.held().replace(before, after), "99")
        flow.held_profile(
            fixtures.held().replace("OverSubscribe=OK", "OverSubscribe=NO"), "99"
        )

    def test_site_mismatch_does_not_consume_submission_claim(self):
        with (
            patch.object(
                flow,
                "site_profile",
                side_effect=flow.ProfileError("TotalNodes", "1", "2"),
            ),
            self.assertRaises(flow.SubmissionError) as raised,
        ):
            self.fixture.submit()
        self.assertEqual(raised.exception.report["stage"], "site_preflight")
        self.fixture.command.assert_not_called()
        self.assertFalse(flow.root_for(self.fixture.sha).exists())

    def test_release_timeout_preserves_id_and_error_stage(self):
        original = self.fixture.scheduler

        def scheduler(args, **kwargs):
            if args[:2] == ["scontrol", "release"]:
                raise TimeoutError("PRIVATE STDERR MUST NOT LEAK")
            return original(args, **kwargs)

        self.fixture.command.side_effect = scheduler
        with self.assertRaises(flow.SubmissionError) as raised:
            self.fixture.submit()
        self.assertEqual(raised.exception.report["stage"], "release_job")
        self.assertNotIn("PRIVATE", str(raised.exception.report))
        state = flow.state_for(self.fixture.directory, "easy")
        self.assertTrue((state / "release.started").exists())
        self.assertFalse((state / "released.json").exists())

    def test_collection_and_nested_validation_still_work(self):
        self.fixture.test_complete_nested_export_is_sanitized_idempotent_and_tamper_checked()

    def test_medium_still_requires_independent_review(self):
        self.fixture.submit()
        with self.assertRaises((ValueError, FileNotFoundError, TypeError)):
            flow.submit(self.fixture.directory, self.fixture.sha, "medium", "a" * 64)
        self.assertEqual(sum(args[0] == "sbatch" for args, _ in self.fixture.calls), 1)

    def test_recovery_prepares_once_without_scheduler_submission_or_prompt(self):
        (self.fixture.evidence / "pr78").mkdir()
        prior_bytes = (self.fixture.directory / "operator_approval.json").read_bytes()
        with (
            patch.object(recovery, "review_ci", return_value={"reviewed": True}),
            patch.object(
                recovery,
                "predecessor",
                return_value={"state": "CANCELLED", "start": None},
            ),
        ):
            result = recovery.prepare()
            with self.assertRaises(ValueError):
                recovery.prepare()
        directory = Path(result["directory"])
        flow.approved(directory, result["approval_sha256"])
        self.assertEqual(
            prior_bytes,
            (self.fixture.directory / "operator_approval.json").read_bytes(),
        )
        self.assertEqual(self.fixture.calls, [])
        self.assertTrue(
            (self.fixture.evidence / "pr78/job3481-recovery.claim").is_file()
        )
        self.assertFalse((directory / "operator-state").exists())

    def test_changed_predecessor_blocks_before_recovery_claim(self):
        (self.fixture.evidence / "pr78").mkdir()
        with (
            patch.object(recovery, "review_ci", return_value={}),
            patch.object(recovery, "predecessor", side_effect=ValueError("changed")),
            self.assertRaises(ValueError),
        ):
            recovery.prepare()
        self.assertFalse(
            (self.fixture.evidence / "pr78/job3481-recovery.claim").exists()
        )
        self.assertEqual(self.fixture.calls, [])


class RecoveryTests(unittest.TestCase):
    def test_cancelled_without_start_requires_no_steps_no_elapsed_and_no_start(self):
        self.assertEqual(
            recovery.cancelled_without_start("3481|CANCELLED by 1|0|None\n")[
                "step_rows"
            ],
            0,
        )
        for text in (
            "3481|RUNNING|0|None",
            "3481|CANCELLED|1|None",
            "3481|CANCELLED|0|2026-10-06T12:00:00",
            "3481|CANCELLED|0|None\n3481.batch|CANCELLED|0|None",
            "3482|CANCELLED|0|None",
            "",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                recovery.cancelled_without_start(text)

    def test_live_site_profile_accepts_core_sharing_and_rejects_second_node(self):
        responses = [
            "PartitionName=batch Nodes=dgx-dasci TotalNodes=1 TotalCPUs=80 OverSubscribe=NO",
            "SelectType = select/cons_tres\nSelectTypeParameters = CR_CORE_MEMORY,CR_ONE_TASK_PER_CORE\nTaskPlugin = affinity,cgroup",
            "NodeName=dgx-dasci Sockets=2 CoresPerSocket=20 ThreadsPerCore=2 CPUTot=80 RealMemory=490042",
        ]
        with patch.object(flow.site, "command", side_effect=responses):
            self.assertEqual(flow.site_profile()["physical_cores"], 40)
        changed = copy.copy(responses)
        changed[0] = changed[0].replace("TotalNodes=1", "TotalNodes=2")
        with (
            patch.object(flow.site, "command", side_effect=changed),
            self.assertRaises(flow.ProfileError),
        ):
            flow.site_profile()


if __name__ == "__main__":
    unittest.main()
