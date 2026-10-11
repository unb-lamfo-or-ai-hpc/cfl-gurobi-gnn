"""Offline regression gates for the immutable PR85 context receipt."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import close_pr85_scientific_audit as closure  # noqa: E402


class ScientificClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = json.loads((closure.ROOT / closure.RECEIPT).read_bytes())
        cls.request = json.loads((closure.ROOT / closure.REQUEST).read_bytes())
        _, _, chains, _ = closure.audit.build()
        cls.chain = {c["cohort"]: c for c in chains}
        package = closure.audit.c1.read_package(
            closure.ROOT / "docs/evidence/pr80-job3503-return.json"
        )
        cls.observations = json.loads(
            package["members"]["numeric/numeric.json"]["text"]
        )["parents"]

    def test_closure_retains_false_execution_gates(self):
        report, training, models = closure.build()
        self.assertEqual(report["state"], "audit_complete_with_explicit_limitations")
        self.assertEqual(report["admitted_numeric_parents_reconciled"], 54)
        self.assertEqual(
            report["partition_counts"], {"train": 34, "validation": 10, "test": 10}
        )
        self.assertEqual((len(training), len(models)), (2, 2))
        for key in (
            "new_comparison_admitted",
            "resource_budget_approved",
            "full_benchmark_formulation_semantics_qualified",
            "raw_receipt_flags_rewritten",
            "historical_fit_independently_replayed",
        ):
            self.assertIs(report[key], False)

    def test_raw_receipt_hash_is_not_text_normalized(self):
        raw = (closure.ROOT / closure.RECEIPT).read_bytes()
        self.assertEqual(closure.context.digest(raw), closure.RECEIPT_SHA)
        with self.assertRaisesRegex(ValueError, "receipt_hash"):
            closure.context.review(raw + b"\n", closure.RECEIPT_SHA, self.request)

    def test_training_inconsistencies_rejected(self):
        mutations = {
            "epochs_completed": 99,
            "train_parents": 17,
            "prenorm_training_graphs": 19,
            "test_graphs_loaded": 1,
            "pos_weight": float("nan"),
            "threshold": 0.5,
            "historical_fit_replayed": True,
            "train_only_prenorm_attested_by_hashed_report": False,
            "pos_weight_train_only_scope": "proven_by_replay",
        }
        for key, change in mutations.items():
            with self.subTest(key=key):
                item = copy.deepcopy(self.value["training_reports"]["easy"])
                item[key] = change
                with self.assertRaises(ValueError):
                    closure.reconcile_training(
                        item, self.request["models"]["easy"], self.chain["easy"]
                    )

    def test_model_inconsistencies_rejected(self):
        parent = "CFL_easy_instance_0"
        mutations = {
            "variables_observed": 1,
            "explicit_binary_variables": 1,
            "remaining_continuous_by_linear_lp_default": 1,
            "explicit_general_variables": 1,
            "required_effective_sense": "MAXIMIZE",
            "source_sha256": "0" * 64,
            "full_semantics_qualified": True,
            "coverage": "all_54",
            "economic_units": "euros",
        }
        for key, change in mutations.items():
            with self.subTest(key=key):
                item = copy.deepcopy(self.value["representative_models"][parent])
                item[key] = change
                with self.assertRaises(ValueError):
                    closure.reconcile_model(parent, item, self.observations[parent])

    def test_negative_cost_or_false_equality_rejected(self):
        parent = "CFL_medium_instance_0"
        for key in ("objective", "row_senses"):
            with self.subTest(key=key):
                item = copy.deepcopy(self.value["representative_models"][parent])
                if key == "objective":
                    item[key]["families"]["x"]["minimum"] = -1
                else:
                    item[key] = {"=": 2400}
                with self.assertRaises(ValueError):
                    closure.reconcile_model(parent, item, self.observations[parent])

    def test_published_outputs_reproduce_without_overwrite(self):
        published = closure.ROOT / "docs/evidence/e0/pr85-closure"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "closure"
            closure.produce(output)
            self.assertEqual(
                {p.name for p in published.iterdir()},
                {p.name for p in output.iterdir()},
            )
            for path in output.iterdir():
                self.assertEqual(
                    path.read_bytes(), (published / path.name).read_bytes()
                )
            with self.assertRaises(FileExistsError):
                closure.produce(output)


if __name__ == "__main__":
    unittest.main()
