"""Exercise the pasted exporter with synthetic receipts; never access HPC."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

HERE = Path(__file__).resolve().parent
SHELL = (HERE / "pr89-delta-20261101.sh").read_text(encoding="utf-8")
CODE = SHELL.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
HEAD = "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5"
TREE = "69ed16b9635c493161bf620727c9e0a0aee7a7dc"
CONTROL_HASHES = {
    "plan.json": "48fca37e2cc698f4d35e4850fdd48d8115b36d7f64b97438ded3b9e17dea3dd1",
    "preflight.json": "b31d5ac2e80a3ae76c3904e197851ce8b42c1bbc92a955212dc277c4cbb252c0",
    "authorization.json": "0fc7aee5c53639ca05edfb46ba8cec826f843dfe2597ebea780d4bcdbe68b47e",
}


class DeltaExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        parent = Path(self.temporary.name)
        self.stage = parent / "cpu12h-9ab7823c6886"
        self.stage.mkdir()
        self.output = self.stage / "partial-results-delta-20261101-jobs3725-3728.zip"
        plan = {"source_commit": HEAD, "cells": [{"fixture": i} for i in range(60)]}
        self.raw = {
            "plan.json": json.dumps(plan).encode(),
            "preflight.json": b"{}",
            "authorization.json": b'{"explicit_user_authorization":true}',
        }
        self.code = CODE.replace('Path("/raid")', "Path(" + repr(str(parent)) + ")")
        for name, raw in self.raw.items():
            (self.stage / name).write_bytes(raw)
            self.code = self.code.replace(CONTROL_HASHES[name], hashlib.sha256(raw).hexdigest())
        # No directories exist for the fifty previously received jobs or running jobs.
        for i in range(50, 54):
            run = self.stage / "runs" / str(i)
            run.mkdir(parents=True)
            sub = {"index": i, "job_id": str(3675+i),
                   "plan_sha256": hashlib.sha256(self.raw["plan.json"]).hexdigest()}
            (run / "submission.json").write_text(json.dumps(sub))
            for name in ("child.json", "supervision.json", "checked.json", "costs.json"):
                (run / name).write_text("{}")
            (run / "private.log").write_text("MUST NOT EXPORT")
        self.calls = []

    def run_export(self, states=None, duplicate=False, hostname="dgx-dasci"):
        states = states or {}
        def command(args, **kwargs):
            self.calls.append(args)
            if args[0] == "git":
                return (TREE if args[-1] == "HEAD^{tree}" else HEAD) + "\n"
            self.assertEqual(args[0], "sacct")
            self.assertEqual(args[args.index("-j")+1], "3725,3726,3727,3728")
            result = ""
            for job in range(3725, 3729):
                state = states.get(str(job), "COMPLETED")
                result += f"{job}|{state}|0:0|123|00:01|4|64G||a|b\n"
                result += f"{job}.batch|{state}|0:0|123|00:01|4||123K|a|b\n"
            if duplicate:
                result += "3725|COMPLETED|0:0|123|00:01|4|64G||a|b\n"
            return result
        with mock.patch("socket.gethostname", return_value=hostname), \
             mock.patch("getpass.getuser", return_value="vrcelestino"), \
             mock.patch.dict("os.environ", {"CONDA_DEFAULT_ENV": "tfm_env"}), \
             mock.patch.object(sys, "argv", ["-", str(self.stage)]), \
             mock.patch("subprocess.check_output", side_effect=command), \
             contextlib.redirect_stdout(io.StringIO()):
            exec(compile(self.code, "delta_exporter", "exec"), {})

    def manifest(self):
        with zipfile.ZipFile(self.output) as archive:
            return json.loads(archive.read("partial-manifest.json"))

    def test_exact_four_jobs_and_all_member_hashes(self):
        self.run_export()
        with zipfile.ZipFile(self.output) as archive:
            manifest = self.manifest()
            self.assertEqual(manifest["collected_job_ids"], ["3725", "3726", "3727", "3728"])
            self.assertFalse(manifest["scientific_reporting_eligible"])
            self.assertFalse(manifest["final_campaign_return"])
            self.assertEqual(manifest["terminal_jobs"], 4)
            self.assertEqual({n.split("/")[1] for n in archive.namelist() if n.startswith("runs/")},
                             {"50", "51", "52", "53"})
            self.assertFalse(any("private.log" in n for n in archive.namelist()))
            for name, digest in manifest["sha256"].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)

    def test_running_job_prevents_any_archive(self):
        with self.assertRaisesRegex(SystemExit, "NOT_TERMINAL"):
            self.run_export({"3728": "RUNNING"})
        self.assertFalse(self.output.exists())

    def test_other_cluster_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "HOST_MISMATCH"):
            self.run_export(hostname="service0")
        self.assertFalse(self.output.exists())

    def test_duplicate_accounting_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "AMBIGUOUS_ACCOUNTING"):
            self.run_export(duplicate=True)
        self.assertFalse(self.output.exists())

    def test_changed_frozen_control_is_rejected(self):
        (self.stage / "authorization.json").write_text("{}")
        with self.assertRaisesRegex(SystemExit, "HASH_MISMATCH"):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_wrong_submission_identity_is_rejected(self):
        sub = self.stage / "runs/50/submission.json"
        value = json.loads(sub.read_text())
        value["job_id"] = "9999"
        sub.write_text(json.dumps(value))
        with self.assertRaisesRegex(SystemExit, "SUBMISSION_BINDING"):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_missing_receipt_is_disclosed_without_repair(self):
        (self.stage / "runs/51/checked.json").unlink()
        self.run_export()
        self.assertEqual(self.manifest()["missing_files"],
                         [{"job_id": "3726", "path": "runs/51/checked.json"}])

    def test_failed_terminal_is_preserved_not_retried(self):
        self.run_export({"3728": "FAILED"})
        with zipfile.ZipFile(self.output) as archive:
            jobs = json.loads(archive.read("scheduler-snapshot.json"))["jobs"]
            self.assertEqual(jobs[-1]["state"], "FAILED")
        self.assertEqual({call[0] for call in self.calls}, {"git", "sacct"})

    def test_existing_archive_is_not_overwritten(self):
        self.run_export()
        old = self.output.read_bytes()
        with self.assertRaisesRegex(SystemExit, "OUTPUT_ALREADY_EXISTS"):
            self.run_export()
        self.assertEqual(self.output.read_bytes(), old)


if __name__ == "__main__":
    unittest.main(verbosity=2)
