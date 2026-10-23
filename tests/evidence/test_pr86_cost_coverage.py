"""Reproduce measured historical cost coverage without a solver."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import review_pr86_cost_coverage as coverage  # noqa: E402


class CoverageTests(unittest.TestCase):
    def test_original_eighteen_rows_no_invented_guidance_cost(self):
        rows = coverage.build()
        self.assertEqual(len(rows), 18)
        for row in rows:
            self.assertFalse(row["prospective_pr86_result"])
            self.assertIsNone(row["cold_end_to_end_seconds"])
            self.assertIsNone(row["worker_overhead_seconds"])
            if row["method"] != "M0":
                self.assertIsNone(row["cold_end_to_end_seconds"])
                self.assertIsNone(row["preparation_seconds"])
            self.assertGreater(row["execution_seconds"], 0)

    def test_published_outputs_reproduce_without_overwrite(self):
        published = coverage.binding.proposal.ROOT / "docs/evidence/pr86/preparation"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "coverage"
            coverage.produce(output)
            for path in output.iterdir():
                self.assertEqual(
                    path.read_bytes(), (published / path.name).read_bytes()
                )
            with self.assertRaises(FileExistsError):
                coverage.produce(output)


if __name__ == "__main__":
    unittest.main()
