# ADR 0006: Contract-locked held-out parent-instance evaluation

- Status: accepted
- Date: 2026-08-31

## Context

ADR 0005 introduced serial training for canonical parent-instance folds. The
legacy evaluator reconstructs graph-count splits with `random_split` and also
supports threshold selection from evaluation predictions. Reusing either
behavior would break the parent-level split contract or tune a decision rule
on the test population.

A plain Gasse state dictionary remains necessary for compatibility with the
existing hint generator, but the checkpoint must still be cryptographically
bound to the experiment that produced it.

## Decision

Add a separate `cfl_gnn.cli.evaluate_instance` entrypoint. It performs a
CPU-only admission stage before importing PyTorch:

1. reload the saved training plan and experiment summary;
2. rebuild the current schema-v2 graph audit with SHA-256 verification;
3. require identical contract SHA-256 values and exact test membership;
4. require the experiment summary's checkpoint SHA-256 to match the supplied
   `best_model.pt` bytes;
5. require proof that the test partition was not loaded during training;
6. infer model dimensions from the first held-out batch and load the saved
   plain state dictionary;
7. deserialize only records assigned to the canonical test role.

Classification uses the precommitted probability threshold 0.5, equivalent to
logit zero. No test-set threshold sweep, calibration, model selection, class
weight estimation, or prenormalization fitting is allowed. The training-only
`pos_weight` is reused solely to report the matching weighted BCE objective.

Outputs are path-sanitized and contain aggregate, per-difficulty, and
per-instance confusion counts, accuracy, precision, recall, F1, and weighted
BCE. The development/scientific eligibility flag is inherited unchanged.

## Consequences

- The current six easy test parents can validate mechanics but cannot support
  final cross-difficulty claims.
- A changed graph, sidecar, split, summary, or checkpoint fails closed before
  any test graph is deserialized.
- The incumbent-conditioned evaluator remains untouched.
- Validation-based threshold calibration, if later required, must be designed
  as a separate protocol and frozen before test evaluation.
- Distributed training remains a later change and must emit the same contract
  and checkpoint provenance.
