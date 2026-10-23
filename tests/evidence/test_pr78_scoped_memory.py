import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
sys.path.insert(0, str(HERE))
from paired_memory_runtime_v2 import qualified as candidate  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "baseline_tests", ROOT / "tests/evidence/test_pr78_hierarchical_memory.py"
)
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
baseline.memory = candidate


class ScopedTests(baseline.HierarchicalTests):
    def test_missing_usage_file_fails_closed(self):
        gate = candidate.MemoryGate("99")
        self.missing = gate.chain[-1] / "memory.usage_in_bytes"
        with self.assertRaises(candidate.MemoryObservationError) as caught:
            gate.sample()
        self.assertEqual(caught.exception.diagnostic["stage"], "usage_read_or_parse")
        self.assertEqual(caught.exception.diagnostic["depth_from_leaf"], 2)
        self.assertEqual(
            caught.exception.diagnostic["exception_type"], "FileNotFoundError"
        )

    def test_unrelated_mount_allowed(self):
        gate = candidate.MemoryGate("99")
        self.mounts += "99 2 0:99 / /unrelated rw - tmpfs tmpfs rw\n"
        self.assertEqual(gate.sample(), 30)

    def test_mount_reorder_allowed(self):
        gate = candidate.MemoryGate("99")
        self.mounts = "\n".join(reversed(self.mounts.splitlines())) + "\n"
        self.assertEqual(gate.sample(), 30)

    def test_relevant_mount_change_rejected(self):
        gate = candidate.MemoryGate("99")
        self.mounts = self.mounts.replace("rw,memory", "rw,memory,nosuid")
        with self.assertRaises(candidate.MemoryObservationError) as caught:
            gate.sample()
        self.assertEqual(caught.exception.diagnostic["stage"], "memory_mount_changed")

    def test_shadow_mount_any_level_rejected(self):
        for suffix in (
            "",
            "/memory.usage_in_bytes",
            "/step_0",
            "/step_0/task_0/memory.usage_in_bytes",
        ):
            gate = candidate.MemoryGate("99")
            saved = self.mounts
            self.mounts += (
                "99 2 0:99 / /sys/fs/cgroup/memory/slurm/uid_10/job_99"
                + suffix
                + " rw - tmpfs tmpfs rw\n"
            )
            with self.assertRaises(candidate.MemoryObservationError):
                gate.sample()
            self.mounts = saved

    def test_replaced_mount_id_rejected(self):
        gate = candidate.MemoryGate("99")
        self.mounts = self.mounts.replace("1 2 0:3", "3 2 0:3")
        with self.assertRaises(candidate.MemoryObservationError):
            gate.sample()

    def test_sanitized_exception(self):
        exc = PermissionError(13, "PRIVATE-LICENSE /private/path")
        result = candidate.failure("usage_read_or_parse", exc, 2)
        self.assertNotIn("PRIVATE", str(result))
        self.assertEqual(result["errno"], 13)
        self.assertEqual(result["exception_type"], "PermissionError")

    def test_membership_change_stage(self):
        gate = candidate.MemoryGate("99")
        self.membership += "\n"
        with self.assertRaises(candidate.MemoryObservationError) as caught:
            gate.sample()
        self.assertEqual(caught.exception.diagnostic["stage"], "membership_changed")

    def test_limit_change_stage(self):
        gate = candidate.MemoryGate("99")
        self.limits["job_99"] -= 1
        with self.assertRaises(candidate.MemoryObservationError) as caught:
            gate.sample()
        self.assertEqual(caught.exception.diagnostic["stage"], "limit_changed")


if __name__ == "__main__":
    unittest.main()
