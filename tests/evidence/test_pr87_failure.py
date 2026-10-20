"""Regression of terminal-failure review and Slurm-copy entry, no real scheduler."""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import pr87_contract as c  # noqa: E402
import pr87_workflow as w  # noqa: E402
import review_pr87_job3671 as failure  # noqa: E402


class FailureReview(unittest.TestCase):
    def receipt(self):
        return json.loads((failure.DEST / "public_return.json").read_bytes())

    def test_failed_transfer_is_intact_but_not_qualified_training(self):
        value = w.inspect_return(self.receipt())
        self.assertTrue(value["transfer_and_envelope_verified"])
        self.assertFalse(value["ready_for_independent_review"])
        self.assertFalse(value["remaining_dispatch_admitted"])
        self.assertEqual(value["result_reports_present"], 0)
        self.assertEqual(
            [r["state"] for r in value["job_states"]], ["FAILED", "CANCELLED"]
        )
        self.assertEqual(
            value["historical_training_started"], "not_established_by_missing_reports"
        )

    def test_none_result_raises_domain_error_not_typeerror(self):
        with self.assertRaisesRegex(ValueError, "training_result_absent"):
            c.validate_result(None, {}, 0)
        with self.assertRaises(ValueError):
            w.review(self.receipt())

    def test_failed_return_cannot_bypass_identity_or_promote_results(self):
        for key, changed in (
            ("private_paths_included", True),
            ("ready_for_independent_review", True),
        ):
            value = copy.deepcopy(self.receipt())
            value[key] = changed
            with self.assertRaises(ValueError):
                w.inspect_return(value)
        value = self.receipt()
        value["accounting"]["jobs"][1]["job_id"] = "3671"
        with self.assertRaises(ValueError):
            w.inspect_return(value)
        value = self.receipt()
        value["approval"]["budget"] = {}
        with self.assertRaises(ValueError):
            w.inspect_return(value)

    def test_historical_bytes_and_deterministic_review(self):
        raw = (failure.DEST / "public_return.json").read_bytes()
        self.assertEqual(c.sha(raw), failure.SHA)
        for name, content in failure.products(raw).items():
            self.assertEqual((failure.DEST / name).read_bytes(), content)

    @unittest.skipIf(
        sys.platform == "win32", "Real Bash spool simulation runs in Linux CI"
    )
    def test_batch_copy_dispatches_to_stage_not_spool(self):
        bash = shutil.which("bash")
        self.assertIsNotNone(bash)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            spool = directory / "var/spool/slurmd/job3671"
            spool.mkdir(parents=True)
            script = spool / "slurm_script"
            shutil.copyfile(ROOT / "scripts/evidence/operate_pr87_training.sh", script)
            mocked = directory / "mock-bin"
            mocked.mkdir()
            for name, contents in {
                "hostname": "#!/bin/sh\nprintf '%s\\n' dgx-dasci\n",
                "python3": '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$PR87_TEST_CAPTURE"\n',
            }.items():
                path = mocked / name
                path.write_text(contents, encoding="utf-8")
                path.chmod(0o700)
            capture = directory / "invocation.txt"
            env = dict(
                os.environ,
                PATH=str(mocked) + os.pathsep + os.environ["PATH"],
                CONDA_DEFAULT_ENV="tfm_env",
                PR87_TEST_CAPTURE=str(capture),
            )
            stage = "/raid/vrcelestino/data/cfl-mvp2-evidence/pr87/training-" + "a" * 12
            result = subprocess.run(
                [bash, str(script), "batch", stage, "0"],
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            args = capture.read_text().splitlines()
            self.assertEqual(
                args,
                [
                    "-B",
                    stage + "/source/scripts/evidence/pr87_workflow.py",
                    "run",
                    "--stage",
                    stage,
                    "--index",
                    "0",
                ],
            )
            capture.unlink()
            bad = subprocess.run(
                [bash, str(script), "batch", "/tmp/not-an-approved-stage", "0"],
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse(capture.exists())


if __name__ == "__main__":
    unittest.main()
