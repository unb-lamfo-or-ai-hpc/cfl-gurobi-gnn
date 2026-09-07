# Paired six-parent MVP vertical slice

This gate expands the one-parent engineering smoke into the smallest balanced
slice that can exercise training, validation, and held-out test behavior. It
does not claim scientific representativeness of the planned 90-parent study.

## Precommitted population

Rotation 0 maps fold 0 to test, fold 1 to validation, and folds 2--4 to train.
The six parents contain exactly one easy and one medium instance in each role:

| Role | Easy | Medium |
|---|---|---|
| train | `CFL_easy_instance_2` | `CFL_medium_instance_2` |
| validation | `CFL_easy_instance_1` | `CFL_medium_instance_5` |
| test | `CFL_easy_instance_0` | `CFL_medium_instance_0` |

The explicit list prevents compute availability or observed solver performance
from changing the sample after execution starts. Hard instances remain absent
because none are currently available in the development inventory.

Every parent is independently solved by Gurobi and SCIP under the same
one-hour, one-thread, one-million-node budget and seed 42. Online incumbents are
preserved for both solvers. Only the two training parents may become sources of
local-branching descendants; validation and test remain original-only.

## Outputs and gates

The preflight writes a path-sanitized plan and twelve-task JSONL manifest. A
Slurm array runs at most four fresh solver processes concurrently. The audit
then requires all twelve labels, checks solver artifacts and hashes, and emits
`parent_runs.tsv` with paths relative to the configured runtime run root.

Training-parent reports must pass the augmentation gate. Validation/test
reports are expected to be `inconclusive` only because augmentation is
prohibited; their original labels must still be gap-eligible. No test graph is
loaded or inspected at this stage.

The next gate applies the symmetric local-branching operator to the four
solver/train-parent pairs, solves the descendants independently, generates the
graphs, composes the four manifests, and repeats the PR #30 loader audit.
