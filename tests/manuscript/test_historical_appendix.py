"""Boundaries for recovering historical tables, without tensor or solver access."""
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "historical_appendix", ROOT / "scripts/manuscript/build_historical_appendix.py")
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


class HistoricalAppendixTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "manuscript"
        shutil.copytree(
            ROOT / "manuscript", self.root,
            ignore=shutil.ignore_patterns("_manuscript", ".quarto", "figures", "tables", "*.tex"))
        self.manifest = self.root / "supplement/historical-appendix-manifest.json"

    def replace_bound_json(self, source_id, change):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        record = next(s for s in data["sources"] if s["id"] == source_id)
        path = self.root / "results" / (source_id + ".json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        change(payload)
        raw = (json.dumps(payload) + "\n").encode()
        path.write_bytes(raw)
        record["sha256"] = hashlib.sha256(raw).hexdigest()
        record["git_blob_sha1"] = hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        self.manifest.write_text(json.dumps(data), encoding="utf-8")

    def test_original_sources_are_bound_to_distinct_historical_population(self):
        self.assertEqual(HISTORY.check_source(self.root), [])
        manifest, data = HISTORY.load_sources(self.root)
        self.assertEqual(len(manifest["sources"]), 9)
        self.assertEqual(len(data["graph_statistics"]), 39)
        self.assertEqual(len(data["per_parent_metrics"]), 8)
        self.assertTrue(all(r["right_censored"] == "" for r in data["graph_statistics"]))
        current = json.loads((self.root / "evidence-status.json").read_text())
        self.assertEqual(current["current_protocol"]["parents"], 54)

    def test_archived_pca_coordinate_edits_are_not_silently_redrawn(self):
        path = self.root / "results/graph_clustering.csv"
        path.write_bytes(path.read_bytes().replace(b"-1.748822", b"-9.748822", 1))
        self.assertTrue(any("historical_source_hash:graph_clustering" in error
                            for error in HISTORY.check_source(self.root)))

    def test_outcomes_cannot_be_added_to_descriptive_projection(self):
        self.replace_bound_json(
            "graph_clustering_report",
            lambda value: value["methodology"]["features"].append("positive_label_fraction"))
        self.assertTrue(any("historical_projection_scope" in error
                            for error in HISTORY.check_source(self.root)))

    def test_historical_population_cannot_be_relabelled_current(self):
        self.replace_bound_json(
            "confirmation_final", lambda value: value["cohort"].update(parents=54))
        self.assertTrue(any("historical_population" in error
                            for error in HISTORY.check_source(self.root)))

    def test_refit_flag_is_outside_editorial_restoration(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["projection_refitted"] = True
        self.manifest.write_text(json.dumps(manifest))
        self.assertTrue(any("historical_manifest_scope" in error
                            for error in HISTORY.check_source(self.root)))

    def test_historical_f1_change_is_detected_in_reader_text(self):
        path = self.root / "supplement/extended-results.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "Pooled F1 is 0.5825", "Pooled F1 is 0.9999"), encoding="utf-8")
        self.assertIn("historical_claim_mismatch:history39_f1", HISTORY.check_source(self.root))

    def test_projection_paths_cannot_escape_the_recorded_sources(self):
        data = json.loads(self.manifest.read_text())
        next(s for s in data["sources"] if s["id"] == "graph_clustering")["path"] = "../private.csv"
        self.manifest.write_text(json.dumps(data))
        self.assertTrue(any("historical_source_path" in error
                            for error in HISTORY.check_source(self.root)))

    def test_historical_and_later_training_minima_remain_distinct(self):
        _, sources = HISTORY.load_sources(self.root)
        self.assertEqual(sources["confirmation_final"]["training"]["best_validation_epoch_from_history"], 91)
        current = HISTORY.ROOT / "results/current/table_training_epoch_metrics.csv"
        import csv
        with current.open(encoding="utf-8", newline="") as stream:
            later = min(csv.DictReader(stream), key=lambda r: float(r["validation_weighted_bce"]))
        self.assertEqual(int(later["epoch"]), 34)


if __name__ == "__main__":
    unittest.main()
