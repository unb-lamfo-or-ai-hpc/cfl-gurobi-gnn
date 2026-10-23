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
candidate = HERE / "paired_memory_guard_v2.py"
if not candidate.exists():
    candidate = ROOT / "scripts/evidence/paired_memory_guard_v2.py"
spec = importlib.util.spec_from_file_location("memory_candidate", candidate)
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)

qualifier_path = HERE / "qualify_pr78_hybrid_memory.py"
if not qualifier_path.exists():
    qualifier_path = ROOT / "scripts/evidence/qualify_pr78_hybrid_memory.py"
sys.path.insert(0, str(qualifier_path.parent))
qualifier_spec = importlib.util.spec_from_file_location("qualifier", qualifier_path)
qualifier = importlib.util.module_from_spec(qualifier_spec)
qualifier_spec.loader.exec_module(qualifier)

V1 = "5:memory:/slurm/uid_10/job_99/step_0\n"
V2 = "0::/user.slice/session.scope\n"
M1 = "1 2 0:3 / /sys/fs/cgroup/memory rw - cgroup cgroup rw,memory\n"
M2 = "2 2 0:4 / /sys/fs/cgroup/unified rw - cgroup2 cgroup rw\n"


class HybridTests(unittest.TestCase):
    def test_inventory_hides_paths_and_reports_ambiguity_count(self):
        with patch.object(
            memory.original, "bounded_text", side_effect=[V1 + V2, M1 + M2]
        ):
            result = qualifier.observations(memory.original, memory, "", False)
        self.assertEqual(result["old_candidate_count"], 2)
        self.assertEqual(result["v1_memory_memberships"], 1)
        self.assertEqual(result["unified_memberships"], 1)
        self.assertNotIn("uid_10", json.dumps(result))
        self.assertNotIn("session.scope", json.dumps(result))

    def test_allocated_inventory_includes_limits_without_paths(self):
        with (
            patch.object(
                memory.original, "bounded_text", side_effect=[V1 + V2, M1 + M2]
            ),
            patch.object(Path, "resolve", lambda p, **kwargs: p),
            patch.object(
                qualifier, "numeric_observation", return_value=64 * memory.original.GIB
            ),
        ):
            result = qualifier.observations(memory.original, memory, "99", True)
        self.assertEqual(result["selected_controller_version"], "v1")
        self.assertEqual(len(result["job_scoped_memory_observations"]), 2)
        self.assertTrue(result["job_scoped_memory_observations"][-1]["job_anchor"])
        self.assertNotIn("uid_10", json.dumps(result))

    def test_hybrid_uses_explicit_memory_not_unrelated_unified(self):
        for membership in (V1 + V2, V2 + V1):
            result = memory.resolve_cgroup(membership, M1 + M2, "99")
            self.assertEqual(result[0], "v1")
            self.assertEqual(result[2].name, "memory.limit_in_bytes")
        with self.assertRaises(ValueError):
            memory.original.resolve_cgroup(V1 + V2, M1 + M2, "99")

    def test_pure_v1_and_v2_unchanged(self):
        for membership, mounts in ((V1, M1), ("0::/slurm/job_99/step_0\n", M2)):
            self.assertEqual(
                memory.resolve_cgroup(membership, mounts, "99"),
                memory.original.resolve_cgroup(membership, mounts, "99"),
            )

    def test_duplicate_memberships_rejected(self):
        for membership in (V1 + V1, V1 + V2 + V2, V2 + V2):
            with self.assertRaises(ValueError):
                memory.resolve_cgroup(membership, M1 + M2, "99")

    def test_wrong_job_does_not_fall_back(self):
        with self.assertRaises(ValueError):
            memory.resolve_cgroup(
                V1.replace("job_99", "job_98") + "0::/slurm/job_99/step_0",
                M1 + M2,
                "99",
            )

    def test_missing_v1_mount_does_not_fall_back(self):
        with self.assertRaises(ValueError):
            memory.resolve_cgroup(V1 + "0::/slurm/job_99/step_0", M2, "99")

    def test_unsafe_or_duplicate_mounts_rejected(self):
        for mounts in (
            M1 + M1,
            M1.replace("0:3 / ", "0:3 /namespace "),
            M1.replace("/sys/fs/cgroup/memory", "/tmp/memory"),
        ):
            with self.assertRaises(ValueError):
                memory.resolve_cgroup(V1 + V2, mounts, "99")

    def test_no_memory_membership_rejected(self):
        for membership in ("", "2:cpu:/slurm/job_99", "invalid"):
            with self.assertRaises(ValueError):
                memory.resolve_cgroup(membership, M1 + M2, "99")

    def gate(self, limit, hierarchy=1, usage=100):
        def text(path):
            return V1 + V2 if str(path).endswith("/cgroup") else M1 + M2

        values = {
            "memory.limit_in_bytes": limit,
            "memory.use_hierarchy": hierarchy,
            "memory.usage_in_bytes": usage,
        }
        with (
            patch.object(memory.original, "bounded_text", side_effect=text),
            patch.object(
                memory.original, "numeric", side_effect=lambda p: values[p.name]
            ),
            patch.object(Path, "resolve", lambda p, **kwargs: p),
        ):
            return memory.MemoryGate("99").public()

    def test_limits_and_hierarchy_unchanged(self):
        self.assertEqual(memory.POLICY, memory.original.POLICY)
        result = self.gate(64 * memory.original.GIB)
        self.assertEqual(result["job_leaf_ram_limit_bytes"], 64 * memory.original.GIB)
        for limit in (56 * memory.original.GIB, 65 * memory.original.GIB, 2**63 - 4096):
            with self.assertRaises(ValueError):
                self.gate(limit)
        with self.assertRaises(ValueError):
            self.gate(64 * memory.original.GIB, hierarchy=0)
        with self.assertRaises(ValueError):
            self.gate(64 * memory.original.GIB, usage=56 * memory.original.GIB)


if __name__ == "__main__":
    unittest.main()
