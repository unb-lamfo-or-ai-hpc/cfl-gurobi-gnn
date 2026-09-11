"""Outcome-free descriptors of the encoded bipartite graph (not embeddings)."""
from __future__ import annotations

import numpy as np

FEATURES = (
    "density", "discrete_fraction", "constraint_variable_ratio",
    "objective_log_mean", "objective_log_std", "rhs_log_mean", "rhs_log_std",
    "coefficient_log_mean", "coefficient_log_std", "lower_bound_log_mean",
    "upper_bound_log_mean", "fixed_domain_fraction", "variable_degree_std",
    "constraint_degree_std", "root_lp_mean", "root_lp_std", "binary_lp_fractionality",
)


def _array(value):
    return value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)


def graph_descriptors(graph):
    """Describe stored features; clipped infinities cannot be reconstructed."""
    v = _array(graph["variable"].x).astype(float)
    c = _array(graph["constraint"].x).astype(float)
    edge = graph["variable", "rev_coef", "constraint"]
    indices = _array(edge.edge_index)
    coefficients = _array(edge.edge_attr).ravel()
    if not len(v) or not len(c) or not all(np.isfinite(x).all() for x in (v, c, coefficients)):
        raise ValueError("nonempty finite graph features are required")
    mask = _array(graph["variable"].is_discrete).astype(bool)
    lp = v[mask, 6]
    n, m, e = len(v), len(c), indices.shape[1]
    result = dict(zip(FEATURES, (
        e / (n * m), mask.mean(), m / n,
        v[:, 0].mean(), v[:, 0].std(), c[:, 0].mean(), c[:, 0].std(),
        coefficients.mean() if e else 0., coefficients.std() if e else 0.,
        v[:, 1].mean(), v[:, 2].mean(), np.isclose(v[:, 1], v[:, 2], atol=1e-9, rtol=0).mean(),
        np.bincount(indices[0], minlength=n).std(), np.bincount(indices[1], minlength=m).std(),
        v[:, 6].mean(), v[:, 6].std(), np.abs(lp - np.rint(lp)).mean() if lp.size else 0.,
    )))
    return {key: float(value) for key, value in result.items()}


def binary_prevalence(graph):
    store = graph["variable"]
    mask = _array(store.is_discrete).astype(bool)
    targets = _array(store.y)[mask]
    if not targets.size or not np.isfinite(targets).all() or not np.allclose(targets, np.rint(targets), atol=1e-5, rtol=0) or not np.isin(np.rint(targets), [0, 1]).all():
        raise ValueError("binary prevalence requires valid discrete labels")
    return float(np.rint(targets).mean())


def descriptive_distribution(values):
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    return {"count": len(values), "finite_count": len(finite),
            "minimum": float(finite.min()) if len(finite) else None,
            "median": float(np.median(finite)) if len(finite) else None,
            "q25": float(np.quantile(finite, .25)) if len(finite) else None,
            "q75": float(np.quantile(finite, .75)) if len(finite) else None,
            "maximum": float(finite.max()) if len(finite) else None}
