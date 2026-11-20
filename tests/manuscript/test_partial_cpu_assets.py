"""Boundary tests for partial evidence and endpoint-specific interpretation."""

import csv
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
    def test_complete_campaign_has_sixty_sealed_cells(self):
        sources = P.load_sources()
        self.assertEqual(len(sources["cells.csv"]), 60)
        self.assertEqual(len(sources["disposition.csv"]), 60)
        self.assertFalse(sources["review.json"]["scientific_reporting_eligible"])

    def test_prior_fifty_cells_and_temporal_records_are_preserved(self):
        sources = P.load_sources()
        prior = ROOT / "docs/evidence/pr89/partial-20261031"
        for name in ("cells.csv", "thresholds.csv", "horizons.csv"):
            with (prior / name).open(encoding="utf-8", newline="") as stream:
                original = list(csv.DictReader(stream))
            self.assertEqual(sources[name][: len(original)], original)

    def test_new_zero_gap_does_not_resolve_cross_run_m12_disagreement(self):
        sources = P.load_sources()
        by_job = {r["job_id"]: r for r in sources["cells.csv"]}
        g, b = by_job["3726"], by_job["3727"]
        self.assertEqual(g["gap_fraction"], "0.0")
        self.assertGreater(float(g["dual"]), float(b["primal"]))
        self.assertLess(float(g["runtime_seconds"]), float(b["runtime_seconds"]))
        self.assertEqual(g["scientific_reporting_eligible"], "False")
        self.assertIsNone(
            P.time_ratio(
                P.threshold(sources, "3727"),
                P.threshold(sources, "3726"),
                sensitive=True,
            )
        )

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
            path = root / "supplement/extended-results.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "do not establish certified speedups",
                    "establish certified speedups",
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                any("partial_appendix_scope" in e for e in P.check_source(root))
            )

    def test_population_table_cannot_revert_to_partial_sample(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.prose_fixture(d)
            path = root / "supplement/extended-results.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "60 completed configurations on the same four medium instances",
                    "50 completed configurations on the same four medium instances",
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                any("complete_appendix_population" in e for e in P.check_source(root))
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
