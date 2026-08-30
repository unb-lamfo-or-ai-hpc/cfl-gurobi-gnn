"""Dependency-free tests for parent-instance label selection."""

import math

import pytest

from cfl_gnn.graph.instance_selection import (
    SolutionSelectionError,
    require_minimization,
    select_best_solution,
    select_best_solution_with_audit,
)


def candidate(
    objective,
    vector=(0.0, 1.0),
    *,
    gap=0.1,
    source="incumbents.parquet",
    source_index=0,
    time=1.0,
    node=1,
):
    return {
        "objective": objective,
        "solution_vector": vector,
        "mip_gap": gap,
        "source": source,
        "source_index": source_index,
        "time": time,
        "node": node,
    }


def test_minimum_objective_is_the_primary_selection_rule() -> None:
    selected = select_best_solution(
        [candidate(12.0, gap=0.0), candidate(10.0, gap=0.8)],
        expected_num_vars=2,
    )
    assert selected.objective == 10.0


def test_ties_prefer_gap_then_final_solution_pool() -> None:
    selected = select_best_solution(
        [
            candidate(10.0, gap=0.2, source="solutions.pickle.gz"),
            candidate(10.0, gap=0.1, source="incumbents.parquet"),
            candidate(
                10.0,
                gap=0.1,
                source="solutions.pickle.gz",
                source_index=2,
            ),
        ],
        expected_num_vars=2,
    )
    assert selected.source == "solutions.pickle.gz"
    assert selected.source_index == 2


def test_invalid_candidates_are_ignored_in_streaming_input() -> None:
    records = (
        record
        for record in [
            candidate(math.nan),
            candidate(1.0, vector=(0.0,)),
            candidate(2.0, vector=(0.0, math.inf)),
            candidate(3.0, vector=(1.0, 0.0)),
        ]
    )
    selected = select_best_solution(records, expected_num_vars=2)
    assert selected.objective == 3.0
    assert selected.solution_vector == (1.0, 0.0)


def test_selected_vector_is_not_copied_into_python_tuple_storage() -> None:
    vector = [0.0, 1.0]
    selected = select_best_solution(
        [candidate(3.0, vector=vector)], expected_num_vars=2
    )
    assert selected.solution_vector is vector


def test_no_valid_candidate_fails_closed() -> None:
    with pytest.raises(SolutionSelectionError, match="no valid solution"):
        select_best_solution([candidate(None)], expected_num_vars=2)


def test_candidate_audit_explains_cross_artifact_selection() -> None:
    selected, audit = select_best_solution_with_audit(
        [
            candidate(10.0, source="solutions.pickle.gz"),
            candidate(9.0, source="incumbents.parquet"),
            candidate(None, source="incumbents.parquet"),
        ],
        expected_num_vars=2,
    )
    assert selected.source == "incumbents.parquet"
    assert audit["selection_reason"] == "minimum_objective_across_artifacts"
    assert audit["by_artifact"]["solutions.pickle.gz"] == {
        "evaluated": 1,
        "valid": 1,
        "invalid": 0,
        "best_objective": 10.0,
        "best_mip_gap_at_best_objective": 0.1,
    }
    assert audit["by_artifact"]["incumbents.parquet"] == {
        "evaluated": 2,
        "valid": 1,
        "invalid": 1,
        "best_objective": 9.0,
        "best_mip_gap_at_best_objective": 0.1,
    }


def test_candidate_audit_marks_the_only_valid_artifact() -> None:
    _, audit = select_best_solution_with_audit(
        [
            candidate(None, source="solutions.pickle.gz"),
            candidate(9.0, source="incumbents.parquet"),
        ],
        expected_num_vars=2,
    )
    assert audit["selection_reason"] == "only_artifact_with_valid_candidates"


def test_non_minimization_artifacts_are_rejected() -> None:
    require_minimization({"objective_sense_override": "MINIMIZE"}, 1)

    with pytest.raises(SolutionSelectionError, match="objective_sense_override"):
        require_minimization({"objective_sense_override": "MAXIMIZE"}, 1)

    with pytest.raises(SolutionSelectionError, match="persisted model sense"):
        require_minimization({"objective_sense_override": "MINIMIZE"}, -1)

    with pytest.raises(SolutionSelectionError, match="only supports"):
        select_best_solution(
            [candidate(1.0)], expected_num_vars=2, objective_sense="MAXIMIZE"
        )
