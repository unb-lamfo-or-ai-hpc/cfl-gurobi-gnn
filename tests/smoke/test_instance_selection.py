"""Dependency-free tests for parent-instance label selection."""

import math

import pytest

from cfl_gnn.graph.instance_selection import (
    SolutionSelectionError,
    require_minimization,
    select_best_solution,
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
