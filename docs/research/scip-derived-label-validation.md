# Independent label validation for SCIP-derived MIPs

## Question

Can every graph-observable, domain-restricted node MIP produce its own valid
optimal label without consuming the parent instance's incumbent?

## Scope

This audit accepts exactly the root and node artifacts approved by the upstream
graph-observability report. It verifies their names and SHA-256 values before
solving. Every node MIP is then loaded and optimized by a fresh Python process
and a fresh PySCIPOpt model. Candidate processes may run concurrently, but each
SCIP model remains single-threaded. Completed worker artifacts are reusable
only when their schema, contract hash, candidate name, and candidate hash all
match the current run.

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

The schema-v3 worker reconstructs its incumbent sequence only after
`optimize()` from the solutions retained by SCIP, using `getSols()`,
`getSolTime()`, and `getSolObjVal()`. It sorts those observations by discovery
time, retains strict objective improvements, and fails closed unless times are
monotonic, objectives improve monotonically, and the final trace entry matches
the best solution and its discovery time. This avoids reading stale global
primal-bound state inside a `BESTSOLFOUND` callback.

## Outcome semantics

Execution success and scientific eligibility are independent dimensions:

- `passed`: every candidate has an independently proven optimal label;
- `inconclusive`: every candidate has valid feasible solution evidence, but at
  least one stopped before proving optimality;
- `failed`: a contract, independence, domain, feasibility, or integrity check
  failed, or no valid solution evidence was produced.

An inconclusive run exits successfully because the experiment completed and
wrote valid evidence. Its solutions remain `label_eligible=false`. Only an
execution or integrity failure produces a failing process exit.

## Performance feature tags

MIP gap and execution time are first-class experimental features. The schema
stores both the machine-readable tag vocabulary and its values:

- instance: `execution_time_seconds`, `mip_gap_relative`, and
  `mip_gap_percent`;
- incumbent: `incumbent_objective`, `incumbent_discovery_time_seconds`,
  `incumbent_mip_gap_relative_at_discovery`, and
  `incumbent_mip_gap_percent_at_discovery`.

The relative terminal gap is the raw SCIP ratio; the percent field is exactly
one hundred times that ratio. PySCIPOpt reliably exposes each retained
incumbent's objective and discovery time after the solve, but it does not
reliably expose the contemporaneous dual bound needed to reconstruct the MIP
gap at discovery. Consequently, schema v3 records both incumbent gap fields as
`null` and tags their availability as
`not_reliably_exposed_by_pyscipopt`. The terminal instance gap remains observed
and valid.

These canonical names are solver-neutral. When the Gurobi instance and
incumbent collectors are reviewed, their native callback fields must be mapped
to this same vocabulary rather than introducing parallel names. Solver-native
names and units may be retained as provenance, but not as the canonical feature
tags. In particular, the incumbent gap-at-discovery tags remain reserved for a
future Gurobi collector that can populate them from coherent callback state.

## Eligibility boundary

A passed gate makes the tested solution artifacts label-eligible. It does not
make the variants dataset-eligible or scientifically reportable. Dataset
eligibility remains false until a later contract defines parent grouping,
sampling, deduplication, split inheritance, and leakage prevention.

Pyomo remains excluded. The only SCIP Python interface is PySCIPOpt.
