# Gasse training pipeline reconnection

## Scope

This stage reconnects the preserved Gasse bipartite GNN architecture to the
audited parent-instance pipeline. The model file is protected by its Git blob
identity, `e2937ebcca149f8a99ec437c3c8e7fd31e49438b`, which is identical to the
version in `legacy/main-before-instance-baseline`.

PR #44 covers original parent instances only. Local-branching descendants are
not silently relabeled with their parent solutions; they must enter through a
subsequent augmentation adapter that consumes independently audited derived-MIP
labels.

## Data contract

Each mathematical parent MIP has one graph built by Gurobi. The graph contains
the exact Gurobi root-node LP relaxation feature. Gurobi and SCIP experiments
reuse that graph identity and overlay a solver-specific, named solution vector
only when the sample is loaded. The graph MIP SHA-256 must equal the MIP SHA-256
of the corresponding solver task.

Labels with a terminal relative MIP gap above 10% are excluded. Parent IDs,
not graph rows, define train, validation, and test partitions. Training uses a
deterministic parent-balanced schedule with equal draws per parent.

## Training and evaluation controls

- Serial and DDP training invoke the preserved training loops.
- DDP ranks receive disjoint slices of one deterministic global schedule.
- Checkpoints minimize validation weighted BCE.
- The probability threshold maximizes F1 on validation only.
- Test graphs are not instantiated during training.
- Evaluation consumes the fixed checkpoint and validation-selected threshold.
- Held-out outputs include aggregate, per-parent, and per-difficulty metrics,
  ROC and precision-recall curves, and calibration bins.

The current single-parent DaSCI artifact can validate only the explicitly
flagged, one-epoch engineering smoke. It cannot validate checkpoint selection,
threshold selection, or held-out evaluation until Gurobi-authoritative graphs
exist for at least one train, validation, and test parent.

## Scientific status

All PR #44 artifacts remain development-only and ineligible for scientific
reporting. Full eligibility still requires the planned parent population and
the complete downstream solver comparison protocol.
