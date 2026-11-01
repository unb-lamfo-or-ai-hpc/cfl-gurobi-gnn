"""Synthetic, solver-free checks of the closed-file export boundary."""
import ast
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("forensic_export", HERE / "pr89_m12_forensic_export.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ClosedExport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.controls = {}

        def emit(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
            return m.digest(path)

        model = self.root / "original.lp"
        model.write_text("Minimize\n obj: x\nBounds\n x >= 0\nEnd\n", encoding="utf-8")
        self.controls["MODEL"] = m.digest(model)
        binding = self.root / "cfl-mvp2-evidence/pr86/bindings-46802675ff99/prepared/private/input_paths.json"
        emit(binding, [{"parent": m.PARENT, "mip_path": str(model)}])
        cells = [{} for _ in range(60)]
        for i in range(50, 54):
            cells[i] = {"parent": m.PARENT, "model_sha256": self.controls["MODEL"], "index": i}
        self.controls["PLAN"] = emit(self.stage / "plan.json", {"source_commit": m.HEAD, "cells": cells})
        self.controls["PREFLIGHT"] = emit(self.stage / "preflight.json", {})
        self.controls["AUTH"] = emit(self.stage / "authorization.json", {})
        new_cells = {}
        for i, (job, _) in m.CELLS.items():
            folder = self.stage / "runs" / str(i)
            folder.mkdir(parents=True)
            log = folder / "gurobi.private.log"
            log.write_text("Optimal solution found\n", encoding="utf-8")
            child_sha = emit(folder / "child.json", {
                "cell": cells[i], "plan_sha256": self.controls["PLAN"],
                "result": {"optimization_calls": 1}, "gurobi_log": {"log_sha256": m.digest(log)},
            })
            new_cells[i] = (job, child_sha)
            emit(folder / "submission.json", {"index": i, "job_id": job, "plan_sha256": self.controls["PLAN"]})
            supervisor = emit(folder / "supervision.json", {})
            cost = emit(folder / "costs.json", {})
            emit(folder / "checked.json", {"complete": True, "child_sha256": child_sha, "index": i,
                "plan_sha256": self.controls["PLAN"], "supervision_sha256": supervisor, "costs_sha256": cost})
            for name in ("solution.private.json.gz", "optimize.intent.json", "held_profile.json"):
                (folder / name).write_bytes(b"synthetic existing bytes")
        self.controls["CELLS"] = new_cells
        self.accounting = "".join(job + "|COMPLETED|0:0|\n" for job, _ in new_cells.values())
        self.patcher = patch.multiple(m, **self.controls)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def export(self):
        return m.copy_closed_files(self.stage, self.root, self.accounting)

    def test_round_trip_and_no_original_changes(self):
        original = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        out, manifest = self.export()
        self.assertEqual(out.parent, self.stage)
        self.assertEqual(manifest["optimization_calls_added"], 0)
        with zipfile.ZipFile(out) as archive:
            self.assertEqual(len(archive.namelist()), 42)
            for name, expected in manifest["sha256"].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)
        for path, raw in original.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_active_job_rejected_before_output(self):
        self.accounting = self.accounting.replace("3726|COMPLETED", "3726|RUNNING")
        with self.assertRaisesRegex(ValueError, "four_completed"):
            self.export()
        self.assertEqual(list(self.stage.glob("*.zip")), [])

    def test_foreign_cluster_like_accounting_rejected(self):
        with self.assertRaises(ValueError):
            m.closed_job_states(self.accounting.replace("3727", "9999"))

    def test_duplicate_accounting_rejected(self):
        with self.assertRaises(ValueError):
            m.closed_job_states(self.accounting + self.accounting.splitlines()[0] + "\n")

    def test_tampered_child_rejected(self):
        (self.stage / "runs/51/child.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sealed_file_hash"):
            self.export()

    def test_tampered_log_rejected(self):
        (self.stage / "runs/52/gurobi.private.log").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sealed_file_hash"):
            self.export()

    def test_model_hash_is_not_only_a_path_check(self):
        (self.root / "original.lp").write_text("different model", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sealed_file_hash:model"):
            self.export()

    def test_path_escape_rejected(self):
        with self.assertRaisesRegex(ValueError, "path_outside"):
            m.scoped(HERE / "pr89_m12_forensic_export.py", self.root)

    def test_read_cap_rejected(self):
        with patch.object(m, "MAX_TOTAL", 1):
            with self.assertRaisesRegex(ValueError, "total_read_cap"):
                self.export()

    def test_archive_creation_is_exclusive(self):
        with patch.object(m.uuid, "uuid4", return_value=type("Id", (), {"hex": "fixed"})()):
            out, _ = self.export()
            first = out.read_bytes()
            with self.assertRaises(FileExistsError):
                self.export()
            self.assertEqual(out.read_bytes(), first)

    def test_changed_during_copy_preserves_original_and_fails(self):
        real_write = zipfile.ZipFile.write
        def changed(archive, path, *args, **kwargs):
            result = real_write(archive, path, *args, **kwargs)
            if str(path).endswith("solution.private.json.gz"):
                Path(path).write_bytes(b"concurrent mutation in synthetic fixture")
            return result
        with patch.object(zipfile.ZipFile, "write", changed):
            with self.assertRaisesRegex(ValueError, "changed_during_copy"):
                self.export()
        self.assertEqual(len(list(self.stage.glob("*.zip"))), 1)

    def test_no_solver_or_campaign_imports_or_mutating_commands(self):
        tree = ast.parse((HERE / "pr89_m12_forensic_export.py").read_text(encoding="utf-8"))
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = [a.name.split(".")[0] for n in imports for a in n.names]
        self.assertFalse(set(names) & {"gurobipy", "numpy", "torch", "pr89_cpu_workflow", "pr86_solver"})
        attrs = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(attrs & {"optimize", "submit", "terminate", "mkdir", "unlink", "remove", "rename"})


if __name__ == "__main__":
    unittest.main()
