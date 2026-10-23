"""Installed inference review and no-solver start-binding regressions."""

import ast
import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import prepare_e0_easy_starts as binding  # noqa: E402
import review_e0_job3505 as review  # noqa: E402


class Job3505Tests(unittest.TestCase):
    def test_installed_receipt_and_effects(self):
        value, rows = review.reviewed()
        summary, effects = review.summarize(rows)
        self.assertEqual(value["job_id"], "3505")
        self.assertEqual(len(rows), 20)
        self.assertEqual([r["parents"] for r in summary], [6, 6, 4, 4])
        self.assertEqual(sum(r["mixed_minus_easy_f1_score"] > 0 for r in effects), 10)
        self.assertAlmostEqual(summary[2]["macro_f1_score"], 0.18775035450675115)
        self.assertAlmostEqual(summary[3]["macro_f1_score"], 0.6882829967699693)

    def test_exports_reproduce_and_manifest_binds(self):
        stored = review.SOURCE.parent / "job3505-results"
        manifest = json.loads((stored / "asset_hashes.json").read_text())
        for name, sha in manifest["files"].items():
            self.assertEqual(review.flow.meta.digest((stored / name).read_bytes()), sha)
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            output = Path(folder) / "review"
            review.produce(output)
            for path in output.glob("*.csv"):
                self.assertEqual(path.read_bytes(), (stored / path.name).read_bytes())

    def test_proposal_not_solver_admission(self):
        plan = review.proposal()
        self.assertEqual(plan["maximum_main_solves"], 18)
        self.assertEqual(plan["maximum_main_solver_seconds"], 64800)
        self.assertFalse(plan["resource_budget_approved"])
        self.assertFalse(plan["solver_execution_admitted"])
        self.assertEqual(plan["cohort"], "mixed")
        self.assertEqual(len(plan["parents"]), 6)

    def fixture(self):
        sys.path.insert(0, str(review.flow.c1.ROOT / "src"))
        from cfl_gnn.experiments.pr58_guidance import (
            class_aware_gnn_assignments,
            matched_root_lp_assignments,
        )

        model = review.flow.plan()["models"]["mixed"]
        predictions = [
            {"variable_name": "x", "probability": 1.0, "predicted_value": 1},
            {"variable_name": "y", "probability": 0.0, "predicted_value": 0},
        ]
        payload = {
            "parent": review.EASY[0],
            "role": "test",
            "cohort": "mixed",
            "checkpoint_sha256": model["checkpoint_sha256"],
            "threshold": model["threshold"],
            "submitted_to_solver": False,
            "target_labels_included": False,
            "predictions": predictions,
            "gnn_partial_start": class_aware_gnn_assignments(
                predictions, fraction=0.1, absolute_cap=20000
            ),
            "root_lp_matched_partial_start": matched_root_lp_assignments(
                ["x", "y"], [0.1, 0.9], support=1, positive_assignments=1
            ),
        }
        return (
            payload,
            {"parent": review.EASY[0], "n_targets": 2, "selected_support": 1},
            {"variable_names": ["x", "y"], "relaxation_vector": [0.1, 0.9]},
        )

    def test_both_existing_selections_recomputed(self):
        gnn, lp = binding.assignments(*self.fixture())
        self.assertEqual(gnn["assignments"][0]["variable_name"], "x")
        self.assertEqual(lp["assignments"][0]["variable_name"], "y")

    def test_changed_identity_or_selection_rejected(self):
        for field, value in (
            ("cohort", "easy"),
            ("threshold", 0.5),
            ("target_labels_included", True),
        ):
            payload, row, root = self.fixture()
            payload[field] = value
            with self.assertRaises(ValueError):
                binding.assignments(payload, row, root)
        payload, row, root = self.fixture()
        payload["gnn_partial_start"]["assignments"][0]["value"] = 0
        with self.assertRaises(ValueError):
            binding.assignments(payload, row, root)

    def public_fixture(self):
        _, rows = review.reviewed()
        admitted = binding.numeric.selected_parents(binding.numeric.source_receipt())
        parents = []
        for parent in review.EASY:
            source = next(
                r for r in rows if r["cohort"] == "mixed" and r["parent"] == parent
            )
            parents.append(
                {
                    "parent": parent,
                    "role": "test",
                    "cohort": "mixed",
                    "mip_sha256": admitted[parent]["mip_sha256_declared"],
                    "root_sha256": admitted[parent]["root"]["sha256"],
                    "prediction_sha256": source["prediction_sha256"],
                    "selected_support": source["selected_support"],
                    "positive_assignments": 1,
                    "private_starts_sha256": "a" * 64,
                    "gnn_assignment_sha256": "b" * 64,
                    "lp_assignment_sha256": "c" * 64,
                    "start_feasibility_qualified": False,
                    "root_precomputation_seconds": None,
                }
            )
        return {
            "protocol_id": binding.PROTOCOL,
            "source_inference_sha256": review.SHA,
            "proposal": review.proposal(),
            "parents": parents,
            "existing_starts_recomputed_and_bound": True,
            **dict.fromkeys(
                (
                    "optimization_runs_added",
                    "training_runs_added",
                    "forwards_added",
                    "scheduler_queries",
                    "submissions_added",
                ),
                0,
            ),
            **dict.fromkeys(
                (
                    "raw_predictions_exported",
                    "solver_execution_admitted",
                    "scientific_reporting_eligible",
                ),
                False,
            ),
        }

    def test_public_binding(self):
        value = self.public_fixture()
        raw = json.dumps(value).encode()
        self.assertEqual(
            len(binding.validate(raw, review.flow.meta.digest(raw))["parents"]), 6
        )
        for key, changed in (
            ("solver_execution_admitted", True),
            ("source_inference_sha256", "0" * 64),
            ("forwards_added", 1),
        ):
            bad = copy.deepcopy(value)
            bad[key] = changed
            raw = json.dumps(bad).encode()
            with self.assertRaises(ValueError):
                binding.validate(raw, review.flow.meta.digest(raw))

    def test_no_solver_or_training_in_new_code(self):
        for module in (review, binding):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(
                        node.func.attr,
                        {"optimize", "optimizeAsync", "backward", "step", "infer"},
                    )


if __name__ == "__main__":
    unittest.main()
