# Experiment protocol

Current approved planning contract: 2026-10-10. Detailed PR85 scope and PR86/87
protocol/resource proposals: [submission protocol](research/submission-protocol-20261010.md).
This document approves no experiment, training, retry or HPC submission.

## Required record for every run

Record the following before execution:

- protocol ID and source commit;
- parent IDs, cohort, role, and partition;
- method arm and whether the start is none, relaxation-derived, or GNN-derived;
- model/checkpoint and normalization hashes;
- Gurobi version, Python version, parameters, seed, objective sense, gap and
  time limits;
- physical CPU cores, thread cap, GPU count/type, memory limit, partition,
  wall limit, and requeue policy;
- input, receipt, and public-output SHA256 values.

## Data separation

Partitioning is performed at the parent-instance level. Derived samples never
cross from validation or test into training. Training labels may fit the model;
validation labels may select its checkpoint/threshold; test labels may only
evaluate frozen predictions. Solver-produced evaluation references are not
training data or permission to generate new labels. No test label may select
a start, support budget, checkpoint or hyperparameter. No dataset expansion or
new hyperparameter search is admitted without scientific justification.

The admitted 54-parent cohort is 30 easy + 24 medium, with train/validation/test
34/10/10. The ten test parents are historically exposed. Report the label-quality
selection and resulting population bias, and describe future solver comparisons
as retrospective controlled evaluations, not independent generalization tests.

The easy and medium strata are reported separately. A table must state the
number of parents, number of derived artifacts, number of attempted runs,
number of qualified runs, and number excluded, with the exclusion reason.

## Solver comparison

For each eligible parent and each thread cap in `{1, 2, 4, 8, 16}`, compare
the three arms under matched instance, seed, stopping rule, and resource
contract. Report preparation cost separately from solver cost. A partial start
must be checked for variable-order identity, bounds, integrality policy,
feasibility, and the exact number of values supplied.

Use explicit labels M0 (no external start), M1 (LP-matched partial start), and
M2 (frozen GNN partial start). These method labels are not medium-parent IDs;
tables must keep separate `method` and `parent` columns. The root comes from
Gurobi preparation, not from the GNN. Existing M1 matches M2's support and
positive-count budget: disclose that dependency and account for its preparation
cost. Supply only selected binary values, leaving continuous and unselected
variables unspecified; a partial start is not a feasible complete solution or
a fixing of bounds. Report acceptance, rejection, repair and abstention.

Do not equate a `MINIMIZE` override with mathematical validity. PR85 must verify
the intended CFL formulation, coefficients/units, constraints, variable domains,
objective constants/signs and any transformation from the source `MAXIMIZE`.
Keep original bytes and historical interpretations; unresolved inconsistency
blocks new solver comparisons and the corresponding manuscript claims.

## Mandatory GPU comparison

Compare full serial training on one GPU, without DDP, against full PyTorch DDP
training on four GPUs. Use identical architecture, dataset, parent partitions,
global batch, sample schedule, initialization and optimizer policy, and an equal
number of epochs/updates. Reuse the existing parent-aware DDP pipeline. Fix the
global-batch/update mismatch before use; do not run the legacy graph-random-split
entry point. Measure whole training time, speedup `T1/T4`, efficiency `T1/(4*T4)`,
GPU/CPU/memory use and final predictive metrics. See the detailed protocol for
budget bounds and acceptance criteria. This obligation does not authorize jobs.

## Reporting

Report primal objective, best bound, relative gap, time to first incumbent,
time to termination, preparation time, memory, CPU allocation, GPU allocation,
and solver status. Include paired differences and confidence/dispersion
summaries where the number of qualified pairs permits them. Never infer a
performance result from a receipt that is marked partial, unqualified, or
scientifically ineligible.

A raw receipt's original eligibility flag is never rewritten. A separate,
versioned scientific review may qualify named metrics/rows only, with the
required hashes and limitations; it cannot blanket-promote an incomplete run.
Unknown costs remain missing. Pair at the parent level, distinguish solver
seeds from independent parents, preserve censored times and all failed attempts.
Record cold end-to-end cost and cache-amortized cost separately. No automatic
retry, requeue, extension, package upgrade or historical result overwrite.
