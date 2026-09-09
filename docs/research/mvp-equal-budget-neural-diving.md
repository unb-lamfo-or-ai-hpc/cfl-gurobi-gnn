# Equal-budget Gurobi/SCIP Neural Diving smoke

PR #37 is the first end-to-end solver experiment in the four-arm MVP. It
crosses every GNN arm with both target solvers and adds one unguided control
for each solver. For one held-out parent this produces ten independent runs:
eight guided runs and two controls.

This remains a development-only engineering smoke. It does not select an arm
and is not eligible for scientific reporting while the planned 90-parent
population and replication design are incomplete.

## Symmetric Neural Diving operator

The solver-neutral PR #36 artifact contains one prediction and confidence for
every discrete variable. PR #37 sorts those records by priority descending,
confidence descending, and variable name ascending. It fixes exactly the top
10 percent to their predicted values.

The selected variable names and values receive a semantic SHA-256 fingerprint.
The audit requires that the fingerprint be identical when the same GNN arm is
run with Gurobi and SCIP. Gurobi applies a fixing through equal lower and upper
bounds; PySCIPOpt applies the same fixing through `Model.fixVar`. Solver-native
advisory mechanisms are deliberately excluded because Gurobi variable hints
and SCIP partial solutions do not have equivalent semantics.

An infeasible or incumbent-free guided run is a valid solver outcome but it
cannot pass the primary-outcome completeness gate. Such a result triggers a
review of the fixing policy; it must not be silently replaced or discarded.

## Equal-budget contract

One experiment selects a single optimization time limit between 3,600 and
14,400 seconds, inclusive. Every guided and control run uses that exact limit,
one thread, seed 42, the same original held-out MIP, and forced minimization.
Different limits constitute different experiments and must never be pooled as
if they were paired observations.

Each task runs in a fresh Slurm array process. The aggregate gate requires the
same hardware-class fingerprint across tasks. The design supports three
families of descriptive comparisons:

- guided versus unguided within each target solver;
- incumbent-augmented versus original-only training within source and target
  solver;
- the same GNN fixing set on SCIP versus Gurobi.

## Four timing regions

All durations use `time.perf_counter`, which is monotonic and appropriate for
elapsed wall time.

1. `total_wall_time_seconds` starts before contract and input verification and
   ends after solver teardown and outcome extraction.
2. `data_read_wall_time_seconds` covers plan verification, SHA-256 reads of the
   source artifacts, and decompression/validation of the neutral hints.
3. `model_build_wall_time_seconds` covers solver import, model parsing,
   minimization correction, parameterization, variable lookup, and fixings.
4. `model_optimize_wall_time_seconds` surrounds only `model.optimize()`.

Post-optimization extraction and unattributed overhead are also retained so
the total can be reconciled. Solver-reported runtime is recorded independently
as an audit value; the primary execution-time measurement is the external wall
time around `model.optimize()`.

## Primary outcomes

The primary outcomes are terminal relative MIP gap and optimization wall time.
Objective value, best bound, status, censoring, node count, total time, input
time, model-build time, and solver-reported runtime provide interpretation and
reproducibility. GNN classification metrics from PR #36 remain secondary and
are not used for selection in this experiment.
