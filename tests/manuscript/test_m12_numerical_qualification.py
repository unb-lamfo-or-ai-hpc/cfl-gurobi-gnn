"""Reject promotion of a scoped primal check to a global result."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("partial_m12", ROOT / "scripts/manuscript/build_partial_cpu_assets.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class M12Qualification(unittest.TestCase):
    def setUp(self):
        self.value = json.loads((ROOT / p.M12_AUDIT).read_text(encoding="utf-8"))

    def test_scoped_feasibility_is_consistent(self):
        p.validate_m12_audit(self.value)

    def test_global_optimality_promotion_rejected(self):
        self.value["exact_optimality_certified"] = True
        with self.assertRaisesRegex(ValueError, "m12_audit_scope"):
            p.validate_m12_audit(self.value)

    def test_control_is_not_an_exact_feasible_counterexample(self):
        self.value["rows"][2]["diagnostics"]["exact_integer_primal_feasible_decimal_lp_model"] = True
        with self.assertRaisesRegex(ValueError, "m12_primal_not_global"):
            p.validate_m12_audit(self.value)

    def test_rounding_is_not_a_repaired_result(self):
        self.value["rows"][2]["diagnostics"]["integer_rounded_copy"]["exact_decimal_lp_rows"]["max_row_residual_rational"] = "0"
        with self.assertRaisesRegex(ValueError, "m12_rounded_residual"):
            p.validate_m12_audit(self.value)

    def test_continuous_completion_obstruction_cannot_be_silently_removed(self):
        self.value["rows"][0]["diagnostics"]["fixed_rounded_integer_pattern_row_obstructions"] = []
        with self.assertRaisesRegex(ValueError, "m12_fixed_pattern_obstruction"):
            p.validate_m12_audit(self.value)


if __name__ == "__main__":
    unittest.main()
