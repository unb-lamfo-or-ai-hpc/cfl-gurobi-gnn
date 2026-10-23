"""Synthetic parser and original-receipt collection tests; no solver runtime."""

import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import collect_pr66_log_phases as phases  # noqa: E402


def report(name="easy-threads1"):
    return json.loads((phases.EVIDENCE / name / "attempt_report.json").read_bytes())


def log_text(receipt, root="objective 4.601225560528e+00"):
    controls = "\n".join(f"{k} {v}" for k, v in receipt["parameters"].items())
    return (
        "Gurobi Optimizer version 13.0.1 (linux64)\n"
        "License identifier secret-never-export /home/private/path\n"
        f"{controls}\nPresolve time: 0.10s\n"
        f"Root relaxation: {root}, 12 iterations, 1.20 seconds (1.10 work units)\n"
        f"Explored {int(receipt['node_count'])} nodes (14 simplex iterations) in "
        f"{receipt['solver_runtime_seconds']:.2f} seconds (1.30 work units)\n"
        f"Best objective {receipt['primal']:.12e}, best bound {receipt['dual']:.12e}, "
        f"gap {receipt['mip_gap_relative'] * 100:.4f}%\n"
    )


class ParserTests(unittest.TestCase):
    def test_completed_relaxation(self):
        value = phases.parse_log(log_text(report()), report())
        self.assertEqual(value["log_state"], "receipt_consistent_observations")
        self.assertEqual(value["root_relaxation_state"], "completed")
        self.assertEqual(value["root_relaxation_display_seconds"], 1.2)
        self.assertEqual(value["presolve_display_seconds"], 0.1)
        self.assertEqual(value["warnings"], [])

    def test_interrupted_relaxation_is_not_completed(self):
        value = phases.parse_log(log_text(report(), "interrupted"), report())
        self.assertEqual(value["root_relaxation_state"], "interrupted")

    def test_missing_is_not_zero_or_interrupted(self):
        text = log_text(report()).replace("Root relaxation:", "Unsupported relaxation:")
        value = phases.parse_log(text, report())
        self.assertIsNone(value["root_relaxation_display_seconds"])
        self.assertEqual(value["root_relaxation_state"], "unavailable")

    def test_duplicate_root_observations_not_summed(self):
        value = phases.parse_log(
            log_text(report())
            + "Root relaxation: interrupted, 1 iterations, 2 seconds\n",
            report(),
        )
        self.assertIsNone(value["root_relaxation_display_seconds"])
        self.assertIsNotNone(value["presolve_display_seconds"])

    def test_concatenated_solver_logs_rejected(self):
        value = phases.parse_log(log_text(report()) * 2, report())
        self.assertEqual(value["log_state"], "unqualified")
        self.assertIsNone(value["presolve_display_seconds"])

    def test_foreign_version_or_parameter_rejected(self):
        for old, new in (("13.0.1", "13.0.2"), ("Threads 1", "Threads 2")):
            value = phases.parse_log(log_text(report()).replace(old, new), report())
            self.assertEqual(value["log_state"], "unqualified")

    def test_terminal_summary_must_match_receipt(self):
        for old, new in (("934 nodes", "1 nodes"), ("53.49 seconds", "50.49 seconds")):
            value = phases.parse_log(log_text(report()).replace(old, new), report())
            self.assertEqual(value["log_state"], "unqualified")

    def test_unsupported_or_impossible_duration_not_inferred(self):
        for old, new in (
            ("1.20 seconds", "999 seconds"),
            ("1.20 seconds", "nan seconds"),
        ):
            value = phases.parse_log(log_text(report()).replace(old, new), report())
            self.assertIsNone(value["root_relaxation_display_seconds"])

    def test_optional_work_units_and_whitespace(self):
        text = log_text(report()).replace(" (1.10 work units)", "")
        value = phases.parse_log(
            "\n".join("  " + s for s in text.splitlines()), report()
        )
        self.assertEqual(value["root_relaxation_display_seconds"], 1.2)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "plan"
        shutil.copytree(phases.EVIDENCE, self.source)

    def test_all_missing_preserved_and_no_solver_import(self):
        result = phases.collect(self.source, self.root / "output")
        self.assertEqual(len(result["rows"]), 10)
        self.assertTrue(all(r["log_state"] == "missing" for r in result["rows"]))
        self.assertFalse(result["scientific_reporting_eligible"])
        self.assertFalse(result["tree_phase_duration_qualified"])
        self.assertNotIn("gurobipy", sys.modules)

    def test_allowlisted_package_never_contains_private_text(self):
        path = self.source / "easy-threads1/gurobi.private.log"
        data = log_text(report()).encode()
        path.write_bytes(data)
        result = phases.collect(self.source, self.root / "output")
        self.assertEqual(
            result["rows"][0]["log_sha256"], hashlib.sha256(data).hexdigest()
        )
        self.assertEqual(path.read_bytes(), data)
        with tarfile.open(
            self.root / "output/pr66_phase_observations.tar.gz"
        ) as archive:
            self.assertEqual(
                set(archive.getnames()),
                {"phase_observations.json", "phase_observations.csv", "SHA256SUMS.txt"},
            )
            for member in archive.getmembers():
                output = archive.extractfile(member).read()
                self.assertNotIn(b"secret-never-export", output)
                self.assertNotIn(b"/home/private", output)

    def test_fresh_output_and_changed_receipt_guards(self):
        output = self.root / "output"
        output.mkdir()
        with self.assertRaisesRegex(ValueError, "fresh_output"):
            phases.collect(self.source, output)
        path = self.source / "easy-threads1/attempt_report.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "differs_from_reviewed"):
            phases.collect(self.source, self.root / "different")

    def test_output_cannot_be_under_source(self):
        with self.assertRaisesRegex(ValueError, "fresh_output"):
            phases.collect(self.source, self.source / "new")

    def test_reviewed_manifest_cannot_be_replaced(self):
        (self.source / "SHA256SUMS.txt").write_text("untrusted")
        with self.assertRaisesRegex(ValueError, "manifest_changed"):
            phases.public_receipts(self.source)

    def test_oversized_log_stops_before_output(self):
        path = self.source / "easy-threads1/gurobi.private.log"
        with path.open("wb") as stream:
            stream.truncate(phases.MAX_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "oversized"):
            phases.collect(self.source, self.root / "output")
        self.assertFalse((self.root / "output").exists())


if __name__ == "__main__":
    unittest.main()
