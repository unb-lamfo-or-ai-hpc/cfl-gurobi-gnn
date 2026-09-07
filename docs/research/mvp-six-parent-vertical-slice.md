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
separates valid fixed-budget benchmark observations from label admissibility.
An observation with a terminal gap above 10% remains valid right-censored
benchmark evidence, but it cannot label a graph. `parent_runs.tsv` inventories
all mechanically valid paired runs using paths relative to the runtime root.

Every solver-specific training parent must eventually have an admissible label.
Validation/test require one common best-known admissible reference per parent,
not an admissible label from both solvers. Missing labels are completed under a
separate rescue contract; the one-hour benchmark artifacts remain immutable.
No test graph is loaded or inspected at this stage.

The audit also verifies every parent-plan contract hash and the precommitted
solver, profile, time, node, thread, seed, objective-sense, fresh-process, and
no-warm-start settings. When coverage is incomplete it writes a deterministic
`label_rescue_tasks.jsonl`. The rescue keeps the one-hour benchmark immutable,
uses a separate four-hour single-thread budget, selects Gurobi `default` and
SCIP `feasibility` profiles, and prohibits cross-solver warm starts.

The next gate executes and audits the precommitted parent-label rescue described
in `mvp-label-rescue.md`. Only after all required labels are admissible does the
pipeline apply the symmetric local-branching operator to the four
solver/train-parent pairs, solve the descendants independently, generate the
graphs, compose the four manifests, and repeat the PR #30 loader audit.

