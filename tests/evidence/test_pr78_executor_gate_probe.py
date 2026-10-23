import importlib.util
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

module_path = Path(__file__).with_name("probe_pr78_executor_gates.py")
if not module_path.exists():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "scripts/evidence/probe_pr78_executor_gates.py"
    )
spec = importlib.util.spec_from_file_location("gate_probe", module_path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def executor(self):
        return SimpleNamespace(
            load_flow=Mock(return_value={"source_commit": probe.HEAD}),
            workflow=SimpleNamespace(source_head=Mock(return_value=probe.HEAD)),
            reviewed_evidence=Mock(),
            execution_host=Mock(),
            memory=SimpleNamespace(MemoryGate=Mock()),
            adapter=SimpleNamespace(screen=SimpleNamespace(qualify_affinity=Mock())),
        )

    def test_static_never_calls_runtime_gates(self):
        ex = self.executor()
        self.assertTrue(probe.gates(ex, False)[0]["passed"])
        ex.execution_host.assert_not_called()
        ex.memory.MemoryGate.assert_not_called()
        ex.adapter.screen.qualify_affinity.assert_not_called()

    def test_bad_plan_prevents_all_runtime_checks(self):
        ex = self.executor()
        ex.load_flow.side_effect = ValueError("private text")
        result = probe.gates(ex, True)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["passed"])
        self.assertNotIn("private text", str(result))
        ex.execution_host.assert_not_called()

    def test_all_resource_failures_visible_without_matrix_methods(self):
        ex = self.executor()
        ex.execution_host.side_effect = ValueError("secret")
        ex.memory.MemoryGate.side_effect = ValueError("secret")
        result = probe.gates(ex, True)
        self.assertEqual([r["passed"] for r in result], [True, False, False, True])
        self.assertNotIn("secret", str(result))

    def test_solver_import_blocked(self):
        for name in ("gurobipy", "gurobipy._core"):
            with self.assertRaises(RuntimeError):
                probe.NoSolver().find_spec(name)

    def test_environment_allowlist_redacts_text(self):
        with patch.dict(
            os.environ,
            {
                "SLURM_JOB_ID": "secret",
                "SLURM_MEM_PER_NODE": "65536",
                "TOKEN": "secret",
            },
            clear=True,
        ):
            result = probe.environment()
        self.assertEqual(result["SLURM_JOB_ID"], "non_numeric")
        self.assertEqual(result["SLURM_MEM_PER_NODE"], "65536")
        self.assertNotIn("secret", str(result))
        self.assertNotIn("TOKEN", result)


if __name__ == "__main__":
    unittest.main()
