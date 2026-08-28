# Repository architecture

The repository separates five concerns: solver integration, sample-generation
pipelines, graph transformation, learning, and evaluation. Command-line modules
under `cfl_gnn.cli` compose those layers and are the only paths referenced by
the Slurm scripts.

Artifact schemas live in the dependency-free `cfl_gnn.artifacts` package so
datasets can be read without importing a solver backend.

```text
CLI -> pipeline -> solver
 |        |
 |        +-> collected artifacts
 v
graph transformation -> training -> evaluation -> solver hints/benchmark
```

## Pipeline matrix

| Solver | One graph per parent instance | Incumbent-conditioned graphs |
|---|---|---|
| Gurobi | Planned next | Preserved from the legacy pipeline |
| SCIP/Pyomo | Future | Future |

The four variants must share graph schemas, model implementations, evaluation
metrics, and artifact contracts. They must not be maintained as four copies of
the codebase.

## Stability boundary

Files in `cfl_gnn.cli` provide stable, unversioned entrypoints. Implementation
modules may evolve behind those entrypoints. Generated data and experimental
outputs remain outside the Python package.
