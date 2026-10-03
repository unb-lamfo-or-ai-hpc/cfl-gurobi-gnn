"""Check cohort and counter semantics without using HPC evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("computational_inventory", Path(__file__).resolve().parents[2] / "scripts/archive/collect_mvp_computational_inventory.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ComputationalInventoryTests(unittest.TestCase):
    def test_counts_are_not_solutions_and_boolean_is_not_count(self):
        rows = M.counters({"task": {"incumbent_count": 5}, "num_incumbents": True})
        self.assertEqual(rows, [{"json_pointer": "/task/incumbent_count", "reported_counter": 5}])

    def test_membership_is_identity_bound(self):
        self.assertEqual(M.identities({"entries": [{"source_instance_id": "CFL_easy_instance_0"}]}), {"CFL_easy_instance_0"})

    def test_invalid_or_missing_reports_do_not_invent_population_counts(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            data, training = base / "data", base / "training"
            (data / "analysis").mkdir(parents=True)
            training.mkdir()
            population = [f"CFL_easy_instance_{i}" for i in range(30)] + [f"CFL_medium_instance_{i}" for i in range(24)]
            (training / "gasse_training_plan.json").write_text(json.dumps({"cohort": population}))
            (data / "analysis/invalid.json").write_text("")
            M.collect(data, training, base / "output")
            result = json.loads((base / "output/incumbent_inventory.json").read_text())
            self.assertIsNone(result["complete_scip_54_parent_incumbent_total"])
            self.assertEqual(result["solver_runs"], 0)
            self.assertTrue(any(x.get("reason") == "invalid_json" for x in result["issues"]))


if __name__ == "__main__":
    unittest.main()
