"""Exercise the PowerShell publisher reader with Git's real ownership guard.

SPDX-License-Identifier: MIT
"""

import base64
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parents[2] / "scripts/evidence/pr66_git_read.ps1"
SHELLS = list(
    dict.fromkeys(x for x in (shutil.which("powershell"), shutil.which("pwsh")) if x)
)


@unittest.skipUnless(
    SHELLS, "PowerShell runtime unavailable; Windows CI exercises the reader"
)
class PublisherGitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.primary = self.root / "primary"
        self.linked = self.root / "linked checkout"
        self.configuration = self.root / "caller-global-config"
        self.configuration.write_text("[user]\n\tname = Fixture\n", encoding="utf-8")
        self.environment = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": str(self.configuration),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "0",
            "GIT_CONFIG_PARAMETERS": "",
            "GIT_TEST_ASSUME_DIFFERENT_OWNER": "0",
            "TEMP": str(self.root),
            "TMP": str(self.root),
            "CFL_HELPER_PATH": str(HELPER),
            "CFL_TEST_REPOSITORY": str(self.linked),
        }
        self.git("init", str(self.primary))
        self.blob = "Readable UTF-8 fixture: α\r\nsecond line\n"
        self.environment["CFL_EXPECTED_BLOB"] = base64.b64encode(
            self.blob.encode()
        ).decode("ascii")
        (self.primary / "fixture.txt").write_bytes(self.blob.encode())
        self.git("-C", str(self.primary), "add", "fixture.txt")
        self.git(
            "-C",
            str(self.primary),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        )
        self.git(
            "-C", str(self.primary), "worktree", "add", "--detach", str(self.linked)
        )
        self.environment["GIT_TEST_ASSUME_DIFFERENT_OWNER"] = "1"

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments], env=self.environment, check=True, capture_output=True
        )

    def run_reader(self, body):
        before = self.configuration.read_bytes()
        for shell in SHELLS:
            with self.subTest(shell=Path(shell).name):
                result = subprocess.run(
                    [
                        shell,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        "$ErrorActionPreference='Stop'; . $env:CFL_HELPER_PATH; "
                        + body,
                    ],
                    env=self.environment,
                    capture_output=True,
                    check=False,
                    timeout=45,
                )
                self.assertEqual(
                    result.returncode, 0, result.stderr.decode(errors="replace")
                )
                self.assertIn(b"CFL_PUBLISHER_GIT_TEST_OK", result.stdout)
                self.assertEqual(self.configuration.read_bytes(), before)
                self.assertFalse(list(self.root.glob("cfl-pr66-git-*")))

    def test_real_guard_then_exact_checkout_and_blob_with_caller_environment_unchanged(
        self,
    ):
        denied = subprocess.run(
            ["git", "-C", str(self.linked), "rev-parse", "HEAD"],
            env=self.environment,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn(b"dubious ownership", denied.stderr)
        self.run_reader("""
            $Before = $env:GIT_CONFIG_GLOBAL
            $Commit = Invoke-Pr66GitRead -Repository $env:CFL_TEST_REPOSITORY -GitArguments @('rev-parse','HEAD')
            if ($Commit.Trim() -notmatch '^[0-9a-f]{40}$') { throw 'bad commit' }
            $Blob = Invoke-Pr66GitRead -Repository $env:CFL_TEST_REPOSITORY -GitArguments @('cat-file','blob','HEAD:fixture.txt')
            $Bytes = [Text.Encoding]::UTF8.GetBytes($Blob)
            if ([Convert]::ToBase64String($Bytes) -ne $env:CFL_EXPECTED_BLOB) { throw 'blob conversion' }
            if ($Before -ne $env:GIT_CONFIG_GLOBAL) { throw 'caller environment changed' }
            Write-Output CFL_PUBLISHER_GIT_TEST_OK
        """)

    def test_git_failure_cleans_temporary_trust(self):
        self.run_reader("""
            $Failed = $false
            try { Invoke-Pr66GitRead -Repository $env:CFL_TEST_REPOSITORY -GitArguments @('cat-file','blob','HEAD:missing.txt') }
            catch { $Failed = $_.Exception.Message.Contains('Git inspection failed') }
            if (!$Failed) { throw 'missing blob not rejected' }
            Write-Output CFL_PUBLISHER_GIT_TEST_OK
        """)

    def test_mutating_git_command_is_refused(self):
        self.run_reader("""
            $Failed = $false
            try { Invoke-Pr66GitRead -Repository $env:CFL_TEST_REPOSITORY -GitArguments @('config','--global','safe.directory','*') }
            catch { $Failed = $_.Exception.Message.Contains('Only publisher Git inspection') }
            if (!$Failed) { throw 'mutation not rejected' }
            Write-Output CFL_PUBLISHER_GIT_TEST_OK
        """)

    def test_nonexistent_checkout_is_not_trusted(self):
        self.environment["CFL_TEST_REPOSITORY"] = str(self.root / "missing")
        self.run_reader("""
            $Failed = $false
            try { Invoke-Pr66GitRead -Repository $env:CFL_TEST_REPOSITORY -GitArguments @('rev-parse','HEAD') }
            catch { $Failed = $true }
            if (!$Failed) { throw 'nonexistent checkout not rejected' }
            Write-Output CFL_PUBLISHER_GIT_TEST_OK
        """)


if __name__ == "__main__":
    unittest.main()
