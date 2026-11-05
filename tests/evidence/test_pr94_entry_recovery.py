"""Synthetic recovery admission: original evidence and scientific policy stay fixed."""

import ast
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import pr94_evaluation_recovery as recovery  # noqa: E402


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write(path, value):
    raw = encoded(value)
    with path.open("xb") as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


class CIGateTests(unittest.TestCase):
    def setUp(self):
        template = (
            ROOT / "docs/research/solver-seed-extension-v2/recovery-launch.template.sh"
        ).read_text()
        code = template.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        tree = ast.parse(code)
        namespace = {}
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "verify_ci"
        )
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), "ci-gate", "exec"),
            namespace,
        )
        self.verify = namespace["verify_ci"]
        self.run = {
            "id": 123,
            "head_sha": "a" * 40,
            "name": "Public evidence integrity",
            "repository": {"full_name": "unb-lamfo-or-ai-hpc/cfl-gurobi-gnn"},
            "status": "completed",
            "conclusion": "success",
        }
        names = [
            "matched-step",
            *[
                f"verify ({os}, {v})"
                for os in ("ubuntu-latest", "windows-latest")
                for v in ("3.10", "3.12")
            ],
        ]
        self.jobs = {
            "jobs": [
                {
                    "name": name,
                    "head_sha": "a" * 40,
                    "status": "completed",
                    "conclusion": "success",
                }
                for name in names
            ]
        }

    def test_exact_source_and_all_five_successes_are_required(self):
        self.assertTrue(self.verify(self.run, self.jobs, "a" * 40, 123))
        for key, value in (
            ("head_sha", "b" * 40),
            ("id", 124),
            ("name", "unrelated"),
            ("repository", {"full_name": "other/repo"}),
        ):
            run = {**self.run, key: value}
            with self.assertRaises(SystemExit):
                self.verify(run, self.jobs, "a" * 40, 123)

    def test_incomplete_CI_never_releases_and_failed_CI_aborts(self):
        self.assertFalse(
            self.verify({**self.run, "status": "in_progress"}, None, "a" * 40, 123)
        )
        with self.assertRaises(SystemExit):
            self.verify({**self.run, "conclusion": "failure"}, None, "a" * 40, 123)

    def test_skipped_missing_or_wrong_source_matrix_job_is_not_success(self):
        for what in ("skipped", "missing", "source"):
            jobs = copy.deepcopy(self.jobs)
            if what == "skipped":
                jobs["jobs"][0]["conclusion"] = "skipped"
            elif what == "missing":
                jobs["jobs"].pop()
            else:
                jobs["jobs"][0]["head_sha"] = "b" * 40
            with self.assertRaises(SystemExit):
                self.verify(self.run, jobs, "a" * 40, 123)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.parent = self.folder / "original"
        (self.parent / "claims").mkdir(parents=True)
        (self.parent / "run").mkdir()
        self.raw = (
            (ROOT / "docs/evidence/pr94/evaluation-attempt-10fd1af/accepted-plan.json")
            .read_bytes()
            .replace(b"\r\n", b"\n")
        )
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), recovery.PARENT_PLAN)
        self.plan = json.loads(self.raw)
        self.rows = [
            {
                "JobIDRaw": job,
                "User": "vrcelestino",
                "State": "FAILED" if i < 4 else "CANCELLED",
                "ExitCode": "2:0" if i < 4 else "0:0",
                "ElapsedRaw": "0",
            }
            for i, job in enumerate(recovery.IDS)
        ]
        claim = {
            "plan_sha256": recovery.PARENT_PLAN,
            "source_commit": recovery.PARENT_SOURCE,
            "maximum_evaluations": 144,
            "maximum_submissions": 48,
            "concurrency_ceiling": 4,
            "automatic_retry": False,
            "explicit_author_CLI": True,
        }
        self.closure = {
            "accounting": self.rows,
            "all_48_terminal": True,
            "failure_before_python_worker": True,
            "durable_optimize_intents": [],
            "run_file_names": [],
            "source_commit": recovery.PARENT_SOURCE,
            "plan_sha256": recovery.PARENT_PLAN,
            "entry_sha256": recovery.ENTRY_SHA,
        }
        self.members = {
            "original-plan.private.json": self.raw,
            "original-submission.json": encoded(
                {
                    "plan_sha256": recovery.PARENT_PLAN,
                    "jobs": [{"job_id": job} for job in recovery.IDS],
                }
            ),
            "original-approval.json": encoded(claim),
            "original-global-claim.json": encoded(claim),
            "closure-review.json": encoded(self.closure),
        }
        for job in recovery.IDS[:4]:
            for ext in ("err", "out"):
                value = b"PR94_EVALUATION_INVALID_STAGE\n" if ext == "err" else b""
                self.members[f"terminal-logs/evaluation-{job}.private.{ext}"] = value
                (self.parent / f"evaluation-{job}.private.{ext}").write_bytes(value)
        for name, target in (
            ("original-plan.private.json", "plan.json"),
            ("original-submission.json", "submission.json"),
            ("original-approval.json", "approval.json"),
        ):
            (self.parent / target).write_bytes(self.members[name])
        self.original_claim = self.folder / "original-global.claim.json"
        self.original_claim.write_bytes(encoded(claim))
        entry = self.parent / "source/scripts/evidence/operate_pr94_evaluation.sh"
        entry.parent.mkdir(parents=True)
        entry.write_bytes(
            (
                ROOT
                / "docs/research/solver-seed-extension-v2/evaluation-entry-10fd1af.sh.txt"
            )
            .read_bytes()
            .replace(b"\r\n", b"\n")
        )
        self.archive = self.folder / "receipt.zip"
        with zipfile.ZipFile(self.archive, "x") as z:
            for name, raw in self.members.items():
                z.writestr(name, raw)
            z.writestr(
                "manifest.json",
                encoded(
                    {
                        "sha256": {
                            name: hashlib.sha256(raw).hexdigest()
                            for name, raw in self.members.items()
                        }
                    }
                ),
            )
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in {
            "PARENT": self.parent,
            "ORIGINAL_CLAIM": self.original_claim,
            "CLAIM": self.folder / "recovery.claim.json",
            "ARCHIVE": self.archive,
            "ARCHIVE_SHA": hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            "CLOSURE_SHA": hashlib.sha256(
                self.members["closure-review.json"]
            ).hexdigest(),
        }.items():
            self.stack.enter_context(patch.object(recovery, name, value))
        self.calls = []

    def command(self, args):
        self.calls.append(args)
        if args[0] == "git":
            return recovery.PARENT_SOURCE
        self.assertEqual(args[0], "sacct")
        return "\n".join(
            "|".join(
                row[k] for k in ("JobIDRaw", "User", "State", "ExitCode", "ElapsedRaw")
            )
            for row in self.rows
        )

    def new_plan(self):
        plan = copy.deepcopy(self.plan)
        plan["source"]["commit"] = "a" * 40
        for path in (
            "scripts/evidence/operate_pr94_evaluation.sh",
            "scripts/evidence/pr94_evaluation_workflow.py",
            "scripts/evidence/pr94_evaluation_recovery.py",
        ):
            plan["source"]["sha256_lf"][path] = "b" * 64
        plan["site"]["query_utc"] = "a newer query"
        plan["storage"]["workspace_bytes"] += 1
        plan["recovery_record"] = recovery.record()
        plan["recovery_validation"] = recovery.validate_current(self.command)
        return plan

    def test_closed_parent_and_exact_original_claim_are_preserved(self):
        before = self.original_claim.read_bytes()
        report = recovery.validate_current(self.command)
        self.assertEqual(report["FAILED"], 4)
        self.assertEqual(report["CANCELLED"], 44)
        self.assertEqual(before, self.original_claim.read_bytes())
        self.assertEqual([c[0] for c in self.calls], ["git", "sacct"])
        self.assertFalse(recovery.CLAIM.exists())

    def test_changed_archive_is_not_an_automatic_replacement(self):
        with self.archive.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "archive_sha256"):
            recovery.record()

    def test_current_original_claim_cannot_be_removed_or_rewritten(self):
        self.original_claim.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "original_bytes_changed"):
            recovery.validate_current(self.command)

    def test_new_optimizer_intent_or_worker_file_stops_recovery(self):
        for folder, name in (("claims", "cell.optimize.json"), ("run", "child.json")):
            p = self.parent / folder / name
            p.write_text("{}")
            with self.assertRaisesRegex(ValueError, "unexpected_(intent|worker)"):
                recovery.validate_current(self.command)
            p.unlink()

    def test_current_head_log_must_still_be_the_same_failure(self):
        (self.parent / "evaluation-3785.private.err").write_text("different")
        with self.assertRaisesRegex(ValueError, "current_log"):
            recovery.validate_current(self.command)

    def test_running_foreign_elapsed_or_duplicate_parent_is_rejected(self):
        for key, value in (
            ("State", "RUNNING"),
            ("User", "other"),
            ("ElapsedRaw", "1"),
            ("ExitCode", "0:0"),
        ):
            with self.subTest(key=key):
                rows = copy.deepcopy(self.rows)
                rows[0][key] = value
                with self.assertRaises(ValueError):
                    recovery.closed_rows(rows)
        rows = copy.deepcopy(self.rows)
        rows[-1] = rows[0]
        with self.assertRaisesRegex(ValueError, "accounting_ids"):
            recovery.closed_rows(rows)

    def test_equivalence_accepts_only_the_authorized_technical_changes(self):
        report = recovery.equivalence(self.new_plan())
        self.assertTrue(report["same_scientific_and_resource_fields"])
        self.assertFalse(report["automatic_retry"])
        self.assertEqual(report["parent_plan_sha256"], recovery.PARENT_PLAN)

    def test_boolean_cannot_masquerade_as_a_numeric_resource(self):
        plan = self.new_plan()
        plan["physical_cores_each"] = True
        with self.assertRaisesRegex(ValueError, "scientific_or_resource_change"):
            recovery.equivalence(plan)

    def test_any_scientific_resource_identity_or_order_change_is_rejected(self):
        for key, value in (
            ("maximum_evaluations", 145),
            ("concurrency_ceiling", 8),
            ("memory_GiB_each", 128),
            ("wall_seconds_each", 1),
            ("private_inputs_sha256", "wrong"),
            ("cells_csv_sha256", "wrong"),
            ("accepted_guidance_sha256", "wrong"),
        ):
            with self.subTest(key=key):
                plan = self.new_plan()
                plan[key] = value
                with self.assertRaisesRegex(
                    ValueError, "scientific_or_resource_change"
                ):
                    recovery.equivalence(plan)
        for key, value in (("Method", 0), ("IntFeasTol", 1e-9), ("TimeLimit", 7200)):
            plan = self.new_plan()
            plan["baseline_parameters"][key] = value
            with self.assertRaises(ValueError):
                recovery.equivalence(plan)
        plan = self.new_plan()
        plan["groups"][0]["methods"].reverse()
        with self.assertRaises(ValueError):
            recovery.equivalence(plan)

    def test_unreviewed_source_or_removed_original_file_stops(self):
        for key in ("src/cfl_gnn/unreviewed.py", "configs/experiments/new.json"):
            plan = self.new_plan()
            plan["source"]["sha256_lf"][key] = "f" * 64
            with self.assertRaisesRegex(ValueError, "unreviewed_source_change"):
                recovery.equivalence(plan)
        plan = self.new_plan()
        plan["source"]["sha256_lf"].pop(next(iter(self.plan["source"]["sha256_lf"])))
        with self.assertRaises(ValueError):
            recovery.equivalence(plan)

    def test_site_storage_extra_keys_and_recovery_record_cannot_drift(self):
        for what in ("site", "storage", "extra", "record"):
            plan = self.new_plan()
            if what == "site":
                plan["site"]["configured_memory_MiB"] += 1
            elif what == "storage":
                plan["storage"]["allowance_GiB"] += 1
            elif what == "extra":
                plan["unexpected"] = True
            else:
                plan["recovery_record"]["automatic_retry"] = True
            with self.assertRaises(ValueError):
                recovery.equivalence(plan)

    def test_durable_review_is_bound_to_exact_plan_and_cannot_overwrite(self):
        stage = self.folder / "replacement"
        stage.mkdir()
        plan = self.new_plan()
        write(stage / "plan.json", plan)
        with self.assertRaises(ValueError):
            recovery.require_review(stage, plan)
        report = recovery.review(stage, plan, write, encoded)
        recovery.require_review(stage, plan)
        self.assertEqual(
            report["plan_sha256"],
            hashlib.sha256((stage / "plan.json").read_bytes()).hexdigest(),
        )
        with self.assertRaises(FileExistsError):
            recovery.review(stage, plan, write, encoded)
        report["scientific_reporting_eligible"] = True
        (stage / "recovery-plan-review.json").write_bytes(encoded(report))
        with self.assertRaisesRegex(ValueError, "review_missing_or_changed"):
            recovery.require_review(stage, plan)

    def test_single_entry_reviews_exact_plan_before_any_submission(self):
        import pr94_evaluation_workflow as flow

        stage = self.folder / "replacement"
        stage.mkdir()
        plan = self.new_plan()
        write(stage / "plan.json", plan)

        def submit(actual_stage, actual_sha):
            self.assertEqual(actual_stage, stage)
            recovery.require_review(stage, plan)
            self.assertEqual(
                actual_sha, recovery.sha((stage / "plan.json").read_bytes())
            )
            return {"synthetic": True}

        with (
            patch.object(sys, "argv", ["recovery", "--stage", str(stage)]),
            patch.object(flow, "stage_path", return_value=stage),
            patch.object(flow, "load", return_value=plan),
            patch.object(flow, "submit", side_effect=submit) as call,
            redirect_stdout(io.StringIO()),
        ):
            recovery.main()
        call.assert_called_once()
        self.assertFalse(recovery.CLAIM.exists())
        self.assertEqual(
            self.original_claim.read_bytes(), self.members["original-global-claim.json"]
        )

    def test_complete_submission_is_status_only_and_partial_claim_never_retries(self):
        import pr94_evaluation_workflow as flow

        stage = self.folder / "replacement"
        stage.mkdir()
        plan = self.new_plan()
        write(stage / "submission.json", {})
        with (
            patch.object(sys, "argv", ["recovery", "--stage", str(stage)]),
            patch.object(flow, "stage_path", return_value=stage),
            patch.object(flow, "load", return_value=plan),
            patch.object(flow, "submit") as submit,
            patch.object(
                flow, "accounting", return_value={"synthetic": True}
            ) as status,
            redirect_stdout(io.StringIO()),
        ):
            recovery.main()
            status.assert_called_once_with(stage)
            submit.assert_not_called()
            (stage / "submission.json").unlink()
            recovery.CLAIM.write_text("{}")
            with self.assertRaisesRegex(ValueError, "claim_exists_preserve"):
                recovery.main()
            submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
