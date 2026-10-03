# GNN models and version identity

[gasse.py](gasse.py) preserves the legacy Gasse-style implementation, Git blob
`e2937ebcca149f8a99ec437c3c8e7fd31e49438b`.
Do not edit that file to introduce a corrected model.

[gasse_calibrated.py](gasse_calibrated.py) provides
`gasse_v2_alternating_prenorm`: the trainable architecture is retained while
variable-side prenormalization is fitted from updated constraint messages.
Training-population moments exclude validation and test.
[versioning.py](versioning.py) records the selected implementation.

The name “calibrated” here refers to message normalization, not a guarantee of
probability calibration. Corrected checkpoints require retraining and explicit
model-version provenance. [liang.py](liang.py) remains available for the toy
comparison. See [sandbox](../../../sandbox/README.md).

