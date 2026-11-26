"""Qualification release gates are tested without a license or native solve."""
# ruff: noqa: E402 -- repository-source bootstrap

import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cfl_gnn.mvp3.contract import ContractError, canonical_bytes
from cfl_gnn.mvp3.journal import file_sha256
from cfl_gnn.mvp3.qualification import (
    CELLS,
    TINY_LP,
    check_source,
    main,
    qualify,
    worker,
)


class QualificationGuardTests(unittest.TestCase):
    def test_source_requires_exact_head_and_clean_tree(self):
        for head, dirty in (
            ("b" * 40, ""),
            ("a" * 40, " M source.py"),
            ("a" * 40, "?? untracked.py"),
        ):
            with (
                patch(
                    "cfl_gnn.mvp3.qualification.subprocess.check_output",
                    side_effect=[head, dirty],
                ),
                self.assertRaises(ContractError),
            ):
                check_source("a" * 40)
        with patch(
            "cfl_gnn.mvp3.qualification.subprocess.check_output",
            side_effect=["a" * 40, ""],
        ):
            check_source("a" * 40)

    def test_missing_cli_authority_has_no_output_or_native_import(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("cfl_gnn.mvp3.qualification.check_source"),
        ):
            output = Path(temporary) / "private"
            with self.assertRaises(ContractError):
                qualify(output, "a" * 40, "")
            self.assertFalse(output.exists())
        with redirect_stdout(StringIO()) as stdout:
            self.assertEqual(main([]), 1)
        self.assertIn("ContractError", stdout.getvalue())

    def test_worker_tampered_spec_rejected_before_source_or_native_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            spec = Path(temporary) / "spec.json"
            spec.write_bytes(b"{}")
            with (
                patch("cfl_gnn.mvp3.qualification.check_source") as source,
                self.assertRaises(ContractError),
            ):
                worker(spec, "0" * 64)
            source.assert_not_called()

    def test_worker_cannot_run_primary_population(self):
        with tempfile.TemporaryDirectory() as temporary:
            spec = Path(temporary) / "spec.json"
            spec.write_bytes(
                canonical_bytes(
                    {"binding": {"source_commit": "a" * 40, "mode": "primary"}}
                )
            )
            with (
                patch("cfl_gnn.mvp3.qualification.check_source"),
                self.assertRaises(ContractError),
            ):
                worker(spec, file_sha256(spec))

    def test_envelope_is_exactly_five_tiny_technical_cells(self):
        self.assertEqual(len(CELLS), 5)
        self.assertEqual(
            CELLS[-3:], (("evaluation", "B"), ("evaluation", "R"), ("evaluation", "G"))
        )
        self.assertIn(">= 10.5", TINY_LP)
        self.assertTrue(TINY_LP.startswith("Maximize"))
        self.assertNotIn("HPC", TINY_LP)


if __name__ == "__main__":
    unittest.main()
