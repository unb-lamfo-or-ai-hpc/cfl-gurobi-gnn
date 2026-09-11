# ADR 0014: Solver-native neural guidance precedes restricted sub-MIPs

## Status

Accepted for the development MVP.

## Context

The historical benchmark fixed selected variables by setting their lower and
upper bounds to the predicted value. That operation is a restricted sub-MIP,
not a solver hint: a wrong assignment may exclude the original optimum or make
the restricted model infeasible. The recovered pipeline must preserve this
distinction and must not select a method from held-out test outcomes.

## Decision

Gurobi `VarHintVal` and `VarHintPri` are the primary neural-guidance method.
They guide heuristics and branching without changing the feasible region. The
unguided Gurobi run is its primary paired control.

Partial MIP starts are a separately reported matched comparison. Gurobi and
SCIP receive the same deterministic top-confidence assignment coverage, but
their native completion mechanisms are not claimed to be algorithmically
identical.

Confidence-based partial fixing and a local-branching trust region remain
exploratory two-phase methods. Each may restrict the first 20 percent of the
time budget, but the full original model must then be restored and solved for
the remaining budget. Any incumbent found in the restricted phase may be
offered as a start. This recovery phase is mandatory even when the restricted
phase succeeds.

The fixed sensitivity values are 1, 5, and 10 percent assignment coverage and
0.1, 0.5, and 1 percent local-branching radius. The solver budgets are 3,600
and 14,400 seconds. Terminal relative MIP gap and optimization wall time are
the primary outcomes; total, data-read, model-build, and optimization times
are recorded separately. Right-censored observations are retained and flagged.

## Consequences

- Global hard fixing is removed from the primary path.
- Gurobi remains the priority solver and graph authority.
- SCIP remains a matched comparison and label/incumbent source.
- Test data cannot choose method, coverage, radius, checkpoint, or budget.
- The PR #49 policy gate performs no solver run. PR #50 implements the native
  adapters and executes the paired benchmark.

