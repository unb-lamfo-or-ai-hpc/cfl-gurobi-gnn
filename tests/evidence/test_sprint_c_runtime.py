"""Offline regression checks; no live dataset, GPU or scheduler."""

import importlib.metadata
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import audit_sprint_c_numeric as numeric  # noqa: E402
import pr80_integrated as flow  # noqa: E402
import sprint_c_runtime as runtime  # noqa: E402


class RuntimeTests(unittest.TestCase):
    def test_existing_runtime_recorded_not_rejected(self):
        with patch.object(importlib.metadata, "version", return_value="2.1.2+cu121"):
            result = runtime.observe()
        self.assertEqual(result["packages"]["torch"], "2.1.2+cu121")
        self.assertFalse(result["minimum_torch_version_gate"])
        self.assertFalse(result["packages_modified"])

    def test_missing_and_private_metadata(self):
        with patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError,
        ):
            self.assertTrue(all(v is None for v in runtime.versions().values()))
        with patch.object(importlib.metadata, "version", return_value="private/path"):
            self.assertEqual(
                runtime.versions()["torch"], "redacted_nonstandard_version"
            )

    def test_trusted_graph_same_fd_hash_before_load_old_torch(self):
        class Graph:
            pass

        torch = SimpleNamespace(
            __version__="2.1.2+cu121",
            load=Mock(return_value=Graph()),
            set_num_threads=Mock(),
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "graph.pt"
            path.write_bytes(b"synthetic-not-a-pickle")
            with patch.dict(
                sys.modules,
                {
                    "torch": torch,
                    "torch_geometric.data": SimpleNamespace(HeteroData=Graph),
                },
            ):
                with self.assertRaisesRegex(ValueError, "graph_hash_before_load"):
                    numeric.load_graph(path, "0" * 64)
                torch.load.assert_not_called()
                graph, version = numeric.load_graph(
                    path, numeric.metadata.digest(path.read_bytes())
                )
                self.assertIsInstance(graph, Graph)
                self.assertEqual(version, "2.1.2+cu121")
                self.assertFalse(torch.load.call_args.kwargs["weights_only"])

    def test_report_binding_and_no_threshold_fallback(self):
        plan = {
            "contract_sha256": "a" * 64,
            "protocol": {
                "architecture": {"model_version": "gasse_v2_alternating_prenorm"}
            },
        }
        report = {
            "gate_status": "passed",
            "training_contract_sha256": "a" * 64,
            "test_graphs_loaded": 0,
            "checkpoint_selection": "minimum_validation_weighted_bce",
            "threshold_source": "maximum_validation_f1",
            "selected_probability_threshold": 0.4,
            "model_version": "gasse_v2_alternating_prenorm",
        }
        self.assertEqual(flow.report_binding(plan, report), 0.4)
        for key, value in (
            ("test_graphs_loaded", 1),
            ("threshold_source", "fixed"),
            ("selected_probability_threshold", float("nan")),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                flow.report_binding(plan, dict(report, **{key: value}))

    def test_sample_counts_missingness_and_quantiles(self):
        parents = numeric.selected_parents(numeric.source_receipt())
        report = {
            "parents": {p: {"state": "not_attempted_after_stop"} for p in parents}
        }
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            summary = flow.descriptive(report, output)
            self.assertEqual(summary["parents"], 54)
            self.assertEqual(summary["numerically_passed"], 0)
            self.assertIn(
                "missing", (output / "descriptive_statistics.csv").read_text()
            )
            self.assertIn(
                "CFL_medium_instance_11", (output / "parent_statistics.csv").read_text()
            )
        self.assertEqual(flow.quantile([1, 2, 3, 4], 0.25), 1.75)
        self.assertEqual(flow.quantile([7], 0.75), 7)
        for parent in flow.CASES:
            self.assertEqual(numeric.split_for(parent)[1], "validation")

    def test_package_allowlist_and_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage / "run").mkdir()
            (stage / "run/runtime.json").write_text("{}")
            (stage / "run/inference.private.log").write_text("SECRET")
            (stage / "job_id.txt").write_text("123")
            (stage / "accounting.txt").write_text("123|FAILED")
            flow.package(stage)
            first = (stage / "public_return.json").read_bytes()
            self.assertNotIn(b"SECRET", first)
            flow.package(stage)
            self.assertEqual(first, (stage / "public_return.json").read_bytes())
            (stage / "run/runtime.json").write_text('{"changed":true}')
            with self.assertRaises(ValueError):
                flow.package(stage)
            self.assertEqual(first, (stage / "public_return.json").read_bytes())

    def test_integrated_budget_no_install_or_retry(self):
        script = (SCRIPTS / "operate_pr80_integrated.sh").read_text()
        self.assertEqual(script.count("sbatch --parsable"), 1)
        for option in (
            "--gres=gpu:1",
            "--mem=32G",
            "--time=00:45:00",
            "--no-requeue",
            "--nodes=1-1",
        ):
            self.assertIn(option, script)
        self.assertLess(
            script.index('mkdir "$STAGE/submission.started"'),
            script.index("sbatch --parsable"),
        )
        for forbidden in ("pip install", "conda create", "while ", "sleep ", "-m venv"):
            self.assertNotIn(forbidden, script)

    def test_numeric_failure_retains_tables_and_skips_inference(self):
        parents = numeric.selected_parents(numeric.source_receipt())
        audit = {
            "parents": {p: {"state": "unqualified"} for p in parents},
            "cohorts": {c: {"numeric_checks_passed": False} for c in ("easy", "mixed")},
        }
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(numeric, "collect", return_value=audit),
            patch.object(flow.subprocess, "run") as child,
        ):
            output = Path(folder) / "run"
            self.assertEqual(flow.run(Path(folder), output), 2)
            child.assert_not_called()
            self.assertTrue((output / "parent_statistics.csv").is_file())
            receipt = flow.meta.strict_json((output / "integrated.json").read_bytes())
            self.assertEqual(
                receipt["inference"]["state"], "not_attempted_numeric_incomplete"
            )

    def test_existing_output_never_reused(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            self.assertRaises(FileExistsError),
        ):
            flow.run(Path(folder), Path(folder))

    def test_four_cases_and_no_training_or_solver_calls(self):
        import ast

        tree = ast.parse(Path(flow.__file__).read_text())
        forbidden = {
            "optimize",
            "optimizeAsync",
            "fit",
            "fit_prenorm",
            "backward",
            "step",
        }
        for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
            if isinstance(call.func, ast.Attribute):
                self.assertNotIn(call.func.attr, forbidden)
        self.assertEqual(len(flow.CASES), 2)


if __name__ == "__main__":
    unittest.main()
