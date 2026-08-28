"""Dependency-free schemas persisted in ``original_features.pickle.gz``.

Keeping these classes outside solver modules lets graph construction read new
artifacts without importing Gurobi. Field order is identical to the legacy v7
named tuples.
"""

from collections import namedtuple


ModelFeatures = namedtuple(
    "ModelFeatures",
    [
        "num_vars",
        "num_constrs",
        "num_binary",
        "num_integer",
        "num_continuous",
        "obj_sense",
        "obj_offset",
    ],
)

VariableFeatures = namedtuple(
    "VariableFeatures", ["types", "lower_bounds", "upper_bounds", "obj_coeffs"]
)

ConstraintFeatures = namedtuple(
    "ConstraintFeatures", ["senses", "rhs_values", "row_norms"]
)
