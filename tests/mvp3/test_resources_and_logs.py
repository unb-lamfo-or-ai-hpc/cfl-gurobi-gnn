"""Offline OS-scope and released-parser tests; log text is invented, not G14 evidence."""
# ruff: noqa: E402 -- repository-source bootstrap, no installed project required

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from cfl_gnn.mvp3.contract import ContractError
from cfl_gnn.mvp3.logparse import parse_native_log
from cfl_gnn.mvp3.resources import JobCgroup, OwnedProcessTree, affinity_evidence
from cfl_gnn.mvp3.supervisor import supervise

SYNTHETIC_LOG = """Gurobi Optimizer version 14.0.0 build v14.0.0rc0 (synthetic)
Set parameter WLSSecret to value fake-sensitive-value
Academic license - for non-commercial use only
Thread count: 2 physical cores, 4 logical processors, using up to 1 threads
Optimize a model with 1 rows, 20 columns and 20 nonzeros
Presolve removed 1 rows and 20 columns
Presolve time: 0.00s
Presolve: All rows and columns removed
Explored 0 nodes (0 simplex iterations) in 0.01 seconds (0.00 work units)
Thread count was 1 (of 4 available processors)
Solution count 1: 11
Optimal solution found (tolerance 1.00e-04)
Best objective 1.100000000000e+01, best bound 1.100000000000e+01, gap 0.0000%
"""


class ResourceAndLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_exact_job_cgroup_scope_and_unavailable_counters(self):
        root = self.folder / "cgroup"
        job = root / "user" / "job_42"
        step = job / "step_0"
        step.mkdir(parents=True)
        (job / "memory.current").write_text("123")
        (job / "memory.peak").write_text("456")
        (job / "memory.events").write_text("oom 1\noom_kill 0\n")
        reader = JobCgroup(step, 42, root=root)
        result = reader.snapshot()
        self.assertEqual(result["current_bytes"]["value"], 123)
        self.assertEqual(result["peak_bytes"]["value"], 456)
        self.assertEqual(result["memory_events"]["oom_kill"], 0)
        (job / "memory.current").unlink()
        self.assertIsNone(reader.snapshot()["current_bytes"]["value"])
        for path in (root, root / "job_420", self.folder / "job_42"):
            with self.assertRaises(ContractError):
                JobCgroup(path, 42, root=root)

    def test_affinity_maps_physical_siblings_without_inventing_counts(self):
        for cpu in (0, 1):
            topology = self.folder / f"cpu{cpu}" / "topology"
            topology.mkdir(parents=True)
            (topology / "physical_package_id").write_text("0")
            (topology / "core_id").write_text("3")
        result = affinity_evidence(NS(cpu_affinity=lambda: [1, 0]), sysfs=self.folder)
        self.assertEqual(
            len(
                {
                    (row["package_id"], row["core_id"])
                    for row in result["physical_cores"]
                }
            ),
            1,
        )
        self.assertEqual(result["logical_ids"], [0, 1])
        result = affinity_evidence(NS(cpu_affinity=lambda: [5]), sysfs=self.folder)
        self.assertIsNone(result["physical_cores"])

    def test_cgroup_must_contain_the_actual_worker_membership(self):
        root = self.folder / "cgroup"
        job = root / "job_42"
        job.mkdir(parents=True)
        proc = self.folder / "proc" / "123"
        proc.mkdir(parents=True)
        membership = proc / "cgroup"
        membership.write_text("0::/job_42/step_0\n")
        reader = JobCgroup(job, 42, root=root)
        self.assertTrue(reader.contains_pid(123, proc=proc.parent, root=root))
        membership.write_text("0::/job_420/step_0\n")
        self.assertFalse(reader.contains_pid(123, proc=proc.parent, root=root))

    def test_normal_child_return_is_not_a_guard_or_scheduler_outcome(self):
        result = supervise(
            [sys.executable, "-c", "print('offline fixture')"],
            self.folder / "normal",
            cwd=self.folder,
            wall_seconds=10,
            memory_bytes=512 * 1024 * 1024,
            approval_reference="offline-unit-test-no-solver",
            interval=0.025,
        )
        self.assertEqual(result["child_returncode"], 0)
        self.assertIsNone(result["guard"])
        self.assertIsNone(result["job_memory_after"])

    def test_reused_pid_is_never_measured_or_signalled(self):
        killed = []
        created = [1]
        process = NS(
            pid=42,
            create_time=lambda: created[0],
            children=lambda recursive: [],
            kill=lambda: killed.append(42),
            suspend=lambda: None,
            memory_info=lambda: NS(rss=100),
        )
        api = NS(Process=lambda pid: process, Error=RuntimeError)
        owned = OwnedProcessTree(42, api)
        created[0] = 2
        self.assertIsNone(owned.sample()["bytes"])
        self.assertEqual(owned.stop(), [])
        self.assertFalse(killed)

    def test_supervisor_stops_only_its_tiny_offline_child_at_wall_guard(self):
        result = supervise(
            [
                sys.executable,
                "-c",
                "import time; print('offline child', flush=True); time.sleep(20)",
            ],
            self.folder / "supervision",
            cwd=self.folder,
            wall_seconds=0.2,
            memory_bytes=512 * 1024 * 1024,
            approval_reference="offline-unit-test-no-solver",
            interval=0.025,
        )
        self.assertEqual(result["guard"], "external_wall_guard")
        self.assertFalse(result["automatic_retry"])
        self.assertIsNone(result["job_memory_after"])
        self.assertLess(result["external_wall_seconds"], 10)
        self.assertGreaterEqual(result["sample_count"], 1)

    def test_parser_pinned_release_synthetic14_and_credential_filter(self):
        path = self.folder / "synthetic.log"
        path.write_text(SYNTHETIC_LOG)
        result = parse_native_log(
            path, self.folder / "parsed", source_kind="synthetic_fixture"
        )
        self.assertEqual(result["parser"]["version"], "4.0.1")
        self.assertEqual(result["redacted_line_count"], 2)
        self.assertEqual(result["summaries"][0]["fields"]["Version"]["value"], "14.0.0")
        self.assertEqual(result["summaries"][0]["fields"]["Status"]["value"], "OPTIMAL")
        self.assertIn("synthetic", result["native14_qualification"])
        self.assertNotIn(
            "fake-sensitive-value",
            (self.folder / "parsed" / "sanitized.log").read_text(),
        )
        self.assertNotIn(
            "fake-sensitive-value", (self.folder / "parsed" / "parsed.json").read_text()
        )

        fields = result["summaries"][0]["fields"]
        self.assertEqual(fields["NumConstrs"]["value"], 1)
        self.assertEqual(fields["NumVars"]["value"], 20)
        self.assertEqual(fields["PresolvedNumVars"]["value"], 0)
        self.assertEqual(fields["Runtime"]["value"], 0.01)
        self.assertEqual(fields["ObjVal"]["value"], 11)
        tree = next(row for row in result["progress"] if row["section"] == "nodelog")
        self.assertEqual(tree["rows"][-1]["CurrentNode"]["value"], 0)

    def test_root_LP_status_and_time_cannot_become_truncated_MIP_terminal(self):
        path = self.folder / "synthetic-truncated.log"
        path.write_text(
            "Gurobi Optimizer version 14.0.0 (synthetic)\nOptimize a model with 1 rows, 20 columns and 20 nonzeros\nSolved in 1 iterations and 0.02 seconds (0.01 work units)\nOptimal objective 1.100000000e+01\n"
        )
        result = parse_native_log(
            path, self.folder / "parsed", source_kind="synthetic_fixture"
        )
        summary = result["summaries"][0]
        self.assertIsNone(summary["fields"]["Status"]["value"])
        self.assertIsNone(summary["fields"]["Runtime"]["value"])
        self.assertIsNone(summary["fields"]["ObjVal"]["value"])
        self.assertEqual(
            summary["continuous_phase"]["fields"]["Status"]["value"], "OPTIMAL"
        )
        self.assertEqual(
            summary["continuous_phase"]["fields"]["Runtime"]["value"], 0.02
        )

    def test_truncated_or_unsupported_terminal_is_missing_not_optimal(self):
        for index, ending in enumerate(
            ("", "Sub-optimal termination", "Locally optimal solution found")
        ):
            path = self.folder / f"synthetic-{index}.log"
            path.write_text(
                "Gurobi Optimizer version 14.0.0 (synthetic)\n" + ending + "\n"
            )
            result = parse_native_log(
                path, self.folder / f"parsed-{index}", source_kind="synthetic_fixture"
            )
            self.assertIsNone(result["summaries"][0]["fields"]["Status"]["value"])

    def test_parser_version_drift_rejected_before_output(self):
        with (
            patch("cfl_gnn.mvp3.logparse.version", return_value="99.0.0"),
            self.assertRaises(ContractError),
        ):
            parse_native_log(
                self.folder / "absent",
                self.folder / "parsed",
                source_kind="synthetic_fixture",
            )
        self.assertFalse((self.folder / "parsed").exists())

    def test_NoRel_keeps_its_own_clock_origin(self):
        path = self.folder / "synthetic.log"
        path.write_text(
            "Gurobi Optimizer version 14.0.0 (synthetic)\nStarting NoRel heuristic\nElapsed time for NoRel heuristic: 5s (best bound 10)\n"
        )
        result = parse_native_log(
            path, self.folder / "parsed", source_kind="synthetic_fixture"
        )
        progress = next(row for row in result["progress"] if row["section"] == "norel")
        self.assertEqual(
            progress["clock_origin"], "NoRel_heuristic_entry_not_optimize_entry"
        )
        self.assertTrue(progress["rows"])


if __name__ == "__main__":
    unittest.main()
