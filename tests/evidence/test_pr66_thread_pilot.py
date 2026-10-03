"""Offline pilot contracts; no licensed solver, HPC submission or training.

SPDX-License-Identifier: MIT
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr66_thread_pilot as pilot  # noqa: E402
from collect_computational_ledger import digest  # noqa: E402


class PilotTests(unittest.TestCase):
    def simulated_plan(self, root):
        raw = root / "raw"
        records = []
        for difficulty in ("easy", "medium"):
            path = raw / f"CFL_{difficulty}_instance/LP/CFL_{difficulty}_instance_1.lp"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"offline fixture only")
            records.append(
                {"parent_instance_id": f"CFL_{difficulty}_instance_1", "role": "train"}
            )
        roles = root / "roles.json"
        roles.write_text(json.dumps({"records": records}))
        plan = root / "plan"
        pilot.freeze(raw, roles, digest(roles), plan)
        return raw, plan, digest(plan / "pilot_plan.json")

    def test_supervisor_runs_exactly_ten_children_serially_and_never_restarts(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, plan, sha = self.simulated_plan(Path(tmp))
            seen = []

            def child(command, **kwargs):
                difficulty = command[command.index("--difficulty") + 1]
                threads = int(command[command.index("--threads") + 1])
                seen.append((threads, difficulty))
                self.assertEqual(kwargs["timeout"], 480)
                output = plan / f"{difficulty}-threads{threads}"
                output.mkdir()
                (output / "attempt_report.json").write_text('{"solver_status":9}')
                return SimpleNamespace(returncode=0)

            with (
                patch.object(
                    pilot, "qualify_affinity", return_value={"physical_cores": 16}
                ),
                patch.object(pilot.subprocess, "run", side_effect=child),
            ):
                pilot.run(plan, sha, raw)
                with self.assertRaisesRegex(ValueError, "already_started"):
                    pilot.run(plan, sha, raw)
            self.assertEqual(
                seen, [(t, d) for t in pilot.CAPS for d in ("easy", "medium")]
            )
            report = pilot.strict_json(plan / "pilot_execution_report.json")
            self.assertEqual(len(report["executions"]), 10)
            self.assertIsNone(report["failure_type"])
            self.assertFalse(report["scientific_reporting_eligible"])

    def test_supervisor_timeout_retains_failed_attempt_and_pauses_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, plan, sha = self.simulated_plan(Path(tmp))
            failure = pilot.subprocess.TimeoutExpired("offline", 480)
            with (
                patch.object(pilot, "qualify_affinity", return_value={}),
                patch.object(pilot.subprocess, "run", side_effect=failure) as child,
                self.assertRaises(pilot.subprocess.TimeoutExpired),
            ):
                pilot.run(plan, sha, raw)
            self.assertEqual(child.call_count, 1)
            report = pilot.strict_json(plan / "pilot_execution_report.json")
            self.assertEqual(report["failure_type"], "TimeoutExpired")
            self.assertEqual(len(report["executions"]), 1)
            self.assertIsNone(report["executions"][0]["exit_code"])

    def test_supervisor_affinity_failure_precedes_child_optimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, plan, sha = self.simulated_plan(Path(tmp))
            with (
                patch.object(
                    pilot, "qualify_affinity", side_effect=ValueError("topology")
                ),
                patch.object(pilot.subprocess, "run") as child,
                self.assertRaises(ValueError),
            ):
                pilot.run(plan, sha, raw)
            child.assert_not_called()

    def test_draw_is_reproducible_and_excludes_other_roles(self):
        roles = {
            f"CFL_{d}_instance_{i}": "train"
            for d in ("easy", "medium")
            for i in range(8)
        }
        roles["CFL_easy_instance_0"] = "test"
        exclusions = {"CFL_medium_instance_0", "CFL_medium_instance_4"}
        pools, selected = pilot.draw_pair(roles, exclusions)
        self.assertEqual(
            (pools, selected),
            pilot.draw_pair(dict(reversed(list(roles.items()))), exclusions),
        )
        self.assertNotIn("CFL_easy_instance_0", pools["easy"])
        self.assertFalse(exclusions.intersection(pools["medium"]))

    def test_empty_pool_is_not_redrawn_from_test(self):
        with self.assertRaisesRegex(ValueError, "empty_eligible"):
            pilot.draw_pair({"CFL_easy_instance_0": "test"}, set())

    def test_conflicting_roles_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting"):
            pilot.roles_from_plan(
                {
                    "records": [
                        {"parent_instance_id": "CFL_easy_instance_1", "role": r}
                        for r in ("train", "test")
                    ]
                }
            )

    def test_noncanonical_parent_rejected(self):
        with self.assertRaises(ValueError):
            pilot.roles_from_plan(
                {
                    "records": [
                        {"parent_instance_id": "CFL_easy_instance_01", "role": "train"}
                    ]
                }
            )

    def test_physical_mask_does_not_use_smt_siblings(self):
        mask = pilot.physical_mask(range(32), lambda cpu: (0, cpu % 16))
        self.assertEqual(mask, list(range(16)))

    def test_insufficient_and_unbounded_affinity_refused(self):
        for count in (8, 40):
            with self.subTest(count=count), self.assertRaises(ValueError):
                pilot.physical_mask(range(count), lambda cpu: (0, cpu))

    def test_socket_part_of_core_identity(self):
        self.assertEqual(
            len(pilot.physical_mask(range(16), lambda cpu: (cpu // 8, cpu % 8))), 16
        )

    def test_loose_gap_optimal_status_is_not_zero(self):
        self.assertEqual(pilot.termination(2, 0.09, 1, 0.1), "gap_target_reached")
        self.assertEqual(
            pilot.termination(2, 0, 1, 0.1), "zero_reported_gap_at_solver_tolerances"
        )
        self.assertEqual(pilot.termination(9, None, 0, 0.1), "no_incumbent")
        self.assertEqual(pilot.termination(9, 0.5, 1, 0.1), "time_limit")
        self.assertEqual(pilot.termination(17, 0.5, 1, 0.1), "memory_limit")

    def test_configuration_is_small_and_dasci_only(self):
        config = pilot.strict_json(pilot.BASE_CONFIG)
        self.assertEqual(config["cluster"], "dgx-dasci")
        self.assertFalse(config["exclusive"])
        self.assertFalse(config["extension_enabled"])
        self.assertEqual(config["thread_caps"], [1, 2, 4, 8, 16])
        self.assertEqual(config["time_limit_seconds"], 300)
        self.assertEqual(config["mip_gap_relative"], 0.1)
        self.assertEqual(config["seed"], 42)
        self.assertEqual(config["fixed_parameters"]["ConcurrentMIP"], 1)

    def test_scheduler_has_no_exclusive_or_gpu_and_no_conflicting_binding(self):
        root = pilot.BASE_CONFIG.parents[2]
        text = (root / "scripts/slurm/dasci/submit_pr66_thread_screen.sbs").read_text()
        directives = "\n".join(
            line for line in text.splitlines() if line.startswith("#SBATCH")
        )
        self.assertIn("--cpus-per-task=16", directives)
        self.assertIn("--hint=nomultithread", directives)
        self.assertNotIn("--exclusive", directives)
        self.assertNotIn("--gres", directives)
        self.assertNotIn("--array", directives)
        self.assertNotIn("--cpu-bind=cores ", text)

    def test_duplicate_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            for text in ('{"x":1,"x":2}', '{"x":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    pilot.strict_json(path)

    def test_freeze_binds_gzip_stored_bytes_and_does_not_copy_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            records = []
            for difficulty in ("easy", "medium"):
                lp = (
                    raw
                    / f"CFL_{difficulty}_instance/LP/CFL_{difficulty}_instance_1.lp.gz"
                )
                lp.parent.mkdir(parents=True)
                lp.write_bytes(b"test stored bytes not passed to a solver")
                records.append(
                    {
                        "parent_instance_id": f"CFL_{difficulty}_instance_1",
                        "role": "train",
                    }
                )
            roles = root / "roles.json"
            roles.write_text(json.dumps({"records": records}))
            output = root / "plan"
            plan = pilot.freeze(raw, roles, digest(roles), output)
            self.assertEqual(plan["optimization_runs"], 0)
            self.assertEqual(
                {p.name for p in output.iterdir()},
                {"pilot_plan.json", "pilot_plan.sha256"},
            )
            expected = digest(output / "pilot_plan.json")
            self.assertEqual(pilot.verified_plan(output, expected), plan)
            tampered = copy.deepcopy(plan)
            tampered["models"][0]["source_instance_id"] = "CFL_easy_instance_2"
            (output / "pilot_plan.json").write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "hash_mismatch"):
                pilot.verified_plan(output, expected)
            with self.assertRaisesRegex(ValueError, "drawn_pair"):
                pilot.verified_plan(output, digest(output / "pilot_plan.json"))

    def test_freeze_wrong_role_hash_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roles = root / "roles.json"
            roles.write_text("{}")
            with self.assertRaisesRegex(ValueError, "role_plan_hash"):
                pilot.freeze(root, roles, "0" * 64, root / "out")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
