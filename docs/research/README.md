# Research protocols and runbooks

Documents in this directory record the protocol at a particular development
stage. Their PR numbers, paths, and examples are historical context, not
instructions to replay every preceding campaign.

## Current routes

- [Scalable paired parent collection](scalable-paired-parent-collection.md):
  population planning, Gurobi-first execution, budget isolation, and rescue.
- [Gurobi graph contract](gurobi-root-graph-pipeline.md):
  first optimal root-MIPNODE observation and no zero fallback.
- [Derived graphs](gurobi-derived-gasse-augmentation.md) and
  [scalable augmentation](scalable-paired-augmentation.md):
  synthetic MIP identity and independent labels.
- [Gasse reconnection](gasse-training-reconnection.md) and
  [confirmation validation](pr49-confirmation-validation.md):
  the latter specifies the corrected model and frozen 42-parent protocol.
- [Guidance methods](neural-guidance-methods-review.md) and
  [precommitted policy](literature-backed-neural-guidance-policy.md):
  distinguish hints, starts, and restrictive interventions.

## Superseded assumptions

The early `mvp-*` sequence records useful engineering evidence, but zero-valued
root features, small-cohort dashboards, and primary hard fixing are not accepted
confirmation defaults. Consult [ADR 0013](../decisions/0013-gurobi-first-legacy-recovery.md).

The earlier [scalable training document](scalable-four-arm-gasse-training.md)
records the 30-easy diagnostic run and an earlier proposed 45-graph population.
The current frozen confirmation is **42 parents**, not 45, and does not permit
silently excluding the 12 medium parents. Source recovery is tracked in
[PR #50](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/50).

Node-state probes and SCIP domain-only audits remain isolated research studies.
They do not establish that an incumbent is a serialized branch-and-bound node.

Return to the [documentation index](../README.md) for the current reading order.

