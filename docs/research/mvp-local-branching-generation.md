# MVP local-branching generation gate

PR #25 implements the first dataset-generation slice of the four-arm MVP. It
materializes local-branching MILPs from one incumbent produced by the same
solver arm. It does not solve, label, graph, or admit those MILPs into training.

## Symmetric operator

For binary incumbent values `x*`, both adapters add exactly

`sum(x_j: x*_j = 0) + sum(1 - x_j: x*_j = 1) <= k`.

The canonical linear form, radius rule, and operator hash are solver-neutral.
Gurobi and SCIP outputs share the operator-contract hash. Their concrete
constraint hashes may differ because the source incumbents may differ.

The radius is `max(1, ceil(fraction * number_of_binary_variables))`, using the
precommitted fractions 0.001, 0.005, and 0.01. Equal integer radii are
deduplicated, which matters for toy instances.

## Incumbent inputs and provenance

- Gurobi: `incumbents.parquet`; its positional vector is bound to the parent
  model's variable order.
- SCIP: a gzip or plain JSON solution containing named variable values, as
  emitted by the independent PySCIPOpt solution worker.

Every variant records the parent and incumbent hashes, solver, fold, local
branching radius, source incumbent objective, admission MIP gap, its measurement
point, execution time, and incumbent discovery/terminal metrics when available.
Gurobi's callback gap is correctly tagged as measured at incumbent discovery;
SCIP's solution-file gap is terminal. The selected incumbent must satisfy the
MVP maximum admission relative gap of 0.10. CFL objective sense is forced to
`MINIMIZE` while the original sense remains in provenance.

Legacy Gurobi Parquet files may contain Unix epoch timestamps instead of solver
runtime. They are normalized with the first recorded incumbent as the origin,
using `unix_epoch_minus_first_incumbent`. Such a value is explicitly tagged as
an elapsed-time proxy from the first incumbent, not as full solve wall time;
the original timestamp and origin remain preserved.

Derived MILPs inherit the parent fold and are marked train-only. Their
`dataset_eligible`, `label_eligible`, and `scientific_reporting_eligible` flags
remain false. The next gate must independently solve and label each derived
MILP, then build and audit its graph.

## DaSCI-DGX smoke acceptance

Run one original parent with one incumbent in each solver arm. Accept this gate
only when both reports have `gate_status=passed`, no artifact is eligible yet,
the effective objective sense is `MINIMIZE`, every output and provenance file
exists, and both reports expose the same `operator_contract_sha256`.

Do not compare `constraint_sha256` across solvers unless deliberately feeding
the exact same named incumbent to both adapters.
