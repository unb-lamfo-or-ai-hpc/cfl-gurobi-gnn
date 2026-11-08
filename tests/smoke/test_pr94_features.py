"""CPU tensor/encoder parity fixtures; no license, GPU, real data or training."""

import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/evidence"))

from cfl_gnn.artifacts.schemas import (  # noqa: E402
    ConstraintFeatures,
    ModelFeatures,
    VariableFeatures,
)
from cfl_gnn.graph.build_dataset import build_heterodata  # noqa: E402
from cfl_gnn.graph.label_free_gurobi import build_features  # noqa: E402
from cfl_gnn.models.versioning import model_class  # noqa: E402

flow = importlib.import_module("pr94_isolated_preparation")
science = importlib.import_module("pr94_preparation_science")


class FeatureParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.mip = self.base / "synthetic.lp"
        self.mip.write_bytes(b"fixture_only_no_solver_parser")
        self.names = ["x0", "x1", "x2"]
        self.types = np.array(["B", "C", "B"])
        self.lower = np.array([0.0, 0.0, 0.0])
        self.upper = np.array([1.0, np.inf, 1.0])
        self.objective = np.array([1.0, -0.3, 0.2])
        self.row = np.array([0, 0, 1, 1])
        self.col = np.array([0, 1, 1, 2])
        self.coefficients = np.array([1.0, 2.0, -3.0, 4.0])
        self.vector = [0.25, 0.5, 0.75]
        self.root = {
            "source_mip_sha256": flow.file_sha(self.mip),
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "effective_objective_sense": "MINIMIZE",
            "variable_names": self.names,
            "variable_order_sha256": flow.canonical_sha(self.names),
            "relaxation_vector": self.vector,
            "vector_sha256": flow.canonical_sha(self.vector),
            "mathematical_signature_sha256": "a" * 64,
        }
        self.fake_gp = types.ModuleType("gurobipy")
        self.fake_gp.GRB = SimpleNamespace(MINIMIZE=1)
        self.fake_gp.Env = lambda **kw: self.context(SimpleNamespace())
        self.fake_gp.read = lambda *a, **k: self.context(self.model())
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {"gurobipy": self.fake_gp}).start()

    def context(self, value):
        class Context:
            def __enter__(self):
                return value

            def __exit__(self, *args):
                pass

        return Context()

    def model(self):
        variables = [
            SimpleNamespace(VarName=n, VType=t, LB=lb, UB=ub, Obj=o)
            for n, t, lb, ub, o in zip(
                self.names, self.types, self.lower, self.upper, self.objective
            )
        ]
        constraints = [
            SimpleNamespace(Sense="<", RHS=2.0),
            SimpleNamespace(Sense=">", RHS=-1.0),
        ]
        coo = SimpleNamespace(row=self.row, col=self.col, data=self.coefficients)
        return SimpleNamespace(
            ModelSense=1,
            ObjCon=0,
            NumQNZs=0,
            NumQConstrs=0,
            NumGenConstrs=0,
            NumSOS=0,
            update=lambda: None,
            getVars=lambda: variables,
            getConstrs=lambda: constraints,
            getA=lambda: SimpleNamespace(tocoo=lambda: coo),
        )

    def training_features(self, labels):
        return build_heterodata(
            ModelFeatures(
                num_vars=3,
                num_constrs=2,
                num_binary=2,
                num_integer=0,
                num_continuous=1,
                obj_sense="MINIMIZE",
                obj_offset=0,
            ),
            VariableFeatures(
                types=self.types,
                lower_bounds=self.lower,
                upper_bounds=self.upper,
                obj_coeffs=self.objective,
            ),
            ConstraintFeatures(
                senses=np.array(["<", ">"]),
                rhs_values=np.array([2.0, -1.0]),
                row_norms=np.sqrt(np.array([5.0, 25.0])),
            ),
            np.array([self.row, self.col]),
            self.coefficients,
            np.array(labels),
            np.array(self.vector),
            0,
            0,
            False,
            -1,
            "synthetic",
            {},
            strict=True,
            edge_layout="constraint_variable",
        )

    def features(self):
        return build_features(self.mip, flow.file_sha(self.mip), self.root)

    def test_label_free_features_equal_training_encoder_channels_exactly(self):
        graph, order, metadata = self.features()
        training = self.training_features([1.0, 0.0, 0.0])
        other = self.training_features([0.0, 100.0, 1.0])
        self.assertEqual(order, ["x0", "x2"])
        for key in ("variable", "constraint"):
            self.assertTrue(torch.equal(graph[key].x, training[key].x))
            self.assertTrue(torch.equal(graph[key].x, other[key].x))
        for key in (
            ("variable", "rev_coef", "constraint"),
            ("constraint", "coef", "variable"),
        ):
            self.assertTrue(
                torch.equal(graph[key].edge_index, training[key].edge_index)
            )
            self.assertTrue(torch.equal(graph[key].edge_attr, training[key].edge_attr))
        self.assertNotIn("y", graph["variable"])
        self.assertFalse(metadata["target_labels_loaded"])
        science.graph_checks(graph, self.root, order)

    def test_feature_serialization_preserves_values_and_has_no_targets(self):
        graph, order, _ = self.features()
        path = self.base / "graph.pt"
        with path.open("xb") as stream:
            torch.save(graph, stream)
        with path.open("rb") as stream:
            restored = torch.load(stream, map_location="cpu", weights_only=False)
        self.assertEqual(science.tensor_sha(graph), science.tensor_sha(restored))
        science.graph_checks(restored, self.root, order)
        restored["variable"].y = torch.zeros(3)
        with self.assertRaisesRegex(ValueError, "target_label"):
            science.graph_checks(restored, self.root, order)

    def test_wrong_root_channel_binary_order_or_edges_is_rejected(self):
        graph, order, _ = self.features()
        with self.assertRaisesRegex(ValueError, "binary_order"):
            science.graph_checks(graph, self.root, order[::-1])
        graph["variable"].x[0, 6] += 0.1
        with self.assertRaisesRegex(ValueError, "root_feature"):
            science.graph_checks(graph, self.root, order)
        graph, order, _ = self.features()
        graph["constraint", "coef", "variable"].edge_index = graph[
            "constraint", "coef", "variable"
        ].edge_index.flip(1)
        with self.assertRaisesRegex(ValueError, "edge_order"):
            science.graph_checks(graph, self.root, order)

    def test_model_keeps_prefix_handling_frozen_parameters_and_prenorm(self):
        torch.manual_seed(42)
        model = model_class("gasse_v2_alternating_prenorm")(
            var_in_dim=7,
            cons_in_dim=5,
            edge_dim=1,
            hidden_dim=32,
            num_layers=2,
        )
        path = self.base / "checkpoint.pt"
        torch.save({"module." + k: v for k, v in model.state_dict().items()}, path)
        with patch.object(flow, "CHECKPOINT", flow.file_sha(path)):
            frozen = science.checkpoint_model(path, torch.device("cpu"))
        before = {k: v.clone() for k, v in frozen.state_dict().items()}
        graph, _, _ = self.features()
        edge = graph["variable", "rev_coef", "constraint"]
        with torch.no_grad():
            logits = frozen(
                x_var=graph["variable"].x,
                x_cons=graph["constraint"].x,
                edge_v2c=edge.edge_index,
                edge_attr=edge.edge_attr,
                binary_mask=graph["variable"].is_discrete.bool(),
            )
        self.assertEqual(logits.numel(), 2)
        self.assertTrue(torch.isfinite(logits).all())
        self.assertFalse(frozen.training)
        self.assertTrue(all(not p.requires_grad for p in frozen.parameters()))
        self.assertTrue(
            all(torch.equal(v, frozen.state_dict()[k]) for k, v in before.items())
        )
        with self.assertRaisesRegex(ValueError, "checkpoint_hash"):
            science.checkpoint_model(path, torch.device("cpu"))

    def test_full_guidance_fixture_round_trip_single_forward_and_matched_Starts(self):
        class SyntheticForward(torch.nn.Module):
            calls = 0

            def forward(self, **kwargs):
                self.calls += 1
                return torch.tensor([10.0, -10.0])

        model = SyntheticForward()
        target = {"model_sha256": flow.file_sha(self.mip), "root_sha256": "b" * 64}
        runtime = SimpleNamespace(
            NativeModel=lambda *a: SimpleNamespace(model=object(), close=lambda: None),
            signature=lambda model: "a" * 64,
        )
        calls = []
        with (
            patch.object(science, "api", return_value=runtime),
            patch.object(torch.cuda, "reset_peak_memory_stats"),
            patch.object(torch.cuda, "synchronize"),
            patch.object(torch.cuda, "max_memory_allocated", return_value=0),
            patch.object(torch.cuda, "max_memory_reserved", return_value=0),
        ):
            result = science.guidance_one(
                "fixture",
                target,
                self.mip,
                self.root,
                model,
                torch.device("cpu"),
                self.base,
                lambda: calls.append("forward"),
            )
        self.assertEqual(model.calls, 1)
        self.assertEqual(calls, ["forward"])
        self.assertEqual(result["selected_support"], 1)
        self.assertEqual(result["positive_assignments"], 1)
        self.assertEqual(result["optimization_calls"], 0)
        self.assertTrue(result["graph_round_trip"])
        starts = flow.read(self.base / "starts.private.json")
        self.assertNotEqual(
            starts["gnn"]["assignments"][0]["variable_name"],
            starts["root_lp"]["assignments"][0]["variable_name"],
        )
        flow.validate_starts(starts["gnn"], starts["root_lp"], 2)


if __name__ == "__main__":
    unittest.main()
