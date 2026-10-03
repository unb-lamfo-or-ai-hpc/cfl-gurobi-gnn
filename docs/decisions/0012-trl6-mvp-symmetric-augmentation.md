# ADR 0012: TRL-6 MVP with symmetric incumbent augmentation

- Status: accepted for implementation
- Date: 2026-09-04

## Context

The research MVP must compare Gurobi and SCIP with and without training-data
augmentation. Gurobi's documented callback API does not expose enough
node-local branch state to serialize an exact branch-and-bound subproblem.
Using exact SCIP node MIPs and a different Gurobi approximation as the primary
2 x 2 experiment would confound solver and sampling effects.

The currently available population is incomplete. It is suitable for
engineering the pipeline, but not for the final academic claims planned for 30
easy, 30 medium, and 30 hard parent instances.

## Decision

The primary MVP is a solver x sampling 2 x 2 design:

| Arm | Label solver | Training samples |
|---|---|---|
| `gurobi_original` | Gurobi | original parents |
| `gurobi_incumbent_augmented` | Gurobi | parents plus local-branching descendants |
| `scip_original` | SCIP/PySCIPOpt | original parents |
| `scip_incumbent_augmented` | SCIP/PySCIPOpt | parents plus local-branching descendants |

Both augmented arms use `incumbent_local_branching_v1`. For an incumbent
binary vector x*, its neighbourhood is defined by

```
sum(x_j for x*_j = 0) + sum(1 - x_j for x*_j = 1) <= k.
```

Only binary variables participate. The radius is a precommitted fraction of
the number of binary variables, with a minimum integer radius. The mathematical
operator, radius schedule, objective direction, and artifact fields are the
same for both solver backends.

Derived samples are new optimization artifacts but are not independent
benchmark instances. They inherit the parent identifier, category, difficulty,
and fold. They may augment training only. Validation and held-out test contain
original parent instances exclusively, and a parent contributes equal total
training mass regardless of its number of descendants.

Exact SCIP node MIPs remain an exploratory arm. They are not part of the
factorial solver x augmentation comparison.

## Label-quality policy

The MVP stores every validated feasible label with relative MIP gap at most
0.10. The exact relative/percentage gap, objective, execution time, solver,
versions, and solution provenance remain attached to every sample.

Training analyses are precommitted at nested thresholds of 0.01, 0.05, 0.06,
and 0.10. A threshold is fixed in each training contract. Missing, negative,
non-finite, or greater-than-0.10 gaps fail closed. Sensitivity analysis changes
eligibility, not the persisted graph or label.

## Evaluation boundary

- augmentation is restricted to training parents;
- the test target is the best known valid solution across Gurobi and SCIP
  artifacts, selected without reference to GNN predictions;
- predictive metrics are secondary to solver performance;
- primary optimization outcomes are terminal MIP gap at a common budget and
  right-censored execution time to a common target;
- all partial-population outputs are `development_only=true` and
  `scientific_reporting_eligible=false`.

## Consequences

- the core comparison can separate solver and augmentation factors;
- Pyomo remains excluded;
- the existing Gurobi incumbent collector is preserved as a source of
  incumbents, not as a source of exact tree-node models;
- the PySCIPOpt node-MIP prototype remains valuable exploratory evidence;
- the full 90-parent experiment reuses the same contracts after the MVP gate.
