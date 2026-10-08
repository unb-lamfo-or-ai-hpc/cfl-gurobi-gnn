"""No scheduler, installed solver, dataset or package installation in tests."""

import ast
import importlib.metadata
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import audit_sprint_c_numeric as audit  # noqa: E402
import sprint_c_runtime as runtime  # noqa: E402


class RuntimeTests(unittest.TestCase):
    def test_package_preserves_partial_and_rejects_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage / "run/results").mkdir(parents=True)
            numeric = {
                "protocol_id": audit.PROTOCOL,
                "source_artifact_receipt_sha256": audit.RECEIPT_SHA,
                "implementation_sha256": runtime.hashlib.sha256(
                    Path(audit.__file__).read_bytes()
                ).hexdigest(),
                "parents": {
                    p: {"state": "not_attempted_after_stop"}
                    for p in audit.selected_parents(audit.source_receipt())
                },
                "training_admitted": False,
                "scientific_reporting_eligible": False,
                "raw_logs_included": False,
                "optimization_runs_added": 0,
            }
            (stage / "run/results/numeric.json").write_text(json.dumps(numeric))
            value = {
                "protocol_id": "sprint_c_cpu_runtime_preflight_v1",
                "passed": True,
                "python": "3.10.20",
                "package_versions": runtime.EXPECTED,
            }
            for name in ("prepared", "presubmit", "batch"):
                (stage / f"runtime-{name}.json").write_text(json.dumps(value))
            (stage / "environment.freeze.txt").write_text("synthetic")
            (stage / "job_id.txt").write_text("9999")
            result = runtime.package(stage)
            self.assertFalse(result["training_admitted"])
            first = (stage / "audit-return.json").read_bytes()
            self.assertEqual(runtime.package(stage), result)
            self.assertEqual((stage / "audit-return.json").read_bytes(), first)
            numeric["training_admitted"] = True
            (stage / "run/results/numeric.json").write_text(json.dumps(numeric))
            with self.assertRaises(ValueError):
                runtime.package(stage)
            self.assertEqual((stage / "audit-return.json").read_bytes(), first)

    def test_expected_versions(self):
        runtime.check_versions(dict(runtime.EXPECTED), (3, 10, 20))

    def test_old_missing_cuda_and_drift_rejected(self):
        for version in (None, "2.1.2+cu121", "2.6.0", "2.9.1", "2.10.0+cu126"):
            value = dict(runtime.EXPECTED, torch=version)
            with self.subTest(version=version), self.assertRaises(ValueError):
                runtime.check_versions(value, (3, 10, 20))
        with self.assertRaises(ValueError):
            runtime.check_versions(runtime.EXPECTED, (3, 11))

    def test_missing_and_nonstandard_versions(self):
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

    def test_old_runtime_stops_before_smoke(self):
        with (
            patch.object(
                runtime,
                "versions",
                return_value=dict(runtime.EXPECTED, torch="2.1.2+cu121"),
            ),
            patch.object(runtime, "smoke") as smoke,
        ):
            result = runtime.probe()
        smoke.assert_not_called()
        self.assertFalse(result["passed"])
        self.assertEqual(result["stage"], "environment_metadata")
        self.assertEqual(result["package_versions"]["torch"], "2.1.2+cu121")

    def test_failure_does_not_export_exception_text(self):
        with (
            patch.object(runtime, "versions", return_value=runtime.EXPECTED),
            patch.object(runtime.sys, "version_info", (3, 10, 20)),
            patch.object(runtime, "smoke", side_effect=RuntimeError("PRIVATE")),
        ):
            result = runtime.probe()
        self.assertNotIn("PRIVATE", str(result))
        self.assertFalse(result["passed"])
        self.assertEqual(result["stage"], "synthetic_restricted_load_and_imports")

    def test_pass_not_training_admission(self):
        with (
            patch.object(runtime, "versions", return_value=runtime.EXPECTED),
            patch.object(runtime.sys, "version_info", (3, 10, 20)),
            patch.object(runtime, "smoke"),
        ):
            result = runtime.probe()
        self.assertTrue(result["passed"])
        self.assertFalse(result["training_admitted"])
        self.assertEqual(result["dataset_graph_loads"], 0)

    def test_no_solver_or_scheduler_calls(self):
        tree = ast.parse(Path(runtime.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(
                    node.func.attr,
                    {"optimize", "optimizeAsync", "Env", "Model", "run", "Popen"},
                )

    def test_preflight_before_claim_and_batch_bound(self):
        script = (SCRIPTS / "operate_pr80_numeric.sh").read_text()
        self.assertLess(
            script.index('"$STAGE/runtime-presubmit.json"'),
            script.index('mkdir "$STAGE/submission.started"'),
        )
        self.assertLess(
            script.index('"$STAGE/runtime-batch.json"'),
            script.index('exec "$PR80_PYTHON"'),
        )
        self.assertIn('PR80_PYTHON="$STAGE/venv/bin/python3"', script)
        self.assertIn('timeout 30s "$PR80_PYTHON"', script)
        self.assertIn('test ! -e "$STAGE/venv"', script)
        self.assertIn("--retries 0", script)
        self.assertNotIn("--system-site-packages", script)


if __name__ == "__main__":
    unittest.main()
