import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "work/pr78-mvp2-delivery-plan"
if not ROOT.exists():
    ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
candidate = HERE / "paired_memory_guard_v3.py"
if not candidate.exists():
    candidate = ROOT / "scripts/evidence/paired_memory_guard_v3.py"
sys.path.insert(0, str(candidate.parent))
spec = importlib.util.spec_from_file_location("hierarchical_candidate", candidate)
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)

GIB = 1024**3
UNLIMITED = 9223372036854771712
V1 = "5:memory:/slurm/uid_10/job_99/step_0/task_0\n"
V2 = "0::/user.slice/session.scope\n"
M1 = "1 2 0:3 / /sys/fs/cgroup/memory rw - cgroup cgroup rw,memory\n"
M2 = "2 2 0:4 / /sys/fs/cgroup/unified rw - cgroup2 cgroup rw\n"


class HierarchicalTests(unittest.TestCase):
    def setUp(self):
        self.membership = V1 + V2
        self.mounts = M1 + M2
        self.limits = {"task_0": UNLIMITED, "step_0": 64 * GIB, "job_99": 64 * GIB}
        self.usage = {"task_0": 10, "step_0": 20, "job_99": 30}
        self.hierarchy = {name: 1 for name in self.limits}
        self.missing = None

        def text(path):
            path = Path(path)
            if path.name == "cgroup":
                return self.membership
            if path.name == "mountinfo":
                return self.mounts
            if path == self.missing:
                raise FileNotFoundError
            if path.name in ("memory.limit_in_bytes", "memory.max"):
                return str(self.limits[path.parent.name])
            if path.name in ("memory.usage_in_bytes", "memory.current"):
                return str(self.usage[path.parent.name])
            if path.name == "memory.use_hierarchy":
                return str(self.hierarchy[path.parent.name])
            raise AssertionError("unexpected_read")

        self.text = text
        self.addCleanup(patch.stopall)
        patch.object(memory.original, "bounded_text", side_effect=text).start()
        patch.object(Path, "resolve", lambda p, **kwargs: p).start()

    def test_job3484_layout_qualifies_without_claiming_leaf_cap(self):
        result = memory.MemoryGate("99").public()
        self.assertEqual(result["job_anchor_ram_limit_bytes"], 64 * GIB)
        self.assertEqual(result["leaf_ram_limit_bytes"], UNLIMITED)
        self.assertEqual(result["current_max_job_scoped_usage_bytes"], 30)
        self.assertEqual(result["validated_group_count"], 3)
        self.assertNotIn("job_leaf_ram_limit_bytes", result)
        self.assertNotIn("uid_10", json.dumps(result))
        self.assertEqual(memory.POLICY, memory.original.POLICY)

    def test_finite_leaf_and_tighter_step(self):
        self.limits["task_0"] = 63 * GIB
        self.limits["step_0"] = 60 * GIB
        self.assertEqual(memory.MemoryGate("99").scoped_limit, 60 * GIB)

    def test_v2_unlimited_leaf_bounded_job(self):
        self.membership = "0::/slurm/uid_10/job_99/step_0/task_0\n"
        self.limits["task_0"] = "max"
        self.assertEqual(memory.MemoryGate("99").job_limit, 64 * GIB)

    def test_invalid_job_limits_fail_even_with_bounded_step(self):
        for value in (0, 56 * GIB, 65 * GIB, UNLIMITED):
            self.limits["job_99"] = value
            with self.assertRaises(ValueError):
                memory.MemoryGate("99")

    def test_v2_unlimited_job_fails_even_with_bounded_step(self):
        self.membership = "0::/slurm/uid_10/job_99/step_0/task_0\n"
        self.limits["job_99"] = "max"
        with self.assertRaises(ValueError):
            memory.MemoryGate("99")

    def test_descendant_below_watchdog_margin_fails(self):
        for name in ("task_0", "step_0"):
            old = self.limits[name]
            self.limits[name] = 56 * GIB
            with self.assertRaises(ValueError):
                memory.MemoryGate("99")
            self.limits[name] = old

    def test_disabled_hierarchy_at_any_level_fails(self):
        for name in self.hierarchy:
            self.hierarchy[name] = 0
            with self.assertRaises(ValueError):
                memory.MemoryGate("99")
            self.hierarchy[name] = 1

    def test_usage_over_threshold_in_any_group_fails_initial_gate(self):
        for name in self.usage:
            self.usage[name] = 56 * GIB
            with self.assertRaises(ValueError):
                memory.MemoryGate("99")
            self.usage[name] = 10

    def test_sample_observes_sibling_job_usage_for_watchdog(self):
        gate = memory.MemoryGate("99")
        self.usage["job_99"] = 57 * GIB
        self.assertEqual(gate.sample(), 57 * GIB)

    def test_limit_change_at_any_level_fails_sample(self):
        for name in self.limits:
            gate = memory.MemoryGate("99")
            old = self.limits[name]
            self.limits[name] -= 1
            with self.assertRaises(ValueError):
                gate.sample()
            self.limits[name] = old

    def test_hierarchy_change_fails_sample(self):
        gate = memory.MemoryGate("99")
        self.hierarchy["job_99"] = 0
        with self.assertRaises(ValueError):
            gate.sample()

    def test_membership_or_mount_change_fails_sample(self):
        for name in ("membership", "mounts"):
            gate = memory.MemoryGate("99")
            old = getattr(self, name)
            setattr(self, name, old + "\n")
            with self.assertRaises(ValueError):
                gate.sample()
            setattr(self, name, old)

    def test_missing_usage_file_fails_closed(self):
        gate = memory.MemoryGate("99")
        self.missing = gate.chain[-1] / "memory.usage_in_bytes"
        with self.assertRaises(FileNotFoundError):
            gate.sample()

    def test_non_numeric_limit_fails_closed(self):
        for value in ("max", "-1", "1e9", "not_a_number"):
            self.limits["task_0"] = value
            with self.assertRaises(ValueError):
                memory.MemoryGate("99")

    def test_ambiguous_membership_fails(self):
        self.membership += V1
        with self.assertRaises(ValueError):
            memory.MemoryGate("99")

    def test_wrong_job_and_duplicate_anchor_fail(self):
        for path in ("/slurm/job_98/step_0", "/slurm/job_99/job_99/task_0"):
            self.membership = "5:memory:" + path + "\n" + V2
            with self.assertRaises(ValueError):
                memory.MemoryGate("99")

    def test_symlink_or_namespace_redirect_fails(self):
        with (
            patch.object(Path, "resolve", return_value=Path("/tmp/redirect")),
            self.assertRaises(ValueError),
        ):
            memory.MemoryGate("99")

    def test_deep_hierarchy_fails_bounded(self):
        leaf = Path("/sys/fs/cgroup/memory/job_99/" + "/".join(["a"] * 16))
        with self.assertRaises(ValueError):
            memory.job_chain(leaf, "99")


if __name__ == "__main__":
    unittest.main()
