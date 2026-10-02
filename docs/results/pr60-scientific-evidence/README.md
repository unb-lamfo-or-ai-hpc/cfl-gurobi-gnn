# PR #60 scientific evidence synthesis

PR #60 assembled the accepted PR #57-#59 development evidence without running
new optimizations. Its contract SHA-256 is
`1a22c76da1f5bc6be978ac6eb7ea340c10b067c5beae1f71aecb617ac09d6b96`.

## Offline learning

The graph cohort contained 54 original parents: 34 training, 10 validation, and
10 test. Training used seed 42 for 100 epochs. The held-out predictive evaluation
covered 5,536,400 targets, including 5,265 positives. Aggregate results were:

| Metric | Value |
|---|---:|
| Precision | 0.692293 |
| Recall | 0.706363 |
| F1 | 0.699257 |
| PR-AUC | 0.774668 |
| Average precision | 0.774501 |
| ROC-AUC | 0.999694 |

These metrics describe variable assignment prediction, not solver improvement.

## Validation policy selection

Six validation parents compared an unguided control, a root-LP partial start,
and a GNN partial start under equal one-hour budgets. GNN starts were accepted
for all six parents, improved terminal gap on four, and produced median
guided-minus-control gap difference -0.012235. One parent had a large regression.
The registered qualification checks passed and froze the held-out test protocol.

## Held-out optimization benchmark

The frozen test benchmark used six medium parents and the same three methods.
GNN guidance improved the terminal gap on five parents. Mean and median
guided-minus-control differences were -0.072001 and -0.011642. Four guided runs
and all controls were right-censored. At the observed one-hour budget, four GNN
runs and three controls reached a relative gap no greater than 10%.

The influence analysis reports:

| Analysis | Parents | Wins | Mean gap difference | Median gap difference |
|---|---:|---:|---:|---:|
| All held-out | 6 | 5 | -0.072001 | -0.011642 |
| Exclude medium 20 | 5 | 4 | -0.016587 | -0.002135 |
| Exclude medium 12 and 20 | 4 | 3 | -0.005555 | -0.001397 |

The direction remains favorable under the registered exclusions, but the
magnitude is sensitive to individual parents.

## Interpretation boundary

The output is a development-only proof of pipeline function and held-out paired
improvement on a small sample. It is not a powered confirmatory experiment.
There are no hard parents, multi-seed estimates, confidence intervals, or
synthetic-augmentation ablations in this benchmark. The report correctly retains
`scientific_reporting_eligible=false`.

The exact eleven public table/figure names and their roles are listed in the
[output inventory](../../output-inventory.md). Their hashes are authoritative in
`pr60_scientific_evidence_manifest.json` at the external run location.
