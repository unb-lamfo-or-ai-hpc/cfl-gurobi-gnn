"""Exercise a copied Slurm entry script, stopping before any real host/worker call."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPERATOR = ROOT / "scripts/evidence/operate_pr94_evaluation.sh"
REFERENCE = (
    ROOT / "docs/research/solver-seed-extension-v2/evaluation-entry-10fd1af.sh.txt"
)
STAGE = "/raid/vrcelestino/data/cfl-mvp2-evidence/pr94-evaluation-0123456789ab"
MARKER = "PR94_TEST_HOST_GUARD|"


class ReferenceTests(unittest.TestCase):
    def test_reference_preserves_the_actual_failed_source(self):
        raw = REFERENCE.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "9eb631ee51d90c2e95a405c5725cde51b32aaba7706a9be2ae08dfa90c46ffe9",
        )

    def test_worker_body_changes_only_the_explicit_recovery_claim_namespace(self):
        boundary = 'test "$(hostname -s)"'
        self.assertEqual(
            OPERATOR.read_text()
            .split(boundary, 1)[1]
            .replace(
                "    recover-submit)\n"
                '        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_evaluation_recovery.py" \\\n'
                '            --stage "$STAGE" ;;\n',
                "",
            ),
            REFERENCE.read_text()
            .split(boundary, 1)[1]
            .replace(
                "pr94-full-v2-evaluations.claim.json",
                "pr94-full-v2-entry-recovery-1.claim.json",
            ),
        )


@unittest.skipUnless(os.name == "posix", "Linux/Bash batch entry regression")
class CopiedBatchEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = shutil.which("bash")
        if cls.bash is None:
            raise RuntimeError("POSIX batch regression requires Bash")

    def probe(self, text, command="batch", stage=STAGE, normal_location=False):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = (
                folder / "real-stage/source/scripts/evidence/operator.sh"
                if normal_location
                else folder / "spool/job123/slurm_script"
            )
            path.parent.mkdir(parents=True)
            path.write_text(text, encoding="utf-8")
            env = os.environ.copy()
            env.pop("PR94_EVALUATION_STAGE", None)
            env.pop("BASH_ENV", None)
            env.pop("ENV", None)
            if stage is not None:
                env["PR94_EVALUATION_STAGE"] = stage
            # The guard reports routing and deliberately fails. Neither the
            # real hostname nor Python, Slurm, solver or worker can be reached.
            entry = (
                'hostname() { printf "PR94_TEST_HOST_GUARD|%s|%s\\n" '
                '"${STAGE:-unset}" "${SOURCE:-unset}" >&2; return 99; }; '
                'export -f hostname; exec bash "$@"'
            )
            return subprocess.run(
                [self.bash, "-c", entry, "probe", str(path), command, "0"],
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

    def test_actual_old_script_reproduces_stage_failure_when_spooled(self):
        result = self.probe(REFERENCE.read_text())
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("PR94_EVALUATION_INVALID_STAGE", result.stderr)
        self.assertNotIn(MARKER, result.stderr)

    def test_fixed_spooled_script_resolves_explicit_stage_and_source(self):
        result = self.probe(OPERATOR.read_text())
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(MARKER + STAGE + "|" + STAGE + "/source", result.stderr)
        self.assertNotIn("PR94_EVALUATION_INVALID_STAGE", result.stderr)

    def test_batch_cannot_fall_back_to_spool_when_stage_is_absent(self):
        result = self.probe(OPERATOR.read_text(), stage=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PR94_EVALUATION_STAGE", result.stderr)
        self.assertNotIn(MARKER, result.stderr)

    def test_batch_rejects_outside_stage_before_any_host_or_worker_call(self):
        for stage in ("/home/example", STAGE + "/../another-stage"):
            with self.subTest(stage=stage):
                result = self.probe(OPERATOR.read_text(), stage=stage)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("PR94_EVALUATION_INVALID_STAGE", result.stderr)
                self.assertNotIn(MARKER, result.stderr)

    def test_manual_status_cannot_be_redirected_by_batch_stage_environment(self):
        result = self.probe(
            OPERATOR.read_text(), command="status", normal_location=True
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("PR94_EVALUATION_INVALID_STAGE", result.stderr)
        self.assertNotIn(MARKER, result.stderr)


if __name__ == "__main__":
    unittest.main()
