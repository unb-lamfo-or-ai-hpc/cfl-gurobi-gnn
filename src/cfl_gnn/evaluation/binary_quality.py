"""Tie-aware binary score diagnostics; weighted-BCE outputs are not calibrated."""
import numpy as np


def score_quality(targets, scores, bins=10):
    y, p = np.asarray(targets, dtype=float), np.asarray(scores, dtype=float)
    if (y.ndim != 1 or p.shape != y.shape or not y.size or bins < 1
            or not np.isfinite(y).all() or not np.isfinite(p).all()
            or not np.isin(y, [0, 1]).all() or np.any((p < 0) | (p > 1))):
        raise ValueError("finite binary targets and scores in [0,1] are required")
    order = np.argsort(-p, kind="stable")
    s, z = p[order], y[order]
    ends = np.r_[np.flatnonzero(s[:-1] != s[1:]), len(s)-1]
    tp = np.cumsum(z)[ends]
    precision = tp / (ends+1)
    positives = y.sum()
    recall = tp / positives if positives else np.zeros_like(tp)
    ap = float(np.sum(np.diff(np.r_[0., recall]) * precision)) if positives else None
    bucket = np.minimum((p*bins).astype(int), bins-1)
    ece = sum(abs(p[bucket == b].mean()-y[bucket == b].mean()) * (bucket == b).mean()
              for b in range(bins) if np.any(bucket == b))
    epsilon = np.finfo(float).eps
    clipped = np.clip(p, epsilon, 1-epsilon)
    return {"average_precision": ap, "brier_score": float(np.mean((p-y)**2)),
            "expected_calibration_error": float(ece),
            "binary_cross_entropy": float(-np.mean(y*np.log(clipped)+(1-y)*np.log1p(-clipped))),
            "positive_prevalence": float(y.mean()), "calibration_bins": bins,
            "probability_calibration_claimed": False}
