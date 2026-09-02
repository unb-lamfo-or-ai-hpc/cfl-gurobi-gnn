# Parent-grouped domain-variant eligibility protocol

## Purpose

This protocol tests whether SCIP `domain_distinct_same_matrix` artifacts can be
useful derived learning samples without being misrepresented as independent
MILP instances. It operationalizes ADR 0010 and does not authorize dataset
construction.

## Hypotheses

- H1: node MIPs retain distinct local domains after fresh-process reload.
- H2: the graph representation preserves those domain differences.
- H3: independently generated labels remain feasible for the derived domains.
- H4: deterministic sampling and deduplication produce bounded, reproducible
  variants per parent.
- H5: evaluation grouped by parent does not leak sibling variants across roles.

Failure of any required hypothesis is a valid negative result.

## Phase 0: graph-schema audit

Before another large solver run, inspect the current bipartite graph builder and
its normalization path. Record whether every discrete and continuous variable's
local lower and upper bounds are represented in node features. Demonstrate with
a controlled pair that equal-matrix models with different bounds produce
different graph fingerprints while retaining compatible dimensions.

Stop if the bound changes are absent, clipped into equality, or otherwise lost.

## Phase 1: bounded replication

Use a small, precommitted parent set covering every currently available
difficulty. Run presolve-off and default-presolve experiments separately. For
each parent, retain a bounded number of `writeMIP()` candidates across declared
depth strata. Disable transformed controls after one replication confirms their
diagnostic behavior.

Record source SHA-256, parent id, solver versions, seed, limits, root baseline,
semantic-node hash, formulation hash, and artifact hash. Numeric node ids alone
must never define identity.

## Phase 2: label audit

Reload and solve each admitted candidate independently under an explicit time
and optimality policy. Verify the label against the candidate's domains and
objective sense. Report optimal, feasible-nonoptimal, infeasible, unbounded,
timelimit-without-solution, and invalid outcomes separately.

Do not copy a parent solution or incumbent into a child label without an
explicit feasibility check. Do not use test-partition variants for threshold
selection or training decisions.

## Phase 3: grouping, deduplication, and weighting

Join every candidate to the canonical parent manifest. Fail closed when a
parent is missing, ambiguous, or assigned to a different role. Audit duplicates
at four levels: semantic node, mathematical formulation, graph representation,
and target label.

Precommit a per-parent sample cap and a deterministic selection order. Training
may later weight variants so each parent has equal total weight; evaluation must
report parent-level aggregates before any pooled variant-level metric.

## Phase 4: decision report

Produce a path-sanitized report containing:

- parent and variant inventory by difficulty and fold;
- serialization, graph, and label gate outcomes;
- duplicate rates at every identity level;
- depth and bound-change distributions;
- storage and solve-time budgets;
- candidate exclusions with reason codes;
- a final `dataset_eligible` decision that defaults to `false`.

The final review chooses one of:

- stop the domain-variant strategy;
- repeat the bounded experiment with a corrected contract;
- authorize a research-only parent-grouped dataset implementation.

## Acceptance checklist

- [ ] local bounds are visible in the current graph schema;
- [ ] graph fingerprints distinguish controlled bound variants;
- [ ] replication covers multiple parents and available difficulties;
- [ ] candidate labels are generated or validated on the derived MIPs;
- [ ] every descendant inherits its parent's fold and role;
- [ ] duplicates and parent weights are explicit;
- [ ] transformed controls are excluded from dataset artifacts;
- [ ] resource use is bounded and reported;
- [ ] terminology does not claim independent or exact subproblems;
- [ ] Pyomo, Gurobi collectors, canonical folds, trainers, and evaluators remain
  unchanged in the design PR.
