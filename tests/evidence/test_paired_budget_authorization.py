"""Offline explicit-budget tests; no solver, scheduler or production approval."""

import copy
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import paired_budget_authorization as budget  # noqa: E402

flow = budget.flow


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.evidence = Path(
            self.stack.enter_context(tempfile.TemporaryDirectory())
        ).resolve()
        self.directory = self.evidence / "pr76/operator-ad4800505bae/flow"
        self.directory.mkdir(parents=True)
        self.source = self.directory.parent / "source"
        self.source.mkdir()
        self.stack.enter_context(
            patch.object(flow.matrix.adapter, "EVIDENCE_ROOT", self.evidence)
        )
        self.stack.enter_context(patch.object(flow.site, "host"))
        self.stack.enter_context(patch.dict(os.environ))
        os.environ.pop("SLURM_JOB_ID", None)
        self.plan = budget.review()
        self.execution = flow.matrix.plan_for(budget.HEAD)
        flow.write(self.directory / "plan.json", self.execution)
        flow.write(self.directory / "operator_plan.json", self.plan)
        flow.write(
            self.directory / "approval.json",
            flow.matrix.approval_template(self.execution),
        )
        flow.write(
            self.directory / "operator_approval.json", flow.approval_template(self.plan)
        )
        flow.write(
            self.directory.parent / "pr76_operator_preparation.json",
            budget.expected_receipt(self.plan),
        )
        for name in self.plan["dependency_sha256"]:
            relative = (
                Path(name)
                if name.startswith("scripts/")
                else Path("scripts/evidence") / name
            )
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        self.command = self.stack.enter_context(
            patch.object(flow.site, "command", side_effect=self.git_read)
        )
        self.licensed = self.stack.enter_context(
            patch.object(flow.matrix.adapter.screen, "licensed_runtime")
        )
        self.authorization = budget.template(self.directory)
        for name in (
            "explicit_resource_budget_and_submission_approved",
            "exact_head_four_ci_arms_reviewed",
            "installed_no_solver_probes_reviewed",
        ):
            self.authorization[name] = True
        self.path = self.directory.parent / "explicit-authorization.json"
        flow.write(self.path, self.authorization)  # Explicit synthetic fixture only.
        self.sha = flow.digest(self.path)

    def git_read(self, command):
        self.assertEqual(command[0], "git")
        self.assertIn(str(self.source), command)
        return budget.HEAD + "\n" if command[-2:] == ["rev-parse", "HEAD"] else ""

    def record(self):
        result = budget.record(self.directory, self.path, self.sha)
        self.licensed.assert_not_called()
        return result

    def test_archived_bytes_exact_plans_and_thirteen_pins(self):
        self.assertEqual(flow.digest(ROOT / budget.ARCHIVE), budget.RECEIPT_SHA)
        self.assertEqual(len(self.plan["dependency_sha256"]), 13)
        self.assertEqual(self.plan["operator_plan_sha256"], budget.OPERATOR_SHA)
        self.assertEqual(self.plan["matrix_plan_sha256"], budget.MATRIX_SHA)
        self.command.assert_not_called()
        self.licensed.assert_not_called()

    def test_receipt_corruption_unknown_member_and_qualification_rejected(self):
        for change in (
            {"tests_run": True},
            {"skipped": 1},
            {"resource_budget_approved": True},
            {"higher_budget_memory_safety_qualified": True},
            {"scientific_reporting_eligible": True},
            {"optimization_runs_added": 1},
            {"unexpected_private_member": "no"},
        ):
            with self.subTest(change=change):
                value = budget.expected_receipt(self.plan)
                value.update(change)
                self.path.write_bytes(flow.contract.encoded(value))
                with self.assertRaises(ValueError):
                    budget.review(self.path)

    def test_preview_is_false_nonmutating_and_only_source_queries(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        directory, _, _ = budget.frozen_flow(self.directory)
        value = budget.template(directory)
        self.assertFalse(value["explicit_resource_budget_and_submission_approved"])
        self.assertFalse(value["exact_head_four_ci_arms_reviewed"])
        self.assertFalse(value["installed_no_solver_probes_reviewed"])
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.directory.iterdir()}
        )
        self.assertEqual(self.command.call_count, 2)
        self.assertFalse((self.evidence / "paired-budget-authorization-locks").exists())
        self.licensed.assert_not_called()

    def test_false_or_partial_or_wrong_hash_authorization_cannot_record(self):
        for change in (
            {"explicit_resource_budget_and_submission_approved": False},
            {"exact_head_four_ci_arms_reviewed": False},
            {"installed_no_solver_probes_reviewed": False},
            {"flow_directory_sha256": "0" * 64},
            {"source_commit": "0" * 40},
            {"maximum_submissions": 3},
            {"maximum_optimization_calls": 11},
            {"maximum_optimization_seconds": 36001},
            {"maximum_parent_wall_seconds": 19801},
            {"scheduler_memory_mib": 131072},
            {"gpus": 1},
            {"exclusive": True},
            {"requeue": True},
            {"automatic_retry": True},
            {"higher_budget_memory_safety_qualified": True},
            {"scientific_reporting_eligible": True},
            {"exact_head_four_ci_arms_reviewed": 1},
            {"unexpected": "no"},
        ):
            with self.subTest(change=change):
                value = copy.deepcopy(self.authorization)
                value.update(change)
                self.path.write_bytes(flow.contract.encoded(value))
                with self.assertRaises(ValueError):
                    budget.record(self.directory, self.path, flow.digest(self.path))
                self.assertFalse(
                    (self.evidence / "paired-budget-authorization-locks").exists()
                )
        with self.assertRaises(ValueError):
            budget.record(self.directory, self.path, "0" * 64)

    def test_wrong_original_head_or_dirty_source_rejected(self):
        for replies in (("0" * 40 + "\n", ""), (budget.HEAD + "\n", "?? unsafe\n")):
            with (
                self.subTest(replies=replies),
                patch.object(flow.site, "command", side_effect=replies),
                self.assertRaises(ValueError),
            ):
                self.record()
        self.assertFalse((self.evidence / "paired-budget-authorization-locks").exists())

    def test_any_original_dependency_changed_rejected(self):
        for name in self.plan["dependency_sha256"]:
            relative = (
                Path(name)
                if name.startswith("scripts/")
                else Path("scripts/evidence") / name
            )
            target = self.source / relative
            raw = target.read_bytes()
            target.write_bytes(raw + b"\n")
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.record()
            target.write_bytes(raw)

    def test_plan_or_installed_receipt_mutation_rejected(self):
        for target in (
            self.directory / "plan.json",
            self.directory / "operator_plan.json",
            self.directory.parent / "pr76_operator_preparation.json",
        ):
            raw = target.read_bytes()
            target.write_bytes(raw + b" ")
            with self.subTest(target=target.name), self.assertRaises(ValueError):
                self.record()
            target.write_bytes(raw)

    def test_started_flow_or_nested_batch_or_gurobi_env_rejected(self):
        for name in ("operator-state", "easy", "medium"):
            path = self.directory / name
            path.mkdir()
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.record()
            path.rmdir()
        with patch.dict(os.environ, SLURM_JOB_ID="100"), self.assertRaises(ValueError):
            self.record()
        (self.source / "gurobi.env").write_bytes(b"unsafe fixture")
        with self.assertRaises(ValueError):
            self.record()

    def test_record_keeps_plans_and_original_false_backups_no_submission(self):
        plan_bytes = (self.directory / "plan.json").read_bytes()
        operator_bytes = (self.directory / "operator_plan.json").read_bytes()
        result = self.record()
        self.assertTrue(result["recorded_separate_explicit_budget"])
        self.assertEqual(result["optimization_runs_added"], 0)
        self.assertEqual(result["submissions_added"], 0)
        self.assertEqual(result["scheduler_queries"], 0)
        self.assertFalse(result["higher_budget_memory_safety_qualified"])
        self.assertFalse(result["scientific_reporting_eligible"])
        self.assertEqual((self.directory / "plan.json").read_bytes(), plan_bytes)
        self.assertEqual(
            (self.directory / "operator_plan.json").read_bytes(), operator_bytes
        )
        root = self.evidence / "paired-budget-authorization-locks" / self.sha
        self.assertFalse(
            flow.load(root / "matrix_approval.before.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        self.assertFalse(
            flow.load(root / "operator_approval.before.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        self.assertEqual(flow.load(root / "recording.completed.json"), result)
        self.assertEqual(
            flow.digest(self.directory / "approval.json"),
            result["matrix_approval_sha256"],
        )
        self.assertEqual(
            flow.digest(self.directory / "operator_approval.json"),
            result["operator_approval_sha256"],
        )
        self.assertEqual(self.command.call_count, 2)

    def test_record_replay_or_existing_claim_never_overwritten(self):
        self.record()
        with self.assertRaises(ValueError):
            self.record()
        flow.write(self.path.with_name("another.json"), self.authorization)
        with self.assertRaises(ValueError):
            budget.record(self.directory, self.path.with_name("another.json"), self.sha)

    def test_existing_empty_recording_claim_blocks_before_replacement(self):
        root = self.evidence / "paired-budget-authorization-locks" / self.sha
        root.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.record()
        self.assertFalse(
            flow.load(self.directory / "approval.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )

    def test_existing_executor_or_submission_claim_blocks_budget_record(self):
        _, matrix_sha, _, operator_sha = budget.approved_records(
            self.plan, self.execution
        )
        for root in (
            flow.root_for(operator_sha),
            self.evidence / "paired-matrix-locks" / matrix_sha,
        ):
            root.mkdir(parents=True)
            with self.subTest(root=root.parent.name), self.assertRaises(ValueError):
                self.record()
            root.rmdir()

    def test_interruption_preserves_partial_record_and_no_automatic_resume(self):
        real_replace = budget.replace_false_approval

        def interrupt(path, before, after):
            if path.name == "operator_approval.json":
                raise KeyboardInterrupt
            return real_replace(path, before, after)

        with (
            patch.object(budget, "replace_false_approval", side_effect=interrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.record()
        root = self.evidence / "paired-budget-authorization-locks" / self.sha
        self.assertTrue((root / "authorization.json").exists())
        self.assertFalse((root / "recording.completed.json").exists())
        self.assertTrue(
            flow.load(self.directory / "approval.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        self.assertFalse(
            flow.load(self.directory / "operator_approval.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        with self.assertRaises(ValueError):
            self.record()
        self.licensed.assert_not_called()

    def test_wrong_directory_and_archive_line_endings_rejected(self):
        other = self.directory.parent / "wrong"
        other.mkdir()
        with self.assertRaises(ValueError):
            budget.frozen_flow(other)
        self.path.write_bytes(
            (ROOT / budget.ARCHIVE).read_bytes().replace(b"\n", b"\r\n")
        )
        with self.assertRaises(ValueError):
            budget.review(self.path)
        self.assertIn(
            "docs/evidence/pr76/operator-ad4800505bae/** -text",
            (ROOT / ".gitattributes").read_text(),
        )

    def test_authorization_outside_evidence_root_is_rejected(self):
        with self.assertRaises(ValueError):
            budget.validate_authorization(
                self.directory, self.evidence.parent / "outside.json", self.sha
            )

    def test_pending_write_failure_keeps_false_approvals_and_claim(self):
        real_write = flow.write

        def fail_pending(path, value):
            if Path(path).name.endswith(".authorized.pending"):
                raise OSError("injected_write_failure")
            return real_write(path, value)

        with (
            patch.object(flow, "write", side_effect=fail_pending),
            self.assertRaises(OSError),
        ):
            self.record()
        self.assertFalse(
            flow.load(self.directory / "approval.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        self.assertFalse(
            flow.load(self.directory / "operator_approval.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        self.assertTrue(
            (self.evidence / "paired-budget-authorization-locks" / self.sha).exists()
        )
        with self.assertRaises(FileExistsError):
            self.record()

    def test_ack_failure_preserves_both_authorized_files_without_claiming_transaction(
        self,
    ):
        real_write = flow.write

        def fail_ack(path, value):
            if Path(path).name == "recording.completed.json":
                raise OSError("injected_ack_failure")
            return real_write(path, value)

        with (
            patch.object(flow, "write", side_effect=fail_ack),
            self.assertRaises(OSError),
        ):
            self.record()
        self.assertTrue(
            flow.load(self.directory / "approval.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        self.assertTrue(
            flow.load(self.directory / "operator_approval.json")[
                "explicit_resource_budget_and_submission_approved"
            ]
        )
        root = self.evidence / "paired-budget-authorization-locks" / self.sha
        self.assertTrue(root.exists())
        self.assertFalse((root / "recording.completed.json").exists())
        with self.assertRaises(ValueError):
            self.record()
        self.licensed.assert_not_called()

    def test_readonly_cli_review_and_help(self):
        for action in ("review", "--help"):
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/evidence/paired_budget_authorization.py"),
                    action,
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn(b"sbatch", completed.stdout)


if __name__ == "__main__":
    unittest.main()
