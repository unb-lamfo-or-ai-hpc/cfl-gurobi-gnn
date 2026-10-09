"""Immutable installed E0 comparison: arithmetic, limits and reproducibility."""

import ast
import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import review_e0_job3506 as review  # noqa: E402


class Job3506Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value, (cls.rows, cls.trajectory, cls.accounting) = review.reviewed()

    def test_all_eighteen_and_paired_effects(self):
        summary, effects = review.summarize(self.rows)
        self.assertEqual(len(self.rows), 18)
        self.assertEqual(len(effects), 12)
        self.assertEqual(
            [r["faster_than_control_count"] for r in summary], [None, 1, 3]
        )
        self.assertAlmostEqual(
            summary[2]["geometric_mean_runtime_ratio"], 1.1801593261388303
        )
        self.assertGreater(
            summary[2]["sum_solver_seconds"], summary[0]["sum_solver_seconds"]
        )
        self.assertTrue(all(r["gap_fraction"] <= 1e-4 for r in self.rows))
        for i in range(0, 18, 3):
            for j in (1, 2):
                self.assertAlmostEqual(
                    self.rows[i]["primal"], self.rows[i + j]["primal"], places=8
                )

    def test_missing_costs_are_not_zero_or_full_speedup(self):
        self.assertTrue(
            all(r["root_precomputation_seconds"] is None for r in self.rows)
        )
        self.assertTrue(all(r["full_end_to_end_seconds"] is None for r in self.rows))
        self.assertTrue(
            all(
                r["export_seconds_subset_of_other"]
                <= r["other_including_export_seconds"]
                for r in self.rows
            )
        )

    def test_mutations_rejected(self):
        cases = (
            ("solve", "common_mip_gap_relative", 0.1),
            ("solve", "solve_status_code", 9),
            ("independent_feasibility", "recomputed_objective", 0),
            ("timing", "total_wall_time_seconds", 0),
            ("start", "actual_coverage", 0.9),
        )
        for section, key, changed in cases:
            bad = copy.deepcopy(self.value)
            bad["matrix"]["attempts"][0]["child"]["result"][section][key] = changed
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                review.audit(bad)

    def test_trajectory_and_acceptance_tampering_rejected(self):
        bad = copy.deepcopy(self.value)
        bad["matrix"]["attempts"][0]["child"]["result"]["trajectory"][1][
            "common_gap_relative"
        ] = 0.3
        with self.assertRaisesRegex(ValueError, "trajectory_gap"):
            review.audit(bad)
        bad = copy.deepcopy(self.value)
        bad["matrix"]["attempts"][1]["child"]["result"]["start"]["accepted"] = False
        with self.assertRaisesRegex(ValueError, "acceptance"):
            review.audit(bad)

    def test_failure_or_wrong_source_rejected(self):
        for mutate in (
            lambda v: v.update(
                accounting=v["accounting"].replace("COMPLETED", "FAILED")
            ),
            lambda v: v["plan"].update(source_commit="0" * 40),
            lambda v: v["matrix"]["attempts"][0]["supervision"].update(
                child_exit_code=1
            ),
        ):
            bad = copy.deepcopy(self.value)
            mutate(bad)
            with self.assertRaises(ValueError):
                review.audit(bad)

    def test_frozen_pins_survive_additive_review_scripts(self):
        pins = self.value["plan"]["source_sha256_lf"]
        self.assertNotIn("scripts/evidence/review_e0_job3506.py", pins)
        self.assertIn("scripts/evidence/e0_three_method_executor.py", pins)
        self.assertEqual(len(review.audit(self.value)[0]), 18)
        bad = copy.deepcopy(self.value)
        bad["plan"]["source_sha256_lf"][
            "scripts/evidence/e0_three_method_executor.py"
        ] = "0" * 64
        with self.assertRaisesRegex(ValueError, "frozen_source_changed"):
            review.audit(bad)

    def test_exports_reproduce_and_assets_bound(self):
        stored = review.SOURCE.parent / "job3506-results"
        manifest = json.loads((stored / "asset_hashes.json").read_bytes())
        self.assertEqual(manifest["source_return_sha256"], review.SHA)
        for name, sha in manifest["files"].items():
            self.assertEqual(
                review.flow.digest((stored / name).read_bytes()), sha, name
            )
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            output = Path(folder) / "review"
            review.produce(output)
            for path in output.iterdir():
                if path.name != "asset_hashes.json":
                    self.assertEqual(
                        path.read_bytes(), (stored / path.name).read_bytes(), path.name
                    )
            with self.assertRaises(FileExistsError):
                review.produce(output)

    def test_no_solver_or_scheduler_execution(self):
        tree = ast.parse(Path(review.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(
                    node.func.attr,
                    {"optimize", "optimizeAsync", "backward", "Popen", "system"},
                )


if __name__ == "__main__":
    unittest.main()
