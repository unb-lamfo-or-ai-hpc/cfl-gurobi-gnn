"""Dependency-free selection of one best available label per parent instance."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


MINIMIZE = "MINIMIZE"
SOURCE_PRIORITY = {
    "solutions.pickle.gz": 0,
    "incumbents.parquet": 1,
}


class SolutionSelectionError(ValueError):
    """Raised when an instance cannot provide a valid baseline label."""


@dataclass(frozen=True, slots=True)
class SelectedSolution:
    """Normalized label and provenance for one parent-instance graph."""

    solution_vector: Any
    objective: float
    mip_gap: float | None
    time: float | None
    node: int | None
    source: str
    source_index: int


def require_minimization(
    metadata: Mapping[str, Any], model_sense: Any
) -> None:
    """Reject artifacts that do not prove the corrected CFL minimization sense."""
    override = metadata.get("objective_sense_override")
    if override is not None and str(override).upper() != MINIMIZE:
        raise SolutionSelectionError(
            f"objective_sense_override must be {MINIMIZE}, got {override!r}"
        )

    if isinstance(model_sense, str):
        normalized_model_sense = model_sense.upper()
        is_minimize = normalized_model_sense in {MINIMIZE, "MIN", "1"}
    else:
        try:
            is_minimize = int(model_sense) == 1
        except (TypeError, ValueError, OverflowError):
            is_minimize = False

    if not is_minimize:
        raise SolutionSelectionError(
            f"persisted model sense is not minimization: {model_sense!r}"
        )


def _finite_float(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return normalized if math.isfinite(normalized) else None


def _optional_nonnegative_float(value: Any) -> float | None:
    normalized = _finite_float(value)
    return normalized if normalized is not None and normalized >= 0.0 else None


def _optional_nonnegative_int(value: Any) -> int | None:
    normalized = _finite_float(value)
    if normalized is None or normalized < 0.0:
        return None
    return int(normalized)


def _normalize_candidate(
    record: Mapping[str, Any], expected_num_vars: int, fallback_index: int
) -> SelectedSolution | None:
    objective = _finite_float(record.get("objective"))
    if objective is None:
        return None

    raw_vector = record.get("solution_vector")
    try:
        vector_length = len(raw_vector)
        vector_is_finite = all(math.isfinite(float(value)) for value in raw_vector)
    except (TypeError, ValueError, OverflowError):
        return None
    if vector_length != expected_num_vars or not vector_is_finite:
        return None

    source = str(record.get("source", "unknown"))
    source_index = _optional_nonnegative_int(record.get("source_index"))
    return SelectedSolution(
        # Keep the original numpy/list storage. Copying million-variable labels
        # into Python tuples would multiply memory use on medium/hard instances.
        solution_vector=raw_vector,
        objective=objective,
        mip_gap=_optional_nonnegative_float(record.get("mip_gap")),
        time=_optional_nonnegative_float(record.get("time")),
        node=_optional_nonnegative_int(record.get("node")),
        source=source,
        source_index=fallback_index if source_index is None else source_index,
    )


def _selection_key(solution: SelectedSolution) -> tuple[float, ...]:
    """Rank minimization candidates with deterministic quality tie-breakers."""
    return (
        solution.objective,
        solution.mip_gap if solution.mip_gap is not None else math.inf,
        float(SOURCE_PRIORITY.get(solution.source, len(SOURCE_PRIORITY))),
        solution.time if solution.time is not None else math.inf,
        float(solution.node) if solution.node is not None else math.inf,
        float(solution.source_index),
    )


def select_best_solution(
    records: Iterable[Mapping[str, Any]],
    *,
    expected_num_vars: int,
    objective_sense: str = MINIMIZE,
) -> SelectedSolution:
    """Select the minimum-objective valid label from a streaming candidate set."""
    selected, _ = select_best_solution_with_audit(
        records,
        expected_num_vars=expected_num_vars,
        objective_sense=objective_sense,
    )
    return selected


def select_best_solution_with_audit(
    records: Iterable[Mapping[str, Any]],
    *,
    expected_num_vars: int,
    objective_sense: str = MINIMIZE,
) -> tuple[SelectedSolution, dict[str, Any]]:
    """Select one label and report candidate validity and quality by artifact."""
    if objective_sense.upper() != MINIMIZE:
        raise SolutionSelectionError(
            "the parent-instance baseline only supports corrected CFL minimization"
        )
    if expected_num_vars <= 0:
        raise SolutionSelectionError("expected_num_vars must be positive")

    best: SelectedSolution | None = None
    best_by_source: dict[str, SelectedSolution] = {}
    by_source: dict[str, dict[str, Any]] = {
        source: {
            "evaluated": 0,
            "valid": 0,
            "invalid": 0,
            "best_objective": None,
            "best_mip_gap_at_best_objective": None,
        }
        for source in SOURCE_PRIORITY
    }
    evaluated = 0
    valid = 0
    for fallback_index, record in enumerate(records):
        evaluated += 1
        source = str(record.get("source", "unknown"))
        source_stats = by_source.setdefault(
            source,
            {
                "evaluated": 0,
                "valid": 0,
                "invalid": 0,
                "best_objective": None,
                "best_mip_gap_at_best_objective": None,
            },
        )
        source_stats["evaluated"] += 1
        candidate = _normalize_candidate(record, expected_num_vars, fallback_index)
        if candidate is None:
            source_stats["invalid"] += 1
            continue
        valid += 1
        source_stats["valid"] += 1
        source_best = best_by_source.get(candidate.source)
        if source_best is None or _selection_key(candidate) < _selection_key(
            source_best
        ):
            best_by_source[candidate.source] = candidate
        if best is None or _selection_key(candidate) < _selection_key(best):
            best = candidate

    if best is None:
        raise SolutionSelectionError(
            f"no valid solution among {evaluated} candidates "
            f"(expected vector length {expected_num_vars})"
        )

    for source, source_best in best_by_source.items():
        by_source[source]["best_objective"] = source_best.objective
        by_source[source]["best_mip_gap_at_best_objective"] = source_best.mip_gap

    valid_sources = list(best_by_source)
    if len(valid_sources) == 1:
        selection_reason = "only_artifact_with_valid_candidates"
    else:
        other_objectives = [
            candidate.objective
            for source, candidate in best_by_source.items()
            if source != best.source
        ]
        selection_reason = (
            "minimum_objective_across_artifacts"
            if other_objectives and best.objective < min(other_objectives)
            else "deterministic_tie_break"
        )

    audit = {
        "evaluated_candidates": evaluated,
        "valid_candidates": valid,
        "invalid_candidates": evaluated - valid,
        "by_artifact": dict(sorted(by_source.items())),
        "selected_artifact": best.source,
        "selected_source_index": best.source_index,
        "selection_reason": selection_reason,
    }
    return best, audit
