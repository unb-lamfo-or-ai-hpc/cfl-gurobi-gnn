# Independent label validation for SCIP-derived MIPs

## Question

Can every graph-observable, domain-restricted node MIP produce its own valid
optimal label without consuming the parent instance's incumbent?

## Scope

This audit accepts exactly the root and node artifacts approved by the upstream
graph-observability report. It verifies their names and SHA-256 values before
solving. Every node MIP is then loaded and optimized by a fresh Python process
and a fresh PySCIPOpt model.

No warm start, parent incumbent, solution pool, or Gurobi artifact is supplied.
The root artifact is inspected only to recover canonical domains and types; it
is not solved and its solution is never passed to a candidate.

## Required invariants

For a candidate label to be eligible:

- the upstream graph-observability gate passed for the exact same artifacts;
- the fresh model has zero solutions before `optimize()`;
- the objective sense is minimization;
- SCIP terminates with `optimal` status and a gap within tolerance;
- SCIP's complete feasibility check accepts the best solution;
- the solution vector contains exactly the root variables;
- the candidate domains are subsets of the root domains and include at least
  one strict restriction;
- every discrete value is integral and every value respects candidate bounds;
- the reported objective and the best-solution objective agree.

SCIP `writeMIP()` may serialize original binary variables as bounded integers.
The audit therefore recovers a canonical binary type when the root variable is
integral with bounds contained in `[0, 1]`, then requires candidate integrality
and domain compatibility. This normalization is explicit in the contract and
solution artifact.

## Outputs

- `scip_derived_label_audit_plan.json`;
- `scip_derived_label_validation_report.json`;
- `per_candidate_label_audit.jsonl`;
- one compressed, named solution vector per candidate under
  `candidate_solutions/`.

Reports contain only file names and hashes, never absolute source paths.

## Eligibility boundary

A passed gate makes the tested solution artifacts label-eligible. It does not
make the variants dataset-eligible or scientifically reportable. Dataset
eligibility remains false until a later contract defines parent grouping,
sampling, deduplication, split inheritance, and leakage prevention.

Pyomo remains excluded. The only SCIP Python interface is PySCIPOpt.
