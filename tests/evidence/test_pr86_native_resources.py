"""Exercise the real adapter with a fake Gurobi API, never a licensed solver."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
from pr86_native_model import NativeModel  # noqa: E402


class Resources(unittest.TestCase):
    def api(self):
        self.env = Mock()
        self.model = Mock(ModelSense=-1, Params=SimpleNamespace(), NumConstrs=1)
        self.model.getVars.return_value = [
            SimpleNamespace(VarName="x", LB=0, UB=1, VType="B")
        ]
        return SimpleNamespace(
            Env=Mock(return_value=self.env),
            read=Mock(return_value=self.model),
            GRB=SimpleNamespace(MINIMIZE=1),
        )

    def test_real_constructor_and_idempotent_close(self):
        api = self.api()
        with patch.dict(sys.modules, gurobipy=api):
            backend = NativeModel("synthetic", "gurobi", 3600)
        self.assertEqual(backend.binary, {"x"})
        self.assertEqual(backend.original_sense, "MAXIMIZE")
        self.assertEqual(self.model.ModelSense, 1)
        backend.close()
        backend.close()
        self.model.dispose.assert_called_once()
        self.env.dispose.assert_called_once()

    def test_all_constructor_failures_release_owned_resources(self):
        for stage in ("env", "start", "read", "update", "domains"):
            with self.subTest(stage=stage):
                api = self.api()
                error = RuntimeError("original")
                if stage == "env":
                    api.Env.side_effect = error
                elif stage == "start":
                    self.env.start.side_effect = error
                elif stage == "read":
                    api.read.side_effect = error
                elif stage == "update":
                    self.model.update.side_effect = error
                else:
                    self.model.getVars.return_value[0].UB = 2
                    error = ValueError
                with (
                    patch.dict(sys.modules, gurobipy=api),
                    self.assertRaises(
                        error if isinstance(error, type) else type(error)
                    ),
                ):
                    NativeModel("synthetic", "gurobi", 3600)
                self.assertEqual(self.env.dispose.call_count, int(stage != "env"))
                self.assertEqual(
                    self.model.dispose.call_count, int(stage in ("update", "domains"))
                )

    def test_disposal_failure_still_releases_environment(self):
        api = self.api()
        with patch.dict(sys.modules, gurobipy=api):
            backend = NativeModel("synthetic", "gurobi", 3600)
        self.model.dispose.side_effect = RuntimeError("dispose")
        with self.assertRaisesRegex(RuntimeError, "dispose"):
            backend.close()
        self.env.dispose.assert_called_once()
        backend.close()

    def test_initialization_error_is_not_masked_by_cleanup_failure(self):
        api = self.api()
        self.model.update.side_effect = RuntimeError("original")
        self.model.dispose.side_effect = RuntimeError("cleanup")
        with (
            patch.dict(sys.modules, gurobipy=api),
            self.assertRaisesRegex(RuntimeError, "original"),
        ):
            NativeModel("synthetic", "gurobi", 3600)
        self.env.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
