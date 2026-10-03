"""Deterministic class-aware partial starts for PR58 validation qualification."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from cfl_gnn.graph.gurobi_graph_artifact import canonical_sha256


METHODS = (
    "unguided_control",
    "root_lp_matched_partial_start",
    "gnn_class_aware_partial_start",
)


def _probability(row: Mapping[str, object]) -> float:
    value = float(row["probability"])
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("prediction probability must be finite and contained in [0, 1]")
    return value


def _prediction_inventory(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        name = str(row.get("variable_name", ""))
        predicted = row.get("predicted_value")
        probability = _probability(row)
        if not name or predicted not in (0, 1):
            raise ValueError("prediction identity or assigned value is invalid")
        normalized.append(
            {
                "variable_name": name,
                "value": int(predicted),
                "probability": probability,
                "assigned_value_confidence": probability if predicted == 1 else 1.0 - probability,
            }
        )
    names = [str(row["variable_name"]) for row in normalized]
    if not normalized or len(names) != len(set(names)):
        raise ValueError("predictions must be nonempty and unique")
    return normalized


def support_size(binary_variables: int, fraction: float, absolute_cap: int) -> int:
    if binary_variables <= 0 or not math.isfinite(fraction) or not 0.0 < fraction <= 1.0:
        raise ValueError("invalid support population or coverage fraction")
    if absolute_cap <= 0:
        raise ValueError("absolute support cap must be positive")
    return min(binary_variables, absolute_cap, max(1, math.floor(binary_variables * fraction)))


def _assignment(row: Mapping[str, object], *, source: str) -> dict[str, object]:
    confidence = float(row["assigned_value_confidence"])
    return {
        "variable_name": str(row["variable_name"]),
        "value": int(row["value"]),
        "confidence": confidence,
        "priority": min(100, max(0, int(round(100.0 * confidence)))),
        "selection_source": source,
    }


def class_aware_gnn_assignments(
    rows: Sequence[Mapping[str, object]],
    *,
    fraction: float,
    absolute_cap: int,
    abstain_without_positive: bool = True,
) -> dict[str, object]:
    """Keep rare predicted positives from being displaced by confident zeros."""
    inventory = _prediction_inventory(rows)
    count = support_size(len(inventory), fraction, absolute_cap)
    positives = sorted(
        (row for row in inventory if row["value"] == 1),
        key=lambda row: (-float(row["probability"]), str(row["variable_name"])),
    )
    if not positives and abstain_without_positive:
        return {
            "assignments": [],
            "abstained": True,
            "reason_code": "no_threshold_positive_prediction",
            "binary_variables": len(inventory),
            "requested_support": count,
            "selected_support": 0,
            "positive_assignments": 0,
            "negative_assignments": 0,
            "assignment_sha256": canonical_sha256([]),
        }
    selected_positive = positives[:count]
    remaining = count - len(selected_positive)
    negatives = sorted(
        (row for row in inventory if row["value"] == 0),
        key=lambda row: (-float(row["assigned_value_confidence"]), str(row["variable_name"])),
    )
    selected = [
        *(_assignment(row, source="gnn_threshold_positive") for row in selected_positive),
        *(_assignment(row, source="gnn_confident_zero") for row in negatives[:remaining]),
    ]
    return {
        "assignments": selected,
        "abstained": False,
        "reason_code": "class_aware_support_selected",
        "binary_variables": len(inventory),
        "requested_support": count,
        "selected_support": len(selected),
        "positive_assignments": len(selected_positive),
        "negative_assignments": len(selected) - len(selected_positive),
        "assignment_sha256": canonical_sha256(selected),
    }


def matched_root_lp_assignments(
    variable_names: Sequence[str],
    root_values: Sequence[float],
    *,
    support: int,
    positive_assignments: int,
) -> dict[str, object]:
    """Create a root-LP baseline matched on support size and class composition."""
    if len(variable_names) != len(root_values) or not variable_names:
        raise ValueError("root-LP identity or length mismatch")
    if len(set(variable_names)) != len(variable_names):
        raise ValueError("root-LP variable names must be unique")
    if not 0 <= positive_assignments <= support <= len(variable_names):
        raise ValueError("invalid matched-support request")
    rows = []
    for name, raw in zip(variable_names, root_values):
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("root-LP value must be finite")
        probability = min(1.0, max(0.0, value))
        rows.append({"variable_name": str(name), "probability": probability})
    positive_rows = sorted(rows, key=lambda row: (-row["probability"], row["variable_name"]))[
        :positive_assignments
    ]
    positive_names = {row["variable_name"] for row in positive_rows}
    negative_rows = sorted(
        (row for row in rows if row["variable_name"] not in positive_names),
        key=lambda row: (row["probability"], row["variable_name"]),
    )[: support - positive_assignments]
    assignments = [
        {
            "variable_name": row["variable_name"],
            "value": 1,
            "confidence": row["probability"],
            "priority": min(100, max(0, int(round(100.0 * row["probability"])))),
            "selection_source": "root_lp_matched_positive",
        }
        for row in positive_rows
    ] + [
        {
            "variable_name": row["variable_name"],
            "value": 0,
            "confidence": 1.0 - row["probability"],
            "priority": min(100, max(0, int(round(100.0 * (1.0 - row["probability"]))))),
            "selection_source": "root_lp_matched_zero",
        }
        for row in negative_rows
    ]
    return {
        "assignments": assignments,
        "abstained": support == 0,
        "reason_code": "root_lp_support_matched_to_gnn",
        "binary_variables": len(rows),
        "requested_support": support,
        "selected_support": len(assignments),
        "positive_assignments": len(positive_rows),
        "negative_assignments": len(negative_rows),
        "assignment_sha256": canonical_sha256(assignments),
    }
