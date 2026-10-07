"""No-solver continuation lineage and one-shot safety tests."""

import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import recover_pr78_job3482 as recovery  # noqa: E402
import test_paired_matrix_workflow_v3 as fixtures  # noqa: E402

flow = recovery.flow


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.OperatorWorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        (self.fixture.evidence / "pr78").mkdir()

    def test_prepare_preserves_predecessor_and_rejects_second_claim(self):
        before = (self.fixture.directory / "operator_approval.json").read_bytes()
        with (
            patch.object(recovery, "predecessor", return_value={"job_id": "3482"}),
            patch.object(
                recovery.previous, "review_ci", return_value={"reviewed": True}
            ),
        ):
            result = recovery.prepare()
            with self.assertRaises(ValueError):
                recovery.prepare()
        directory = Path(result["directory"])
        plan, _ = flow.approved(directory, result["approval_sha256"])
        self.assertEqual(plan["maximum_optimization_calls"], 10)
        self.assertEqual(plan["maximum_optimization_seconds"], 36000)
        self.assertFalse(plan["automatic_retry"])
        self.assertEqual(
            before, (self.fixture.directory / "operator_approval.json").read_bytes()
        )
        self.assertEqual(self.fixture.calls, [])
        self.assertFalse((directory / "operator-state").exists())

    def test_failed_predecessor_validation_creates_no_claim(self):
        with (
            patch.object(recovery, "predecessor", side_effect=ValueError("changed")),
            patch.object(recovery.previous, "review_ci", return_value={}),
            self.assertRaises(ValueError),
        ):
            recovery.prepare()
        self.assertFalse(
            (self.fixture.evidence / "pr78/job3482-recovery.claim").exists()
        )
        self.assertEqual(self.fixture.calls, [])

    def test_changed_qualification_binding_rejected_by_operator(self):
        path = self.fixture.directory.parent / "recovery.json"
        value = flow.load(path)
        value["installed_hierarchical_qualification_sha256"] = "0" * 64
        path.write_bytes(flow.contract.encoded(value))
        with self.assertRaises(ValueError):
            self.fixture.submit()
        self.assertEqual(self.fixture.calls, [])


class PredecessorTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.root = Path(self.temp).resolve()
        self.directory = self.root / "pr78/recovery-job3481-v2/flow"
        self.source = self.root / "pr78/recovery-source-173b63d62658"
        self.plan = recovery.predecessor_flow.plan_for(recovery.OLD_HEAD)
        self.stack.enter_context(
            patch.object(flow.matrix.adapter, "EVIDENCE_ROOT", self.root)
        )
        self.stack.enter_context(
            patch.object(flow.site, "location", side_effect=lambda p: p)
        )
        self.stack.enter_context(patch.object(flow, "digest", side_effect=self.digest))
        self.stack.enter_context(patch.object(flow, "load", side_effect=self.load))
        self.stack.enter_context(patch.object(flow.matrix.evidence, "review"))
        self.stack.enter_context(
            patch.object(
                recovery.predecessor_flow,
                "validate_return",
                return_value={
                    "accounting": {"job_id": "3482"},
                    "parent_evidence_state": "unavailable",
                    "pause_remaining_matrix": True,
                    "matrix_approval_sha256": recovery.OLD_MATRIX_SHA,
                    "operator_approval_sha256": recovery.OLD_OPERATOR_SHA,
                },
            )
        )
        self.accounting = "\n".join(
            f"3482{suffix}|{state}|{code}|{elapsed}|00:00:00|16|64G|0"
            for suffix, state, code, elapsed in (
                ("", "FAILED", "2:0", 1),
                (".batch", "FAILED", "2:0", 1),
                (".extern", "COMPLETED", "0:0", 1),
                (".0", "FAILED", "2:0", 0),
            )
        )
        self.calls = []
        self.stack.enter_context(
            patch.object(flow.site, "command", side_effect=self.command)
        )

    def command(self, args, **kwargs):
        self.calls.append(args)
        if args[0] == "git":
            return recovery.OLD_HEAD if "rev-parse" in args else ""
        if args[0] == "sacct":
            return self.accounting
        raise AssertionError("unexpected_command")

    def digest(self, path):
        special = {
            "approval.json": recovery.OLD_MATRIX_SHA,
            "operator_approval.json": recovery.OLD_OPERATOR_SHA,
            "authorization.json": recovery.AUTH_SHA,
            "qualification.json": flow.matrix.evidence.QUALIFICATION_SHA,
            "slurm-3482.private.err": "3e3cab03da3895bb5a1ee8cd28d7ebd3a164ccedf85809ac8d4620436d5f79e2",
            "slurm-3482.private.out": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
        if path.name in special:
            return special[path.name]
        relative = path.relative_to(self.source).as_posix()
        key = relative if relative.startswith("scripts/slurm/") else path.name
        return self.plan["dependency_sha256"][key]

    def load(self, path):
        if path.name == "operator_plan.json":
            return self.plan
        if path.name in {"batch.started", "release.started", "released.json"}:
            return {"job_id": "3482"}
        if path.name == "STOP.json":
            return {"code": "batch_failed"}
        if path.name == "recovery.json":
            return {
                "prior_authorization_sha256": recovery.AUTH_SHA,
                "successor_operator_approval_sha256": recovery.OLD_OPERATOR_SHA,
                "successor_matrix_approval_sha256": recovery.OLD_MATRIX_SHA,
            }
        raise AssertionError("unexpected_read")

    def test_pre_executor_failure_accepts_only_bounded_read_queries(self):
        result = recovery.predecessor()
        self.assertTrue(result["terminal"])
        self.assertEqual([x[0] for x in self.calls], ["git", "git", "sacct"])

    def test_existing_parent_or_claim_blocks(self):
        path = self.directory / "easy"
        path.mkdir(parents=True)
        with self.assertRaises(ValueError):
            recovery.predecessor()
        self.assertFalse(any(x[0] == "sacct" for x in self.calls))

    def test_changed_or_running_accounting_blocks(self):
        for before, after in (("FAILED", "RUNNING"), ("|1|", "|100|"), ("2:0", "0:0")):
            old = self.accounting
            self.accounting = old.replace(before, after)
            with self.subTest(after=after), self.assertRaises(ValueError):
                recovery.predecessor()
            self.accounting = old

    def test_changed_guard_bytes_block(self):
        with (
            patch.object(flow, "digest", return_value="0" * 64),
            self.assertRaises(ValueError),
        ):
            recovery.predecessor()


if __name__ == "__main__":
    unittest.main()
