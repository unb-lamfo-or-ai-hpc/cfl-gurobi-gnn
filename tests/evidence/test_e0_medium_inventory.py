"""Targeted discovery never admits labels, solver execution or a retry."""

import ast
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import inventory_e0_medium as inv  # noqa: E402


class InventoryTests(unittest.TestCase):
    def test_exact_parent_matching(self):
        self.assertTrue(
            inv.parent_match("graphs/CFL_medium_instance_13.pt", inv.PARENTS[0])
        )
        self.assertFalse(
            inv.parent_match("graphs/CFL_medium_instance_130.pt", inv.PARENTS[0])
        )
        self.assertFalse(
            inv.parent_match("graphs/CFL_medium_instance_1.pt", inv.PARENTS[0])
        )

    def test_private_and_label_files_excluded(self):
        for name in (
            "secret.json",
            "solution.json",
            "labels.pt",
            "gurobi.log",
            "gurobi.lic",
        ):
            self.assertIsNone(inv.candidate_kind(name))

    def fixture(self, folder):
        root = Path(folder) / "data"
        for group in inv.meta.GROUPS:
            (root / group).mkdir(parents=True)
        for parent in inv.PARENTS:
            path = root / f"raw/MILPBench/CFL/CFL_medium_instance/LP/{parent}.lp"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"original fixture")
            (root / f"bipartite_graphs/{parent}.pt").write_bytes(b"opaque, not loaded")
            (root / f"intermediate/{parent}.root.json.gz").write_bytes(b"opaque root")
            (root / f"analysis/{parent}.solution.json").write_bytes(b"private label")
        return root

    def test_collect_and_validate_no_raw_content(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = self.fixture(folder)
            output = Path(folder) / "result"
            value = inv.collect(root, output)
            data = (output / "inventory.json").read_bytes()
            self.assertEqual(inv.validate(data, inv.meta.digest(data)), value)
            self.assertEqual(len(value["candidates"]), 6)
            self.assertNotIn(str(root).encode(), data)
            self.assertNotIn(b"private label", data)
            self.assertFalse(value["absence_proven"])
            self.assertEqual(
                len(json.loads((output / "private_paths.json").read_bytes())), 6
            )
            with self.assertRaisesRegex(ValueError, "fresh_output"):
                inv.collect(root, output)

    def test_output_inside_data_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            with self.assertRaisesRegex(ValueError, "output_outside"):
                inv.collect(root, root / "output")

    def test_partial_budget_receipt_not_promoted(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = self.fixture(folder)
            with patch.object(
                inv.Reader, "scan", side_effect=inv.AuditStop("time_budget_exceeded")
            ):
                value = inv.collect(root, Path(folder) / "out")
            self.assertEqual(value["state"], "partial")
            self.assertFalse(value["solver_execution_admitted"])
            self.assertEqual(value["warnings"], ["time_budget_exceeded"])

    def test_tampered_scope_and_hash_rejected(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = self.fixture(folder)
            value = inv.collect(root, Path(folder) / "out")
            value["optimization_runs_added"] = 1
            data = json.dumps(value).encode()
            with self.assertRaisesRegex(ValueError, "execution_scope"):
                inv.validate(data, inv.meta.digest(data))
            with self.assertRaisesRegex(ValueError, "receipt_hash"):
                inv.validate(data, "0" * 64)

    def test_no_external_execution_or_deserialization(self):
        tree = ast.parse(Path(inv.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(
                    {alias.name for alias in node.names}
                    & {"torch", "gurobipy", "pickle", "subprocess"}
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(
                    node.func.attr, {"optimize", "backward", "Popen", "system", "load"}
                )


if __name__ == "__main__":
    unittest.main()
