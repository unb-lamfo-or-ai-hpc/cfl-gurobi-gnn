# CFL Neural Diving TRL-6 MVP protocol

## Technological objective

Demonstrate on DaSCI-DGX a reproducible end-to-end prototype that can build,
train, guide, and compare the four precommitted solver x sampling arms using
the currently available parent instances. Completion of the 90-parent
population is a later scientific-validation gate, not an MVP prerequisite.

## Statistical boundary

The parent MILPBench instance is the independent unit. Every incumbent and
local-branching descendant is nested within its parent. A descendant inherits
the canonical fold, and only training parents may produce descendants used by
the learner. Validation and test are original-only.

The equal-parent-mass policy prevents a parent with more accepted descendants
from dominating the objective. A later trainer must implement either explicit
parent weights or balanced parent sampling and record the mechanism.

## Four-arm sequence

1. Solve original parents independently with Gurobi and SCIP.
2. Retain feasible labels up to the maximum configured MIP gap.
3. Capture solver-specific incumbents with objective, gap, and execution-time
   provenance.
4. Apply the same local-branching operator and radius schedule.
5. Solve each derived MILP independently with the corresponding solver.
6. Convert all accepted artifacts with the shared bipartite graph schema.
7. Train the same GNN/hyperparameter budget for each arm.
8. Evaluate every checkpoint on the same original-only held-out parents.
9. Run baseline and GNN-guided solver experiments at a common budget.

## Gap sensitivity

The persisted sample manifest admits validated labels with relative gap no
greater than 0.10. It records nested memberships for 0.01, 0.05, 0.06, and
0.10. Separate training contracts select one threshold before training. No
post-hoc threshold may be chosen from held-out performance.

## Minimum artifact record

Every graph row in `mvp_sample_manifest.jsonl` must include:

- sample and parent identifiers;
- category, difficulty, canonical fold, solver, and sampling strategy;
- graph path and SHA-256;
- label source/hash, objective, relative/percentage MIP gap, and execution time;
- source-incumbent identifier/hash, objective, relative/percentage MIP gap, and
  execution time for derived samples;
- local-branching integer radius and radius fraction for derived samples.

Dataset-producing sprints may add provenance but may not remove these fields.

## MVP completion gate

The prototype reaches the project interpretation of TRL 6 when the four arms
run end-to-end on the partial population in DaSCI-DGX, produce contract-bound
checkpoints, evaluate the same held-out parents, execute both solvers with and
without GNN guidance, and emit a unified comparison report. Statistical
superiority and full-population coverage are explicitly outside this gate.

## Planner

Validate the configuration before any expensive execution:

```bash
python3 -m cfl_gnn.cli.plan_mvp_experiment \
  --config configs/experiments/mvp_partial_v1.json \
  --manifest configs/splits/cfl_90_seed42_folds.csv \
  --output /raid/.../analysis/mvp/mvp_experiment_plan.json
```

When dataset builders begin emitting the unified inventory, add
`--sample_manifest /raid/.../mvp_sample_manifest.jsonl`. Use
`--strict_inventory` only when all four arms are expected to contain eligible
samples.
