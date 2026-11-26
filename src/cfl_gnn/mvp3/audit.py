"""Independent numerical checks of retained points against original MILP rows."""

import math
from dataclasses import asdict, dataclass
from itertools import chain

from .contract import digest, require
from .matrix import real_value, streamed_identity


@dataclass(frozen=True)
class AuditPolicy:
    """Versioned absolute-tolerance policy, never an extra solve or a repair."""

    row: float = 1e-6
    bound: float = 1e-6
    integrality: float = 1e-5
    objective: float = 1e-6

    def tolerances(self):
        values = asdict(self)
        require(
            all(
                type(value) in (int, float) and math.isfinite(value) and value >= 0
                for value in values.values()
            ),
            "Invalid audit tolerance",
        )
        return values

    @property
    def sha256(self):
        return digest(self.tolerances())


def quantity(value, reason=None):
    require(
        (value is None and isinstance(reason, str) and bool(reason.strip()))
        or (value is not None and reason is None),
        "Invalid measurement availability",
    )
    return {"value": value, "missing_reason": reason}


def audit_point(
    matrix, vector, policy, *, native_objective=None, continuous=False, identity=None
):
    """Audit a retained point; integer snapping is explicit and independently checked.

    Every original integer coordinate is rounded only within IntFeasTol. The
    canonical point, original point and rounding effects retain distinct hashes.
    Continuous coordinates are never completed, optimised or silently repaired.
    """
    tolerance = policy.tolerances()
    require(len(vector) == len(matrix.variables), "Incomplete original-variable vector")
    original = [real_value(value) for value in vector]
    canonical = list(original)
    integrality = 0.0
    changed = []
    if not continuous:
        for index, (variable, value) in enumerate(zip(matrix.variables, original)):
            if variable["domain"] in ("I", "B"):
                nearest = round(value)
                residual = abs(value - nearest)
                integrality = max(integrality, residual)
                if residual <= tolerance["integrality"]:
                    canonical[index] = float(nearest)
                    if canonical[index] != value:
                        changed.append(index)
    canonical_integrality = max(
        (
            abs(value - round(value))
            for variable, value in zip(matrix.variables, canonical)
            if variable["domain"] in ("I", "B")
        ),
        default=0.0,
    )
    max_bound = max_row = 0.0
    worst_bound = worst_row = None
    for index, (variable, value) in enumerate(zip(matrix.variables, canonical)):
        lower, upper = variable["lower"], variable["upper"]
        if variable["domain"] == "B":
            lower = 0 if lower is None else max(0, lower)
            upper = 1 if upper is None else min(1, upper)
        residual = max(
            0.0,
            0.0 if lower is None else lower - value,
            0.0 if upper is None else value - upper,
        )
        if residual > max_bound:
            max_bound, worst_bound = residual, index
    try:
        for row in matrix.rows():
            lhs = math.fsum(
                real_value(coefficient) * canonical[index]
                for index, coefficient in row["terms"]
            )
            require(math.isfinite(lhs), "Nonfinite original-row activity")
            rhs = real_value(row["rhs"])
            residual = {
                "<=": max(0.0, lhs - rhs),
                ">=": max(0.0, rhs - lhs),
                "=": abs(lhs - rhs),
            }[row["sense"]]
            if residual > max_row:
                max_row, worst_row = residual, row["name"]
        objective = math.fsum(
            chain(
                (real_value(matrix.objective_constant),),
                (
                    real_value(variable["objective"]) * value
                    for variable, value in zip(matrix.variables, canonical)
                ),
            )
        )
        require(math.isfinite(objective), "Nonfinite recomputed objective")
    except (OverflowError, ValueError) as error:
        # Keep the point and its explicit failed audit; no numeric Infinity in JSON.
        return {
            "status": "numeric_ineligible",
            "reason": type(error).__name__,
            "raw_vector_sha256": digest(original),
            "canonical_vector_sha256": digest(canonical),
            "audit": None,
            "vector": canonical,
        }
    if native_objective is not None:
        objective_residual = abs(objective - real_value(native_objective))
        objective_measurement = quantity(objective_residual)
    else:
        require(
            continuous, "An incumbent audit requires its native candidate objective"
        )
        objective_residual = None
        objective_measurement = quantity(
            None, "root_bound_is_not_a_candidate_objective"
        )
    qualified = (
        max_row <= tolerance["row"]
        and max_bound <= tolerance["bound"]
        and (continuous or integrality <= tolerance["integrality"])
        and (objective_residual is None or objective_residual <= tolerance["objective"])
    )
    identity = identity or streamed_identity(matrix)
    audit = {
        "model_sha256": identity["model_sha256"],
        "vector_sha256": digest(canonical),
        "status": "qualified" if qualified else "unqualified",
        "row_max_violation": quantity(max_row),
        "bound_max_violation": quantity(max_bound),
        "integrality_max_violation": quantity(None, "continuous_relaxation")
        if continuous
        else quantity(canonical_integrality),
        "objective_residual": objective_measurement,
        "tolerances": tolerance,
    }
    return {
        "status": audit["status"],
        "audit": audit,
        "raw_vector_sha256": digest(original),
        "canonical_vector_sha256": digest(canonical),
        "vector": canonical,
        "recomputed_objective": objective,
        "rounding": {
            "changed_count": len(changed),
            "changed_positions_sha256": digest(changed),
            "integer_max_distance": None if continuous else integrality,
        },
        "worst_original_row": worst_row,
        "worst_original_bound_position": worst_bound,
        "policy_sha256": policy.sha256,
        "sum_method": "math.fsum_original_rows_and_objective",
        "exact_rational_certificate": False,
    }
