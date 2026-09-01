# ADR 0007: Isolated Gurobi node-subproblem feasibility audit

- Status: accepted
- Date: 2026-09-01

## Context

The incumbent-conditioned pipeline observes solutions and node relaxations
during Gurobi branch-and-bound. The research question is whether a pruned part
of that tree can be serialized as a structurally distinct MILP, with its own
row, column, and nonzero counts, rather than reused as another label on the
original parent graph.

An incumbent vector does not identify a search node. A node-relaxation vector
also does not contain the branching decisions or local domain changes that
define the node subproblem.

The documented `MIPNODE` query surface exposes relaxation values, optimization
status, global incumbent and bound, explored-node count, solution count, phase,
and runtime. It does not expose a unique node identifier, tree depth, parent,
children, branch path, or node-local variable bounds. Gurobi staff separately
confirm that per-node local bounds are unavailable.

## Decision

Add the standalone `cfl_gnn.cli.audit_gurobi_node_subproblems` research
entrypoint. It loads one original CFL model, forces the established
`MINIMIZE` correction, and observes a bounded number of optimal `MIPNODE`
callbacks with deterministic probe settings:

- `Threads=1`;
- `Presolve=0`;
- a fixed seed;
- explicit time, node, and sample limits.

The observer is passive. It must not add cuts or lazy constraints, inject
solutions, change branching, call `fixed()` or `presolve()`, write a model from
inside the callback, or deserialize Gurobi node files.

Each sample records only callback-visible metadata, relaxation dimensions,
fractionality counts, extrema, and a SHA-256 digest of the relaxation vector.
The full vector is deliberately omitted because this experiment tests API
capability rather than building a dataset.

The output is path-sanitized and separates three claims:

1. what was observed at runtime;
2. what the documented API exposes;
3. whether an exact, structurally distinct MILP was materialized.

The third claim fails closed. A relaxation or incumbent cannot be promoted to
a new MILP instance without exact branch-local state.

## Consequences

- Existing `incumbents.parquet`, `node_relaxations.parquet`, and their collector
  remain unchanged.
- No graph or derived optimization model is produced by this experiment.
- A bounded number of repeated `MIPNODE_NODCNT=0` samples is retained to show
  root-node cut-pass behavior; the count is not relabeled as a node identifier.
- A run with callback errors or no optimal `MIPNODE` samples writes its report
  and then exits nonzero, so the runtime observation remains explicitly
  inconclusive.
- Gurobi Remote Services do not deliver `MIPNODE` callbacks. The DaSCI smoke
  must therefore run the optimizer process locally; WLS license authentication
  alone does not imply remote optimization.
- If DaSCI confirms callback observation, the documented capability boundary
  is sufficient to reject exact Gurobi node-subproblem serialization.
- The subsequent SCIP design must use the solver-native PySCIPOpt interface.
  Pyomo is excluded because the research question concerns node-local tree
  state rather than formulation portability.

## Official references

- [Gurobi callback codes](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html)
- [Gurobi Python model and callback methods](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html)
- [Gurobi staff response on unavailable local node bounds](https://support.gurobi.com/hc/en-us/community/posts/37586816119569-Getting-the-decision-variable-s-local-bounds-within-the-B-B-tree)
- [Callback restrictions with Gurobi Remote Services](https://docs.gurobi.com/projects/remoteservices/en/current/content/programming-with-remote-services/callbacks.html)
