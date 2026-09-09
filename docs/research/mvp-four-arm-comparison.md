# Development-only four-arm Neural Diving comparison

## Purpose

This stage converts the immutable PR #37 equal-budget benchmark into a
contract-checked descriptive comparison. It does not execute either optimizer,
recalibrate the Neural Diving operator, rank GNN arms, or claim statistical
superiority.

Terminal relative MIP gap and external wall time measured strictly around
`model.optimize()` are the two primary outcomes. Total time, data reading,
model construction, post-optimization extraction, solver-reported runtime,
status, nodes, solutions, and right censoring remain required explanatory
measurements.

## Comparisons

For every held-out parent, the review preserves three paired contrasts:

1. every guided arm minus the unguided control within the same target solver;
2. incumbent-augmented minus original-only training within the same source and
   target solver;
3. SCIP minus Gurobi as target solver for the identical GNN arm and identical
   fixing fingerprint.

Positive improvement fields always mean lower gap or shorter optimization
time. A joint descriptive class reports dominance, inferiority, equality, or a
trade-off, but it is not an arm-selection rule. Any comparison involving a
right-censored run is explicitly marked descriptive-only.

## Fail-closed provenance

The review verifies the PR #37 benchmark contract, report gate, source file
hashes, task-result contracts, complete ten-run factorial, finite primary
outcomes, and reconciliation of the four time regions. Outputs contain only
relative file names and SHA-256 identities. Absolute storage paths and license
metadata are excluded.

The resulting reproducibility manifest binds the source benchmark, all task
results, the comparison configuration, and the generated analysis tables.

## Interpretation boundary

The current MVP uses a partial parent population. Consequently, results are
eligible for engineering review only. Inferential statistics, winner
selection, and scientific reporting remain disabled until the planned parent
population is available and the precommitted evaluation protocol is repeated.

## Deferred publication layer

After the executable pipeline is complete, a dedicated stage will generate
publication-quality tables and figures for:

- training and validation loss by epoch;
- GNN classification quality metrics;
- MIP-gap comparisons by solver and arm;
- optimization-time and four-region timing comparisons;
- censoring, sensitivity, and paired-effect diagnostics.

That stage will precede a comprehensive English-only review of the README and
code comments. The manuscript will then be assembled from the external Quarto
Manuscript template selected by the research team; no independent Quarto
framework will be created in this repository.
