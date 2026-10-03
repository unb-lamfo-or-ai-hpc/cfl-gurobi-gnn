# Four-arm common held-out evaluation

PR #36 evaluates every PR #35 checkpoint on exactly the same held-out parent.
It is an engineering gate and does not select a model or claim scientific
performance.

## Leakage controls

The CLI rebuilds the PR #30/PR #34 dataset contract, verifies the complete
PR #35 training plan and aggregate report, and checks all checkpoint and
per-arm summary hashes. Only after these checks pass may it deserialize the
held-out graph.

The probability threshold is fixed at 0.5 before evaluation. The test labels
are used only to calculate unweighted BCE and classification diagnostics. No
threshold, confidence cutoff, arm ranking, or model selection is fitted from
the test outcomes. All four arms advance to the solver experiment.

## Solver-neutral hint artifact

Each checkpoint produces one gzip-compressed JSONL artifact per held-out
parent. Every discrete variable is represented by its canonical name,
probability, binary prediction, confidence, and integer priority. Ground-truth
labels are prohibited from this artifact. Its uncompressed semantic content
and compressed bytes receive separate SHA-256 fingerprints.

The neutral artifact is not yet a Gurobi `.hnt`, a SCIP solution, or a set of
fixed variables. PR #37 will consume the same artifact through solver-specific
adapters and enforce equal budgets. This boundary prevents the evaluation PR
from silently applying different hint semantics to Gurobi and SCIP.

## Metrics and interpretation

Unweighted BCE, F1, precision, recall, and confusion counts are secondary GNN
diagnostics. Within-solver augmented-minus-original deltas are descriptive
only because the development slice contains one test parent. The research
primary outcomes remain terminal relative MIP gap and solver execution time;
they are measured only in the next equal-budget solver gate.
