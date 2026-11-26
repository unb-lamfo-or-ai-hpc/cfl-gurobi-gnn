"""Bounded original-model geometry and S1-A-compatible streaming signatures."""

import hashlib
import math

from .contract import canonical_bytes, digest, require
from .identity import numeric


class NativeMatrix:
    """Read the original model, never its presolved copy or a solver solution."""

    def __init__(self, model, declared_sense, infinity=1e100):
        require(model.ModelSense == 1, "Original model must use MINIMIZE")
        require(
            not any(
                getattr(model, name)
                for name in ("NumQNZs", "NumQConstrs", "NumGenConstrs", "NumSOS")
            ),
            "Only the admitted linear MILP representation is supported",
        )
        self.model = model
        self.declared_sense = declared_sense
        self.infinity = infinity
        self.native_variables = tuple(model.getVars())
        self.variables = tuple(
            {
                "name": variable.VarName,
                "domain": variable.VType,
                "lower": None if variable.LB <= -infinity else float(variable.LB),
                "upper": None if variable.UB >= infinity else float(variable.UB),
                "objective": float(variable.Obj),
            }
            for variable in self.native_variables
        )
        self.objective_constant = float(model.ObjCon)

    def rows(self):
        for constraint in self.model.getConstrs():
            expression = self.model.getRow(constraint)
            yield {
                "name": constraint.ConstrName,
                "sense": {"<": "<=", "=": "=", ">": ">="}[constraint.Sense],
                "rhs": float(constraint.RHS),
                "terms": [
                    [expression.getVar(index).index, float(expression.getCoeff(index))]
                    for index in range(expression.size())
                ],
            }


class DescriptionMatrix:
    """Already extracted geometry, useful for independent small-model tests."""

    def __init__(self, description):
        require(description["effective_sense"] == "MINIMIZE", "MINIMIZE required")
        self.variables = description["variables"]
        self.objective_constant = description["objective_constant"]
        self.declared_sense = description["declared_sense"]
        self.description = description

    def rows(self):
        return iter(self.description["rows"])


def _normal_variable(variable):
    require(
        set(variable) == {"name", "domain", "lower", "upper", "objective"},
        "Unexpected variable fields",
    )
    require(
        isinstance(variable["name"], str) and variable["name"], "Missing variable name"
    )
    require(variable["domain"] in ("B", "I", "C"), "Unsupported variable domain")
    lower, upper = variable["lower"], variable["upper"]
    require(lower is None or upper is None or lower <= upper, "Reversed bounds")
    return {
        **variable,
        "lower": None if lower is None else numeric(lower),
        "upper": None if upper is None else numeric(upper),
        "objective": numeric(variable["objective"]),
    }


def streamed_identity(matrix):
    """Match model_identity() without retaining all rows/coefficients twice."""
    variables = matrix.variables
    names = [variable["name"] for variable in variables]
    require(names and len(set(names)) == len(names), "Missing/duplicate variable names")
    require(matrix.declared_sense in ("MINIMIZE", "MAXIMIZE"), "Unknown declared sense")
    result = hashlib.sha256()
    result.update(b'{"effective_sense":"MINIMIZE","objective_constant":')
    result.update(canonical_bytes(numeric(matrix.objective_constant)))
    result.update(b',"rows":[')
    row_names = set()
    row_count = nonzeros = 0
    for row in matrix.rows():
        require(set(row) == {"name", "sense", "rhs", "terms"}, "Unexpected row fields")
        require(
            isinstance(row["name"], str)
            and row["name"]
            and row["name"] not in row_names,
            "Missing/duplicate row names",
        )
        row_names.add(row["name"])
        require(row["sense"] in ("<=", "=", ">="), "Unknown row sense")
        terms, positions = [], set()
        for position, coefficient in row["terms"]:
            require(
                type(position) is int and 0 <= position < len(variables),
                "Invalid original coordinate",
            )
            require(position not in positions, "Duplicate sparse coordinate")
            positions.add(position)
            normalized = numeric(coefficient)
            if normalized != "0":
                terms.append([position, normalized])
        normal = {
            "name": row["name"],
            "sense": row["sense"],
            "rhs": numeric(row["rhs"]),
            "terms": sorted(terms),
        }
        if row_count:
            result.update(b",")
        result.update(canonical_bytes(normal))
        row_count += 1
        nonzeros += len(terms)
    result.update(b'],"variables":[')
    for index, variable in enumerate(variables):
        if index:
            result.update(b",")
        result.update(canonical_bytes(_normal_variable(variable)))
    result.update(b"]}")
    return {
        "model_sha256": result.hexdigest(),
        "variable_order_sha256": digest(names),
        "declared_sense": matrix.declared_sense,
        "effective_sense": "MINIMIZE",
        "variables": len(variables),
        "rows": row_count,
        "nonzeros": nonzeros,
        "objective_constant": matrix.objective_constant,
    }


def real_value(value):
    require(
        type(value) in (int, float) and math.isfinite(value),
        "Nonfinite/non-numeric vector coordinate",
    )
    return float(value)
