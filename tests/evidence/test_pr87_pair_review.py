"""Analytical closeout regression, no torch, scheduler, inference or training."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import review_pr87_training_pair as r  # noqa: E402


class PairReview(unittest.TestCase):
    def value(self):
        return json.loads((r.DEST / "public_return.json").read_bytes())

    def test_original_bytes_and_products_reproduce(self):
        raw = (r.DEST / "public_return.json").read_bytes()
        self.assertEqual(r.c.sha(raw), r.SHA)
        for name, content in r.products(raw).items():
            self.assertEqual((r.DEST / name).read_bytes(), content, name)
        self.assertFalse(self.value()["scientific_reporting_eligible"])

    def test_case_tradeoff_not_quality_preservation(self):
        result = r.audit(self.value())
        a = result["assessment"]
        self.assertTrue(a["technical_pair_complete"])
        self.assertTrue(a["f1_loss_exceeds_margin"])
        self.assertFalse(a["pr_auc_loss_exceeds_margin"])
        self.assertFalse(a["quality_preservation_supported"])
        self.assertEqual(a["selected_f1_parents_lower"], 10)
        scopes = {row["scope"]: row for row in result["timings"]}
        self.assertAlmostEqual(
            scopes["training_loop_seconds"]["speedup"], 2.1669778666496127
        )
        self.assertAlmostEqual(scopes["job_elapsed_seconds"]["speedup"], 2021 / 1104)
        self.assertNotEqual(
            scopes["training_loop_seconds"]["speedup"],
            scopes["job_elapsed_seconds"]["speedup"],
        )
        serial, ddp = result["summary"]
        self.assertGreater(ddp["allocated_gpu_hours"], serial["allocated_gpu_hours"])
        self.assertEqual(len(result["quality"]), 40)
        self.assertEqual(len(result["history"]), 200)
        self.assertEqual(len(result["ranks"]), 5)

    def test_changed_validation_selection_rejected(self):
        value = self.value()
        value["results"][0]["best_epoch"] = 1
        with self.assertRaisesRegex(ValueError, "validation_selected_epoch"):
            r.audit(value)

    def test_changed_epoch_timing_rejected(self):
        value = self.value()
        value["results"][0]["history"][0]["training_seconds"] += 10
        with self.assertRaisesRegex(ValueError, "epoch_time_sum"):
            r.audit(value)

    def test_duplicated_rank_affinity_rejected(self):
        value = self.value()
        value["results"][1]["rank_resources"][1]["affinity"] = copy.deepcopy(
            value["results"][1]["rank_resources"][0]["affinity"]
        )
        with self.assertRaisesRegex(ValueError, "disjoint_rank_affinity"):
            r.audit(value)

    def test_incomplete_pair_and_authorization_changes_rejected(self):
        value = self.value()
        value["results"][1] = None
        with self.assertRaisesRegex(ValueError, "training_result_absent"):
            r.audit(value)
        value = self.value()
        value["approval"]["authorization_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            r.audit(value)
        raw = (r.DEST / "public_return.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "training_return_hash"):
            r.products(raw + b" ")

    def test_figure_manifest_and_public_scope(self):
        manifest = r.c.read(r.DEST / "figures_manifest.json")
        self.assertEqual(len(manifest["outputs"]), 12)
        self.assertEqual(
            manifest["analysis_manifest_sha256"],
            r.c.sha((r.DEST / "manifest.json").read_bytes()),
        )
        for name, digest in manifest["outputs"].items():
            self.assertEqual(r.c.sha((r.DEST / name).read_bytes()), digest, name)
        for name in ("review.json", "summary.csv", "quality.csv", "ranks.csv"):
            text = (r.DEST / name).read_text(encoding="utf-8")
            self.assertNotIn("/raid/", text)
            self.assertNotIn("secrets/", text)

    def test_plain_import_has_no_torch_dependency(self):
        import subprocess

        command = "import sys;sys.path.insert(0,'scripts/evidence');import review_pr87_training_pair;assert 'torch' not in sys.modules"
        subprocess.run([sys.executable, "-B", "-c", command], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
