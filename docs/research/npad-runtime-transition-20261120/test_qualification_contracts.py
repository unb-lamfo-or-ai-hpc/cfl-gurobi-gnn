"""Offline admission, license-call and no-follow inventory checks; no HPC calls."""

import ast
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


worker = module("qualification_worker", "qualify_training_license.py")
scanner = module("migration_scanner", "dgx_migration_inventory.py")


class InventoryTests(unittest.TestCase):
    def test_sensitive_names(self):
        for name in ("secrets", "gurobi.lic", ".env", ".ssh", "id_rsa", "server.key"):
            self.assertTrue(scanner.sensitive(name))
        self.assertFalse(scanner.sensitive("preflight.json"))

    def test_metadata_only_excludes_credentials_and_git_objects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "secrets").mkdir()
            (root / "secrets" / "gurobi.lic").write_text("NEVER_READ_THIS")
            (root / ".git").mkdir()
            (root / ".git" / "object").write_text("DO_NOT_SCAN")
            (root / "graph.pt").write_bytes(b"1234567")
            with patch.object(
                Path, "read_bytes", side_effect=AssertionError("NO_CONTENT_READ")
            ):
                result = scanner.inventory(root, time.monotonic() + 10)
            self.assertTrue(result["complete"], result["issues"])
            self.assertEqual(result["totals"]["regular_files"], 1)
            self.assertEqual(result["totals"]["regular_logical_bytes"], 7)
            self.assertEqual(result["totals"]["sensitive_entries_excluded"], 1)
            self.assertEqual(result["repository_paths"], [str(root)])

    def test_external_symlink_is_reported_without_following(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            root.mkdir()
            outside = Path(temp) / "outside"
            outside.mkdir()
            (outside / "unique.pt").write_bytes(b"PRESERVE")
            try:
                (root / "linked").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("symlink privilege unavailable")
            result = scanner.inventory(root, time.monotonic() + 10)
            self.assertEqual(result["files"], [])
            self.assertEqual(result["symlinks_not_followed"][0]["followed"], False)
            self.assertTrue((outside / "unique.pt").exists())

    def test_incomplete_scan_is_never_reported_as_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in range(4):
                (root / str(n)).write_text("x")
            result = scanner.inventory(root, time.monotonic() + 10, entry_limit=2)
            self.assertFalse(result["complete"])
            self.assertLessEqual(len(result["files"]), 2)
            expired = scanner.inventory(root, time.monotonic() - 1)
            self.assertFalse(expired["complete"])

    def test_no_cleanup_or_credential_content_api_in_scanner(self):
        text = (HERE / "dgx_migration_inventory.py").read_text()
        for forbidden in (
            "shutil.rmtree",
            ".unlink(",
            "os.remove(",
            "os.rename(",
            "shutil.move",
        ):
            self.assertNotIn(forbidden, text)


class LicenseTests(unittest.TestCase):
    def fake_api(self, stage, status=2):
        params = types.SimpleNamespace()
        calls = {"optimize": 0, "env": 0}

        class Env:
            def __init__(self, empty):
                assert empty
                calls["env"] += 1

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def setParam(self, name, value):
                assert (name, value) == ("OutputFlag", 0)

            def start(self):
                return None

        class Model:
            Params = params
            Status = status
            SolCount = 1
            ObjVal = 1.0
            ObjBound = 1.0
            MIPGap = 0.0
            NumVars = 2501
            NumConstrs = 1
            Runtime = 0.01

            def __init__(self, name, env):
                assert env is not None

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def addVars(self, count, vtype):
                assert count == 2501 and vtype == "B"
                return dict.fromkeys(range(count), 0)

            def addConstr(self, expression):
                return None

            def setObjective(self, expression, sense):
                assert sense == 1

            def update(self):
                return None

            def optimize(self):
                assert (stage / "license-optimize.intent.json").is_file()
                calls["optimize"] += 1

        api = types.SimpleNamespace(
            Env=Env,
            Model=Model,
            quicksum=lambda values: 2501,
            gurobi=types.SimpleNamespace(version=lambda: (14, 0, 0)),
            GRB=types.SimpleNamespace(BINARY="B", MINIMIZE=1, OPTIMAL=2),
        )
        return api, calls, params

    def test_exactly_one_call_above_restricted_limit_no_credentials_in_result(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            license_file = stage / "gurobi.lic"
            license_file.write_text("PRIVATE_TOKEN_MUST_NOT_BE_READ")
            api, calls, params = self.fake_api(stage)
            with (
                patch.dict(sys.modules, gurobipy=api),
                patch.dict(os.environ, GRB_LICENSE_FILE=str(license_file)),
            ):
                result = worker.license_test(stage)
            self.assertEqual(calls, {"optimize": 1, "env": 1})
            self.assertEqual((params.Threads, params.TimeLimit), (1, 30))
            self.assertTrue(result["above_bundled_restricted_variable_limit"])
            self.assertNotIn("PRIVATE_TOKEN", json.dumps(result))
            self.assertNotIn(str(license_file), json.dumps(result))

    def test_failed_milp_keeps_intent_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            license_file = stage / "gurobi.lic"
            license_file.write_text("private")
            api, calls, _ = self.fake_api(stage, status=9)
            with (
                patch.dict(sys.modules, gurobipy=api),
                patch.dict(os.environ, GRB_LICENSE_FILE=str(license_file)),
                self.assertRaisesRegex(ValueError, "DID_NOT_RETURN_OPTIMAL"),
            ):
                worker.license_test(stage)
            self.assertEqual(calls["optimize"], 1)
            self.assertTrue((stage / "license-optimize.intent.json").is_file())

    def test_missing_license_stops_before_environment_initialization(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            api, calls, _ = self.fake_api(stage)
            with (
                patch.dict(sys.modules, gurobipy=api),
                patch.dict(os.environ, GRB_LICENSE_FILE=str(stage / "absent.lic")),
                self.assertRaisesRegex(ValueError, "NOT_READABLE"),
            ):
                worker.license_test(stage)
            self.assertEqual(calls, {"optimize": 0, "env": 0})


class GuardTests(unittest.TestCase):
    def test_shell_python_blocks_parse_and_bind_the_exact_worker(self):
        text = (HERE / "submit-training-license.template.sh").read_text()
        blocks = re.findall(r"<<'([A-Z]+)'\n(.*?)\n\1(?:\n|$)", text, re.S)
        self.assertEqual(
            {name for name, _ in blocks}, {"CI", "ADMIT", "FETCH", "BATCH"}
        )
        for name, code in blocks:
            if name != "BATCH":
                ast.parse(code)
        expected = hashlib.sha256(
            (HERE / "qualify_training_license.py").read_bytes()
        ).hexdigest()
        self.assertIn(expected, text)
        self.assertLess(text.index("CI\ntest -r"), text.index('mkdir "$R"'))
        self.assertEqual(
            sum(line.startswith("sbatch ") for line in text.splitlines()), 1
        )
        self.assertIn("--ntasks=1 --cpus-per-task=8 --mem=48G --gres=gpu:1", text)
        self.assertIn("--no-requeue", text)

    def test_collector_never_displays_raw_license_logs(self):
        text = (HERE / "collect-training-license.template.sh").read_text()
        self.assertIn("private_logs_available_bytes_only", text)
        for forbidden in ("tail ", "f.read_text(errors=", "sbatch ", "scancel "):
            self.assertNotIn(forbidden, text)

    def test_changed_project_source_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in worker.SOURCES:
                (root / name).write_text("tampered")
            with self.assertRaisesRegex(ValueError, "SOURCE_IDENTITY_CHANGED"):
                worker.verify_sources(root)

    def test_production_gpu_gate_and_serial_scope(self):
        text = (HERE / "qualify_training_license.py").read_text()
        self.assertIn('torch.device("cuda:0")', text)
        self.assertIn("NO_CPU_FALLBACK", text)
        self.assertNotIn("init_process_group(", text)
        self.assertNotIn("load_state_dict(torch.load", text)
        self.assertIn('"historical_checkpoint_loaded": False', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
