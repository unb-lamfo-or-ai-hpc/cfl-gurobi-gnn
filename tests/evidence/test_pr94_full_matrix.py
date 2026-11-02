"""Offline identity, pairing and release-boundary checks for the full matrix."""

import copy
import csv
import importlib.util
import io
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pr94_full_plan", ROOT / "scripts/evidence/plan_pr94_full_matrix.py"
)
planner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = planner
SPEC.loader.exec_module(planner)
PACKAGE = ROOT / "docs/research/solver-seed-extension-v1"


class FullMatrixTests(unittest.TestCase):
    def setUp(self):
        with (PACKAGE / "cohort.csv").open(encoding="utf-8", newline="") as stream:
            self.cohort = list(csv.DictReader(stream))
        self.bindings = json.loads(
            (PACKAGE / "historical-artifact-bindings.json").read_text()
        )

    def compile(self):
        return planner.compile_plan(self.cohort, self.bindings)

    def test_complete_fresh_pairing_retains_M7_and_sensitive_instances(self):
        plan, raw = self.compile()
        rows = list(csv.DictReader(io.StringIO(raw.decode())))
        self.assertEqual(len({r["cell_id"] for r in rows}), 144)
        self.assertEqual(Counter(r["alias"] for r in rows)["M7"], 9)
        self.assertEqual(Counter(r["alias"] for r in rows)["M4"], 9)
        self.assertEqual(Counter(r["alias"] for r in rows)["M12"], 9)
        for parent in {r["parent"] for r in rows}:
            subset = [r for r in rows if r["parent"] == parent]
            self.assertEqual(
                {(int(r["seed"]), r["method"]) for r in subset},
                {(s, m) for s in (42, 43, 44) for m in ("M0", "M1", "M2")},
            )
        self.assertEqual(plan["historical_rows_counted_as_new"], 0)
        self.assertTrue(all(r["new_solve"] == "True" for r in rows))

    def test_four_serial_lanes_have_no_cycle_or_cross_lane_edge(self):
        plan, _ = self.compile()
        seen = {}
        for g in plan["groups"]:
            if g["predecessor_group_id"]:
                self.assertEqual(seen[g["predecessor_group_id"]]["lane"], g["lane"])
            seen[g["group_id"]] = g
        self.assertEqual(
            Counter(g["lane"] for g in seen.values()), {0: 12, 1: 12, 2: 12, 3: 12}
        )

    def test_within_parent_order_balances_each_method_position(self):
        plan, _ = self.compile()
        for parent in {g["parent"] for g in plan["groups"]}:
            gs = [g for g in plan["groups"] if g["parent"] == parent]
            for position in range(3):
                self.assertEqual(
                    {g["methods"][position] for g in gs}, {"M0", "M1", "M2"}
                )

    def test_closed_release_even_after_successful_compilation(self):
        plan, _ = self.compile()
        for key in (
            "execution_released",
            "reporting_eligible",
            "all_16_current_private_byte_preflights_received",
            "all_Start_bindings_reviewed",
        ):
            self.assertIs(plan[key], False)
        self.assertIs(plan["dispatcher_implemented"], True)
        self.assertEqual(plan["assigned_job_ids"], [])
        self.assertEqual(plan["preparation"]["source"], planner.PREPARATION_SOURCE)
        self.assertFalse(plan["preparation"]["installed_source_modified"])

    def test_duplicate_parent_cannot_displace_missing_M7(self):
        self.cohort[8] = copy.deepcopy(self.cohort[0])
        with self.assertRaisesRegex(ValueError, "cohort_identity"):
            self.compile()

    def test_changed_historical_model_or_checkpoint_stops(self):
        for key in ("model_sha256", "checkpoint_sha256"):
            original = self.bindings["parents"][0][key]
            self.bindings["parents"][0][key] = "0" * 64
            with self.assertRaises(ValueError):
                self.compile()
            self.bindings["parents"][0][key] = original

    def test_missing_start_binding_stops(self):
        self.bindings["parents"][0]["M1_assignment_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "artifact_hash"):
            self.compile()

    def test_new_parent_must_not_be_called_untouched(self):
        self.cohort[-1]["independent_untouched_generalization_claim"] = "true"
        with self.assertRaisesRegex(ValueError, "exposure"):
            self.compile()

    def test_published_plan_reproduces_from_unchanged_inputs(self):
        plan, raw = self.compile()
        package = ROOT / "docs/research/solver-seed-extension-v2"
        self.assertEqual((package / "planned-cells.csv").read_bytes(), raw)
        self.assertEqual(json.loads((package / "plan.json").read_text()), plan)


if __name__ == "__main__":
    unittest.main()
