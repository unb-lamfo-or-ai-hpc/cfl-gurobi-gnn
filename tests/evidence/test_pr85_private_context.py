"""Synthetic read-only context audit; never imports a solver or Torch."""

import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import collect_pr85_private_context as context  # noqa: E402

LP = b"""\\ synthetic cost example, not benchmark evidence
Maximize
 obj: 4 y_0 + 2 x_0_0 + 3 x_1_0 + 7
Subject To
 demand0: x_0_0 + x_1_0 = 1
 capacity0: 2 x_0_0 + 3 x_1_0 - 5 y_0 <= 0
Bounds
 0 <= x_0_0 <= 1
 x_1_0 free
Binaries
 y_0 x_0_0
End
"""


class PrivateContextTests(unittest.TestCase):
    def test_structure_not_economic_semantics(self):
        result = context.lp_summary(io.BytesIO(LP))
        self.assertEqual(result["source_sense"], "MAXIMIZE")
        self.assertEqual(result["required_effective_sense"], "MINIMIZE")
        self.assertEqual(result["objective"]["constant"], 7)
        self.assertEqual(result["variables_observed"], 3)
        self.assertEqual(result["explicit_binary_variables"], 2)
        self.assertEqual(result["remaining_continuous_by_linear_lp_default"], 1)
        self.assertEqual(result["row_senses"], {"=": 1, "<=": 1})
        self.assertFalse(result["full_semantics_qualified"])
        self.assertEqual(result["economic_units"], "not_encoded_or_inferred")
        self.assertNotIn("x_0_0", str(result))
        self.assertNotIn("capacity0", str(result))

    def test_wrapped_objective_and_rows(self):
        wrapped = LP.replace(b" + 3 x_1_0", b"\n + 3 x_1_0")
        wrapped = wrapped.replace(b" - 5 y_0", b"\n - 5 y_0")
        self.assertEqual(
            context.lp_summary(io.BytesIO(LP))["objective"],
            context.lp_summary(io.BytesIO(wrapped))["objective"],
        )

    def test_signed_exponents_and_implicit_coefficients(self):
        terms, constant = context.linear("- x_1 + 2e-3 y_0 - .5")
        self.assertEqual(terms, [("x_1", -1), ("y_0", 0.002)])
        self.assertEqual(constant, -0.5)

    def test_unsupported_syntax_fails_closed(self):
        for bad in (b" x_1 * x_2", b"[ x_1 ^ 2 ]", b"x_1 +", b"1e999 x_0"):
            with self.assertRaises(ValueError):
                context.linear(bad.decode())

    def test_missing_end_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete_lp_file"):
            context.lp_summary(io.BytesIO(LP.replace(b"End", b"")))

    def test_conflicting_domain_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlapping_lp_domains"):
            context.lp_summary(io.BytesIO(LP.replace(b"End", b"Generals\ny_0\nEnd")))

    def test_nonconstant_rhs_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonconstant_lp_rhs"):
            context.lp_summary(io.BytesIO(LP.replace(b"= 1", b"= y_0")))

    def test_training_report_bound_to_checkpoint_and_contract(self):
        plan, report, model = self.fixture()
        result = context.report_summary(plan, report, model, "easy")
        self.assertTrue(result["train_only_prenorm_attested_by_hashed_report"])
        self.assertFalse(result["historical_fit_replayed"])
        self.assertEqual(result["pos_weight"], 400)
        self.assertEqual(result["epochs_completed"], 100)

    def test_test_exposure_not_hidden(self):
        plan, report, model = self.fixture()
        report["test_graphs_loaded"] = 1
        with self.assertRaisesRegex(ValueError, "historical_report_gate"):
            context.report_summary(plan, report, model, "easy")

    def test_incomplete_prenorm_is_not_promoted(self):
        plan, report, model = self.fixture()
        report["prenorm_audit"] = {}
        self.assertFalse(
            context.report_summary(plan, report, model, "easy")[
                "train_only_prenorm_attested_by_hashed_report"
            ]
        )

    def test_report_identity_mutations_rejected(self):
        plan, report, model = self.fixture()
        for key, value in (
            ("training_contract_sha256", "x"),
            ("selected_probability_threshold", 0.8),
            ("threshold_source", "test"),
            ("pos_weight", float("nan")),
            ("epochs_completed", True),
        ):
            bad = copy.deepcopy(report)
            bad[key] = value
            with self.assertRaises(ValueError):
                context.report_summary(plan, bad, model, "easy")

    def test_missing_frozen_document_before_any_data_read(self):
        with self.assertRaisesRegex(ValueError, "request_protocol"):
            context.collect(Path("not_a_real_data_root"), {})

    def test_oversized_compressed_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "lp_line_limit"):
            list(context.bounded_lines(io.BytesIO(b"x" * (1024**2 + 1))))

    def test_transfer_hash_and_scope_rejected(self):
        request = {"models": {}, "parents": {}}
        result = {
            "protocol_id": context.PROTOCOL,
            "request_sha256": context.digest(
                json.dumps(request, sort_keys=True).encode()
            ),
            "training_reports": {},
            "representative_models": {},
            "optimization_runs_added": 0,
            "training_runs_added": 0,
            "submissions_added": 0,
            "raw_model_text_included": False,
            "private_paths_included": False,
            "new_comparison_admitted": False,
            "scientific_reporting_eligible": False,
        }
        raw = json.dumps(result).encode()
        self.assertEqual(context.review(raw, context.digest(raw), request), result)
        with self.assertRaisesRegex(ValueError, "receipt_hash"):
            context.review(raw, "0" * 64, request)
        result["new_comparison_admitted"] = True
        raw = json.dumps(result).encode()
        with self.assertRaisesRegex(ValueError, "receipt_scope"):
            context.review(raw, context.digest(raw), request)

    def test_complete_synthetic_collection_and_nested_review(self):
        plan, report, model = self.fixture()
        plan_raw, report_raw = json.dumps(plan).encode(), json.dumps(report).encode()
        model.update(
            plan_sha256=context.digest(plan_raw),
            report_sha256=context.digest(report_raw),
        )
        request = {
            "protocol_id": context.PROTOCOL,
            "models": {"easy": model, "mixed": model},
            "parents": {
                p: context.digest(LP)
                for p in ("CFL_easy_instance_0", "CFL_medium_instance_0")
            },
            "source_sha256_lf": {
                n: context.digest(
                    Path(context.__file__)
                    .with_name(n)
                    .read_bytes()
                    .replace(b"\r\n", b"\n")
                )
                for n in (
                    "collect_pr85_private_context.py",
                    "verify_sprint_c_artifacts.py",
                    "audit_sprint_c_inputs.py",
                )
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data"
            (root / "analysis").mkdir(parents=True)
            (root / "analysis/gasse_training_plan.json").write_bytes(plan_raw)
            (root / "analysis/gasse_training_report.json").write_bytes(report_raw)
            for parent in request["parents"]:
                directory = (
                    root
                    / "raw/MILPBench/CFL"
                    / ("CFL_" + parent.split("_")[1] + "_instance")
                    / "LP"
                )
                directory.mkdir(parents=True)
                (directory / (parent + ".lp")).write_bytes(LP)
            result = context.collect(root, request)
        self.assertTrue(
            all(
                v["train_only_prenorm_attested_by_hashed_report"]
                for v in result["training_reports"].values()
            )
        )
        self.assertTrue(
            all(
                v["variables_observed"] == 3
                for v in result["representative_models"].values()
            )
        )
        raw = json.dumps(result).encode()
        self.assertEqual(context.review(raw, context.digest(raw), request), result)

    @staticmethod
    def fixture():
        model = {
            "plan_sha256": "a" * 64,
            "report_sha256": "b" * 64,
            "checkpoint_sha256": "c" * 64,
            "checkpoint_selection": "minimum_validation_weighted_bce",
            "threshold_source": "maximum_validation_f1",
            "threshold": 0.9,
        }
        plan = {
            "contract_sha256": "d" * 64,
            "records": [{"role": "train"}, {"role": "validation"}],
        }
        report = {
            "training_contract_sha256": "d" * 64,
            "outputs": {"checkpoint": {"sha256": "c" * 64}},
            "gate_status": "passed",
            "test_graphs_loaded": 0,
            "checkpoint_selection": model["checkpoint_selection"],
            "threshold_source": model["threshold_source"],
            "selected_probability_threshold": 0.9,
            "pos_weight": 400,
            "epochs_completed": 100,
            "prenorm_audit": {
                "validation_or_test_used": False,
                "training_graphs": 1,
                "method": "streaming_population_moments_all_training_graphs",
            },
        }
        return plan, report, model


if __name__ == "__main__":
    unittest.main()
