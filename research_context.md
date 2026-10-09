# CFL--GNN research context

## Research question

Can a graph neural network (GNN) learn useful guidance for capacitated
facility-location (CFL) mixed-integer programs, and can that guidance improve
the quality reached or the time required by Gurobi under a controlled,
reproducible protocol?

The relevant comparison is not only whether a method finds an optimum. It is
also the incumbent quality, primal/dual bounds, relative gap, runtime, memory,
thread/GPU allocation, and the cost of preparing the guidance.

## Scientific object

Each parent instance is an indivisible experimental unit. Derived artifacts
must retain their parent ID and may only be generated from training parents.
The project uses the explicit easy/medium/hard cohorts and the 34/10/10
parent-level train/validation/test contract. Instance labels in tables should
use the stable notation `F0`--`F29` for easy parents and `M0`--`M29` for medium
parents whenever a cohort-level presentation is intended.

## Three solver methods

The controlled solver comparison has three distinct arms:

1. Gurobi without an external start;
2. Gurobi with a partial start obtained from a verified root LP relaxation;
3. Gurobi with a partial start produced by the frozen GNN.

The relaxation start is not a GNN prediction and does not mean that Gurobi is
absent from the experiment: the root relaxation is an explicitly measured
Gurobi preparation step. Its source, cost, variable order, feasibility checks,
and partial-start policy must be reported separately from the GNN arm.

## Current project boundary

The MVP is a scientific prototype, not a production service. Reproducibility
and honest qualification take priority over package modernization or broad
automation. The repository records code and sanitized evidence; HPC keeps
private paths and large raw logs.
