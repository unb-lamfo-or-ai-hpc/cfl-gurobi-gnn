# Research protocols and runbooks

Documents in this directory record the protocol at a particular development
stage. Their PR numbers, paths, and examples are historical context, not
instructions to replay every preceding campaign.

## Current routes

- [PR80 job 3500 runtime diagnosis and immediate CLI](pr80-job3500-runtime-diagnosis.md):
  numerical audit blocked by the installed PyTorch version; no resubmission.
- [MVP2 current contract, sample, methods and next CLI](mvp2-contract-20261008.md):
  approved October 8 revision; mandatory CPU/GPU study, early E0 and PR80 gates.
  Start here before using older campaign instructions.
- [Scalable paired parent collection](scalable-paired-parent-collection.md):
  population planning, Gurobi-first execution, budget isolation, and rescue.
- [Gurobi graph contract](gurobi-root-graph-pipeline.md):
  first optimal root-MIPNODE observation and no zero fallback.
- [Derived graphs](gurobi-derived-gasse-augmentation.md) and
  [scalable augmentation](scalable-paired-augmentation.md):
  synthetic MIP identity and independent labels.
- [Gasse reconnection](gasse-training-reconnection.md) and
  [confirmation validation](pr49-confirmation-validation.md):
  these preserve the corrected model and earlier confirmation protocols.
- [Guidance methods](neural-guidance-methods-review.md) and
  [precommitted policy](literature-backed-neural-guidance-policy.md):
  distinguish hints, starts, and restrictive interventions.
- [PR #60 evidence summary](../results/pr60-scientific-evidence/README.md):
  the current 54-parent training, validation-selection, held-out benchmark, and
  influence-analysis chain.

## Superseded assumptions

The early `mvp-*` sequence records useful engineering evidence, but zero-valued
root features, small-cohort dashboards, and primary hard fixing are not accepted
confirmation defaults. Consult [ADR 0013](../decisions/0013-gurobi-first-legacy-recovery.md).

The earlier [scalable training document](scalable-four-arm-gasse-training.md)
and PR #50 record bounded engineering stages. Their populations and metrics do
not replace the current 54-parent PR #57 contract. Historical documents remain
available to explain decisions and failures; they are not current runbooks.

Node-state probes and SCIP domain-only audits remain isolated research studies.
They do not establish that an incumbent is a serialized branch-and-bound node.

Return to the [documentation index](../README.md) for the current reading order.

