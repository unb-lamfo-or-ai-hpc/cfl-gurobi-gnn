# ADR 0004: Parent-instance training eligibility

- Status: accepted
- Date: 2026-08-31

## Context

The parent-instance ETL now produces one graph per available MILPBench CFL
parent and assigns the canonical fold from ADR 0002. The legacy training code
discovers incumbent-conditioned files named `data_<index>.pt` and applies a
random graph-count split. Reusing that behavior for parent graphs would either
discover no files or discard the accepted instance-level split methodology.

The partial DaSCI inventory also contains two materially different label
populations: 30 labels within the declared optimality tolerance and 12 medium
labels with MIP gaps greater than 40%. A mechanically valid solution vector is
not automatically an appropriate target for the primary scientific baseline.

## Decision

Introduce a separate, fold-aware parent-instance consumer. It discovers only
`<source_instance_id>.pt` files paired with schema-v2 provenance sidecars,
cross-checks the canonical identifier and fold, verifies the serialized graph
digest by default, and derives the role solely from the selected rotation:

- fold `k` is test;
- fold `(k + 1) mod 5` is validation;
- the remaining folds are training.

The consumer never calls `random_split` and never reassigns a fold when the
inventory is partial. Serialized graph metadata is checked again when a graph
is loaded by PyTorch.

Two explicit label policies are supported:

- `optimal_only` accepts only `optimal_tolerance` and is the default for the
  primary baseline;
- `all_available` accepts every known nonnegative MIP-gap band and is limited
  to engineering smoke tests until a different supervision policy is reviewed.

Unknown-gap labels are not eligible under either policy. Partial inventory,
missing difficulties, excluded labels, stale sidecars, and non-optimal smoke
labels remain visible in the audit report.

## Consequences

- Inventory and split auditing requires neither PyTorch nor a GPU.
- The current 30-label strict population can validate the easy-instance
  mechanics but cannot support final cross-difficulty claims.
- The 42-label development population may validate plumbing, provided its
  non-optimal-label warning is retained.
- Training, DDP, and evaluation entrypoints remain unchanged in this decision;
  the new record contract is their prerequisite.
- The incumbent-conditioned dataset and `toy_bipartite` remain untouched.
