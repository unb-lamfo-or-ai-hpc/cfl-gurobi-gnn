"""Qualification release gates are tested without a license or native solve."""
# ruff: noqa: E402 -- repository-source bootstrap

import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fake_native import fake_api

from cfl_gnn.mvp3.collection import collect_attempt
from cfl_gnn.mvp3.contract import ContractError, canonical_bytes, load_json
from cfl_gnn.mvp3.journal import file_sha256
from cfl_gnn.mvp3.qualification import (
    CELLS,
    TINY_LP,
    check_source,
    configure_worker_license,
    explicit_license_path,
    main,
    qualify,
    safe_worker_error,
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

    def test_explicit_license_routing_never_opens_or_hashes_license_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            license_path = Path(temporary) / "fake.lic"
            license_path.write_text("invented-test-sentinel-do-not-read")
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("License must not be read"),
                ),
                patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError("License must not be read"),
                ),
            ):
                configure_worker_license(license_path)
                self.assertEqual(
                    os.environ["GRB_LICENSE_FILE"], str(license_path.resolve())
                )
            with self.assertRaises(ContractError):
                explicit_license_path(Path(temporary) / "absent.lic")

    def test_safe_error_diagnostics_keep_code_and_phase_without_message(self):
        error = RuntimeError("private-test-message")
        error.errno = 10009
        record = safe_worker_error(error, "environment_start", "a" * 64)
        self.assertEqual(record["native_error_code"], 10009)
        self.assertNotIn("private-test-message", str(record))
        self.assertFalse(record["exception_message_copied"])

    def test_worker_environment_failure_seals_diagnostics_without_optimize(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "tiny.lp"
            source.write_bytes(TINY_LP.encode("ascii"))
            license_file = folder / "fake.lic"
            license_file.write_text("invented-test-license-not-read")
            binding = {
                "source_commit": "a" * 40,
                "mode": "technical_qualification",
                "input_sha256": file_sha256(source),
                "key": {
                    "parent_id": "QUAL_TINY20",
                    "stage": "root_relaxation",
                    "method": None,
                    "seed": 42,
                    "attempt": "failed-env",
                },
            }
            spec = {
                "binding": binding,
                "input_path": str(source),
                "input_sha256": file_sha256(source),
                "attempt_folder": str(folder / "attempt"),
                "license_file": str(license_file),
                "approval_reference": "offline-double-only",
            }
            spec_path = folder / "spec.json"
            spec_path.write_bytes(canonical_bytes(spec))
            api, model, environment = fake_api()
            error = RuntimeError("private-test-message")
            error.errno = 10009
            environment.start = lambda: (_ for _ in ()).throw(error)
            with (
                patch("cfl_gnn.mvp3.qualification.check_source"),
                patch.dict(sys.modules, {"gurobipy": api}),
                patch.dict(os.environ),
                self.assertRaises(RuntimeError),
            ):
                worker(spec_path, file_sha256(spec_path))
            collected = collect_attempt(folder / "attempt")
            self.assertEqual(collected["state"], "no_native_intent")
            self.assertEqual(collected["worker_error"]["phase"], "environment_start")
            self.assertEqual(collected["worker_error"]["native_error_code"], 10009)
            self.assertEqual(model.calls, 0)
            self.assertTrue(environment.closed)

    def test_parent_passes_explicit_license_and_stops_after_first_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            license_file = folder / "fake.lic"
            license_file.write_text("invented-test-only")
            dependencies = {
                "gurobipy": "14.0.0",
                "psutil": "7.2.2",
                "gurobi-logtools": "4.0.1",
                "jsonschema": "4.26.0",
            }
            with (
                patch("cfl_gnn.mvp3.qualification.check_source"),
                patch(
                    "cfl_gnn.mvp3.qualification.version",
                    side_effect=lambda name: dependencies[name],
                ),
                patch(
                    "cfl_gnn.mvp3.qualification.supervise",
                    return_value={"child_returncode": 1, "guard": None},
                ) as supervised,
            ):
                result = qualify(
                    folder / "output",
                    "a" * 40,
                    "offline-double-only",
                    license_file=license_file,
                )
            self.assertEqual(supervised.call_count, 1)
            self.assertFalse(result["all_five_cells_qualified"])
            spec = load_json(folder / "output/1-root_relaxation-none.spec.json")
            self.assertEqual(spec["license_file"], str(license_file.resolve()))


if __name__ == "__main__":
    unittest.main()
