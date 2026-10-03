"""One binary-domain/target contract shared by training and evaluation."""

from __future__ import annotations


def binary_targets(graph, tolerance: float = 1e-5):
    import math
    import torch

    store = graph["variable"]
    mask = store.is_discrete.bool()
    features = store.x
    if features.ndim != 2 or features.shape[1] != 7 or not bool(mask.any()):
        raise ValueError("missing binary graph features or targets")
    # Version-1 features encode bounds with signed log1p. Integer encodings
    # of binary/fixed binary domains are permitted; general integers are not.
    bound_ok = ((features[:, 1].abs() <= tolerance)
                | ((features[:, 1]-math.log(2)).abs() <= tolerance)) & (
                    (features[:, 2].abs() <= tolerance)
                    | ((features[:, 2]-math.log(2)).abs() <= tolerance))
    binary_domain = ((features[:, 4] > .5) | (features[:, 5] > .5)) & bound_ok & (features[:, 1] <= features[:, 2] + tolerance)
    if bool((mask & ~binary_domain).any()):
        raise ValueError("general integer/nonbinary domain is not a BCE target")
    labels = store.y[mask]
    rounded = labels.round()
    if (not bool(torch.isfinite(labels).all()) or bool((labels-rounded).abs().gt(tolerance).any())
            or bool(((rounded != 0) & (rounded != 1)).any())):
        raise ValueError("binary targets violate integrality or range")
    return mask, rounded
