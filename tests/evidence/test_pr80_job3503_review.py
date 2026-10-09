"""Real sealed receipt and adversarial review checks; no GPU or optimization."""

import copy
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import review_pr80_job3503 as review  # noqa: E402


class ReviewTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.path = review.ROOT / "docs/evidence/pr80-job3503-return.json"
        self.package = review.read_package(self.path)

    def test_real_receipt_all_54_and_four_cases(self):
        rows, summary, inference = review.validate(self.package)
        self.assertEqual(len(rows), 54)
        self.assertEqual(len(inference["cases"]), 4)
        self.assertEqual(sum(r["difficulty"] == "medium" for r in rows), 24)
        self.assertTrue(all(r["missing"] == 0 for r in summary))

    def test_byte_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "return.json"
            changed.write_bytes(self.path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "return hash"):
                review.read_package(changed)

    def change(self, name, callback):
        package = copy.deepcopy(self.package)
        value = json.loads(package["members"][name]["text"])
        callback(value)
        package["members"][name]["text"] = json.dumps(value)
        return package

    def test_partial_numeric_is_not_completion(self):
        package = self.change(
            "numeric/numeric.json",
            lambda x: x["parents"]["CFL_medium_instance_11"].update(
                state="unqualified"
            ),
        )
        with self.assertRaisesRegex(ValueError, "unqualified parent"):
            review.validate(package)

    def test_reused_row_must_be_identical(self):
        package = self.change(
            "numeric/numeric.json",
            lambda x: x["parents"]["CFL_easy_instance_1"].update(role="train"),
        )
        with self.assertRaisesRegex(ValueError, "reused row changed"):
            review.validate(package)

    def test_bad_confusion_metric_rejected(self):
        package = copy.deepcopy(self.package)
        inference = json.loads(package["members"]["inference.json"]["text"])
        inference["cases"][0]["metrics"]["f1_score"] = 0.99
        package["members"]["inference.json"]["text"] = json.dumps(inference)
        integrated = json.loads(package["members"]["integrated.json"]["text"])
        integrated["inference"] = inference
        package["members"]["integrated.json"]["text"] = json.dumps(integrated)
        with self.assertRaisesRegex(ValueError, "confusion-derived metric"):
            review.validate(package)

    def test_outputs_and_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            report, _, _, _ = review.produce(output)
            self.assertTrue(report["sample_admission_supported"])
            self.assertFalse(report["new_execution_authorized"])
            self.assertFalse(report["auc_independently_recomputed"])
            self.assertEqual(report["e0_missing_published_method_rows"], 24)
            with (output / "sprint_b_cpu.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            censored = [r for r in rows if r["observed_target_state"] != "observed"]
            self.assertEqual(len(censored), 3)
            self.assertTrue(
                all(r["first_observed_target_seconds"] == "" for r in censored)
            )
            with self.assertRaisesRegex(ValueError, "fresh output"):
                review.produce(output)

    def test_quantiles_and_alias(self):
        self.assertEqual(review.quantile([1, 2, 3, 4], 0.25), 1.75)
        self.assertEqual(review.alias("CFL_medium_instance_11"), "M11")
        self.assertEqual(review.ordered_mean([1e16, 1.0, -1e16]), 0.0)

    def test_public_sprint_b_document_line_endings(self):
        read_bytes = Path.read_bytes
        expected = json.loads(
            (review.ROOT / "docs/evidence/pr80-results/review.json").read_bytes()
        )
        for ending in (b"\n", b"\r\n"):

            def public_document_bytes(path):
                raw = read_bytes(path)
                if path.name == "pr79-sprint-b-review.json":
                    return raw.replace(b"\r\n", b"\n").replace(b"\n", ending)
                return raw

            with tempfile.TemporaryDirectory() as directory:
                with mock.patch.object(Path, "read_bytes", public_document_bytes):
                    report, _, _, _ = review.produce(Path(directory) / "new")
                self.assertEqual(report, expected)

    def test_published_tables_regenerate_and_figures_match_manifest(self):
        source = review.ROOT / "docs/evidence/pr80-results"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            report, _, _, _ = review.produce(output)
            for name, sha in report["table_hashes"].items():
                self.assertEqual(
                    review.audit.metadata.digest((source / name).read_bytes()), sha
                )
            self.assertEqual(json.loads((source / "review.json").read_bytes()), report)
        manifest = json.loads((source / "figures_manifest.json").read_bytes())
        self.assertEqual(len(manifest["figure_hashes"]), 12)
        for name, sha in manifest["figure_hashes"].items():
            self.assertEqual(
                review.audit.metadata.digest((source / name).read_bytes()), sha
            )


if __name__ == "__main__":
    unittest.main()
