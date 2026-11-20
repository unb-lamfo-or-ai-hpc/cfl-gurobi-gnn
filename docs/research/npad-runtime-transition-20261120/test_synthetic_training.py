"""CPU implementation check for the future single-GPU technical qualification."""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location(
    "qualification", HERE / "qualify_training_license.py"
)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

try:
    import torch
    import torch_geometric  # noqa: F401
except ImportError:
    torch = None


@unittest.skipIf(
    torch is None, "pinned CPU tensor CI executes this implementation check"
)
class TrainingTests(unittest.TestCase):
    def test_three_updates_finite_gradients_and_own_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            (stage / "source").mkdir()
            fixture = os.environ.get("CFL_QUALIFICATION_SOURCE_FIXTURE")
            files = {
                "gasse.py": ROOT / "src/cfl_gnn/models/gasse.py",
                "gasse_calibrated.py": ROOT / "src/cfl_gnn/models/gasse_calibrated.py",
                "matched_gpu.py": ROOT / "src/cfl_gnn/training/matched_gpu.py",
            }
            for name, file in files.items():
                shutil.copyfile(
                    Path(fixture) / name if fixture else file, stage / "source" / name
                )
            try:
                result = worker.train_synthetic(stage, torch.device("cpu"))
            finally:
                for key in list(sys.modules):
                    if key == "cfl_gnn" or key.startswith("cfl_gnn."):
                        del sys.modules[key]
            self.assertEqual(result["compatibility"], "PASS")
            self.assertEqual(result["optimizer_updates"], 3)
            self.assertEqual(result["training_graph_draws"], 12)
            self.assertTrue(result["finite_gradients"])
            self.assertTrue(result["parameters_changed"])
            self.assertTrue(result["own_model_optimizer_roundtrip"])
            self.assertFalse(result["real_data_loaded"])
            self.assertFalse(result["historical_checkpoint_loaded"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
