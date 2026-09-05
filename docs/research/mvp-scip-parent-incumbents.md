# SCIP original-parent solve and online incumbents

## Purpose

This component creates the SCIP-original arm's label for one original CFL
parent and preserves every best incumbent observed online.  It is also the
source of incumbent vectors used by the symmetric local-branching operator.
It does not create a training graph and it does not admit derived samples.

PySCIPOpt is the only SCIP interface.  Pyomo is outside the architecture.

## Solve contract

- read the original MILPBench CFL LP/MPS in a fresh process;
- force the effective objective sense to `MINIMIZE` because the source CFL
  files carry the known erroneous `MAXIMIZE` declaration;
- use the precommitted `default` SCIP profile, one thread and a fixed seed;
- attach a passive `BESTSOLFOUND` callback with
  `Model.attachEventHandlerCallback`;
- stream each full incumbent vector to Parquet instead of retaining all
  vectors in memory;
- store objective, discovery time, primal-dual gap and node count for every
  incumbent;
- write the final named solution in the format consumed by the shared
  local-branching generator.

The callback does not add constraints, inject solutions or alter branching.
Its I/O overhead is part of this instrumented data-collection run and is
reported through `execution_time_seconds`.

## Eligibility gate

The final solution becomes a valid SCIP label when the named solution is
feasible, the online trace passes its consistency audit, the Parquet stream is
complete, and the terminal relative MIP gap is at most 10%.  It becomes an
augmentation source only when the parent belongs to the training partition.
Validation and test parents remain original-only.

Even after passing this gate, the artifacts remain
`dataset_eligible=false` and `scientific_reporting_eligible=false`.  Graph
generation and sample-manifest admission are later gates.

## Outputs

- `scip_parent_solve_plan.json`: immutable input and solver contract;
- `parent_solution.json.gz`: final named solution and online trace;
- `incumbents.parquet`: full online incumbent vectors;
- `incumbent_variable_order.json.gz`: explicit vector-to-variable mapping;
- `scip_parent_solve_report.json`: checks, primary metrics and eligibility.


