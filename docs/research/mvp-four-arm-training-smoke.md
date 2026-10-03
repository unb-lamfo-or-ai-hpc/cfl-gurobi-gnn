# Four-arm MVP training smoke

PR #35 executes the first complete training pass over the easy-only dataset.
It is an engineering gate, not a scientific comparison. The four independent
models represent Gurobi/SCIP crossed with original/incumbent-augmented
training data.

## Paired controls

Each arm restarts the same model initialization seed and receives the same
number of optimizer steps per epoch. A deterministic parent-balanced sampler
gives every parent equal draw mass. In the one-parent easy slice, the original
sample is repeated four times in an original-only arm, while the original and
three descendants are drawn once each in its augmented counterpart.

The original and augmented arms for one solver reuse two nuisance controls:

- prenormalization is fitted on the same solver-original training graph;
- positive-class weighting is calculated from the solver-original training
  labels and reused in both arms.

Consequently, the within-solver contrast changes the training sample set but
not initialization, normalization, class weighting, or optimizer-step budget.
The common validation reference is identical across all four arms.

## Held-out and eligibility boundaries

The training CLI reconstructs and verifies the PR #30 loader contract before
importing the heavy ML stack. It deserializes only selected training graphs and
the common validation graph. The held-out test partition is represented in the
run contract only by count, parent identifier, and hash; its graph path is not
included in the training-run plan and it is never loaded.

Each arm writes a checkpoint, CSV history, and path-sanitized JSON summary.
The aggregate report verifies the initial model-state hash, actual optimizer
update count, exact validation-reference hash, effective device, paired
controls, and output artifact hashes.
Outputs remain development-only and ineligible for scientific reporting.

The next gate evaluates all four checkpoints on the same held-out parent and
then generates neural-diving hints for equal-budget solver comparisons. Solver
MIP gap and execution time remain the primary metrics; GNN classification
metrics are secondary diagnostics.
