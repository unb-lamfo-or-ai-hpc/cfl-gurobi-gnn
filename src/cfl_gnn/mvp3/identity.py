"""Canonical mathematical identity from an already extracted model description."""

import math
from decimal import Decimal

from .contract import digest, require


def numeric(value):
    require(type(value) in (int, float), "Expected a finite real number, not bool")
    require(
        not isinstance(value, float) or math.isfinite(value), "Nonfinite model value"
    )
    number = Decimal(str(value))
    if number == 0:
        return "0"
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def model_identity(model):
    """Hash effective MINIMIZE mathematics, retaining original coordinate order.

    Null lower/upper bounds denote negative/positive infinity respectively.
    This function reads no LP, changes no solver model and audits no solution.
    """
    require(
        set(model)
        == {
            "declared_sense",
            "effective_sense",
            "objective_constant",
            "variables",
            "rows",
        },
        "Unexpected model fields",
    )
    require(
        model["declared_sense"] in ("MINIMIZE", "MAXIMIZE"), "Unknown declared sense"
    )
    require(model["effective_sense"] == "MINIMIZE", "Effective sense must be MINIMIZE")
    variables = []
    for variable in model["variables"]:
        require(
            set(variable) == {"name", "domain", "lower", "upper", "objective"},
            "Unexpected variable fields",
        )
        require(
            isinstance(variable["name"], str) and variable["name"],
            "Empty variable name",
        )
        require(variable["domain"] in ("B", "I", "C"), "Unknown variable domain")
        lower, upper = variable["lower"], variable["upper"]
        if lower is not None:
            numeric(lower)
        if upper is not None:
            numeric(upper)
        require(lower is None or upper is None or lower <= upper, "Reversed bounds")
        variables.append(
            {
                "name": variable["name"],
                "domain": variable["domain"],
                "lower": None if lower is None else numeric(lower),
                "upper": None if upper is None else numeric(upper),
                "objective": numeric(variable["objective"]),
            }
        )
    names = [variable["name"] for variable in variables]
    require(
        bool(names) and len(set(names)) == len(names),
        "Missing/duplicate variable names",
    )
    rows = []
    for row in model["rows"]:
        require(set(row) == {"name", "sense", "rhs", "terms"}, "Unexpected row fields")
        require(isinstance(row["name"], str) and row["name"], "Empty row name")
        require(row["sense"] in ("<=", "=", ">="), "Unknown row sense")
        terms = []
        positions = set()
        for position, coefficient in row["terms"]:
            require(
                type(position) is int and 0 <= position < len(variables),
                "Invalid coefficient position",
            )
            require(position not in positions, "Duplicate row coordinate")
            positions.add(position)
            value = numeric(coefficient)
            if value != "0":
                terms.append([position, value])
        rows.append(
            {
                "name": row["name"],
                "sense": row["sense"],
                "rhs": numeric(row["rhs"]),
                "terms": sorted(terms),
            }
        )
    require(len({row["name"] for row in rows}) == len(rows), "Duplicate row name")
    payload = {
        "effective_sense": "MINIMIZE",
        "objective_constant": numeric(model["objective_constant"]),
        "variables": variables,
        "rows": rows,
    }
    return {
        "model_sha256": digest(payload),
        "variable_order_sha256": digest(names),
        "declared_sense": model["declared_sense"],
        "effective_sense": "MINIMIZE",
        "variables": len(variables),
        "rows": len(rows),
        "nonzeros": sum(len(row["terms"]) for row in rows),
        "objective_constant": model["objective_constant"],
    }
