"""Synthetic binding regressions; no access to private data or solver."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import bind_pr86_existing_starts as binding  # noqa: E402


class BindingTests(unittest.TestCase):
    def receipt(self):
        _, sources = binding.existing.review.reviewed()
        sources = {r["parent"]: r for r in sources if r["cohort"] == "mixed"}
        selected = binding.proposal.numeric.selected_parents(
            binding.proposal.numeric.source_receipt()
        )
        parents = []
        for parent in binding.existing.flow.CASES:
            row, record = sources[parent], selected[parent]
            parents.append(
                {
                    "parent": parent,
                    "role": "test",
                    "cohort": "mixed",
                    "mip_sha256": record["mip_sha256_declared"],
                    "root_sha256": record["root"]["sha256"],
                    "prediction_sha256": row["prediction_sha256"],
                    "selected_support": row["selected_support"],
                    "positive_assignments": min(
                        row["tp"] + row["fp"], row["selected_support"]
                    ),
                    "binary_variables": row["n_targets"],
                    "effective_objective_sense": "MINIMIZE",
                    "binary_identity_verified": True,
                    "start_feasibility_qualified": False,
                    "root_precomputation_seconds": None,
                    **dict.fromkeys(
                        (
                            "private_starts_sha256",
                            "gnn_assignment_sha256",
                            "lp_assignment_sha256",
                        ),
                        "a" * 64,
                    ),
                }
            )
        return {
            "protocol_id": binding.PROTOCOL,
            "source_commit": "1" * 40,
            "source_inference_sha256": binding.existing.review.SHA,
            "merged_pr85_commit": binding.MERGED_PR85,
            "parents": parents,
            "existing_starts_recomputed_and_bound": True,
            **dict.fromkeys(binding.ZERO, 0),
            **dict.fromkeys(binding.FALSE, False),
        }

    def test_public_review_exact_schema_hash_scope_and_parent_count(self):
        value = self.receipt()
        raw = binding.proposal.encoded(value)
        self.assertEqual(
            len(binding.validate(raw, binding.proposal.digest(raw))["parents"]), 10
        )
        for mutation in (
            lambda v: v.update(raw_predictions=[]),
            lambda v: v.update(solver_execution_admitted=True),
            lambda v: v.update(forwards_added=True),
            lambda v: v["parents"].pop(),
            lambda v: v["parents"][0].update(positive_assignments=0),
            lambda v: v["parents"][0].update(private_path="forbidden"),
        ):
            changed = copy.deepcopy(value)
            mutation(changed)
            raw = binding.proposal.encoded(changed)
            with self.assertRaises(ValueError):
                binding.validate(raw, binding.proposal.digest(raw))
        with self.assertRaisesRegex(ValueError, "binding_hash"):
            binding.validate(binding.proposal.encoded(value), "0" * 64)

    def fixture(self):
        sys.path.insert(0, str(binding.proposal.ROOT / "src"))
        from cfl_gnn.experiments.pr58_guidance import (
            class_aware_gnn_assignments,
            matched_root_lp_assignments,
        )

        model = binding.existing.flow.plan()["models"]["mixed"]
        predictions = [
            {"variable_name": "x0", "probability": 1.0, "predicted_value": 1},
            {"variable_name": "x1", "probability": 0.0, "predicted_value": 0},
        ]
        gnn = class_aware_gnn_assignments(predictions, fraction=0.1, absolute_cap=20000)
        lp = matched_root_lp_assignments(
            ["x0", "x1"], [0.1, 0.9], support=1, positive_assignments=1
        )
        payload = {
            "parent": "CFL_medium_instance_0",
            "role": "test",
            "cohort": "mixed",
            "checkpoint_sha256": model["checkpoint_sha256"],
            "threshold": model["threshold"],
            "submitted_to_solver": False,
            "target_labels_included": False,
            "predictions": predictions,
            "gnn_partial_start": gnn,
            "root_lp_matched_partial_start": lp,
        }
        root = {
            "variable_names": ["x0", "x1", "continuous"],
            "relaxation_vector": [0.1, 0.9, 2.0],
            "effective_objective_sense": "MINIMIZE",
            "capture_method": "first_optimal_root_gurobi_mipnode",
        }
        for key, source in (
            ("variable_order_sha256", "variable_names"),
            ("vector_sha256", "relaxation_vector"),
        ):
            root[key] = binding.proposal.digest(
                binding.existing.flow.meta.canonical(root[source])
            )
        row = {"parent": payload["parent"], "n_targets": 2, "selected_support": 1}
        return payload, row, root, {"x0", "x1"}

    def test_medium_binding_reuses_policy_not_identical_indices(self):
        gnn, lp = binding.bind(*self.fixture())
        self.assertEqual(gnn["selected_support"], lp["selected_support"])
        self.assertEqual(gnn["positive_assignments"], lp["positive_assignments"])
        self.assertEqual(gnn["assignments"][0]["variable_name"], "x0")
        self.assertEqual(lp["assignments"][0]["variable_name"], "x1")

    def test_continuous_and_missing_binary_rejected(self):
        for binary in ({"x0", "continuous"}, {"x0"}, {"x0", "x1", "x2"}):
            payload, row, root, _ = self.fixture()
            with self.assertRaisesRegex(ValueError, "binary_identity"):
                binding.bind(payload, row, root, binary)

    def test_changed_root_sense_order_vector_and_threshold_rejected(self):
        for field, value in (
            ("effective_objective_sense", "MAXIMIZE"),
            ("capture_method", "model_relax"),
            ("variable_order_sha256", "0" * 64),
            ("vector_sha256", "0" * 64),
        ):
            payload, row, root, binary = self.fixture()
            root[field] = value
            with self.assertRaises(ValueError):
                binding.bind(payload, row, root, binary)
        payload, row, root, binary = self.fixture()
        payload["threshold"] = 0.5
        with self.assertRaises(ValueError):
            binding.bind(payload, row, root, binary)

    def test_binary_parser_bounded_and_separate_from_continuous(self):
        names = binding.domain(
            ["Maximize\n", "x0 + continuous\n", "Binaries\n", "x0 x1\n", "End\n"]
        )
        self.assertEqual(names, {"x0", "x1"})
        for lines in (
            ["Binaries", "x0 x0", "End"],
            ["Binaries", "x0"],
            ["Binaries", "1", "End"],
        ):
            with self.assertRaises(ValueError):
                binding.domain(lines)

    def test_zero_execution_contract_and_ten_parent_selection(self):
        self.assertEqual(len(binding.existing.flow.CASES), 10)
        self.assertEqual(sum("_medium_" in p for p in binding.existing.flow.CASES), 4)
        self.assertIn("solver_execution_admitted", binding.FALSE)
        self.assertIn("forwards_added", binding.ZERO)

    def test_unexpected_abstention_is_not_silently_excluded(self):
        payload, row, root, binary = self.fixture()
        payload = copy.deepcopy(payload)
        for prediction in payload["predictions"]:
            prediction.update(probability=0.0, predicted_value=0)
        with self.assertRaises(ValueError):
            binding.bind(payload, row, root, binary)


if __name__ == "__main__":
    unittest.main()
