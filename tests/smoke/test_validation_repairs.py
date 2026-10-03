"""Numerical contracts for the approved CFL validation recovery."""
import numpy as np
import pytest

from cfl_gnn.analysis.graph_clustering import _standardize, _pca, _kmeans
from cfl_gnn.evaluation.binary_quality import score_quality
from cfl_gnn.experiments.neural_guidance_policy import guidance_directives
from cfl_gnn.training.gasse_reconnected import threshold_from_validation
from cfl_gnn.validation.mathematical import validate_linear_solution, common_gap


def fixture(**changes):
    data = dict(values=[1., 0.], lower=[0., 0.], upper=[1., 1.], types=["B", "I"],
                objective=[2., 3.], objective_offset=7., rows=[0, 0], columns=[0, 1],
                coefficients=[1., 1.], senses=[">"], rhs=[1.], reported_objective=9.)
    return validate_linear_solution(**(data | changes))


def test_independent_feasibility_and_objective_constant():
    assert fixture()["valid"]
    for changes in ({"values": [0., 0.]}, {"values": [1.5, 0.]},
                    {"reported_objective": 2.}, {"values": [1., 2.]}):
        assert not fixture(**changes)["valid"]
    with pytest.raises(ValueError):
        fixture(values=[float("nan"), 0.])
    assert common_gap(110., 100.) == pytest.approx(10/110)
    assert common_gap(0., 1.) is None
    assert common_gap(0., 0.) == 0.


def test_constant_projection_cannot_create_variance_or_clusters():
    data = _standardize(np.full((9, 17), .1))
    coordinates, explained = _pca(data)
    assert np.count_nonzero(coordinates) == 0
    assert explained == [0., 0.]
    assert len(np.unique(_kmeans(data, 3))) == 1


def test_threshold_matches_exhaustive_tie_rule():
    rng = np.random.default_rng(42)
    for _ in range(20):
        y = rng.integers(0, 2, 50)
        p = np.round(rng.random(50), 2)
        def key(t):
            tp = np.sum((p >= t) & (y == 1))
            fp = np.sum((p >= t) & (y == 0))
            fn = np.sum((p < t) & (y == 1))
            return (2*tp/max(1, 2*tp+fp+fn), -abs(t-.5), -t)
        expected = max(set(p) | {0., .5, 1.}, key=key)
        assert threshold_from_validation(y.tolist(), p.tolist()) == expected


def test_average_precision_is_tie_aware_and_calibration_is_not_assumed():
    row = score_quality([0, 1, 1, 0], [.5]*4)
    assert row["average_precision"] == .5
    assert row["brier_score"] == .25
    assert not row["probability_calibration_claimed"]
    assert score_quality([0, 0], [.1, .2])["average_precision"] is None


def test_lb_support_and_radius_are_explicit():
    rows = [dict(variable_name=f"x{i}", predicted_value=0, probability=.1,
                 confidence=.9, priority=90) for i in range(100)]
    with pytest.raises(ValueError):
        guidance_directives(rows, method="local_branching_trust_region_with_recovery")
    directive = guidance_directives(rows, method="local_branching_trust_region_with_recovery", radius_fraction=.01)
    assert len(directive["assignments"]) == 100
    assert directive["radius"] == 1
    assert directive["recovery_phase_always_executed"]
