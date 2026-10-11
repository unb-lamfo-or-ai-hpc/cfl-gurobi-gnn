"""Existing-evidence audit regressions; no solver, Torch, network or HPC."""

import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import audit_pr85_scientific as audit  # noqa: E402


class ScientificAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = audit.build()
        cls.artifacts = audit.numeric.source_receipt()
        cls.selected = audit.numeric.selected_parents(cls.artifacts)
        package = audit.c1.read_package(
            audit.ROOT / "docs/evidence/pr80-job3503-return.json"
        )
        cls.observations = json.loads(
            package["members"]["numeric/numeric.json"]["text"]
        )["parents"]
        cls.split = (audit.ROOT / "configs/splits/cfl_90_seed42_folds.csv").read_bytes()
        with zipfile.ZipFile(
            audit.ROOT / "docs/evidence/pr80-inputs-receipt.zip"
        ) as archive:
            cls.metadata = json.loads(archive.read("inputs.json"))
        cls.models = audit.inference.plan()["models"]

    def test_population_split_and_no_promotion(self):
        report, parents, chains, metrics = self.result
        self.assertEqual(len(parents), 90)
        self.assertEqual(
            report["partition_counts"], {"train": 34, "validation": 10, "test": 10}
        )
        self.assertEqual(sum(p["numeric_checks_passed"] for p in parents), 54)
        self.assertEqual(len(chains), 2)
        self.assertEqual(len(metrics), 6)
        self.assertFalse(report["new_comparison_admitted"])
        self.assertFalse(report["full_benchmark_formulation_semantics_qualified"])
        for key in (
            "optimization_runs_added",
            "training_runs_added",
            "submissions_added",
        ):
            self.assertEqual(report[key], 0)

    def test_exposed_test_and_excluded_training_parents(self):
        parents = {r["parent"]: r for r in self.result[1]}
        for parent in audit.inference.CASES:
            self.assertEqual(parents[parent]["role"], "test")
            self.assertEqual(parents[parent]["exposure"], "historically_exposed")
        for index in (13, 26):
            row = parents[f"CFL_medium_instance_{index}"]
            self.assertEqual(row["role"], "train")
            self.assertFalse(row["admitted"])

    def test_effective_maximize_rejected(self):
        for sense in ("MAXIMIZE", "minimize", -1, None):
            with self.assertRaises(ValueError):
                audit.objective_policy("MAXIMIZE", sense)

    def test_correction_not_equivalence(self):
        self.assertIn("correct_source_sense", audit.objective_policy(-1, "MINIMIZE"))
        self.assertFalse(self.result[0]["equivalence_to_original_maximization_claimed"])
        # Two already feasible cost examples: reversing sense reverses preference.
        cheap_cost, expensive_cost = 7, 12
        self.assertLess(cheap_cost, expensive_cost)
        self.assertFalse(
            self.result[0]["hard_maximize_triviality"].startswith("verified")
        )

    def test_source_sense_not_silently_reinterpreted(self):
        with self.assertRaisesRegex(ValueError, "source_sense"):
            audit.objective_policy("MINIMIZE", "MINIMIZE")

    def test_duplicate_split_rejected(self):
        lines = self.split.decode().splitlines()
        lines[2] = lines[1]
        with self.assertRaisesRegex(ValueError, "population_identity"):
            audit.partition_rows(
                "\n".join(lines).encode(), self.selected, self.observations
            )

    def test_role_leakage_rejected(self):
        selected = copy.deepcopy(self.selected)
        selected["CFL_easy_instance_0"]["role"] = "train"
        with self.assertRaisesRegex(ValueError, "role_leakage"):
            audit.partition_rows(self.split, selected, self.observations)

    def test_gap_gate_rejected(self):
        for bad in (0.11, -0.01, float("nan"), True):
            selected = copy.deepcopy(self.selected)
            selected["CFL_easy_instance_0"]["label_gap_declared"] = bad
            with self.assertRaisesRegex(ValueError, "quality_gate"):
                audit.partition_rows(self.split, selected, self.observations)

    def test_cross_parent_duplicate_graph_rejected(self):
        selected = copy.deepcopy(self.selected)
        selected["CFL_easy_instance_1"]["graph"] = selected["CFL_easy_instance_0"][
            "graph"
        ]
        with self.assertRaisesRegex(ValueError, "duplicate_parent_artifact"):
            audit.partition_rows(self.split, selected, self.observations)

    def test_model_identity_mismatch_rejected(self):
        selected = copy.deepcopy(self.selected)
        selected["CFL_easy_instance_0"]["mip_sha256_declared"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "model_identity"):
            audit.partition_rows(self.split, selected, self.observations)

    def test_feasibility_failure_rejected(self):
        observations = copy.deepcopy(self.observations)
        observations["CFL_easy_instance_0"]["feasibility"]["checks"]["rows"] = False
        with self.assertRaisesRegex(ValueError, "feasibility_checks"):
            audit.partition_rows(self.split, self.selected, observations)

    def test_micro_is_pooled_not_mean_of_parent_f1(self):
        metrics = self.result[3]
        mixed = next(
            r for r in metrics if r["cohort"] == "mixed" and r["difficulty"] == "all"
        )
        self.assertAlmostEqual(
            mixed["micro_f1"],
            2 * mixed["tp"] / (2 * mixed["tp"] + mixed["fp"] + mixed["fn"]),
        )
        self.assertNotAlmostEqual(mixed["micro_f1"], mixed["parent_macro_f1"], places=5)
        self.assertFalse(mixed["independent_auc_or_calibration_rescoring"])

    def test_historical_metadata_issues_not_erased(self):
        for chain in self.result[2]:
            self.assertIn(
                "declared_parent_roles_mismatch",
                chain["historical_plan_summary_issues"],
            )
            self.assertIn(
                "historical_fit_not_independently_replayed",
                chain["prenorm_and_pos_weight"],
            )

    def test_checkpoint_tamper_rejected(self):
        models = copy.deepcopy(self.models)
        models["mixed"]["checkpoint_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checkpoint_identity"):
            audit.checkpoint_rows(self.metadata, self.artifacts, models)

    def test_test_based_threshold_selection_rejected(self):
        models = copy.deepcopy(self.models)
        models["mixed"]["threshold_source"] = "maximum_test_f1"
        with self.assertRaisesRegex(ValueError, "checkpoint_selection"):
            audit.checkpoint_rows(self.metadata, self.artifacts, models)

    def test_checkpoint_training_parent_changed_rejected(self):
        metadata = copy.deepcopy(self.metadata)
        for plan in metadata["plans"]:
            if plan["sha256"] == self.models["mixed"]["plan_sha256"]:
                plan["records"][0]["role"] = "train"
        with self.assertRaisesRegex(ValueError, "training_role_binding"):
            audit.checkpoint_rows(metadata, self.artifacts, self.models)

    def test_missing_forward_rejected(self):
        rows = audit.inference.validate_return(
            (audit.ROOT / "docs/evidence/e0/job3505-return.json").read_bytes(),
            audit.INFERENCE_SHA,
        )
        with self.assertRaisesRegex(ValueError, "twenty_forwards"):
            audit.predictive_summary(rows[:-1])

    def test_published_outputs_bound_and_reproduced(self):
        stored = audit.ROOT / "docs/evidence/e0/pr85"
        manifest = json.loads((stored / "manifest.json").read_bytes())
        for name, sha in manifest["files"].items():
            self.assertEqual(
                audit.numeric.metadata.digest((stored / name).read_bytes()), sha
            )
        for name, sha in manifest["source_text_sha256_lf"].items():
            self.assertEqual(
                audit.numeric.metadata.digest(
                    (audit.ROOT / name).read_bytes().replace(b"\r\n", b"\n")
                ),
                sha,
            )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "reproduced"
            audit.produce(output)
            for path in output.iterdir():
                self.assertEqual(path.read_bytes(), (stored / path.name).read_bytes())

    def test_reproducible_exports_and_preserve_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            audit.produce(output)
            manifest = json.loads((output / "manifest.json").read_bytes())
            for name, sha in manifest["files"].items():
                self.assertEqual(
                    audit.numeric.metadata.digest((output / name).read_bytes()), sha
                )
            with self.assertRaises(FileExistsError):
                audit.produce(output)

    def test_existing_warmstart_trace_is_six_easy_not_ten(self):
        rows = audit.warmstart_trace()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all("_easy_" in r["parent"] for r in rows))
        self.assertEqual(sum(r["accepted_starts_recorded"] for r in rows), 12)
        self.assertTrue(all(r["lp_control_depends_on_gnn_support"] for r in rows))
        self.assertTrue(all(r["root_preparation_cost_seconds"] is None for r in rows))
        self.assertTrue(all(r["new_optimization_runs"] == 0 for r in rows))


if __name__ == "__main__":
    unittest.main()
