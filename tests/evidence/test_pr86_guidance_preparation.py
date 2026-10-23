"""No GPU, Gurobi, scheduler or training is used by these offline tests."""

import ast
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_guidance_preparation as flow  # noqa: E402
import review_pr86_job3520 as review  # noqa: E402


class RootReview(unittest.TestCase):
    def test_original_bytes_and_nested_costs(self):
        raw = (review.DESTINATION / "public_return.json").read_bytes()
        _, rows, report = review.review(raw)
        self.assertEqual(len(rows), 10)
        self.assertEqual(report["observed_root_optimization_calls"], 10)
        self.assertGreater(
            report["batch_observed_wall_seconds"], report["supervisor_wall_seconds_sum"]
        )
        self.assertFalse(report["main_comparison_admitted"])
        with self.assertRaisesRegex(ValueError, "immutable_return_hash"):
            review.review(raw + b" ")

    def test_review_reproduces_every_byte_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            review.produce(review.DESTINATION / "public_return.json", output)
            for p in output.iterdir():
                self.assertEqual(
                    p.read_bytes(), (review.DESTINATION / p.name).read_bytes()
                )
            with self.assertRaises(FileExistsError):
                review.produce(review.DESTINATION / "public_return.json", output)


class Guidance(unittest.TestCase):
    def setUp(self):
        self.frozen = flow.plan("a" * 40)

    def test_proposal_reuses_mixed_model_and_ten_new_roots(self):
        self.assertEqual(self.frozen["maximum_forwards"], 10)
        self.assertEqual(self.frozen["optimization_calls"], 0)
        self.assertEqual(self.frozen["scheduler"]["gpus"], 1)
        self.assertEqual(
            self.frozen["frozen_model"]["checkpoint_sha256"],
            flow.roots.isolated.proposal.CHECKPOINT,
        )
        self.assertFalse(self.frozen["resource_budget_approved"])
        self.assertEqual(len(self.frozen["parents"]), 10)

    def test_no_optimize_training_or_cached_prediction_entrypoint(self):
        tree = ast.parse(Path(flow.__file__).read_text())
        calls = {
            n.func.attr
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        self.assertFalse(
            calls.intersection(
                {"optimize", "backward", "step", "capture_root_relaxation", "infer"}
            )
        )
        # Graph encoding is the production no-optimization function; capture
        # exists elsewhere in the module, but is not called from this function.
        import inspect

        from cfl_gnn.graph.gurobi_graph_artifact import build_graph_artifact

        body = ast.parse(inspect.getsource(build_graph_artifact))
        self.assertFalse(
            any(
                isinstance(n, ast.Attribute) and n.attr == "optimize"
                for n in ast.walk(body)
            )
        )

    def test_changed_plan_or_stage_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            stage = base / ("guidance-" + "a" * 12)
            stage.mkdir()
            flow.write(stage / "plan.json", self.frozen)
            with (
                patch.object(flow, "BASE", base),
                patch.object(flow.roots, "head", return_value="a" * 40),
            ):
                self.assertEqual(flow.load(stage), self.frozen)
                with (
                    patch.object(
                        flow,
                        "plan",
                        return_value={**self.frozen, "maximum_forwards": 11},
                    ),
                    self.assertRaises(ValueError),
                ):
                    flow.load(stage)

    def test_wrong_authorization_and_second_submit_stop_before_scheduler(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            stage = base / "guidance"
            stage.mkdir()
            flow.write(stage / "plan.json", self.frozen)
            (base / "prospective-guidance-preparation.claim").mkdir()
            with (
                patch.object(flow, "BASE", base),
                patch.object(flow, "load", return_value=self.frozen),
                patch.object(flow.roots.accounting, "host"),
                patch.object(flow, "ROOT_STAGE", review.DESTINATION),
                patch.dict(flow.os.environ, {"CONDA_DEFAULT_ENV": "tfm_env"}),
                patch.object(flow.roots.accounting, "command") as scheduler,
            ):
                with self.assertRaisesRegex(ValueError, "approved_plan_hash"):
                    flow.submit(stage, "0" * 64)
                with self.assertRaises(FileExistsError):
                    flow.submit(stage, flow.digest(flow.encoded(self.frozen)))
                scheduler.assert_not_called()

    def test_root_model_sense_and_order_are_checked(self):
        target = {
            "root_sha256": "a" * 64,
            "variable_count": 1,
            "variable_order_sha256": flow.roots.canonical_sha256(["x"]),
            "vector_sha256": flow.roots.canonical_sha256([0.25]),
            "mathematical_signature_sha256": "b" * 64,
            "model_sha256": "c" * 64,
        }
        payload = {
            **target,
            "source_mip_sha256": "c" * 64,
            "effective_objective_sense": "MINIMIZE",
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "variable_names": ["x"],
            "relaxation_vector": [0.25],
        }
        with (
            patch.object(flow.roots, "sha256_file", return_value="a" * 64),
            patch.object(
                flow.historical.legacy.numeric,
                "bounded_json_gzip",
                return_value=payload,
            ),
        ):
            self.assertEqual(flow.root_input(0, target), payload)
            payload["effective_objective_sense"] = "MAXIMIZE"
            with self.assertRaisesRegex(ValueError, "root_sense"):
                flow.root_input(0, target)

    def fixture(self):
        rows = []
        for target in self.frozen["parents"]:
            rows.append(
                {
                    "parent": target["parent"],
                    "model_sha256": target["model_sha256"],
                    "root_sha256": target["root_sha256"],
                    **{
                        k: "b" * 64
                        for k in (
                            "graph_sha256",
                            "prediction_sha256",
                            "private_starts_sha256",
                            "M1_assignment_sha256",
                            "M2_assignment_sha256",
                        )
                    },
                    "checkpoint_sha256": self.frozen["frozen_model"][
                        "checkpoint_sha256"
                    ],
                    "binary_variables": 100,
                    "selected_support": 10,
                    "positive_assignments": 1,
                    "abstained": False,
                    "effective_objective_sense": "MINIMIZE",
                    "regions_seconds": dict.fromkeys(flow.REGIONS, 1.0),
                    "forward_seconds_nested_in_inference": 0.5,
                    "gpu_peak_allocated_bytes": 100,
                    "gpu_peak_reserved_bytes": 100,
                    "forward_calls": 1,
                    "optimization_calls": 0,
                    "training_runs": 0,
                    "scientific_reporting_eligible": False,
                }
            )
        return {
            "protocol_id": flow.PROTOCOL,
            "plan": self.frozen,
            "plan_sha256": flow.digest(flow.encoded(self.frozen)),
            "accounting": flow.roots.accounting.parse_accounting(
                "123|COMPLETED|0:0|80|00:50|8|64G|", "123"
            ),
            "child": {
                "job_id": "123",
                "rows": rows,
                "complete": True,
                "failure_type": None,
                "shared_setup_seconds": 10,
                "child_observed_wall_seconds": 65,
                "runtime": {},
                "scientific_reporting_eligible": False,
            },
            "supervision": {
                "guard_stop": None,
                "child_exit_code": 0,
                "memory_failure_diagnostic": None,
                "peak_is_sampled_not_exact": True,
                "sampled_cgroup_peak_bytes": 1000,
                "supervisor_wall_seconds": 70,
            },
            "private_log": None,
            "raw_logs_included": False,
            "raw_predictions_included": False,
            "scientific_reporting_eligible": False,
        }

    def test_complete_partial_and_absent_child_returns(self):
        value = self.fixture()
        self.assertTrue(flow.validate_return(flow.encoded(value))["ready"])
        value["child"]["rows"] = value["child"]["rows"][:2]
        value["child"].update(complete=False, failure_type="ValueError")
        self.assertFalse(flow.validate_return(flow.encoded(value))["ready"])
        value["child"] = None
        self.assertFalse(flow.validate_return(flow.encoded(value))["ready"])

    def test_schema_scope_counts_identity_timing_rejected(self):
        value = self.fixture()
        for key, replacement in (
            ("optimization_calls", 1),
            ("forward_calls", True),
            ("effective_objective_sense", "MAXIMIZE"),
            ("checkpoint_sha256", "0" * 64),
            ("selected_support", 11),
            ("forward_seconds_nested_in_inference", 2),
        ):
            corrupt = copy.deepcopy(value)
            corrupt["child"]["rows"][0][key] = replacement
            with self.assertRaises(ValueError, msg=key):
                flow.validate_return(flow.encoded(corrupt))
        value["child"]["child_observed_wall_seconds"] = 1
        with self.assertRaisesRegex(ValueError, "disjoint_costs"):
            flow.validate_return(flow.encoded(value))

    def test_child_failure_stops_loop_and_preserves_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            (stage / "run").mkdir()
            fake_torch = Mock()
            fake_torch.cuda.is_available.return_value = False
            with (
                patch.object(flow, "load", return_value=self.frozen),
                patch.object(flow, "approved"),
                patch.object(flow, "allocation", return_value=("123", None)),
                patch.dict(sys.modules, {"torch": fake_torch}),
                patch.object(flow, "one_parent") as parent,
            ):
                with self.assertRaisesRegex(ValueError, "one_gpu"):
                    flow.child(stage)
                parent.assert_not_called()
            summary = flow.parsed(stage / "run/child.json")
            self.assertFalse(summary["complete"])
            self.assertEqual(summary["failure_type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
