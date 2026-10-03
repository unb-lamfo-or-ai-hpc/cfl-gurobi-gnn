# Documentation index

This index separates current methodological guidance from historical experiments.
PR numbers identify development history; they are not scientific acceptance levels.

## Current reading order

1. [Project overview](../README.md) and [architecture](architecture.md).
2. [Reproducibility and environment boundaries](reproducibility.md).
3. [Pipeline output inventory](output-inventory.md).
4. [Gurobi-first recovery decision](decisions/0013-gurobi-first-legacy-recovery.md).
5. [Paired parent collection](research/scalable-paired-parent-collection.md).
6. [Gurobi root graph contract](research/gurobi-root-graph-pipeline.md) and
   [paired augmentation](research/scalable-paired-augmentation.md).
7. [Training and evaluation chain](results/pr60-scientific-evidence/README.md):
   54 parents, corrected prenormalization, 100 epochs, validation-only method
   selection, and frozen held-out solver benchmarking.
8. [Native guidance policy](research/literature-backed-neural-guidance-policy.md).

The [PR #50 result](results/pr50-confirmation/README.md) remains an immutable
historical development baseline. It is superseded for current interpretation
by PRs #57-#60; its cohort and metrics must not be mixed with the 54-parent
training contract or the six-parent solver benchmark.

## Evidence and historical interpretation

- [Research protocols](research/README.md): scope, supersession, and runbook cautions.
- [Architecture decisions](decisions/README.md): design rationale, not runtime proof.
- [Validation receipts](validation/README.md): bounded observations and sanitization.
- [Legacy pipeline reference](pipeline.md): earlier collection and training route.
- [Legacy-to-current audit](research/legacy-current-pipeline-audit.md): comparison
  at the recorded pre-recovery commits, not a continuously updated code diff.
- [Editorial review](documentation-review.md): English-language scope, source
  preservation, dependency declaration, and outstanding release requirements.

Do not copy historical absolute paths, model versions, or permissive label gaps
into a current run. Resolve the exact upstream artifact contract first.
