"""PR86 planning checks, without a solver, scheduler, GPU or training."""

import csv
import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import plan_pr86_comparison as proposal  # noqa: E402


class ComparisonPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.cells = proposal.build()

    def test_exact_population_and_matrix(self):
        self.assertEqual(
            {p["alias"] for p in self.plan["parents"]},
            {"F0", "F3", "F6", "F14", "F27", "F29", "M0", "M4", "M7", "M12"},
        )
        self.assertEqual(len(self.cells), 210)
        self.assertEqual(len({c["cell_id"] for c in self.cells}), 210)
        self.assertEqual(
            Counter(c["seed"] for c in self.cells), {42: 150, 43: 30, 44: 30}
        )
        self.assertTrue(all(c["threads"] == 1 for c in self.cells if c["seed"] != 42))

    def test_paired_groups_and_counterbalanced_one_thread_seeds(self):
        self.assertEqual(len(self.plan["groups"]), 70)
        for parent in self.plan["parents"]:
            groups = [g for g in self.plan["groups"] if g["parent"] == parent["parent"]]
            self.assertEqual(len(groups), 7)
            for method in proposal.METHODS:
                positions = [
                    g["method_order"].index(method) for g in groups if g["threads"] == 1
                ]
                self.assertEqual(sorted(positions), [0, 1, 2])
        for group in self.plan["groups"]:
            cells = [c for c in self.cells if c["group_id"] == group["group_id"]]
            self.assertEqual([c["method"] for c in cells], group["method_order"])
            self.assertEqual(len(cells), 3)
            self.assertEqual(len({c["model_sha256"] for c in cells}), 1)
            self.assertLessEqual(
                3 * group["child_deadline_seconds"], group["job_wall_seconds"]
            )

    def test_resource_ceiling_arithmetic(self):
        budget = self.plan["budget"]
        self.assertEqual(budget["total_jobs_maximum"], 81)
        self.assertEqual(budget["total_optimization_calls_maximum"], 220)
        self.assertEqual(budget["main_solver_seconds_maximum"], 210 * 3600)
        self.assertEqual(
            budget["main_solver_capacity_physical_core_seconds"], 990 * 3600
        )
        self.assertEqual(
            budget["main_reserved_physical_core_seconds_maximum"], 1320 * 3600
        )
        self.assertEqual(
            budget["total_sequential_job_wall_seconds_maximum"], 284 * 3600
        )
        self.assertEqual(
            budget["total_reserved_physical_core_seconds_maximum"], 1326 * 3600
        )
        self.assertEqual(budget["reserved_gpu_seconds_maximum"], 2400)

    def test_all_execution_gates_false(self):
        for key in (
            "resource_budget_approved",
            "solver_execution_admitted",
            "training_admitted",
            "scientific_reporting_eligible",
            "execution_interface_included",
            "historically_untouched_test_claimed",
        ):
            self.assertIs(self.plan[key], False)
        self.assertTrue(all(v is False for v in self.plan["execution_gates"].values()))
        self.assertTrue(all(c["state"] == "planned_not_executed" for c in self.cells))

    def test_fixed_comparison_parameters_and_resources(self):
        self.assertEqual(
            self.plan["parameters"],
            {"TimeLimit": 3600, "MIPGap": 1e-4, "SoftMemLimit": 48},
        )
        self.assertEqual(
            {c["effective_objective_sense"] for c in self.cells}, {"MINIMIZE"}
        )
        for group in self.plan["groups"]:
            self.assertEqual(group["physical_cores_requested"], group["threads"])
        self.assertEqual(self.plan["scheduler"]["nodes"], 1)
        self.assertEqual(self.plan["scheduler"]["concurrent_jobs_maximum"], 1)
        self.assertFalse(self.plan["scheduler"]["requeue"])
        self.assertFalse(self.plan["scheduler"]["exclusive"])

    def test_no_false_results_or_test_selected_checkpoint(self):
        self.assertNotIn("runtime_seconds", self.cells[0])
        self.assertNotIn("objective_value", self.cells[0])
        self.assertEqual(
            self.plan["checkpoint"]["checkpoint_sha256"], proposal.CHECKPOINT
        )
        self.assertIn("not_solver_test_speed", self.plan["checkpoint_choice"])
        for cell in self.cells:
            self.assertEqual(
                cell["checkpoint_sha256"],
                "" if cell["method"] == "M0" else proposal.CHECKPOINT,
            )

    def test_published_plan_and_tables_reproduce(self):
        published = proposal.ROOT / "docs/evidence/pr86/proposal"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "proposal"
            proposal.produce(output)
            manifest = json.loads((output / "manifest.json").read_bytes())
            for name, sha in manifest["files"].items():
                self.assertEqual(proposal.digest((output / name).read_bytes()), sha)
            for path in output.iterdir():
                self.assertEqual(
                    path.read_bytes(), (published / path.name).read_bytes()
                )
            rows = list(
                csv.DictReader(io.StringIO((output / "planned_cells.csv").read_text()))
            )
            self.assertEqual(len(rows), 210)
            with self.assertRaises(FileExistsError):
                proposal.produce(output)


if __name__ == "__main__":
    unittest.main()
