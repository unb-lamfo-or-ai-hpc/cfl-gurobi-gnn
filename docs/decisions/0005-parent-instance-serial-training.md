# ADR 0005: Separate serial training for parent instances

- Status: accepted
- Date: 2026-08-31

## Context

ADR 0004 established a fold-aware consumer for one graph per original CFL
parent. The existing serial trainer is still coupled to incumbent-conditioned
`data_<index>.pt` graphs, category graph counts, and `random_split`. Modifying
that entrypoint in place would obscure which experimental population produced
a checkpoint and would endanger the preserved incumbent workflow.

The available DaSCI inventory is also incomplete: its strict-label population
contains 30 easy parents and no eligible medium or hard parents. It is useful
for an engineering smoke but not for cross-difficulty scientific claims.

## Decision

Add a separate `cfl_gnn.cli.train_instance_serial` entrypoint. Before importing
PyTorch or allocating a GPU, it:

1. verifies the canonical manifest, schema-v2 sidecars, provenance, and graph
   SHA-256 digests;
2. derives train, validation, and test roles exclusively from the selected
   five-fold rotation;
3. rejects invalid graphs, empty roles, and parent leakage;
4. defaults to the `optimal_only` label policy;
5. requires `--development_only` for a partial inventory or for
   `all_available` labels;
6. writes a path-sanitized run contract with a deterministic SHA-256 identity.

Only the training and validation records are instantiated as PyG datasets.
The test membership is recorded but is not loaded, inspected, or used for
early stopping, class weighting, prenormalization, or model selection.

The saved `best_model.pt` remains a plain Gasse state dictionary so the current
hint-generation code can consume it. Reusing an existing checkpoint requires
an explicit `--overwrite`; experiment directories are otherwise fail-closed.

## Consequences

- The incumbent-conditioned `train_serial`, distributed trainer, collector,
  ETL, and `toy_bipartite` remain unchanged.
- A CPU-only `--dry_run` can validate the complete training contract on a
  login node before a Slurm job is submitted.
- The current 18/6/6 easy-only rotation-0 plan is marked development-only.
- Final scientific runs require a complete, eligible 90-parent inventory with
  easy, medium, and hard instances.
- DDP adaptation and test-set evaluation remain separate future changes.
