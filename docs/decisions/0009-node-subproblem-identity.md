# ADR 0009: identify SCIP node MIPs relative to a root MIP baseline

## Status

Validated mechanically on one real easy-CFL instance; scientific dataset
eligibility remains unresolved by this ADR.

## Context

The PySCIPOpt prototype established that `writeMIP()` can produce readable
node-local MILPs whose branching bounds survive a fresh-process round trip.
The first CFL smoke also showed that rows, columns, nonzeros, and file size can
remain unchanged across nodes. Those dimensions therefore cannot establish
that two serialized node MIPs are the same formulation.

The research question is narrower than dataset construction: do node-local
domains, objective data, or the constraint matrix produce formulations that
are semantically distinct from the MIP written at the root?

## Decision

Every probe must serialize a root `writeMIP()` baseline after the root LP is
solved. A node candidate is compared with that baseline using independent,
canonical SHA-256 fingerprints for:

- the constraint matrix and row sides;
- objective sense and coefficients;
- variable types and bounds;
- the combination of those three components.

Rows, columns, and nonzeros are reported as dimensional deltas, not as an
identity key. File SHA-256 distinguishes serialized artifacts, while the
formulation fingerprint distinguishes their mathematical content.

The report classifies a mechanically valid node MIP as one of:

- `identical_to_root`;
- `domain_distinct_same_matrix`;
- `objective_distinct_only`;
- `objective_and_domain_distinct`;
- `matrix_distinct_domain_unchanged`;
- `matrix_and_domain_distinct`.

`writeProblem(trans=True)` remains a diagnostic control and never qualifies as
a node-MIP candidate. It can be disabled after the comparison has been
replicated, reducing storage without changing the `writeMIP()` gate.

## Scientific boundary

Passing this audit means only that a readable node MIP is mechanically valid
and distinct from the root baseline. It does not prove exact reconstruction of
the complete SCIP search state, independence among samples, or suitability as
a training instance. Accordingly:

- `exact_node_subproblem_proven` remains `false`;
- `dataset_eligible` remains `false`;
- no graph builder, trainer, evaluator, canonical split, or Gurobi collector is
  changed;
- Pyomo remains excluded.

## Acceptance gate

The gate passes only when a root baseline passes its fresh-process mechanical
checks and at least one `writeMIP()` node candidate both passes its mechanical
checks and has a distinct formulation fingerprint. The report must also expose
artifact/formulation duplicates, dimensional deltas, materialization classes,
and measured/projected storage.

## DaSCI validation result

The bounded easy-CFL run passed the schema-v3 gate. The root MIP and all four
sampled node MIPs were readable and mechanically valid. All four node MIPs were
unique formulations classified as `domain_distinct_same_matrix`: their local
domains differed from the root, while rows, columns, nonzeros, matrix, and
objective remained unchanged. The transformed-problem artifacts were readable
controls but failed the node-candidate mechanical gate.

This validates the identity instrumentation. It does not make the artifacts
independent MILP instances. ADR 0010 defines their admissible interpretation.
