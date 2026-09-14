# Documentation index

This index separates current methodological guidance from historical experiments.
PR numbers identify development history; they are not scientific acceptance levels.

## Current reading order

1. [Project overview](../README.md) and [architecture](architecture.md).
2. [Reproducibility and environment boundaries](reproducibility.md).
3. [Gurobi-first recovery decision](decisions/0013-gurobi-first-legacy-recovery.md).
4. [Paired parent collection](research/scalable-paired-parent-collection.md).
5. [Gurobi root graph contract](research/gurobi-root-graph-pipeline.md) and
   [paired augmentation](research/scalable-paired-augmentation.md).
6. [Confirmation validation](research/pr49-confirmation-validation.md):
   42 original parents, independent label audits, corrected prenormalization,
   100 epochs, and held-out evaluation.
7. [Native guidance policy](research/literature-backed-neural-guidance-policy.md).

The [final original-parent results](results/pr50-confirmation/README.md) report
the completed 39-parent revision, 100 training epochs and eight-parent held-out
evaluation. The initial 42-parent target remained incomplete. Matched four-arm
and native solver benchmarking remain future work for this confirmation cohort.

## Evidence and historical interpretation

- [Research protocols](research/README.md): scope, supersession, and runbook cautions.
- [Architecture decisions](decisions/README.md): design rationale, not runtime proof.
- [Validation receipts](validation/README.md): bounded observations and sanitization.
- [Legacy pipeline reference](pipeline.md): earlier collection and training route.
- [Legacy-to-current audit](research/legacy-current-pipeline-audit.md): comparison
  at the recorded pre-recovery commits, not a continuously updated code diff.
- [Editorial review](documentation-review.md): English-language scope, source
  preservation, and outstanding release requirements.

Do not copy historical absolute paths, model versions, or permissive label gaps
into a current run. Resolve the exact upstream artifact contract first.
