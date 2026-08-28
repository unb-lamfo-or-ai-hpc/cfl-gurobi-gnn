# ADR 0002: Instance-level rotating cross-validation

- Status: accepted
- Date: 2026-08-28

## Context

The incumbent dataset repeats the same parent-instance graph with different
labels. Random graph-level splitting can therefore place structurally identical
inputs in training and test, causing leakage and ambiguous supervision. The
canonical CFL study targets 30 easy, 30 medium, and 30 hard parent instances,
but collected solutions will become available incrementally because medium and
hard instances require substantial solve time.

## Decision

Assign folds once at the original-instance level. The canonical manifest uses
five folds, seed 42, and a stable SHA-256 rank of `source_instance_id`. Each fold
contains exactly six instances from each MILPBench category.

For rotation `k`:

- fold `k` is test;
- fold `(k + 1) mod 5` is validation;
- the other three folds are training.

Every rotation therefore has 18/6/6 train/validation/test instances per
category (54/18/18 overall). Across five rotations, every parent instance is
used once for test, once for validation, and three times for training.

All future graphs derived from an incumbent or a branch-and-bound subproblem
must retain `source_instance_id` and inherit its parent's fold. A descendant
must never be assigned independently.

## Partial-inventory policy

The 90-instance manifest is fixed even while only a subset is available. The
inventory audit filters the canonical plan without reassigning folds. This
ensures that adding newly solved instances cannot move an existing instance
between train, validation, and test.

Runs on partial inventory are engineering/development checks only. They must
report available and missing counts per role and cannot be presented as final
cross-validation results. Final evaluation requires all 90 eligible parent
instances or a separately reviewed missing-data protocol.

## Consequences

- Split generation and validation do not require Gurobi, PyTorch, or DaSCI.
- The next ETL change may select one best available label per parent instance
  without revisiting the split methodology.
- The preserved incumbent collector remains untouched.
- Existing graph-count arguments in training are not yet replaced; manifest
  consumption belongs to the next implementation PR.
