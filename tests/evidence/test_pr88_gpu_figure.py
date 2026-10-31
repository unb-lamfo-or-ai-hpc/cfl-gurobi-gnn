"""Publication integrity of existing GPU results; no rendering or training."""

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import plot_pr88_gpu_bce as gpu  # noqa: E402


class GPUFigureTests(unittest.TestCase):
    def test_exact_original_histories_and_selection(self):
        value = gpu.data()
        archived = json.loads((ROOT / gpu.DEST / "curves.json").read_bytes())
        self.assertEqual(archived, value)
        self.assertFalse(value["smoothing_or_interpolation"])
        self.assertEqual(value["seed"], 42)
        self.assertEqual(value["optimizer_updates_per_arm"], 3400)
        for arm, epoch in (("serial1", 99), ("ddp4", 92)):
            obs = value["arms"][arm]
            self.assertEqual(obs["epochs"], list(range(1, 101)))
            self.assertEqual(len(obs["train_loss"]), 100)
            self.assertEqual(len(obs["validation_loss"]), 100)
            self.assertEqual(obs["selected_epoch"], epoch)
            self.assertEqual(
                obs["selected_validation_loss"], min(obs["validation_loss"])
            )

    def test_all_source_and_output_hashes(self):
        manifest = json.loads((ROOT / gpu.DEST / "manifest.json").read_bytes())
        self.assertEqual(manifest["source_return_sha256"], gpu.review.SHA)
        self.assertEqual(len(manifest["outputs"]), 7)
        for key in ("sources", "outputs"):
            for name, digest in manifest[key].items():
                path = ROOT / name
                self.assertTrue(path.resolve().is_relative_to(ROOT.resolve()))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertEqual(manifest["training_runs_added"], 0)
        self.assertEqual(manifest["optimization_runs_added"], 0)

    def test_valid_vector_and_raster_outputs(self):
        for lang, directory in (("es", gpu.DEST), ("en", gpu.ARTICLE)):
            base = (
                ROOT
                / directory
                / (gpu.STEM + "_es" if lang == "es" else gpu.ARTICLE_STEM)
            )
            self.assertTrue(base.with_suffix(".pdf").read_bytes().startswith(b"%PDF-"))
            self.assertTrue(
                base.with_suffix(".png").read_bytes().startswith(b"\x89PNG")
            )
            svg = base.with_suffix(".svg").read_text(encoding="utf-8")
            self.assertIn("<svg", svg)
            self.assertIn("DDP: 4 GPUs", svg)
            self.assertIn("Serial: 1 GPU", svg)
            self.assertNotIn("/raid/", svg)
            if lang == "en":
                self.assertIn("#333333", svg)
                self.assertIn("#888888", svg)
                self.assertNotIn("DejaVuSans-Bold", svg)

    def test_article_keeps_negative_quality_and_no_new_cpu_results(self):
        article = (ROOT / "manuscript/index.qmd").read_text(encoding="utf-8")
        for text in (
            "#sec-gpu-matched",
            "#tbl-gpu-pair",
            "#fig-gpu-bce",
            "0.032468",
            "0.02 loss margin",
            "13,600 presentations",
            "3,400 updates",
            "cause is unproven",
            "historically exposed",
            "not replace",
        ):
            self.assertIn(text, article)
        self.assertNotIn("Neither its speedup nor", article)
        self.assertNotIn("GPU training remain pending", article)
        # Execution/qualification status belongs in repository metadata, not journal prose.
        metadata = json.loads(
            (ROOT / "manuscript/evidence-status.json").read_text(encoding="utf-8")
        )["mvp2_continuation"]["pr89"]
        self.assertIs(metadata["final_return_received"], False)
        self.assertIs(metadata["scientific_results_included"], False)
        self.assertIs(metadata["new_execution_authorized_by_this_revision"], False)
        self.assertNotIn("separate resource approval", article)
        raw = json.loads((ROOT / gpu.SOURCE / "public_return.json").read_bytes())
        self.assertIs(raw["scientific_reporting_eligible"], False)


if __name__ == "__main__":
    unittest.main()
