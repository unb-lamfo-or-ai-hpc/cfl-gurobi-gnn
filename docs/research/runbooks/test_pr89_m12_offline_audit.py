"""Independent synthetic checks of the numerical audit, no solver imports."""
import importlib.util
import io
import unittest
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

import numpy as np

spec = importlib.util.spec_from_file_location("m12_offline", Path(__file__).with_name("pr89_m12_offline_audit.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

LP = """Maximize
  x0 + 2 x1
  + 0.5 x2
Subject To
 R0: x0 + x1 >= 1
 R1: x2 - 800 x1 <= 0
Bounds
 x2 <= 1
Binaries
 x0 x1
End
"""


class ExactArithmetic(unittest.TestCase):
    def toy(self):
        return dict(rows=np.array([0, 0, 1]), cols=np.array([0, 1, 1]),
                    coefficients=np.array([-800., 1., -1.]), tokens=["-800", "1", "-1"],
                    rhs=np.array([0., -0.00004]), rhs_tokens=["0", "-0.00004"], senses=["<=", "<="],
                    binary=np.array([True, False]), upper=np.array([1., 1.]),
                    objective=np.array([3., 2.]), cost_tokens={0:"3", 1:"2"})

    def test_rounding_can_break_row_despite_small_integer_residual(self):
        a = self.toy()
        x = np.array([2.**-24, 800*2.**-24])
        original, _ = m.exact_rows(a, x)
        self.assertTrue(original["all_rows_exactly_satisfied"])
        copy = x.copy()
        copy[0] = 0
        rounded, _ = m.exact_rows(a, copy)
        self.assertEqual(rounded["rows_exceeding_frozen_1e_minus6"], 1)
        self.assertEqual(rounded["max_row_residual"], 800*2.**-24)
        self.assertLess(x[0], 1e-5)
        self.assertEqual(x[0], 2.**-24)

    def test_integer_pattern_obstruction_in_a_different_row(self):
        # Fixing the first binary at0 allows y=0 in row0, but row1 demands y>0.
        # A single-row interval screen must not incorrectly prove full completion.
        a = self.toy()
        x = np.array([0., 0.00004])
        obstruction = m.fixed_integer_row_obstruction(a, x, 0)
        self.assertFalse(obstruction["continuous_completion_impossible_from_this_row"])

    def test_positive_fixed_binary_term_proves_no_continuous_completion(self):
        a = self.toy()
        a["rows"], a["cols"] = np.array([0, 0]), np.array([0, 1])
        a["coefficients"], a["tokens"] = np.array([0.0000416587, 1.]), ["0.0000416587", "1"]
        a["rhs"], a["rhs_tokens"], a["senses"] = np.array([0.]), ["0"], ["<="]
        obstruction = m.fixed_integer_row_obstruction(a, np.array([1., 0.]), 0)
        self.assertTrue(obstruction["continuous_completion_impossible_from_this_row"])
        self.assertEqual(F(obstruction["violation_margin_rational_decimal_lp"]), F("0.0000416587"))

    def test_binary64_and_decimal_coefficient_semantics_are_distinct(self):
        a = dict(rows=np.array([0]), cols=np.array([0]), coefficients=np.array([0.1]), tokens=["0.1"],
                 rhs=np.array([0.3]), rhs_tokens=["0.3"], senses=["<="])
        binary, _ = m.exact_rows(a, np.array([3.]))
        decimal, _ = m.exact_rows(a, np.array([3.]), True)
        self.assertGreater(binary["max_row_residual"], 0)
        self.assertEqual(decimal["max_row_residual"], 0)

    def test_objective_uses_exact_products_and_sum(self):
        a = self.toy()
        x = np.array([2.**-24, 800*2.**-24])
        self.assertEqual(m.objective(a, x), F(1603, 2**24))


class LPParser(unittest.TestCase):
    def parse(self, text):
        with patch.object(m, "N", 3):
            return m.parse_lp(io.StringIO(text), np.ones(3, dtype=bool), (2, 4, 2, 1))

    def test_linear_subset_matches_known_arrays(self):
        a = self.parse(LP)
        np.testing.assert_array_equal(a["objective"], [1., 2., 0.5])
        np.testing.assert_array_equal(a["rows"], [0, 0, 1, 1])
        np.testing.assert_array_equal(a["cols"], [0, 1, 2, 1])
        np.testing.assert_array_equal(a["coefficients"], [1., 1., 1., -800.])
        self.assertEqual(a["senses"], [">=", "<="])
        np.testing.assert_array_equal(a["binary"], [True, True, False])

    def test_unknown_bound_does_not_silently_default(self):
        with self.assertRaisesRegex(ValueError, "unsupported_bound"):
            self.parse(LP.replace("x2 <= 1", "x2 free"))

    def test_constant_objective_is_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            self.parse(LP.replace("+ 0.5 x2", "+ 0.5 x2 + 1"))

    def test_duplicate_objective_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate_objective"):
            self.parse(LP.replace("+ 0.5 x2", "+ 0.5 x2 + x0"))

    def test_missing_term_separator_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing_term_separator"):
            list(m.terms("x0 x1"))

    def test_row_sequence_rejected(self):
        with self.assertRaisesRegex(ValueError, "row_sequence"):
            self.parse(LP.replace("R1:", "R9:"))

    def test_scientific_notation_and_implicit_unit_coefficient(self):
        self.assertEqual(list(m.terms("- x0 + 4.16587e-05 x1")), [(0, -1., "-1"), (1, 4.16587e-5, "4.16587e-05")])


if __name__ == "__main__":
    unittest.main()
