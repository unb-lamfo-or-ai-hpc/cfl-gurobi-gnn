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
| Gurobi | Provenance, fold-aware serial trainer, and contract-locked evaluator available | Preserved; isolated node-materialization feasibility audit available |
| SCIP/PySCIPOpt | Root-relative node-MIP identity validated mechanically | Domain-restricted variants remain research-only and ineligible pending ADR 0010 gates |

The four variants must share graph schemas, model implementations, evaluation
metrics, and artifact contracts. They must not be maintained as four copies of
the codebase.

Domain-restricted SCIP variants are descendants of one parent instance, not
additional independent benchmark instances. Parent identity is the split and
inference boundary. Any future derived dataset must live behind a separate
artifact contract and preserve the canonical parent fold.

Pyomo is excluded from the architecture. SCIP integration will use PySCIPOpt
directly so node-local state is not hidden behind a formulation layer.

## Stability boundary

Files in `cfl_gnn.cli` provide stable, unversioned entrypoints. Implementation
modules may evolve behind those entrypoints. Generated data and experimental
outputs remain outside the Python package.
