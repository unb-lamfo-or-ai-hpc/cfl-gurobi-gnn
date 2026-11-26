"""Detect formulation drift without importing Gurobi or reading real models."""

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fixtures import model  # noqa: E402

from cfl_gnn.mvp3.contract import ContractError  # noqa: E402
from cfl_gnn.mvp3.identity import model_identity, numeric  # noqa: E402


class MathematicalIdentityTests(unittest.TestCase):
    def test_declared_sense_is_preserved_but_effective_minimization_is_canonical(self):
        original = model()
        identity = model_identity(original)
        changed = copy.deepcopy(original)
        changed["declared_sense"] = "MINIMIZE"
        other = model_identity(changed)
        self.assertEqual(identity["model_sha256"], other["model_sha256"])
        self.assertNotEqual(identity["declared_sense"], other["declared_sense"])
        self.assertEqual(original["declared_sense"], "MAXIMIZE")

    def test_all_mathematical_dimensions_affect_identity(self):
        reference = model_identity(model())["model_sha256"]
        changes = [
            lambda m: m.update(objective_constant=1),
            lambda m: m["variables"][0].update(objective=2),
            lambda m: m["variables"][0].update(lower=0.5),
            lambda m: m["variables"][0].update(upper=0.5),
            lambda m: m["variables"][0].update(domain="I"),
            lambda m: m["rows"][0].update(rhs=19),
            lambda m: m["rows"][0].update(sense="<="),
            lambda m: m["rows"][0]["terms"].__setitem__(0, [0, 2]),
            lambda m: m["variables"].reverse(),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                data = model()
                change(data)
                self.assertNotEqual(model_identity(data)["model_sha256"], reference)

    def test_scalar_spelling_and_sparse_term_order_do_not_change_mathematics(self):
        data = model()
        reference = model_identity(data)
        data["objective_constant"] = -0.0
        data["variables"][0]["objective"] = 1.0
        data["rows"][0]["terms"].reverse()
        self.assertEqual(
            model_identity(data)["model_sha256"], reference["model_sha256"]
        )

    def test_unbounded_limits_have_explicit_null_semantics(self):
        data = model()
        data["variables"][0].update(domain="C", lower=None, upper=None)
        self.assertEqual(model_identity(data)["variables"], 20)
        for value in (float("inf"), float("nan"), True):
            data["variables"][0]["lower"] = value
            with self.subTest(value=value), self.assertRaises(ContractError):
                model_identity(data)

    def test_integer_coefficients_are_not_rounded_by_decimal_context(self):
        self.assertEqual(
            numeric(12345678901234567890123456789123),
            "12345678901234567890123456789123",
        )
        self.assertNotEqual(
            numeric(12345678901234567890123456789123),
            numeric(12345678901234567890123456789124),
        )

    def test_duplicate_names_coordinates_and_invalid_indices_fail(self):
        changes = [
            lambda m: m["variables"][0].update(name="x1"),
            lambda m: m["rows"].append(copy.deepcopy(m["rows"][0])),
            lambda m: m["rows"][0]["terms"].append([0, 1]),
            lambda m: m["rows"][0]["terms"].append([20, 1]),
            lambda m: m["variables"][0].update(lower=2),
            lambda m: m.update(effective_sense="MAXIMIZE"),
        ]
        for change in changes:
            data = model()
            change(data)
            with self.assertRaises(ContractError):
                model_identity(data)


if __name__ == "__main__":
    unittest.main()
