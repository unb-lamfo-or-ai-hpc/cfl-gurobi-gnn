"""Offline fake Slurm/solver coverage; no scheduler, license or LP access."""

import copy
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
sys.path.insert(0, str(Path(__file__).parent))
import paired_matrix_workflow as flow  # noqa: E402
import test_paired_matrix_executor as fixtures  # noqa: E402

matrix, site, old = flow.matrix, flow.site, flow.old


def held(job="99"):
    return (
        f"JobId={job} JobState=PENDING Reason=JobHeldUser Priority=0 Partition=batch "
        "Requeue=0 Restarts=0 BatchFlag=1 NumNodes=1 NumTasks=1 NumCPUs=32 "
        "CPUs/Task=16 TimeLimit=05:30:00 MinMemoryNode=64G OverSubscribe=OK "
        "TRES=cpu=32,mem=64G,node=1,billing=32 "
        "Command=/private/not-exported Account=not-exported"
    )


def accounting(job="99", state="COMPLETED", exit_code="0:0"):
    return "\n".join(
        f"{job}{suffix}|{state}|{exit_code}|300|00:05:00|32|64G|200152K"
        for suffix in ("", ".batch", ".extern", ".0")
    )


class OperatorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.evidence = Path(self.temp).resolve()
        self.directory = self.evidence / "flow"
        self.stack.enter_context(
            patch.object(matrix.adapter, "EVIDENCE_ROOT", self.evidence)
        )
        self.stack.enter_context(patch.object(site, "host"))
        self.stack.enter_context(
            patch.object(site, "source_head", return_value="4" * 40)
        )
        self.stack.enter_context(patch.dict(os.environ))
        os.environ.pop("SLURM_JOB_ID", None)
        self.plan = flow.prepare(self.directory)
        self.execution = matrix.load_flow(self.directory)
        self.matrix_approval, self.matrix_sha = fixtures.approved(self.execution)
        # Explicitly authorized synthetic fixtures only; no production approval CLI.
        (self.directory / "approval.json").write_bytes(
            flow.contract.encoded(self.matrix_approval)
        )
        self.approval = flow.approval_template(self.plan)
        self.approval.update(
            matrix_approval_sha256=self.matrix_sha,
            explicit_resource_budget_and_submission_approved=True,
            exact_head_four_ci_arms_reviewed=True,
        )
        (self.directory / "operator_approval.json").write_bytes(
            flow.contract.encoded(self.approval)
        )
        self.sha = flow.digest(self.directory / "operator_approval.json")
        self.calls = []
        self.command = self.stack.enter_context(
            patch.object(site, "command", side_effect=self.scheduler)
        )

    def scheduler(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[0] == "sbatch":
            return "99\n" if args[-1] == "easy" else "100\n"
        if args[:3] == ["scontrol", "show", "job"]:
            return held(args[-1])
        if args[:2] == ["scontrol", "release"]:
            parent = "easy" if args[-1] == "99" else "medium"
            state = flow.state_for(self.directory, parent)
            self.assertEqual(flow.load(state / "submission.json")["job_id"], args[-1])
            self.assertTrue((state / "held_profile.json").is_file())
            self.assertTrue((state / "release.started").is_file())
            return ""
        if args[0] == "sacct":
            return accounting(args[args.index("-j") + 1])
        raise AssertionError("Unexpected real command")

    def submit(self, parent="easy", review=None):
        return flow.submit(self.directory, self.sha, parent, review)

    def make_parent(self, complete=True):
        output = self.directory / "easy"
        output.mkdir()
        state = flow.state_for(self.directory, "easy")
        flow.write(state / "batch.started", {"job_id": "99"})
        receipts = {}
        if complete:
            helper = fixtures.MatrixTests()
            helper.plan, helper.approval, helper.sha = (
                self.execution,
                self.matrix_approval,
                self.matrix_sha,
            )
            gate = Mock(
                sample=Mock(return_value=1),
                public=Mock(return_value=fixtures.gate_value()),
            )

            def simulate(_command, console, _deadline, _gate):
                attempt = Path(console).parent
                request = flow.load(attempt / "request.json")
                helper.synthetic_child(attempt, request["attempt"])
                Path(console).write_bytes(b"private console, never export\n")
                return {
                    "child_exit_code": 0,
                    "guard_stop": None,
                    "sampled_cgroup_peak_bytes": 1,
                    "supervisor_wall_seconds": 1,
                    "peak_is_sampled_not_exact": True,
                }

            for row in matrix.rows_for(self.execution, "easy"):
                with (
                    patch.object(matrix.memory, "MemoryGate", return_value=gate),
                    patch.object(matrix.memory, "supervise", side_effect=simulate),
                ):
                    receipt = matrix.execute_attempt(
                        matrix.request_for(self.execution, self.matrix_sha, row),
                        output / row["attempt_id"],
                        "99",
                    )
                receipts[row["attempt_id"]] = flow.contract.sha(
                    flow.contract.encoded(receipt)
                )
        report = matrix.parent_report(
            self.execution,
            self.matrix_sha,
            "easy",
            "99",
            receipts,
            None if complete else "parent_deadline_reserve",
        )
        flow.write(output / "parent_receipt.json", report)
        return report

    def review(self, summary):
        value = {
            "schema_version": 1,
            "operator_plan_sha256": self.plan["operator_plan_sha256"],
            "operator_approval_sha256": self.sha,
            "job_id": "99",
            "return_sha256": summary["return_sha256"],
            "independent_review_passed": True,
            "scientific_reporting_eligible": False,
        }
        flow.write(self.directory / "easy.review.json", value)
        return flow.digest(self.directory / "easy.review.json")

    def reseal(self, directory):
        names = sorted(
            p.name for p in directory.iterdir() if p.name != "SHA256SUMS.txt"
        )
        (directory / "SHA256SUMS.txt").write_bytes(
            "".join(
                flow.digest(directory / n) + "  " + n + "\n" for n in names
            ).encode()
        )
        return flow.digest(directory / "SHA256SUMS.txt")

    def test_unapproved_prepare_has_no_commands_or_solver_access(self):
        other = self.evidence / "unapproved"
        with patch.object(matrix.adapter.screen, "licensed_runtime") as licensed:
            plan = flow.prepare(other)
        self.command.assert_not_called()
        licensed.assert_not_called()
        self.assertFalse(plan["resource_budget_approved"])
        self.assertEqual(plan["maximum_submissions"], 2)
        self.assertEqual(plan["scheduler"]["wall_seconds"], 19800)
        self.assertEqual(
            plan["matrix_plan_sha256"], matrix.plan_for("4" * 40)["plan_sha256"]
        )
        self.assertIs(
            flow.load(other / "operator_approval.json")["matrix_approval_sha256"], None
        )
        with self.assertRaises(ValueError):
            flow.submit(other, flow.digest(other / "operator_approval.json"), "easy")
        self.command.assert_not_called()

    def test_plan_mutations_and_source_changes_rejected_before_scheduler(self):
        for name in self.plan:
            value = copy.deepcopy(self.plan)
            value[name] = None
            with self.assertRaises((ValueError, TypeError)):
                flow.validate_plan(value)
        with (
            patch.object(site, "source_head", return_value="5" * 40),
            self.assertRaises(ValueError),
        ):
            self.submit()
        self.command.assert_not_called()

    def test_every_approval_mutation_rejected_before_claim(self):
        for name in self.approval:
            value = copy.deepcopy(self.approval)
            value[name] = None
            (self.directory / "operator_approval.json").write_bytes(
                flow.contract.encoded(value)
            )
            with self.assertRaises((ValueError, TypeError)):
                flow.approved(
                    self.directory,
                    flow.digest(self.directory / "operator_approval.json"),
                )
        self.command.assert_not_called()
        self.assertFalse(flow.root_for(self.sha).exists())

    def test_archived_probe_and_all_dependency_pins_reviewed(self):
        flow.reviewed_probe()
        with patch.object(flow, "PROBE_SHA", "0" * 64), self.assertRaises(ValueError):
            flow.reviewed_probe()

    def test_held_id_profile_and_release_order_exactly_once(self):
        result = self.submit()
        self.assertEqual(result["job_id"], "99")
        self.assertEqual(
            [args[:2] for args, _ in self.calls],
            [["sbatch", "--parsable"], ["scontrol", "show"], ["scontrol", "release"]],
        )
        args = self.calls[0][0]
        for flag in (
            "--hold",
            "--no-requeue",
            "--mem=64G",
            "--time=05:30:00",
            "--hint=nomultithread",
        ):
            self.assertIn(flag, args)
        for flag in ("--wait", "--exclusive", "--array", "--dependency", "--gpus"):
            self.assertFalse(any(arg.startswith(flag) for arg in args))
        with self.assertRaises(FileExistsError):
            self.submit()
        self.assertEqual(len(self.calls), 3)

    def test_override_environment_removed_and_batch_submission_rejected(self):
        os.environ.update(
            SBATCH_ARRAY_INX="1-10",
            SRUN_GPUS="8",
            SLURM_CLUSTERS="other",
            BASH_ENV="unsafe",
        )
        self.submit()
        env = self.calls[0][1]["env"]
        self.assertFalse(
            any(
                k.startswith(("SBATCH_", "SRUN_", "SLURM_")) or k == "BASH_ENV"
                for k in env
            )
        )
        os.environ["SLURM_JOB_ID"] = "99"
        with self.assertRaises(ValueError):
            flow.submit(self.directory, self.sha, "medium", "a" * 64)

    def test_failed_submission_consumes_global_budget_in_other_directory_too(self):
        self.command.side_effect = TimeoutError("uncertain")
        with self.assertRaises(TimeoutError):
            self.submit()
        self.assertTrue((flow.root_for(self.sha) / "STOP.json").exists())
        with self.assertRaises(FileExistsError):
            self.submit()
        self.assertEqual(self.command.call_count, 1)
        other = self.evidence / "other"
        other.mkdir()
        for name in (
            "plan.json",
            "approval.json",
            "operator_plan.json",
            "operator_approval.json",
        ):
            (other / name).write_bytes((self.directory / name).read_bytes())
        with self.assertRaises(FileExistsError):
            flow.submit(other, self.sha, "easy")
        self.assertEqual(self.command.call_count, 1)

    def test_ambiguous_sbatch_id_is_not_released_or_retried(self):
        self.command.side_effect = lambda *_a, **_kw: "99;other\n"
        with self.assertRaises(ValueError):
            self.submit()
        self.assertEqual(self.command.call_count, 1)
        self.assertTrue((flow.root_for(self.sha) / "STOP.json").exists())

    def test_bad_held_profile_keeps_known_job_held_and_status_usable(self):
        original = self.scheduler
        self.command.side_effect = lambda a, **kw: (
            held().replace("Requeue=0", "Requeue=1")
            if a[:2] == ["scontrol", "show"]
            else original(a, **kw)
        )
        with self.assertRaises(ValueError):
            self.submit()
        self.assertEqual(
            flow.load(flow.state_for(self.directory, "easy") / "submission.json")[
                "job_id"
            ],
            "99",
        )
        self.assertFalse(
            (flow.state_for(self.directory, "easy") / "release.started").exists()
        )
        self.command.side_effect = self.scheduler
        self.assertTrue(flow.status(self.directory, "easy")["terminal"])

    def test_release_failure_retains_id_and_never_releases_twice(self):
        def fail(args, **kwargs):
            if args[:2] == ["scontrol", "release"]:
                raise TimeoutError("uncertain release")
            return self.scheduler(args, **kwargs)

        self.command.side_effect = fail
        with self.assertRaises(TimeoutError):
            self.submit()
        state = flow.state_for(self.directory, "easy")
        self.assertTrue((state / "submission.json").exists())
        self.assertTrue((state / "release.started").exists())
        self.assertFalse((state / "released.json").exists())
        with self.assertRaises(FileExistsError):
            self.submit()
        self.assertEqual(self.command.call_count, 3)

    def test_held_profile_exact_allowlist_and_gpu_exclusive_requeue_rejected(self):
        value = flow.held_profile(held(), "99")
        flow.validate_held(value, "99")
        self.assertNotIn("Command", value)
        for before, after in (
            ("Requeue=0", "Requeue=1"),
            ("Restarts=0", "Restarts=1"),
            ("JobId=99", "JobId=100"),
            ("Partition=batch", "Partition=gpu"),
            ("OverSubscribe=OK", "OverSubscribe=EXCLUSIVE"),
            ("CPUs/Task=16", "CPUs/Task=32"),
            ("MinMemoryNode=64G", "MinMemoryNode=128G"),
            ("billing=32", "gres/gpu=1"),
            ("NumNodes=1", "NumNodes=2"),
            ("TimeLimit=05:30:00", "TimeLimit=UNLIMITED"),
            ("Priority=0", "Priority=1"),
        ):
            with self.assertRaises(ValueError):
                flow.held_profile(held().replace(before, after), "99")
        with self.assertRaises(ValueError):
            flow.held_profile(held() + " JobId=99", "99")
        with self.assertRaises(ValueError):
            flow.held_profile(held().replace("NumTasks=1 ", ""), "99")

    def test_run_binds_job_and_delegates_once_to_unchanged_memory_guard(self):
        self.submit()
        os.environ["SLURM_JOB_ID"] = "99"
        with patch.object(
            matrix, "run_parent", return_value={"complete_parent": True}
        ) as run:
            self.assertTrue(
                flow.run(self.directory, self.sha, "easy")["complete_parent"]
            )
            run.assert_called_once_with(self.directory, self.matrix_sha, "easy")
            with self.assertRaises(FileExistsError):
                flow.run(self.directory, self.sha, "easy")
            run.assert_called_once()

    def test_run_wrong_job_and_stop_reject_before_executor(self):
        self.submit()
        os.environ["SLURM_JOB_ID"] = "100"
        with patch.object(matrix, "run_parent") as run, self.assertRaises(ValueError):
            flow.run(self.directory, self.sha, "easy")
        run.assert_not_called()
        os.environ["SLURM_JOB_ID"] = "99"
        flow.stop(flow.root_for(self.sha), "submission_uncertain")
        with self.assertRaises(ValueError):
            flow.run(self.directory, self.sha, "easy")

    def test_run_failure_stops_all_remaining_and_keeps_claim(self):
        self.submit()
        os.environ["SLURM_JOB_ID"] = "99"
        with (
            patch.object(matrix, "run_parent", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            flow.run(self.directory, self.sha, "easy")
        self.assertTrue((flow.root_for(self.sha) / "STOP.json").exists())
        self.assertTrue(
            (flow.state_for(self.directory, "easy") / "batch.started").exists()
        )

    def test_status_is_one_query_and_never_waits(self):
        self.submit()
        self.command.reset_mock()
        self.command.side_effect = lambda *_a, **_kw: accounting(state="RUNNING")
        self.assertFalse(flow.status(self.directory, "easy")["terminal"])
        self.command.assert_called_once()
        self.assertEqual(self.command.call_args.args[0][0], "sacct")

    def test_running_or_empty_accounting_collect_makes_no_export_or_claim(self):
        self.submit()
        for response in (accounting(state="RUNNING"), ""):
            self.command.reset_mock()
            self.command.side_effect = lambda *_a, **_kw: response
            value = flow.collect(self.directory, "easy")
            self.assertFalse(value["collected"])
            self.command.assert_called_once()
        self.assertFalse((self.directory / "return-easy").exists())
        self.assertFalse(
            (flow.state_for(self.directory, "easy") / "collection.started").exists()
        )

    def test_root_completed_step_running_waits_for_accounting_consistency(self):
        self.submit()
        self.command.side_effect = lambda *_a, **_kw: accounting().replace(
            "99.0|COMPLETED", "99.0|RUNNING"
        )
        with self.assertRaises(ValueError):
            flow.collect(self.directory, "easy")
        self.assertFalse((self.directory / "return-easy").exists())

    def test_failed_missing_receipt_is_diagnostic_unknown_not_zero(self):
        self.submit()
        self.command.side_effect = lambda *_a, **_kw: accounting(
            state="OUT_OF_MEMORY", exit_code="0:9"
        )
        result = flow.collect(self.directory, "easy")
        self.assertFalse(result["ready_for_independent_review"])
        value = flow.validate_return(
            self.directory / "return-easy", result["return_sha256"]
        )
        self.assertIsNone(value["exact_optimization_call_count"])
        self.assertIsNone(value["completed_attempts_observed"])
        self.assertEqual(value["parent_evidence_state"], "unavailable")
        self.assertFalse((self.directory / "return-easy/matrix.tar.gz").exists())
        self.assertTrue(value["workflow_stop_present"])

    def test_partial_valid_receipt_stays_paused_and_scientifically_ineligible(self):
        self.submit()
        self.make_parent(False)
        result = flow.collect(self.directory, "easy")
        value = flow.validate_return(
            self.directory / "return-easy", result["return_sha256"]
        )
        self.assertFalse(value["ready_for_independent_review"])
        self.assertEqual(value["completed_attempts_observed"], 0)
        self.assertIsNone(value["exact_optimization_call_count"])
        self.assertFalse(value["scientific_reporting_eligible"])
        self.assertTrue((self.directory / "return-easy/matrix.tar.gz").is_file())

    def test_complete_nested_export_is_sanitized_idempotent_and_tamper_checked(self):
        self.submit()
        self.make_parent()
        result = flow.collect(self.directory, "easy")
        output = self.directory / "return-easy"
        self.assertEqual({p.name for p in output.iterdir()}, flow.PUBLIC)
        value = flow.validate_return(output, result["return_sha256"])
        self.assertTrue(value["ready_for_independent_review"])
        self.assertEqual(value["exact_optimization_call_count"], 5)
        self.assertFalse(value["scientific_reporting_eligible"])
        self.command.reset_mock()
        self.assertEqual(flow.collect(self.directory, "easy"), result)
        self.command.assert_not_called()
        (output / "matrix.tar.gz").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            flow.validate_return(output, result["return_sha256"])

    def test_private_log_tampering_never_requalified_or_exported(self):
        self.submit()
        self.make_parent()
        first = matrix.rows_for(self.execution, "easy")[0]["attempt_id"]
        (self.directory / "easy" / first / "console.private.log").write_bytes(
            b"changed"
        )
        result = flow.collect(self.directory, "easy")
        value = flow.validate_return(
            self.directory / "return-easy", result["return_sha256"]
        )
        self.assertEqual(value["parent_evidence_state"], "invalid")
        self.assertIsNone(value["exact_optimization_call_count"])
        self.assertFalse(value["ready_for_independent_review"])

    def test_medium_requires_review_terminal_easy_and_no_stop_then_one_submission(self):
        self.submit()
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.submit("medium", "a" * 64)
        self.make_parent()
        result = flow.collect(self.directory, "easy")
        review = self.review(result)
        with (
            patch.object(
                flow,
                "status",
                return_value=site.parse_accounting(accounting(state="RUNNING"), "99"),
            ),
            self.assertRaises(ValueError),
        ):
            self.submit("medium", review)
        self.assertFalse(
            (flow.state_for(self.directory, "medium") / "submission.json").exists()
        )
        self.assertEqual(self.submit("medium", review)["job_id"], "100")
        with self.assertRaises(FileExistsError):
            self.submit("medium", review)
        self.assertEqual(sum(a[0] == "sbatch" for a, _ in self.calls), 2)

    def test_easy_review_hash_mutation_and_global_stop_prevent_medium(self):
        self.submit()
        self.make_parent()
        result = flow.collect(self.directory, "easy")
        review = self.review(result)
        with self.assertRaises(ValueError):
            self.submit("medium", "0" * 64)
        flow.stop(flow.root_for(self.sha), "batch_failed")
        with self.assertRaises(ValueError):
            self.submit("medium", review)
        self.assertEqual(sum(a[0] == "sbatch" for a, _ in self.calls), 1)

    def test_return_unexpected_member_and_semantic_promotion_rejected(self):
        self.submit()
        result = flow.collect(self.directory, "easy")
        output = self.directory / "return-easy"
        original = (output / "accounting.json").read_bytes()
        value = flow.load(output / "accounting.json")
        for key, bad in (
            ("scientific_reporting_eligible", True),
            ("exact_optimization_call_count", 0),
            ("ready_for_independent_review", True),
            ("parent", "medium"),
            ("schema_version", True),
        ):
            changed = {**value, key: bad}
            (output / "accounting.json").write_bytes(flow.contract.encoded(changed))
            sha = self.reseal(output)
            with self.assertRaises(ValueError):
                flow.validate_return(output, sha)
        (output / "accounting.json").write_bytes(original)
        (output / "unexpected.private.log").write_bytes(b"never export")
        with self.assertRaises(ValueError):
            flow.validate_return(output, result["return_sha256"])

    def test_failed_accounting_cannot_promote_complete_parent(self):
        self.submit()
        self.make_parent()
        self.command.side_effect = lambda *_a, **_kw: accounting(
            state="FAILED", exit_code="1:0"
        )
        result = flow.collect(self.directory, "easy")
        value = flow.validate_return(
            self.directory / "return-easy", result["return_sha256"]
        )
        self.assertTrue(value["complete_parent"])
        self.assertFalse(value["ready_for_independent_review"])
        self.assertTrue(value["pause_remaining_matrix"])

    def test_batch_script_budget_pins_and_no_retry_loop(self):
        text = (ROOT / flow.BATCH).read_text()
        for fragment in (
            "--time=05:30:00",
            "--no-requeue",
            "SLURM_RESTART_COUNT",
            "--parent",
            "paired_matrix_workflow.py run",
        ):
            self.assertIn(fragment, text)
        self.assertNotIn("sbatch", text)
        self.assertNotIn("sacct", text)
        self.assertNotIn("while ", text)
        self.assertEqual(
            self.plan["dependency_sha256"][flow.BATCH], flow.digest(ROOT / flow.BATCH)
        )

    def test_cli_help_is_solver_free_and_normal_exit(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/evidence/paired_matrix_workflow.py"),
                "--help",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn(b"validate-return", completed.stdout)

    def test_batch_only_changes_trigger_both_evidence_ci_events(self):
        text = (ROOT / ".github/workflows/evidence.yml").read_text()
        self.assertEqual(text.count("'" + flow.BATCH + "'"), 2)


if __name__ == "__main__":
    unittest.main()
