# Research pipeline architecture

The package separates solver execution, artifact identity, graph construction,
learning, evaluation, and descriptive analysis. CLI modules compose these layers;
experiment contracts specify which route is admissible.

## Data and authority boundaries

| Layer | Responsibility | Boundary |
|---|---|---|
| Parent collection | Solve originals; retain incumbent trajectories, gaps, and timing | Gurobi first; SCIP is a separately identified comparison |
| Augmentation | Materialize Local Branching MIPs around audited train-parent centers | No one-graph-per-incumbent interpretation |
| Independent labels | Solve and validate each mathematical MIP | Label solver is provenance, not graph authority |
| Graph construction | Encode objective, domains, rows, coefficients, and real root context | Gurobi only; strict route rejects missing root evidence |
| Learning | Fit versioned Gasse models on parent-aware manifests | Training statistics exclude validation and test |
| Evaluation | Apply the selected checkpoint and threshold to original held-out parents | Test results do not select the model or policy |
| Solver benchmark | Compare native guidance with controls at precommitted budgets | Full-model feasibility, gap semantics, and censoring remain explicit |
| Descriptive outputs | Summarize coverage, graph structure, learning, and solver outcomes | No population-level claims from engineering runs |

Gurobi and SCIP labels can be separate views of the same graph. An augmented
training arm adds independently labelled synthetic MIPs without creating new
independent parent units. Validation/test remain original-only; descendants
inherit the canonical parent fold. The paired four-arm population is the common
eligible intersection, not automatically the complete confirmation cohort.

## Implementation map

- [Pipelines](../src/cfl_gnn/pipelines/README.md) own orchestration and receipts.
- [Solvers](../src/cfl_gnn/solvers/README.md) implement native execution.
- [Artifacts](../src/cfl_gnn/artifacts/README.md) define persisted structures.
- [Graph](../src/cfl_gnn/graph/README.md) owns encoding and dataset access.
- [Models](../src/cfl_gnn/models/README.md), [training](../src/cfl_gnn/training/README.md),
  and [evaluation](../src/cfl_gnn/evaluation/README.md) separate architecture,
  learning policy, and held-out assessment.
- [Analysis](../src/cfl_gnn/analysis/README.md) supplies manifest-bound diagnostics.

Pyomo is excluded. The preserved legacy Gasse file is not edited to introduce
numerical changes; corrected prenormalization uses a distinct model version.
The strict graph protocol records the original objective declaration and forces
MINIMIZE for every CFL model.

## Historical and current routes

The earlier incumbent-conditioned CLI, permissive root fallback, and zero-ablation
MVP remain identifiable for reproducibility. They are not alternative defaults
for the recovered confirmation pipeline. In particular, a restricted node model,
an incumbent vector, and an original MILP are different research objects.

Source hashes can include comments and docstrings. Even a documentation-only
edit within a Python module can invalidate a recorded implementation fingerprint.
Do not update a shared checkout during a running campaign or modify old reports
to make their hashes match new code. Preserve the original execution revision
and generate new contracts when code changes.

See [ADR 0013](decisions/0013-gurobi-first-legacy-recovery.md) and
[ADR 0014](decisions/0014-neural-guidance-policy.md) for the governing decisions.

