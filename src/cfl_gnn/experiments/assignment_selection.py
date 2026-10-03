"""Experimental assignment selection primitives, not a qualified solver policy.

Inputs to select_calibrated must be independently calibrated probabilities.
Neither an analytic class-weight correction nor a unit test certifies empirical
calibration. No historical prediction adapter imports this module.
"""
from __future__ import annotations

import math


def probability(value):
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("probability must be finite and in [0, 1]")
    return value


def undo_positive_weight(score, weight):
    """Population optimum identity for constant positive-weighted BCE only."""
    q = probability(score)
    w = float(weight)
    if not math.isfinite(w) or w <= 0:
        raise ValueError("positive class weight required")
    # This stable form avoids cancellation near q=1 for large weights.
    return q / (w * (1 - q) + q)


def assignment_confidence(p, assigned_value):
    p = probability(p)
    if assigned_value not in (0, 1):
        raise ValueError("binary assignment required")
    return p if assigned_value == 1 else 1 - p


def validate_calibration_partition(records):
    """Require original validation parents; never accept test or synthetic rows."""
    if not records:
        raise ValueError("empty calibration population")
    names = set()
    for row in records:
        name = row["parent_instance_id"]
        if (not isinstance(name, str) or not name or name in names
                or row.get("role") != "validation" or row.get("sampling_strategy") != "original"):
            raise ValueError("calibration requires unique original validation parents")
        names.add(name)
    return names


def select_calibrated(names, probabilities, *, threshold, minimum_confidence,
                      coverage_fraction, maximum_assignments):
    """Select by confidence in the submitted value, with abstention and two caps.

    The name is the deterministic tie-breaker, never its incidental tensor index.
    This numerical kernel does not fit or certify a calibration model.
    """
    threshold = probability(threshold)
    minimum_confidence = probability(minimum_confidence)
    coverage_fraction = probability(coverage_fraction)
    if (not names or any(not isinstance(n, str) or not n for n in names)
            or len(names) != len(probabilities) or len(set(names)) != len(names)):
        raise ValueError("unique canonical variable identities required")
    if isinstance(maximum_assignments, bool) or not isinstance(maximum_assignments, int) or maximum_assignments < 0:
        raise ValueError("nonnegative integer assignment cap required")
    rows = []
    for name, raw in zip(names, probabilities):
        p = probability(raw)
        value = int(p >= threshold)
        confidence = assignment_confidence(p, value)
        if confidence >= minimum_confidence:
            rows.append(dict(variable_name=name, value=value, confidence=confidence))
    limit = min(maximum_assignments, math.floor(coverage_fraction * len(names)))
    return sorted(rows, key=lambda r: (-r["confidence"], r["variable_name"]))[:limit]


def completion_capabilities(version):
    """Version-level capabilities only; does not query a license or set parameters."""
    if not isinstance(version, (list, tuple)) or len(version) < 2 or any(type(v) is not int or v < 0 for v in version):
        raise ValueError("numeric Gurobi version required")
    modern = version[0] >= 13
    return {"start_node_limit_available": True, "node_limit_is_wall_time_cap": False,
            "start_time_limit_available": modern, "start_work_limit_available": modern,
            "parameter_api_probe_required_before_execution": True,
            "budget_selected": False}
