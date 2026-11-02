"""Regression coverage for numerical provenance in the integrated article."""
import copy
import csv
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "claim_evidence_check", ROOT / "scripts/manuscript/check_claim_evidence.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class ClaimEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name)
        self.manuscript = self.repository / "manuscript"
        (self.manuscript / "supplement").mkdir(parents=True)
        self.manifest = json.loads(
            (ROOT / "manuscript/supplement/claim-evidence.json").read_text(encoding="utf-8"))
        shutil.copyfile(ROOT / "manuscript/index.qmd", self.manuscript / "index.qmd")
        for source in self.manifest["sources"]:
            path = self.repository / source["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source["path"], path)
        self.write_manifest()

    def write_manifest(self):
        (self.manuscript / "supplement/claim-evidence.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def check(self):
        self.write_manifest()
        return CHECK.check_claim_evidence(self.manuscript, self.repository)

    def claim(self, identity):
        return next(claim for claim in self.manifest["claims"] if claim["id"] == identity)

    def source(self, identity):
        return next(source for source in self.manifest["sources"] if source["id"] == identity)

    def test_existing_public_evidence_matches_article(self):
        self.assertEqual(self.check(), [])

    def test_article_target_count_cannot_drift_from_summary(self):
        path = self.manuscript / "index.qmd"
        text = path.read_text(encoding="utf-8")
        self.assertIn("target attained |97|", text)
        path.write_text(text.replace("target attained |97|", "target attained |98|"), encoding="utf-8")
        self.assertIn("claim_value_mismatch:cpu_reported_targets", self.check())

    def test_changed_evidence_bytes_are_rejected(self):
        path = self.repository / self.source("gpu_review")["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertIn("claim_source_hash_mismatch:gpu_review", self.check())

    def test_omitting_a_negative_result_claim_is_rejected(self):
        self.manifest["claims"].remove(self.claim("gpu_f1_loss"))
        self.assertIn("claim_evidence_coverage_invalid", self.check())

    def test_pooled_metrics_cannot_replace_parent_macro(self):
        self.claim("gpu_selected_f1")["metrics"]["serial"]["row"]["averaging"] = "pooled_binary"
        self.assertIn("claim_value_mismatch:gpu_selected_f1", self.check())

    def test_job_clock_cannot_replace_loop_speedup(self):
        self.claim("gpu_loop_speedup")["metrics"]["n"]["row"]["scope"] = "job_elapsed_seconds"
        self.assertIn("claim_value_mismatch:gpu_loop_speedup", self.check())

    def test_loss_direction_cannot_be_reversed(self):
        self.claim("gpu_f1_loss")["metrics"]["n"]["scale"] = 1
        self.assertIn("claim_value_mismatch:gpu_f1_loss", self.check())

    def test_ambiguous_csv_row_is_not_silently_selected(self):
        source = self.source("gpu_metrics")
        path = self.repository / source["path"]
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows.append(copy.deepcopy(rows[0]))
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertIn("claim_selector_invalid:gpu_selected_f1", self.check())

    def test_source_path_cannot_escape_evidence_directory(self):
        self.source("cpu_main")["path"] = "docs/evidence/../../../outside.json"
        self.assertIn("claim_evidence_invalid", self.check())

    def test_pending_cpu_results_cannot_be_added_to_manifest(self):
        self.manifest["pending_cpu"]["result_claims"] = [{"speedup": 2}]
        self.assertIn("claim_evidence_pending_cpu_promoted", self.check())

    def test_unavailable_value_cannot_be_formatted_as_a_number(self):
        source = self.source("gpu_review")
        path = self.repository / source["path"]
        data = json.loads(path.read_text())
        data["selected_macro_ddp4_minus_serial"]["f1_score"] = None
        path.write_text(json.dumps(data), encoding="utf-8")
        source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertIn("claim_selector_invalid:gpu_f1_loss", self.check())


if __name__ == "__main__":
    unittest.main()
