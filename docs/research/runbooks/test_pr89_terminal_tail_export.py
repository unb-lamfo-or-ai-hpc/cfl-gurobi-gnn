"""Synthetic tests of the final six-job export; no HPC/solver access."""
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
spec = importlib.util.spec_from_file_location("tail_export", HERE / "pr89_terminal_tail_export.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TerminalTailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stage = Path(self.temp.name) / "existing-stage"
        self.stage.mkdir()
        self.plan = {"source_commit": m.HEAD, "cells": [
            {"alias": "M12", "model_sha256": m.MODEL, "seed": 42, "threads": 8 if i<57 else 16, "index": i}
            for i in range(60)]}
        self.controls = {}
        for name, obj in (("plan.json", self.plan), ("preflight.json", {}), ("authorization.json", {})):
            self.controls[name] = self.emit(self.stage / name, obj)
        self.patcher = patch.object(m, "CONTROLS", self.controls)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        for i, job in enumerate(m.ALL_JOBS):
            folder = self.stage / "runs" / str(i)
            self.emit(folder / "submission.json", {"index": i, "job_id": job, "plan_sha256": self.controls["plan.json"]})
            if job not in m.JOBS:
                continue
            log = folder / "gurobi.private.log"
            log.write_bytes(b"synthetic closed log")
            child = {"cell": self.plan["cells"][i], "plan_sha256": self.controls["plan.json"],
                     "gurobi_log": {"log_sha256": m.digest(log)}}
            child_sha = self.emit(folder / "child.json", child)
            supervisor = self.emit(folder / "supervision.json", {})
            cost = self.emit(folder / "costs.json", {})
            self.emit(folder / "checked.json", {"index": i, "plan_sha256": self.controls["plan.json"],
                "child_sha256": child_sha, "supervision_sha256": supervisor, "costs_sha256": cost})
            for name in ("held_profile.json", "optimize.intent.json", "dispatch.started.json", "child.started.json"):
                self.emit(folder / name, {})
            (folder / "solution.private.json.gz").write_bytes(b"unchanged existing gzip fixture")
            (folder / f"batch-{job}.private.out").write_bytes(b"private batch output")
            (folder / "unrequested-private-file").write_bytes(b"MUST NOT COPY")
        self.accounting = "".join(f"{job}|COMPLETED|0:0|120|00:01:00|16|64G||start|end\n"
                                  f"{job}.batch|COMPLETED|0:0|120|00:01:00|16||1024K|start|end\n"
                                  for job in m.ALL_JOBS)

    def emit(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(m.encoded(obj))
        return m.digest(path)

    def export(self):
        return m.export(self.stage, self.accounting, "query-start", "query-end")

    def test_complete_tail_and_all_sixty_accounting(self):
        before = {p: p.read_bytes() for p in self.stage.rglob("*") if p.is_file()}
        out, manifest = self.export()
        self.assertEqual(manifest["collected_job_ids"], list(m.JOBS))
        self.assertEqual(manifest["campaign_terminal_jobs_observed"], 60)
        self.assertEqual(manifest["missing_files"], [])
        self.assertFalse(manifest["scientific_reporting_eligible"])
        self.assertFalse(manifest["final_campaign_return"])
        with zipfile.ZipFile(out) as z:
            self.assertEqual(len(json.loads(z.read("job-cell-map.json"))), 60)
            self.assertEqual({int(n.split("/")[1]) for n in z.namelist() if n.startswith("runs/")}, set(range(54,60)))
            self.assertFalse(any("unrequested-private-file" in n or n.startswith("model.private") for n in z.namelist()))
            for name, h in manifest["sha256"].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), h)
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_running_prevents_any_zip(self):
        self.accounting = self.accounting.replace("3730|COMPLETED", "3730|RUNNING")
        with self.assertRaisesRegex(ValueError, "AGUARDE.*3730:RUNNING"):
            self.export()
        self.assertFalse((self.stage/m.OUT_NAME).exists())

    def test_pending_prevents_any_zip(self):
        self.accounting = self.accounting.replace("3734|COMPLETED", "3734|PENDING")
        with self.assertRaisesRegex(ValueError, "AGUARDE"):
            self.export()
        self.assertFalse((self.stage/m.OUT_NAME).exists())

    def test_running_step_prevents_copy(self):
        self.accounting = self.accounting.replace("3734.batch|COMPLETED", "3734.batch|COMPLETING")
        with self.assertRaisesRegex(ValueError, "AGUARDE.*3734.batch"):
            self.export()

    def test_duplicate_root_rejected(self):
        self.accounting += self.accounting.splitlines()[0] + "\n"
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
            self.export()

    def test_missing_old_root_not_silently_assumed(self):
        self.accounting = "\n".join(s for s in self.accounting.splitlines() if not s.startswith("3675|"))
        with self.assertRaisesRegex(ValueError, "MISSING_OR_AMBIGUOUS_ACCOUNTING_3675"):
            self.export()

    def test_foreign_id_rejected(self):
        self.accounting = self.accounting.replace("3734|", "9999|")
        with self.assertRaisesRegex(ValueError, "UNREQUESTED_JOB"):
            self.export()

    def test_failed_terminal_and_missing_outputs_are_preserved(self):
        self.accounting = self.accounting.replace("3734|COMPLETED|0:0", "3734|FAILED|2:0")
        folder = self.stage / "runs/59"
        for name in ("child.json", "checked.json", "solution.private.json.gz", "gurobi.private.log"):
            (folder/name).unlink()
        out, manifest = self.export()
        self.assertEqual(manifest["non_success_accounting_job_ids"], ["3734"])
        self.assertEqual(len(manifest["missing_files"]), 4)
        self.assertTrue(out.exists())

    def test_completed_missing_receipt_is_not_fabricated(self):
        (self.stage / "runs/55/costs.json").unlink()
        _, manifest = self.export()
        self.assertEqual(manifest["missing_files"], [{"job_id":"3730", "path":"runs/55/costs.json"}])

    def test_changed_control_rejected(self):
        (self.stage / "authorization.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SEALED_HASH_MISMATCH"):
            self.export()

    def test_even_old_submission_identity_is_checked(self):
        self.emit(self.stage / "runs/0/submission.json", {"index":0,"job_id":"9999","plan_sha256":self.controls["plan.json"]})
        with self.assertRaisesRegex(ValueError, "SUBMISSION_BINDING_3675"):
            self.export()

    def test_nested_child_seal_rejected(self):
        child = self.stage / "runs/54/child.json"
        value = m.metadata(child)
        value["extra"] = "changed"
        self.emit(child, value)
        with self.assertRaisesRegex(ValueError, "NESTED_SEAL"):
            self.export()

    def test_closed_log_seal_rejected(self):
        (self.stage / "runs/54/gurobi.private.log").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SEALED_HASH_MISMATCH"):
            self.export()

    def test_existing_zip_not_overwritten(self):
        out, _ = self.export()
        first = out.read_bytes()
        with self.assertRaisesRegex(ValueError, "OUTPUT_ALREADY_EXISTS"):
            self.export()
        self.assertEqual(out.read_bytes(), first)

    def test_total_cap_prevents_output(self):
        with patch.object(m, "MAX_TOTAL", 1):
            with self.assertRaisesRegex(ValueError, "TOTAL_INPUT_SIZE_CAP"):
                self.export()
        self.assertFalse((self.stage/m.OUT_NAME).exists())

    def test_changed_while_copying_detected(self):
        real_write = zipfile.ZipFile.write
        def mutation(z, path, *args, **kwargs):
            result = real_write(z, path, *args, **kwargs)
            if str(path).endswith("solution.private.json.gz"):
                Path(path).write_bytes(b"synthetic concurrent mutation")
            return result
        with patch.object(zipfile.ZipFile, "write", mutation):
            with self.assertRaisesRegex(ValueError, "CHANGED_DURING_COPY"):
                self.export()

    def test_path_escape_rejected(self):
        with self.assertRaisesRegex(ValueError, "PATH_OUTSIDE_STAGE"):
            m.scoped(HERE / "pr89_terminal_tail_export.py", self.stage)

    def test_no_solver_polling_or_mutating_calls(self):
        tree = ast.parse((HERE/"pr89_terminal_tail_export.py").read_text(encoding="utf-8"))
        imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for a in n.names}
        self.assertFalse(imports & {"gurobipy","torch","numpy","pr89_cpu_workflow","pr86_solver","time"})
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls & {"optimize","sleep","mkdir","unlink","remove","rename","terminate"})
        commands = [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="check_output"]
        self.assertEqual(len(commands), 2)  # Git identity loop and one sacct call.


if __name__ == "__main__":
    unittest.main()
