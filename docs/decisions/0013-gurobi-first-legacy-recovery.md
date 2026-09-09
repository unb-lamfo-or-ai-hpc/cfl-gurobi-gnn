# ADR 0013: Gurobi-first recovery of the legacy research pipeline

- Status: accepted for implementation
- Date: 2026-09-09
- Supersedes: the graph-authority and primary-guidance assumptions of the
  engineering MVP in ADR 0012

## Context

The PR #24--#40 sequence demonstrated that the repository can execute a
contract-bound four-arm engineering vertical slice.  A scientific review of
the resulting PR #40 outputs nevertheless found that this path is not an
acceptable replacement for the previously tested baseline.  It used a very
small parent population, two training epochs, zero-valued root-LP features,
and hard domain fixings as solver guidance.

The implementation preserved in commit
`9903c1dc66f65e9497d7faa2d8d4f3ee414a0f42` was not deleted.  Most core files
were renamed into the `cfl_gnn` package with high similarity, while the Gasse
model, graph analyses, and Gurobi benchmark were preserved exactly.  The
problem is integration: later MVP-specific paths bypassed the preserved
collection, graph, training, and evaluation sequence.

This decision is bound to:

- legacy commit `9903c1dc66f65e9497d7faa2d8d4f3ee414a0f42`;
- current pre-recovery commit
  `9f7da7d206129fcd72c72d1a8d682bf3cf413fde`.

## Decision

### Solver roles

Gurobi is the priority solver and the sole graph-construction authority.
PySCIPOpt remains a comparison solver.  Both solvers may independently provide
labels and performance measurements, but solver-specific labels do not define
the graph features.

The defective objective direction encoded by the CFL MILPBench files is
handled as before: the imported original sense is recorded and the effective
optimization sense is forced to `MINIMIZE`.

### Unit of graph construction

The graph unit is a mathematical MIP artifact:

- exactly one graph is built for each original parent MIP;
- exactly one graph is built for each accepted synthetic MIP;
- an incumbent vector is provenance and a candidate center, not a graph;
- Gurobi and SCIP labels are attached as separate manifest views.

Synthetic descendants inherit the parent fold and remain train-only.  Original
parents alone populate validation and held-out test partitions.

### Root-LP feature

The zero-ablation policy is prohibited.  The restored graph builder must obtain
the `root_lp_relaxation` feature from Gurobi for every original or synthetic
MIP and fail closed when it cannot do so.

Before changing the builder, PR #43 must compare the legacy first optimal
root-`MIPNODE` observation with a controlled Gurobi relaxation-copy candidate.
The legacy-compatible mechanism is retained unless that parity audit supports
a documented replacement.  Solver, parameters, variable identity, status,
runtime, and feature hashes must be recorded.

### Parent solution collection

The preserved `cfl_gnn.pipelines.gurobi_incumbents` implementation becomes the
canonical Gurobi backend.  The specialized Gurobi parent CLI must delegate to
that backend.  A SCIP backend will expose the same artifact schema, and the
specialized SCIP parent CLI will delegate to it.

A population orchestrator will execute Gurobi first and then the optional
matched SCIP comparison.  It must support canonical parent manifests, Slurm
arrays, resumable execution, and hash-verified reuse without duplicating solve
logic.

### Descriptive analysis

The phase-1 analysis and graph analyses return to the executable pipeline.
Required outputs include:

- parent coverage, failures, and right censoring;
- terminal MIP gap and 1/5/6/10-percent sensitivity;
- input-read, model-build, optimization, and total wall times;
- incumbent count and trajectory, time to first and best incumbent;
- objective, bound, node count, and difficulty strata;
- paired common-parent summaries under equal controls;
- graph size, sparsity, domains, and feature distributions;
- descriptive graph clustering for parents versus synthetic descendants.

Clustering is descriptive only and may not define folds, select models, or use
held-out outcomes.

### Neural guidance

Hard domain fixing is excluded from the primary recovered pipeline.  Setting
`LB = UB = predicted_value` constructs a restricted sub-MIP; it is not a hint
or a warm start and can exclude the optimum or create infeasibility.  PR #37
therefore remains historical engineering evidence only.

The primary recovered intervention is Gurobi `VarHintVal`/`VarHintPri`.  A
partial Gurobi MIP start is the secondary candidate.  PySCIPOpt partial primal
solutions and diving or large-neighborhood search are comparison-only
candidates.  Held-out test results may not select an intervention.

Pyomo remains excluded.

## Consequences

- the established Gasse architecture and training implementation are recovered
  rather than replaced;
- graph identity no longer depends on which solver generated a label;
- all database graphs use one Gurobi feature protocol;
- SCIP remains scientifically useful without becoming a graph encoder;
- the PR #40 figures remain reproducible engineering artifacts but are not
  accepted scientific results;
- implementation resumes in small gated PRs after this contract-only PR.

## Implementation sequence

1. PR #42: consolidate parent collectors, add Gurobi-first orchestration, and
   restore phase-1 descriptive outputs.
2. PR #43: restore Gurobi graph authority, root-LP parity, dataset statistics,
   and clustering.
3. PR #44: reconnect Gasse serial/DDP training and the full evaluator to
   parent-aware manifests.
4. PR #45: restore native Gurobi hints and compare partial MIP starts, retaining
   SCIP as a matched comparator.
5. PR #46: execute and report the currently available parent population.
6. PR #47: complete academic-English documentation, code-comment review, and
   dependency metadata.

Expansion to all 90 parents occurs only after this recovered MVP passes.

## PR #41 boundary

PR #41 adds documentation, the static contract, a read-only diagnostic, and
smoke tests.  It does not alter any production collector, graph builder,
trainer, evaluator, or solver benchmark.

