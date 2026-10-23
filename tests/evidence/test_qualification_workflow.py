"""Offline scheduler/approval/export regressions: no Slurm or licensed runtime.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import copy
import gzip
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import qualification_workflow as flow  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import test_isolated_attempt_worker as fixtures  # noqa: E402

HEAD = "2" * 40


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.root = Path(self.tmp).resolve()
        self.directory = self.root / "flow"
        self.stack.enter_context(patch.object(flow, "host"))
        self.stack.enter_context(patch.object(flow, "source_head", return_value=HEAD))
        self.stack.enter_context(
            patch.object(flow.worker.adapter, "EVIDENCE_ROOT", self.root)
        )

    def prepare(self):
        with patch.object(flow, "check_preflight") as check:
            plan = flow.prepare(self.directory, self.root / "preflight")
            check.assert_called_once()
        return plan

    def approve(self):
        plan = self.prepare()
        # Test fixture only: production never changes the unapproved template.
        approval = flow.load(self.directory / "approval.json")
        approval["explicitly_approved"] = True
        raw = flow.contract.encoded(approval)
        (self.directory / "approval.json").write_bytes(raw)
        return plan, flow.contract.sha(raw)

    def submit(self, side_effect=None):
        plan, sha = self.approve()
        with patch.object(
            flow, "command", side_effect=side_effect or ["123\n", ""]
        ) as cmd:
            value = flow.submit(self.directory, sha)
        return plan, sha, value, cmd

    def test_prepare_no_scheduler_or_solver_and_template_unapproved(self):
        with (
            patch.object(flow, "command") as cmd,
            patch.object(flow.worker, "supervise_one") as solve,
        ):
            value = self.prepare()
        cmd.assert_not_called()
        solve.assert_not_called()
        self.assertFalse(value["resource_budget_approved"])
        self.assertFalse(
            flow.load(self.directory / "approval.json")["explicitly_approved"]
        )
        self.assertEqual(value["optimization_limit_seconds"], 60)
        self.assertEqual(value["scheduler"]["wall_seconds"], 600)

    def test_second_prepare_no_overwrite(self):
        self.prepare()
        before = (self.directory / "plan.json").read_bytes()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual((self.directory / "plan.json").read_bytes(), before)

    def test_unapproved_or_wrong_sha_never_submits(self):
        self.prepare()
        sha = flow.worker.adapter.screen.digest(self.directory / "approval.json")
        for digest in (sha, "0" * 64):
            with patch.object(flow, "command") as cmd:
                with self.assertRaises(ValueError):
                    flow.submit(self.directory, digest)
                cmd.assert_not_called()
        self.assertFalse((self.directory / "submission.started").exists())

    def test_plan_mutations_refused(self):
        plan = flow.proposed_plan(HEAD)
        for name, value in (
            ("maximum_submissions", 2),
            ("resource_budget_approved", True),
            ("optimization_limit_seconds", 300),
            ("attempt_id", "medium-seed42-threads16"),
            ("dependency_sha256", {}),
        ):
            bad = copy.deepcopy(plan)
            bad[name] = value
            with self.assertRaises(ValueError):
                flow.validate_plan(bad)

    def test_approval_integer_booleans_extra_keys_and_wrong_plan_rejected(self):
        plan, _ = self.approve()
        original = flow.load(self.directory / "approval.json")
        for name, value in (
            ("maximum_submissions", True),
            ("plan_sha256", "0" * 64),
            ("scientific_reporting_eligible", True),
            ("extra", 1),
        ):
            bad = {**original, name: value}
            raw = flow.contract.encoded(bad)
            (self.directory / "approval.json").write_bytes(raw)
            with self.assertRaises(ValueError):
                flow.approved(self.directory, flow.contract.sha(raw))
        self.assertFalse(plan["resource_budget_approved"])

    def test_submission_hold_persist_id_before_release_and_remove_overrides(self):
        plan, sha = self.approve()
        calls = []

        def scheduler(args, **kwargs):
            calls.append(args)
            if args[0] == "sbatch":
                self.assertIn("--hold", args)
                self.assertIn("--no-requeue", args)
                self.assertNotIn("--wait", args)
                self.assertNotIn("SBATCH_GPUS", kwargs["env"])
                self.assertNotIn("SBATCH_EXCLUSIVE", kwargs["env"])
                self.assertTrue(flow.claim_path(sha).is_dir())
                self.assertFalse((self.directory / "submission.json").exists())
                return "123\n"
            self.assertEqual(
                flow.load(self.directory / "submission.json")["job_id"], "123"
            )
            return ""

        with (
            patch.object(flow, "command", side_effect=scheduler),
            patch.dict(flow.os.environ, {"SBATCH_GPUS": "1", "SBATCH_EXCLUSIVE": "1"}),
        ):
            self.assertEqual(flow.submit(self.directory, sha)["job_id"], "123")
        self.assertEqual([c[0] for c in calls], ["sbatch", "scontrol"])
        self.assertEqual(
            flow.submission(self.directory)["plan_sha256"], plan["plan_sha256"]
        )

    def test_second_submit_and_global_approval_reuse_refused(self):
        plan, sha, _, _ = self.submit()
        with patch.object(flow, "command") as cmd:
            with self.assertRaises(ValueError):
                flow.submit(self.directory, sha)
            other = self.root / "other"
            other.mkdir()
            flow.worker.write_json(other / "plan.json", plan)
            (other / "approval.json").write_bytes(
                (self.directory / "approval.json").read_bytes()
            )
            with self.assertRaises(FileExistsError):
                flow.submit(other, sha)
            cmd.assert_not_called()

    def test_submission_timeout_unknown_retained_no_release_no_retry(self):
        _, sha = self.approve()
        with patch.object(
            flow, "command", side_effect=subprocess.TimeoutExpired("sbatch", 20)
        ) as cmd:
            with self.assertRaises(subprocess.TimeoutExpired):
                flow.submit(self.directory, sha)
            self.assertEqual(cmd.call_count, 1)
        self.assertTrue(flow.claim_path(sha).exists())
        self.assertTrue((self.directory / "submission.started").exists())
        self.assertFalse((self.directory / "submission.json").exists())
        with patch.object(flow, "command") as cmd:
            with self.assertRaises(ValueError):
                flow.submit(self.directory, sha)
            cmd.assert_not_called()

    def test_release_failure_retains_job_for_read_only_inspection(self):
        _, sha = self.approve()
        with (
            patch.object(
                flow, "command", side_effect=["123", ValueError("release failed")]
            ),
            self.assertRaises(ValueError),
        ):
            flow.submit(self.directory, sha)
        self.assertEqual(flow.submission(self.directory)["job_id"], "123")

    def test_ambiguous_scheduler_id_refused_and_retained(self):
        _, sha = self.approve()
        with patch.object(flow, "command", return_value="123;remote") as cmd:
            with self.assertRaises(ValueError):
                flow.submit(self.directory, sha)
            self.assertEqual(cmd.call_count, 1)
        self.assertTrue((self.directory / "submission.started").exists())

    def test_job_and_request_binding_before_worker(self):
        _, sha, _, _ = self.submit()
        with (
            patch.dict(flow.os.environ, {"SLURM_JOB_ID": "123"}),
            patch.object(
                flow.worker, "supervise_one", return_value={"status": "synthetic"}
            ) as solve,
        ):
            self.assertEqual(flow.run(self.directory, sha), {"status": "synthetic"})
            solve.assert_called_once()
        with (
            patch.dict(flow.os.environ, {"SLURM_JOB_ID": "124"}),
            patch.object(flow.worker, "supervise_one") as solve,
        ):
            with self.assertRaises(ValueError):
                flow.run(self.directory, sha)
            solve.assert_not_called()
        request = flow.load(self.directory / "request.json")
        request["optimization_limit_seconds"] = 30
        (self.directory / "request.json").write_bytes(flow.contract.encoded(request))
        with self.assertRaises(ValueError):
            flow.submission(self.directory)

    def test_status_one_shot_root_not_step_and_no_mutation(self):
        self.submit()
        original = set(self.directory.iterdir())
        text = "123|COMPLETED|0:0|60|01:01.115|32|64G|\n123.batch|COMPLETED|0:0|60|00:00:00.024|32||4208K\n"
        with patch.object(flow, "command", return_value=text) as cmd:
            value = flow.status(self.directory)
            cmd.assert_called_once()
        self.assertTrue(value["terminal"])
        self.assertEqual(value["state"], "COMPLETED")
        self.assertEqual(set(self.directory.iterdir()), original)
        step_only = flow.parse_accounting(text.splitlines()[1], "123")
        self.assertFalse(step_only["terminal"])
        self.assertEqual(step_only["state"], "ACCOUNTING_UNAVAILABLE")

    def test_accounting_empty_running_cancelled_suffix_and_bad_rows(self):
        self.assertFalse(flow.parse_accounting("", "123")["terminal"])
        self.assertFalse(
            flow.parse_accounting("123|RUNNING|0:0|4|00:00:00|32|64G|", "123")[
                "terminal"
            ]
        )
        row = "123|CANCELLED+ by 1234|0:15|4|00:00:00|32|64G|"
        self.assertEqual(flow.parse_accounting(row, "123")["state"], "CANCELLED")
        for text in (
            row + "\n" + row,
            row.replace("123|", "124|", 1),
            row.replace("64G", "/home/secret"),
            row.replace("CANCELLED+ by 1234", "SECRET"),
        ):
            with self.assertRaises(ValueError):
                flow.parse_accounting(text, "123")

    def test_nonterminal_collect_no_export_or_solver(self):
        self.submit()
        with (
            patch.object(flow, "status", return_value={"terminal": False}),
            patch.object(flow.worker, "export_receipt") as export,
            patch.object(flow.worker, "supervise_one") as solve,
            self.assertRaises(ValueError),
        ):
            flow.collect(self.directory)
        export.assert_not_called()
        solve.assert_not_called()

    def test_missing_terminal_receipt_no_fabricated_result(self):
        self.submit()
        with (
            patch.object(flow, "status", return_value={"terminal": True}),
            self.assertRaises(ValueError),
        ):
            flow.collect(self.directory)
        self.assertFalse((self.directory / "return").exists())

    def test_location_rejects_source_root_and_alias(self):
        with self.assertRaises(ValueError):
            flow.location(self.root)
        with self.assertRaises(ValueError):
            flow.location(flow.SOURCE)
        # Parent traversal must not be silently normalized into a write target.
        with self.assertRaises(ValueError):
            flow.location(self.root / "other/../flow")

    def make_attempt(self, process_failure=False):
        _, sha, _, _ = self.submit()
        req = flow.load(self.directory / "request.json")
        out = self.directory / "attempt"
        original_hash = next(
            r["original_lp_sha256"]
            for r in flow.contract.compile_proposal()["attempts"]
            if r["attempt_id"] == req["attempt_id"]
        )

        def child(command, console, deadline):
            Path(console).write_bytes(b"LICENSEID synthetic private console\n")
            if process_failure:
                return 2, False
            gp, _, _ = fixtures.fake_api(out)
            flow.worker.write_json(out / "request.private.json.child", req)
            (out / "child.started").write_bytes(
                flow.contract.sha(flow.contract.encoded(req)).encode()
            )
            with (
                patch.object(flow.worker, "validate_claim"),
                patch.object(
                    flow.worker.adapter.screen,
                    "qualify_affinity",
                    return_value=fixtures.affinity(),
                ),
                patch.object(
                    flow.worker,
                    "dependency_hashes",
                    return_value=req["dependency_sha256"],
                ),
                patch.dict(sys.modules, {"resource": fixtures.fake_resource()}),
                patch.dict(flow.os.environ, {"SLURM_JOB_ID": "123"}),
                patch.object(
                    flow.worker.adapter.screen,
                    "frozen_source",
                    return_value=out / "original.lp",
                ),
                patch.object(
                    flow.worker.adapter.screen, "digest", return_value=original_hash
                ),
                patch.object(
                    flow.worker.adapter.screen, "licensed_runtime", return_value=gp
                ),
            ):
                flow.worker.run_child(req, out)
            return 0, False

        with (
            patch.object(flow.worker, "qualify_execution", return_value=out),
            patch.object(flow.worker, "claim_authorization"),
            patch.object(flow.worker, "supervise_process", side_effect=child),
        ):
            receipt = flow.worker.supervise_one(req, out)
        return sha, out, receipt

    def test_complete_fake_collect_nested_validation_no_logs_or_reoptimization(self):
        sha, out, receipt = self.make_attempt()
        self.assertEqual(receipt["status"], "completed")
        accounting = flow.parse_accounting(
            "123|COMPLETED|0:0|60|00:01:00|32|64G|", "123"
        )
        with (
            patch.object(flow, "status", return_value=accounting),
            patch.object(flow.worker, "supervise_one") as solve,
        ):
            result = flow.collect(self.directory)
            solve.assert_not_called()
        package = self.directory / "return/qualification_package.tar.gz"
        reviewed = flow.validate_archive(package, result["package_sha256"])
        self.assertTrue(reviewed["ready_for_independent_review"])
        self.assertFalse(reviewed["scientific_reporting_eligible"])
        self.assertEqual(reviewed["approval_sha256"], sha)
        self.assertNotIn(b"LICENSEID", gzip.decompress(package.read_bytes()))
        self.assertTrue((out / "console.private.log").exists())
        with self.assertRaises(ValueError):
            flow.validate_archive(package, "0" * 64)
        with (
            patch.object(flow, "status", return_value=accounting),
            self.assertRaises(ValueError),
        ):
            flow.collect(self.directory)  # Never overwrite an export.

    def test_failed_fake_collect_keeps_unknown_optimization_count_and_pauses(self):
        _, _, receipt = self.make_attempt(process_failure=True)
        self.assertIsNone(receipt["optimization_calls_known"])
        accounting = flow.parse_accounting("123|FAILED|2:0|60|00:01:00|32|64G|", "123")
        with patch.object(flow, "status", return_value=accounting):
            result = flow.collect(self.directory)
        value = flow.validate_archive(
            self.directory / "return/qualification_package.tar.gz",
            result["package_sha256"],
        )
        self.assertFalse(value["ready_for_independent_review"])
        self.assertTrue(value["pause_remaining_matrix"])

    def test_private_log_tampering_collect_refused_before_public_output(self):
        _, out, _ = self.make_attempt()
        (out / "console.private.log").write_bytes(b"modified")
        accounting = flow.parse_accounting(
            "123|COMPLETED|0:0|60|00:01:00|32|64G|", "123"
        )
        with (
            patch.object(flow, "status", return_value=accounting),
            self.assertRaises(ValueError),
        ):
            flow.collect(self.directory)
        self.assertFalse((self.directory / "return").exists())

    def test_command_timeout_output_and_returncode_guard(self):
        for result in (
            subprocess.CompletedProcess([], 1, b"", b"private"),
            subprocess.CompletedProcess([], 0, b"x" * (128 * 1024 + 1), b""),
        ):
            with patch.object(flow.subprocess, "run", return_value=result) as run:
                with self.assertRaises(ValueError):
                    flow.command(["sacct"])
                self.assertEqual(run.call_args.kwargs["timeout"], 20)
                self.assertFalse(run.call_args.kwargs["check"])

    def test_archive_member_allowlist_duplicate_link_trailing_and_size(self):
        def archive(entries):
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as stream:
                for name, raw, kind in entries:
                    info = tarfile.TarInfo(name)
                    info.type, info.size = kind, len(raw)
                    stream.addfile(info, io.BytesIO(raw))
            return buf.getvalue()

        entries = [(n, b"ok", tarfile.REGTYPE) for n in flow.PUBLIC]
        valid = archive(entries)
        self.assertEqual(
            set(flow.archive_payloads(valid, flow.PUBLIC, 10)), set(flow.PUBLIC)
        )
        for bad in (
            archive(entries + [entries[0]]),
            archive(entries + [("../private", b"", tarfile.REGTYPE)]),
            archive([(n, raw, tarfile.SYMTYPE) for n, raw, _ in entries]),
            gzip.compress(gzip.decompress(valid) + b"hidden"),
        ):
            with self.assertRaises(ValueError):
                flow.archive_payloads(bad, flow.PUBLIC, 10)
        with self.assertRaises(ValueError):
            flow.archive_payloads(valid, flow.PUBLIC, 1)
        with self.assertRaises(ValueError):
            flow.archive_payloads(gzip.compress(b"x" * 70000), flow.PUBLIC, 10)

    def test_batch_no_loop_gpu_exclusive_or_wait(self):
        text = (ROOT / flow.BATCH).read_text()
        self.assertIn("--time=00:10:00", text)
        self.assertIn("#SBATCH --no-requeue", text)
        self.assertIn("--hint=nomultithread", text)
        self.assertIn("--cpu-bind=verbose", text)
        self.assertNotIn("--cpu-bind=cores", text)
        for token in ("--wait", "--gres", "--exclusive", "while ", "sleep "):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
