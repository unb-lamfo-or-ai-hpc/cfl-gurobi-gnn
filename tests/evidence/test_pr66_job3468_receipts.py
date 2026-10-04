"""Read-only regressions for the real bounded screen; never optimize or train."""

import csv
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import package_pr66_pilot as packaging
import pr66_thread_pilot as pilot

EVIDENCE = ROOT / "docs/evidence/pr66/job3468"
PLAN_SHA = "7cfd6bf270e04f96c0745ebf61ae427a949d24a85b571879d9c746af1f75b152"


class RealScreenTests(unittest.TestCase):
    def test_original_payload_hashes(self):
        rows = (EVIDENCE / "SHA256SUMS.txt").read_text().splitlines()
        names = []
        for row in rows:
            expected, name = row.split("  ", 1)
            self.assertNotIn(name, names)
            names.append(name)
            self.assertEqual(
                hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest(), expected
            )
        self.assertEqual(len(names), 14)

    def test_complete_real_contract_and_csv(self):
        config = EVIDENCE / "executed_config.json"
        self.assertEqual(
            pilot.strict_json(config), pilot.strict_json(pilot.BASE_CONFIG)
        )
        with patch.object(pilot, "BASE_CONFIG", config):
            rows, _, complete = packaging.verify(EVIDENCE, PLAN_SHA)
        self.assertTrue(complete)
        self.assertEqual(len(rows), 10)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        self.assertEqual(
            stream.getvalue().encode(),
            (EVIDENCE / "thread_screen_outcomes.csv").read_bytes(),
        )

    def test_tolerance_and_censoring_are_not_exact_optima(self):
        for cap in pilot.CAPS:
            easy = pilot.strict_json(
                EVIDENCE / f"easy-threads{cap}/attempt_report.json"
            )
            medium = pilot.strict_json(
                EVIDENCE / f"medium-threads{cap}/attempt_report.json"
            )
            self.assertEqual(easy["termination"], "gap_target_reached")
            self.assertGreater(easy["mip_gap_relative"], 0)
            self.assertLessEqual(easy["mip_gap_relative"], 0.1)
            self.assertEqual(medium["termination"], "time_limit")
            self.assertGreater(medium["mip_gap_relative"], 0.1)
            self.assertFalse(easy["scientific_reporting_eligible"])
            self.assertFalse(medium["scientific_reporting_eligible"])

    def test_accounting_units_and_nonpromotion(self):
        review = json.loads((EVIDENCE / "screen_review.json").read_text())
        self.assertEqual(review["slurm_elapsed_seconds"], 1794)
        self.assertEqual(review["slurm_alloc_cpus"], 32)
        self.assertAlmostEqual(
            review["scheduler_allocated_logical_cpu_hours"], 32 * 1794 / 3600
        )
        self.assertAlmostEqual(
            review["qualified_physical_core_reservation_hours"], 16 * 1794 / 3600
        )
        self.assertFalse(review["scientific_reporting_eligible"])
        self.assertFalse(review["expansion_authorized"])
        self.assertFalse(review["merge_authorized"])
        self.assertFalse(review["incumbent_uniqueness_certified"])


if __name__ == "__main__":
    unittest.main()
