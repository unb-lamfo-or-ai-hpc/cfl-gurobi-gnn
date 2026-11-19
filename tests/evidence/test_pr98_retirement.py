"""Retired CLI must stop before admission, filesystem access or queue operations."""

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "retired_campaign", SCRIPTS / "mvp2_concurrent_mip.py"
)
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


class RetiredCampaignTests(unittest.TestCase):
    def test_mutating_commands_stop_before_admission(self):
        commands = (
            ["freeze", "/not-accessed", "/not-read"],
            ["queue-held", "/not-accessed", "hash", "account", "partition"],
            ["release", "/not-accessed", "hash"],
            ["worker", "/not-accessed", "hash", "1"],
            ["cell", "/not-accessed", "hash", "1", "--method", "M0"],
        )
        for arguments in commands:
            with self.subTest(command=arguments[0]):
                with (
                    patch.object(sys, "argv", ["campaign", *arguments]),
                    patch.object(CAMPAIGN, "site_stage") as admission,
                    contextlib.redirect_stderr(io.StringIO()) as message,
                    self.assertRaises(SystemExit) as stopped,
                ):
                    CAMPAIGN.main()
                self.assertEqual(stopped.exception.code, 2)
                self.assertIn("PR98_CAMPAIGN_RETIRED", message.getvalue())
                admission.assert_not_called()

    def test_archived_matrix_remains_inspectable(self):
        with (
            patch.object(sys, "argv", ["campaign", "matrix"]),
            patch.object(CAMPAIGN, "site_stage") as admission,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            CAMPAIGN.main()
        self.assertIn('"solves": 990', output.getvalue())
        admission.assert_not_called()


if __name__ == "__main__":
    unittest.main()
