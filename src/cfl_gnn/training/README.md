# Training contracts and backends

[gasse_reconnected.py](gasse_reconnected.py) binds graph/label manifests, model
versions, parent-aware sampling, checkpoint selection, and serial/DDP execution.
[binary_contract.py](binary_contract.py) restricts BCE supervision to valid binary
targets; arbitrary general-integer labels must not be silently clamped.

Confirmation uses seed 42 and 100 full epochs. Normalization and class weights
come from training parents only. Validation selects the checkpoint and probability
threshold; held-out test graphs are not loaded during training.
[figures.py](figures.py) presents training and validation losses together, while
distinguishing their measurement contexts.

[serial.py](serial.py) supplies reusable helpers and preserves its earlier CLI.
Its historical random-split main routine is not the confirmation route.
[distributed.py](distributed.py) likewise preserves the older DDP entry point.
Checkpoint reload in these historical routines is not a complete optimizer-state
resume. Do not conflate that behavior with contract-validated experiment reuse.

