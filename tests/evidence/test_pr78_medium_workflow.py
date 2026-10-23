"""Synthetic scheduler and solver only; no HPC, license or network access."""

import copy
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
sys.path.insert(0, str(Path(__file__).parent))
import pr78_medium_workflow as flow  # noqa: E402
import test_paired_matrix_executor_v3 as fixtures  # noqa: E402
from test_paired_matrix_workflow_v3 import accounting, held  # noqa: E402


class MediumWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(
            self.stack.enter_context(tempfile.TemporaryDirectory())
        ).resolve()
        self.directory = self.root / "flow"
        self.stack.enter_context(
            patch.object(flow.matrix.adapter, "RAW_ROOT", self.root)
        )
        self.stack.enter_context(
            patch.object(flow.matrix.adapter, "EVIDENCE_ROOT", self.root)
        )
        self.stack.enter_context(patch.object(flow.site, "host"))
        self.stack.enter_context(
            patch.object(flow.site, "source_head", return_value="9" * 40)
        )
        self.stack.enter_context(
            patch.object(
                flow.proposal,
                "review_returns",
                return_value={"synthetic_verified": True},
            )
        )
        self.ci = self.stack.enter_context(
            patch.object(flow.ci, "review_ci", return_value={"synthetic": True})
        )
        self.stack.enter_context(
            patch.object(
                flow.previous, "site_profile", return_value={"synthetic": True}
            )
        )
        self.stack.enter_context(patch.dict(os.environ))
        os.environ.pop("SLURM_JOB_ID", None)
        inputs = []
        for name in ("easy", "medium"):
            source = self.root / name
            source.mkdir()
            for filename in flow.previous.PUBLIC:
                (source / filename).write_bytes(b"synthetic public fixture\n")
            inputs.append(source)
        self.inputs = inputs
        self.calls = []
        self.state = "COMPLETED"
        self.command = self.stack.enter_context(
            patch.object(flow.site, "command", side_effect=self.scheduler)
        )
        self.prepared = flow.prepare(self.directory, *inputs)
        self.plan = flow.load(self.directory / "plan.json")

    def scheduler(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[0] == "sbatch":
            return "99\n"
        if args[:3] == ["scontrol", "show", "job"]:
            return held("99")
        if args[:2] == ["scontrol", "release"]:
            self.assertTrue((self.directory / "submission.json").exists())
            self.assertTrue((self.directory / "release.started").exists())
            return ""
        if args[0] == "sacct":
            return accounting("99", self.state)
        raise AssertionError("unexpected scheduler call")

    def approve(self):
        self.sha = flow.approve(self.directory, explicit=True)["approval_sha256"]
        return self.sha

    def submit(self):
        self.approve()
        return flow.submit(self.directory, self.sha)

    def allocation(self):
        return patch.dict(
            os.environ,
            {
                "SLURM_JOB_ID": "99",
                "SLURM_CPUS_PER_TASK": "16",
                "SLURM_MEM_PER_NODE": "65536",
                "SLURM_JOB_NUM_NODES": "1",
                "SLURM_RESTART_COUNT": "0",
                "SLURM_JOB_GPUS": "",
                "SLURM_STEP_GPUS": "",
            },
        )

    def run_synthetic(self, interrupted=False):
        self.submit()
        fixture = fixtures.MatrixTests()
        fixture.plan = flow.execution_view(self.plan)
        fixture.sha = self.sha
        gate = Mock(
            sample=Mock(return_value=1), public=Mock(return_value=fixtures.gate_value())
        )
        self.commands = []

        def simulate(command, console, deadline, _gate):
            self.commands.append(command)
            self.assertIn("import pr78_medium_workflow as m", command[3])
            self.assertEqual(deadline, 3780)
            attempt = Path(console).parent
            request = flow.load(attempt / "request.json")
            if not interrupted:
                fixture.synthetic_child(attempt, request["attempt"])
            Path(console).write_bytes(b"private console fixture\n")
            return {
                "child_exit_code": -15 if interrupted else 0,
                "guard_stop": "memory_observation_lost" if interrupted else None,
                "sampled_cgroup_peak_bytes": 1024,
                "supervisor_wall_seconds": 1,
                "peak_is_sampled_not_exact": True,
                "memory_failure_diagnostic": {
                    "stage": "usage_read_or_parse",
                    "exception_type": "FileNotFoundError",
                    "errno": 2,
                    "depth_from_leaf": 2,
                    "private_text_included": False,
                }
                if interrupted
                else None,
            }

        with (
            self.allocation(),
            patch.object(flow.matrix.memory, "MemoryGate", return_value=gate),
            patch.object(flow.matrix.adapter.screen, "qualify_affinity"),
            patch.object(flow.matrix.memory, "supervise", side_effect=simulate),
        ):
            return flow.run(self.directory, self.sha)

    def test_prepare_no_scheduler_no_approval_or_claim(self):
        self.assertEqual(self.calls, [])
        self.ci.assert_not_called()
        self.assertFalse(self.prepared["resource_budget_approved"])
        self.assertFalse(flow.campaign_root().exists())
        self.assertFalse((self.directory / "approval.json").exists())
        with self.assertRaises(ValueError):
            flow.prepare(self.directory, *self.inputs)

    def test_approval_requires_explicit_flag_and_current_ci(self):
        with self.assertRaises(ValueError):
            flow.approve(self.directory)
        self.assertFalse(flow.campaign_root().exists())
        self.ci.side_effect = ValueError("CI pending")
        with self.assertRaises(ValueError):
            self.approve()
        self.assertFalse(flow.campaign_root().exists())

    def test_one_predecessor_claim_across_directories_or_new_approvals(self):
        self.approve()
        other = self.root / "second"
        flow.prepare(other, *self.inputs)
        with self.assertRaises(FileExistsError):
            flow.approve(other, explicit=True)
        with self.assertRaises(FileExistsError):
            flow.approve(self.directory, explicit=True)
        self.assertFalse((other / "approval.json").exists())

    def test_exact_budget_and_no_easy_rows(self):
        approval = flow.approval_template(self.plan)
        self.assertEqual(approval["maximum_new_optimization_calls"], 5)
        self.assertEqual(
            approval["successor_campaign_reserved_optimization_ceiling"], 11
        )
        self.assertEqual(approval["maximum_new_solver_seconds"], 18000)
        self.assertEqual(approval["maximum_new_submissions"], 1)
        self.assertEqual(
            [r["threads"] for r in self.plan["proposal"]["attempts"]], [16, 8, 2, 1, 4]
        )
        self.assertTrue(
            all(
                r["attempt_id"].startswith("medium-")
                for r in self.plan["proposal"]["attempts"]
            )
        )

    def test_tampered_plan_and_approval_rejected(self):
        self.approve()
        for field, value in (
            ("maximum_new_submissions", 2),
            ("maximum_new_optimization_calls", 10),
            ("explicit_additional_medium_budget_approved", False),
            ("schema_version", True),
        ):
            approval = flow.load(self.directory / "approval.json")
            approval[field] = value
            with self.assertRaises(ValueError):
                flow.validate_approval(
                    self.plan,
                    approval,
                    flow.contract.sha(flow.contract.encoded(approval)),
                )
        plan = copy.deepcopy(self.plan)
        plan["proposal"]["scope"] = "unattempted-only"
        with self.assertRaises(ValueError):
            flow.validate_plan(plan, self.directory)

    def test_submit_once_durable_job_before_release_and_clean_environment(self):
        with patch.dict(
            os.environ, {"SBATCH_NODES": "2", "SRUN_GPUS": "1", "BASH_ENV": "bad"}
        ):
            value = self.submit()
        self.assertEqual(value["job_id"], "99")
        args, kwargs = next(c for c in self.calls if c[0][0] == "sbatch")
        self.assertIn("--nodes=1", args)
        self.assertIn("--no-requeue", args)
        self.assertNotIn("--exclusive", args)
        self.assertNotIn("SBATCH_NODES", kwargs["env"])
        self.assertNotIn("BASH_ENV", kwargs["env"])
        with self.assertRaises(FileExistsError):
            flow.submit(self.directory, self.sha)
        self.assertEqual(sum(c[0][0] == "sbatch" for c in self.calls), 1)
        self.assertEqual(
            sum(c[0][:2] == ["scontrol", "release"] for c in self.calls), 1
        )

    def test_uncertain_sbatch_consumes_claim_without_retry(self):
        self.approve()
        self.command.side_effect = TimeoutError("private stderr not exported")
        with self.assertRaises(flow.previous.SubmissionError) as caught:
            flow.submit(self.directory, self.sha)
        self.assertEqual(caught.exception.report["stage"], "sbatch_held")
        self.assertIsNone(caught.exception.report["job_id"])
        self.assertNotIn("private stderr", str(caught.exception.report))
        with self.assertRaises(ValueError):
            flow.submit(self.directory, self.sha)
        self.assertEqual(self.command.call_count, 1)

    def test_mismatched_held_profile_preserves_job_and_never_releases(self):
        self.approve()
        original = self.scheduler

        def mismatch(args, **kwargs):
            value = original(args, **kwargs)
            return (
                value.replace("NumNodes=1", "NumNodes=2")
                if args[:3] == ["scontrol", "show", "job"]
                else value
            )

        self.command.side_effect = mismatch
        with self.assertRaises(flow.previous.SubmissionError):
            flow.submit(self.directory, self.sha)
        self.assertEqual(flow.load(self.directory / "submission.json")["job_id"], "99")
        self.assertFalse(any(c[0][:2] == ["scontrol", "release"] for c in self.calls))

    def test_status_single_query_and_nonterminal_collect_no_claim(self):
        self.submit()
        self.calls.clear()
        self.state = "RUNNING"
        self.assertFalse(flow.status(self.directory)["terminal"])
        self.assertEqual(len(self.calls), 1)
        self.calls.clear()
        self.assertFalse(flow.collect(self.directory)["collected"])
        self.assertEqual(len(self.calls), 1)
        self.assertFalse((self.directory / "collection.started").exists())

    def test_missing_parent_result_never_promoted_by_slurm_completed(self):
        self.submit()
        result = flow.collect(self.directory)
        self.assertFalse(result["ready_for_independent_review"])
        value = flow.load(self.directory / "public_return.json")
        self.assertTrue(value["pause_remaining_matrix"])
        self.assertFalse(value["complete_parent"])
        calls = len(self.calls)
        self.assertEqual(flow.collect(self.directory), result)
        self.assertEqual(len(self.calls), calls)

    def test_full_synthetic_matrix_collection_and_independent_validation(self):
        result = self.run_synthetic()
        self.assertTrue(result["complete_parent"])
        self.assertEqual(len(self.commands), 5)
        self.assertFalse((self.directory / "easy").exists())
        summary = flow.collect(self.directory)
        self.assertTrue(summary["ready_for_independent_review"])
        value = flow.load(self.directory / "public_return.json")
        self.assertEqual(flow.validate_public(value, self.directory), value)
        self.assertFalse(value["scientific_reporting_eligible"])
        self.assertEqual(len(value["attempts"]), 5)
        self.assertNotIn(b"private console fixture", flow.contract.encoded(value))
        for field, changed in (
            ("raw_logs_included", True),
            ("scientific_reporting_eligible", True),
            ("pause_remaining_matrix", True),
            ("complete_parent", 1),
        ):
            tampered = copy.deepcopy(value)
            tampered[field] = changed
            with self.assertRaises(ValueError):
                flow.validate_public(tampered, self.directory)

    def test_memory_loss_stops_after_first_preserves_sanitized_diagnostic(self):
        report = self.run_synthetic(interrupted=True)
        self.assertFalse(report["complete_parent"])
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(report["stop_code"], "memory_observation_lost")
        self.assertFalse(flow.collect(self.directory)["ready_for_independent_review"])
        value = flow.load(self.directory / "public_return.json")
        attempt = value["attempts"]["medium-seed42-threads16"]["receipt"]
        self.assertEqual(attempt["guard"]["memory_failure_diagnostic"]["errno"], 2)
        self.assertIsNone(attempt["child"])
        self.assertTrue((flow.campaign_root() / "STOP.json").exists())

    def test_changed_private_console_rejects_export_and_preserves_stop(self):
        self.run_synthetic()
        path = self.directory / "medium/medium-seed42-threads16/console.private.log"
        path.write_bytes(b"changed after close")
        with self.assertRaises(ValueError):
            flow.collect(self.directory)
        self.assertFalse((self.directory / "public_return.json").exists())
        self.assertTrue((flow.campaign_root() / "STOP.json").exists())
        with self.assertRaises(FileExistsError):
            flow.collect(self.directory)

    def test_foreign_child_module_fails_before_any_memory_or_process_action(self):
        with patch.object(flow.matrix.memory, "MemoryGate") as gate:
            with self.assertRaises(ValueError):
                flow.matrix.execute_attempt(
                    {}, self.root / "bad", "99", child_module="os;bad"
                )
            gate.assert_not_called()

    def test_child_order_claim_and_duplicate_execution(self):
        self.submit()
        flow.write(self.directory / "batch.started", {"job_id": "99"})
        output = self.directory / "medium"
        output.mkdir()
        rows = self.plan["proposal"]["attempts"]
        first = output / rows[0]["attempt_id"]
        second = output / rows[1]["attempt_id"]
        for path, row in ((first, rows[0]), (second, rows[1])):
            path.mkdir()
            flow.write(
                path / "request.json", flow.request_for(self.plan, self.sha, row)
            )
        with self.allocation(), patch.object(flow.matrix, "run_child") as child:
            with self.assertRaises(ValueError):
                flow.internal_child(second, flow.digest(second / "request.json"))
            child.assert_not_called()
            flow.internal_child(first, flow.digest(first / "request.json"))
            self.assertEqual(child.call_count, 1)
            with self.assertRaises(FileExistsError):
                flow.internal_child(first, flow.digest(first / "request.json"))
            self.assertEqual(child.call_count, 1)

    def test_batch_replay_and_wrong_job_rejected_before_solver(self):
        self.submit()
        with (
            self.allocation(),
            patch.dict(os.environ, {"SLURM_JOB_ID": "998"}),
            self.assertRaises(ValueError),
        ):
            flow.run(self.directory, self.sha)
        flow.write(self.directory / "batch.started", {"job_id": "99"})
        with (
            self.allocation(),
            patch.object(flow.matrix.memory, "MemoryGate"),
            patch.object(flow.matrix.adapter.screen, "qualify_affinity"),
            self.assertRaises(FileExistsError),
        ):
            flow.run(self.directory, self.sha)


if __name__ == "__main__":
    unittest.main()
