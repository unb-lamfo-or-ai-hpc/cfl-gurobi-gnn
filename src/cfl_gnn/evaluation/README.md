# Held-out evaluation

[gasse_reconnected.py](gasse_reconnected.py) checks checkpoint and graph contracts,
evaluates original held-out parents, and exports named prediction bundles.
[binary_quality.py](binary_quality.py) implements binary-quality diagnostics.

Report per-parent and aggregate precision, recall, F1, average precision,
Brier/ECE, loss, and baseline diagnostics with their denominators. High accuracy
alone is insufficient for sparse binary targets. Weighted BCE does not establish
probability calibration.

Prediction bundles are not target-label exports. They must remain bound to the
checkpoint, source MIP, and evaluation ledger before solver guidance. A held-out
classification score is not evidence of improved MIP convergence. Earlier
[model.py](model.py), [instance.py](instance.py), and
[mvp_four_arm.py](mvp_four_arm.py) retain their specific historical contracts.

The current PR #57 held-out report covers 10 parents and 5,536,400 targets. Its
F1 (0.699257) and PR-AUC (0.774668) establish predictive development evidence.
Solver impact is evaluated separately by PR #58 validation selection and PR #59
frozen testing; those paired results cannot be inferred from classification
metrics alone.

