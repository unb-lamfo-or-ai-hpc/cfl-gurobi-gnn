"""Byte-preservation regression tests for rebase checkout transitions.

SPDX-License-Identifier: MIT
"""

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "evidence"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "verify_public_checkout", SCRIPTS / "verify_public_checkout.py"
)
CHECKOUT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECKOUT)


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / CHECKOUT.PREFIX
        self.output.mkdir(parents=True)
        self.blobs = {name: b'{\n  "value": 1\n}\n' for name in CHECKOUT.SUMMARIES}
        self.blobs["SHA256SUMS.txt"] = "".join(
            hashlib.sha256(self.blobs[name]).hexdigest() + "  " + name + "\n"
            for name in sorted(CHECKOUT.SUMMARIES)
        ).encode()
        for name, payload in self.blobs.items():
            (self.output / name).write_bytes(payload)

    def verify(self, repair=False):
        return CHECKOUT.verify_checkout(self.root, repair, self.blobs.__getitem__)

    def test_canonical_checkout_needs_no_repair(self):
        self.assertEqual(self.verify(), 0)

    def test_check_only_preserves_crlf_drift(self):
        path = self.output / "closure_verification.json"
        drift = self.blobs[path.name].replace(b"\n", b"\r\n")
        path.write_bytes(drift)
        with self.assertRaisesRegex(ValueError, "explicit repair"):
            self.verify()
        self.assertEqual(path.read_bytes(), drift)

    def test_repair_restores_all_bytes_without_changing_hashes(self):
        for name, blob in self.blobs.items():
            (self.output / name).write_bytes(blob.replace(b"\n", b"\r\n"))
        self.assertEqual(self.verify(repair=True), 5)
        for name, blob in self.blobs.items():
            self.assertEqual((self.output / name).read_bytes(), blob)
        self.assertEqual(self.verify(repair=True), 0)

    def test_content_change_blocks_all_repairs(self):
        first = self.output / "closure_verification.json"
        drift = self.blobs[first.name].replace(b"\n", b"\r\n")
        first.write_bytes(drift)
        changed = self.output / "parent_coverage.json"
        changed.write_bytes(b'{"value": 2}\n')
        with self.assertRaisesRegex(ValueError, "Non-EOL"):
            self.verify(repair=True)
        self.assertEqual(first.read_bytes(), drift)
        self.assertEqual(changed.read_bytes(), b'{"value": 2}\n')

    def test_wrong_committed_hash_is_not_recomputed(self):
        name = "closure_verification.json"
        self.blobs[name] = b'{"value": 3}\n'
        with self.assertRaisesRegex(ValueError, "declared hash"):
            self.verify(repair=True)

    def test_missing_file_is_not_silently_recreated(self):
        (self.output / "parent_coverage.json").unlink()
        with self.assertRaisesRegex(ValueError, "existing regular file"):
            self.verify(repair=True)


class GitReaderTests(unittest.TestCase):
    ISOLATED = {
        "GIT_CONFIG_COUNT": "0",
        "GIT_CONFIG_PARAMETERS": "",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
    }

    def test_real_git_ownership_guard_with_no_global_trust(self):
        repository = SCRIPTS.parents[1]
        with patch.dict(os.environ, self.ISOLATED):
            untrusted = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "--verify", "HEAD"],
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(untrusted.returncode, 0)
            self.assertIn(b"dubious ownership", untrusted.stderr)
            self.assertEqual(CHECKOUT.verify_checkout(repository), 0)

    def test_every_git_call_trusts_only_the_exact_resolved_checkout(self):
        configurations = []

        def read_command(command, *, env):
            configuration = Path(env["GIT_CONFIG_GLOBAL"])
            configurations.append(configuration)
            expected = (
                "[safe]\n\tdirectory =\n\tdirectory = "
                + CHECKOUT.json.dumps(
                    repository.resolve().as_posix(), ensure_ascii=False
                )
                + "\n"
            )
            self.assertEqual(configuration.read_text(encoding="utf-8"), expected)
            self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(env["GIT_CONFIG_COUNT"], "0")
            self.assertEqual(env["GIT_CONFIG_PARAMETERS"], "")
            return b"1234567890\n" if len(configurations) == 1 else b"\x00\xffraw\r\n"

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(
                CHECKOUT.subprocess,
                "check_output",
                side_effect=read_command,
            ) as read,
        ):
            repository = Path(directory)
            reader = CHECKOUT.git_reader(repository)
            self.assertEqual(reader("closure_verification.json"), b"\x00\xffraw\r\n")
            expected = [
                "git",
                "-c",
                "safe.directory=" + repository.resolve().as_posix(),
                "-C",
                str(repository.resolve()),
            ]
            for call in read.call_args_list:
                self.assertEqual(call.args[0][:5], expected)
                self.assertNotIn("--global", call.args[0])
                self.assertNotIn("safe.directory=*", call.args[0])
            self.assertEqual(
                read.call_args_list[1].args[0][5:],
                ["show", "1234567890:" + CHECKOUT.PREFIX + "closure_verification.json"],
            )
            self.assertTrue(all(not path.exists() for path in configurations))

    def test_legacy_command_line_trust_ignored_still_verifies_real_blobs(self):
        original = subprocess.check_output

        def ignore_command_line_trust(command, **kwargs):
            # Emulate older Git's safe.directory scope, not its ownership check.
            self.assertEqual(command[1], "-c")
            return original([command[0]] + command[3:], **kwargs)

        with (
            patch.dict(os.environ, self.ISOLATED),
            patch.object(
                CHECKOUT.subprocess, "check_output", ignore_command_line_trust
            ),
        ):
            self.assertEqual(CHECKOUT.verify_checkout(SCRIPTS.parents[1]), 0)

    def test_temporary_config_cleanup_on_git_failure(self):
        configurations = []

        def fail(command, *, env):
            configurations.append(Path(env["GIT_CONFIG_GLOBAL"]))
            raise subprocess.CalledProcessError(128, command)

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(CHECKOUT.subprocess, "check_output", side_effect=fail),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            CHECKOUT.git_reader(Path(directory))
        self.assertEqual(len(configurations), 1)
        self.assertFalse(configurations[0].parent.exists())

    def test_subprocess_trust_does_not_change_caller_environment(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, self.ISOLATED),
            patch.object(
                CHECKOUT.subprocess, "check_output", return_value=b"1234567890\n"
            ),
        ):
            before = dict(os.environ)
            CHECKOUT.git_reader(Path(directory))
            self.assertEqual(dict(os.environ), before)

    def test_linked_checkout_trust_does_not_authorize_common_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / "primary"
            linked = root / "linked checkout"
            with patch.dict(os.environ, {"GIT_TEST_ASSUME_DIFFERENT_OWNER": "0"}):
                subprocess.run(
                    ["git", "init", str(primary)], check=True, capture_output=True
                )
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(primary),
                        "-c",
                        "user.name=Fixture",
                        "-c",
                        "user.email=fixture@example.invalid",
                        "commit",
                        "--allow-empty",
                        "-m",
                        "fixture",
                    ],
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(primary),
                        "worktree",
                        "add",
                        "--detach",
                        str(linked),
                    ],
                    check=True,
                    capture_output=True,
                )
            original = subprocess.check_output

            def verify_scope(command, *, env):
                result = subprocess.run(
                    ["git", "-C", str(primary), "rev-parse", "HEAD"],
                    env=env,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"dubious ownership", result.stderr)
                return original([command[0]] + command[3:], env=env)

            with (
                patch.dict(os.environ, self.ISOLATED),
                patch.object(
                    CHECKOUT.subprocess, "check_output", side_effect=verify_scope
                ),
            ):
                CHECKOUT.git_reader(linked)

    def test_nonexistent_checkout_is_not_silently_trusted(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(CHECKOUT.subprocess, "check_output") as read,
        ):
            with self.assertRaises(FileNotFoundError):
                CHECKOUT.git_reader(Path(directory) / "missing")
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
