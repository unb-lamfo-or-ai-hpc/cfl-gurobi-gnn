"""No-license regressions for the bounded E0 continuation."""

import ast
import copy
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import e0_three_method_executor as executor  # noqa: E402


class E0ExecutorTests(unittest.TestCase):
    def test_installed_binding_and_budget(self):
        self.assertEqual(len(executor.receipt()["parents"]), 6)
        frozen = executor.plan("a" * 40)
        self.assertEqual(frozen["maximum_optimization_calls"], 18)
        self.assertEqual(frozen["maximum_solver_seconds"], 64800)
        self.assertEqual(frozen["scheduler"]["cpus_per_task"], 1)
        self.assertEqual(frozen["scheduler"]["gpus"], 0)
        self.assertFalse(frozen["automatic_retry"])
        self.assertEqual(frozen["parameters"]["MIPGap"], 1e-4)
        self.assertEqual(
            frozen["memory_policy"]["cgroup_interrupt_bytes"], 56 * 1024**3
        )
        self.assertIn(
            "src/cfl_gnn/solvers/paired_partial_start.py", frozen["source_sha256_lf"]
        )

    def test_never_overwrite_and_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "receipt.json"
            executor.write(path, {"ok": True})
            with self.assertRaises(FileExistsError):
                executor.write(path, {"ok": False})
            self.assertTrue(executor.parsed(path)["ok"])
            self.assertEqual(
                executor.digest(path.read_bytes()),
                executor.digest(executor.encoded({"ok": True})),
            )

    def test_stop_policy(self):
        observed = {"guard_stop": None, "child_exit_code": 0}
        result = {
            "result": {"gate_status": "passed", "solve": {"solve_status_code": 9}}
        }
        self.assertIsNone(executor.should_stop(observed, result))
        for reason in (
            "memory_guard_stop",
            "memory_observation_lost",
            "child_deadline_exceeded",
        ):
            self.assertEqual(
                executor.should_stop({**observed, "guard_stop": reason}, result), reason
            )
        self.assertEqual(executor.should_stop(observed, None), "child_failed")
        result["result"]["solve"]["solve_status_code"] = 17
        self.assertEqual(
            executor.should_stop(observed, result), "solver_soft_memory_stop"
        )
        result["result"]["solve"]["solve_status_code"] = 9
        result["result"]["gate_status"] = "failed"
        self.assertEqual(
            executor.should_stop(observed, result), "result_validation_failed"
        )

    def matrix(self):
        frozen = executor.plan("a" * 40)
        rows = []
        for index in range(18):
            parent = executor.receipt()["parents"][index // 3]
            method = executor.METHODS[index % 3]
            start = {
                "submitted_assignments": parent["selected_support"] if index % 3 else 0,
                "positive_assignments": parent["positive_assignments"]
                if index % 3
                else 0,
                "status": "submitted_outcome_unknown" if index % 3 else "not_submitted",
                "assignment_sha256": parent[
                    "lp_assignment_sha256"
                    if index % 3 == 1
                    else "gnn_assignment_sha256"
                ],
            }
            result = {
                "parameters": dict(executor.PARAMETERS),
                "solver_version": [13, 0, 1],
                "mip_sha256": parent["mip_sha256"],
                "effective_objective_sense": "MINIMIZE",
                "mathematical_model_unchanged": True,
                "mathematical_signature_sha256": "b" * 64,
                "start": start,
                "gate_status": "passed",
                "solve": {"solve_status_code": 9},
            }
            rows.append(
                {
                    "index": index,
                    "optimization_intent_present": True,
                    "supervision": {"guard_stop": None, "child_exit_code": 0},
                    "child": {
                        "index": index,
                        "parent": parent["parent"],
                        "method": method,
                        "source_mip_unchanged": True,
                        "optimization_calls": 1,
                        "result": result,
                    },
                }
            )
        return frozen, {
            "protocol_id": executor.PROTOCOL,
            "plan_sha256": executor.digest(executor.encoded(frozen)),
            "job_id": "123",
            "attempts": rows,
            "complete": True,
            "stop_code": None,
            "scientific_reporting_eligible": False,
        }

    def test_complete_matrix_and_tampering(self):
        frozen, matrix = self.matrix()
        executor.validate_matrix(matrix, frozen)
        for field, value in (
            ("complete", False),
            ("job_id", "bad"),
            ("scientific_reporting_eligible", True),
        ):
            altered = copy.deepcopy(matrix)
            altered[field] = value
            with self.assertRaises(ValueError):
                executor.validate_matrix(altered, frozen)
        for field, value in (
            ("mip_sha256", "0" * 64),
            ("mathematical_signature_sha256", "0" * 64),
        ):
            altered = copy.deepcopy(matrix)
            altered["attempts"][1]["child"]["result"][field] = value
            with self.assertRaises(ValueError):
                executor.validate_matrix(altered, frozen)

    def test_stop_cannot_hide_or_continue(self):
        frozen, matrix = self.matrix()
        matrix["attempts"][1]["supervision"]["guard_stop"] = "memory_guard_stop"
        matrix["stop_code"] = "memory_guard_stop"
        matrix["complete"] = False
        with self.assertRaises(ValueError):
            executor.validate_matrix(matrix, frozen)
        matrix["attempts"] = matrix["attempts"][:2]
        executor.validate_matrix(matrix, frozen)

    def test_return_accounting_and_ready(self):
        frozen, matrix = self.matrix()
        value = {
            "protocol_id": executor.PROTOCOL,
            "plan": frozen,
            "matrix": matrix,
            "job_id": "123",
            "accounting": "JobID|State|ElapsedRaw|ExitCode|TotalCPU|AllocCPUS|ReqMem|MaxRSS\n123|COMPLETED|1|0:0|00:00:01|2|64G|\n",
            "raw_logs_included": False,
            "scientific_reporting_eligible": False,
            "ready_for_independent_review": True,
        }
        executor.validate_return(value)
        value["matrix"] = None
        with self.assertRaises(ValueError):
            executor.validate_return(value)
        value["ready_for_independent_review"] = False
        executor.validate_return(value)
        value["accounting"] = value["accounting"].replace("COMPLETED", "RUNNING")
        with self.assertRaises(ValueError):
            executor.validate_return(value)

    def test_stage_rejects_other_directories(self):
        with self.assertRaises(ValueError):
            executor.validate_stage(Path("/tmp/not-an-e0-stage"))

    def test_public_result_excludes_messages(self):
        # Minimal representative fields follow the export's explicit whitelist.
        source = Path(executor.__file__).read_text(encoding="utf-8")
        self.assertIn('if k != "solver_messages"', source)
        tree = ast.parse(source)
        self.assertFalse(
            any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in {"backward", "fit", "optimize"}
                for n in ast.walk(tree)
            )
        )

    def test_reuse_historical_solver_exactly_one_optimize(self):
        path = executor.ROOT / "src/cfl_gnn/solvers/paired_partial_start.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "optimize"
        ]
        self.assertEqual(len(calls), 1)
        solve = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "solve"
        )
        self.assertEqual(
            [a.arg for a in solve.args.args][-3:],
            ["soft_mem_limit_gb", "private_log_path", "before_optimize"],
        )
        self.assertTrue(
            all(
                isinstance(n, ast.Constant) and n.value is None
                for n in solve.args.defaults[-3:]
            )
        )

    def test_shell_budget_and_no_loop(self):
        source = (executor.ROOT / "scripts/evidence/operate_e0_solves.sh").read_text(
            encoding="utf-8"
        )
        for term in (
            "--nodes=1-1",
            "--cpus-per-task=1",
            "--mem=64G",
            "--time=20:00:00",
            "--no-requeue",
            "E0_SOURCE=${",
            "timeout --signal=TERM",
        ):
            if term == "E0_SOURCE=${":
                term = "SOURCE=${E0_SOURCE:?missing submitted source}"
            self.assertIn(term, source)
        self.assertNotIn("--gres=", source)
        self.assertNotIn("while ", source)

    @unittest.skipUnless(os.name == "posix", "Linux spool-copy shell regression")
    def test_batch_source_survives_spool_copy(self):
        text = (executor.ROOT / "scripts/evidence/operate_e0_solves.sh").read_text()
        prefix = text.split('STAGE=$(dirname "$SOURCE")')[0]
        with tempfile.TemporaryDirectory() as folder:
            spool = Path(folder) / "slurm_script"
            spool.write_text(prefix + '\nprintf "%s" "$SOURCE"\n')
            env = {**os.environ, "E0_SOURCE": "/raid/frozen/source"}
            done = subprocess.run(
                ["bash", str(spool), "batch"],
                env=env,
                capture_output=True,
                check=True,
                text=True,
            )
            self.assertEqual(done.stdout, "/raid/frozen/source")

    def test_failed_child_pauses_without_retry(self):
        frozen = executor.plan("a" * 40)
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            fake_gate = object()

            def failed(command, console, deadline, gate):
                Path(console).write_bytes(b"private error")
                self.assertEqual(deadline, 3780)
                self.assertIs(gate, fake_gate)
                return {"guard_stop": None, "child_exit_code": 2}

            with (
                patch.object(executor, "validate_stage", return_value=frozen),
                patch.object(executor, "allocation", return_value=("123", fake_gate)),
                patch.object(
                    executor.memory, "supervise", side_effect=failed
                ) as supervise,
            ):
                self.assertFalse(executor.run(stage))
                self.assertEqual(supervise.call_count, 1)
                matrix = executor.parsed(stage / "run/matrix.json")
                self.assertFalse(matrix["complete"])
                self.assertEqual(matrix["stop_code"], "child_failed")
                executor.validate_matrix(matrix, frozen)


if __name__ == "__main__":
    unittest.main()
