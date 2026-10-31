"""Boundary tests for partial evidence and endpoint-specific interpretation."""

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "partial_cpu", ROOT / "scripts/manuscript/build_partial_cpu_assets.py"
)
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class PartialCpuTests(unittest.TestCase):
    def test_sealed_subset_remains_fifty_of_sixty(self):
        sources = P.load_sources()
        self.assertEqual(len(sources["cells.csv"]), 50)
        self.assertEqual(len(sources["disposition.csv"]), 60)
        self.assertFalse(sources["review.json"]["scientific_reporting_eligible"])

    def test_terminal_censoring_does_not_censor_every_threshold(self):
        sources = P.load_sources()
        row = next(r for r in sources["cells.csv"] if r["job_id"] == "3711")
        self.assertEqual(row["right_censored"], "True")
        self.assertEqual(P.threshold(sources, "3711", 0.1)["state"], "observed")
        self.assertEqual(P.threshold(sources, "3711", 0.05)["state"], "right_censored")

    def test_censored_times_cannot_form_a_speedup(self):
        self.assertIsNone(
            P.time_ratio({"state": "right_censored"}, {"state": "observed"})
        )

    def test_sensitive_cases_cannot_form_a_certified_ratio(self):
        p = {"state": "observed", "observed_seconds": "10"}
        self.assertIsNone(P.time_ratio(p, p, sensitive=True))

    def test_nonfinite_or_zero_denominator_rejected(self):
        a = {"state": "observed", "observed_seconds": "10"}
        for value in ("nan", "0"):
            with self.assertRaises(ValueError):
                P.time_ratio(a, {"state": "observed", "observed_seconds": value})

    def prose_fixture(self, directory):
        root = Path(directory)
        (root / "supplement").mkdir()
        shutil.copy2(ROOT / "manuscript/index.qmd", root / "index.qmd")
        shutil.copy2(
            ROOT / "manuscript/supplement/extended-results.md",
            root / "supplement/extended-results.md",
        )
        return root

    def test_removing_partial_qualification_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prose_fixture(d)
            path = root / "index.qmd"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "completion-based subset", "complete experiment"
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                any("partial_article_scope" in e for e in P.check_source(root))
            )

    def test_changed_bound_diagnostic_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prose_fixture(d)
            path = root / "supplement/extended-results.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("0.132417%", "0.000000%"),
                encoding="utf-8",
            )
            self.assertTrue(
                any("partial_appendix_value" in e for e in P.check_source(root))
            )

    def test_changed_source_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dest = root / P.SOURCE
            shutil.copytree(ROOT / P.SOURCE, dest)
            with (dest / "cells.csv").open("a") as f:
                f.write("\n")
            with self.assertRaisesRegex(ValueError, "partial_source_hash"):
                P.load_sources(root)


if __name__ == "__main__":
    unittest.main()
