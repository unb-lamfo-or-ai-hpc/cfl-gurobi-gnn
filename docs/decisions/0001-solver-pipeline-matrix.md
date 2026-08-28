# ADR 0001: Compose solver and sampling strategy

- Status: accepted
- Date: 2026-08-28

## Context

The research roadmap requires Gurobi and SCIP backends, each operating either
on original instances or on subproblems derived from incumbent search states.
Maintaining four independent copies would make methodological fixes and feature
schemas diverge.

## Decision

Represent solver integration and sample-generation strategy as separate
modules, combined by explicit pipeline entrypoints. Preserve the current
Gurobi-incumbent collector while the instance baseline is validated. Add SCIP
only after assessing whether Gurobi can expose or reconstruct the required
reduced subproblems.

## Consequences

- Shared schemas and graph transformations have one source of truth.
- Each experimental variant remains explicit and independently runnable.
- Solver-specific APIs do not leak into training and evaluation modules.
- No placeholder SCIP implementation is added before its design is justified.
