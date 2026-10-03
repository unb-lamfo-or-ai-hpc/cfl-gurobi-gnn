# ADR 0011: precommit a controlled SCIP convergence experiment

## Status

Proposed for methodological review. This ADR does not authorize implementation,
dataset construction, or solver-profile selection.

## Context

The schema-v3 independent label audit validated four domain-restricted MIPs
from one easy-CFL parent. Every candidate produced a fresh, feasible solution
without a warm start or parent incumbent, and every post-solve incumbent trace
passed its consistency checks. None proved optimality within 3600 seconds.
Terminal relative MIP gaps ranged from approximately 4.52% to 5.61%.

These runs establish feasible independent solution evidence but not eligible
labels. Repeating only the default configuration with a larger time limit would
consume substantial compute without identifying whether progress is limited by
primal-solution quality or dual-bound improvement. A controlled solver-profile
experiment is therefore the next admissible gate.

## Decision

Run a paired, development-only comparison of three documented SCIP emphasis
profiles:

| Profile id | PySCIPOpt configuration | Experimental purpose |
|---|---|---|
| `default` | no emphasis override | locked control matching the PR #21 solve |
| `feasibility` | `setEmphasis(SCIP_PARAMEMPHASIS.FEASIBILITY)` | test faster or better primal incumbents |
| `optimality` | `setEmphasis(SCIP_PARAMEMPHASIS.OPTIMALITY)` | test faster dual-bound closure and proof |

No individual SCIP parameter may be tuned inside this experiment. The applied
parameter map and SCIP/PySCIPOpt versions must be persisted for every run so
the broad emphasis profiles are auditable and version-bound.

## Experimental unit and dependence

The execution unit is
`(parent_instance_id, candidate_formulation_sha256, profile_id, seed)`.
Comparisons are paired by candidate and seed. Sibling variants from one parent
are dependent observations and must not be treated as an increased independent
sample size.

The first implementation smoke may reuse the four PR #20/#21 candidates and
seed 42. It is an engineering validation only. Any profile comparison intended
to guide the research pipeline requires a precommitted replication set covering
multiple parent instances and every available difficulty, with repeated seeds.
Inference and uncertainty must be clustered by parent.

## Locked controls

Every profile receives the same:

- exact root, candidate, and upstream-report hashes;
- minimization objective sense;
- fresh Python process and fresh PySCIPOpt model;
- zero pre-solve solutions;
- one SCIP thread;
- wall-clock, node, and memory budgets;
- random seed;
- hardware allocation class;
- solution, domain, feasibility, and incumbent-trace checks from schema v3.

Warm starts, parent incumbents, solution pools from another run, Gurobi
artifacts, adaptive per-candidate time limits, and post-hoc parameter changes
are prohibited. Profile execution order must be recorded. Concurrent jobs must
not oversubscribe the allocated CPUs or memory.

## Endpoints

The co-primary metrics remain:

1. terminal relative MIP gap at the common time budget;
2. execution time to independently proven optimality, right-censored at the
   common time limit when optimality is not proven.

The comparison must also retain terminal primal objective and dual bound to
explain the gap, plus best-incumbent objective and discovery time from the
schema-v3 post-solve reconstruction. Incumbent gap at discovery remains `null`
for PySCIPOpt with availability
`not_reliably_exposed_by_pyscipopt`.

For fixed-time runs that all time out, execution time alone is not a ranking
signal; terminal gap is the informative co-primary endpoint. Runtime
comparisons apply only to solved runs or to a later, separately precommitted
time-to-target-gap analysis.

## Analysis and decision rules

The implementation must report, without silently combining endpoints:

- optimality count by profile;
- paired terminal-gap differences and ratios versus `default`;
- execution time for solved runs and censoring indicators otherwise;
- paired primal-objective and dual-bound changes;
- incumbent discovery-time changes;
- failures and invalid runs by explicit reason code.

The four-candidate smoke cannot select a winning profile. Its gate passes only
when all profile/candidate runs complete or are correctly censored, all
independence and integrity checks pass, and the paired comparison is reproduced
from path-sanitized artifacts.

A profile may be selected for later label generation only after the replicated,
parent-grouped experiment is reviewed. Selection must prioritize independently
proven optimal labels; otherwise it must use the precommitted paired terminal-gap
criterion and retain the result as development evidence, not as label validity.

## Required artifacts for the implementation PR

- a contract JSON binding candidate, upstream-report, profile, parameter-map,
  version, seed, and resource hashes/values;
- one immutable result per candidate/profile/seed;
- a long-form paired-results table;
- a sanitized comparison report;
- Slurm launchers that enforce the declared CPU and memory limits;
- smoke tests for deterministic planning, profile isolation, censoring,
  resumption, and fail-closed integrity checks.

## Eligibility boundary

This experiment never makes a feasible nonoptimal solution a label. For each
run, `label_eligible=true` still requires all schema-v3 label checks and
independently proven optimality. At the experiment level:

- `dataset_eligible=false`;
- `scientific_reporting_eligible=false` for the one-parent smoke;
- canonical parent folds, graph builders, trainers, evaluators, and Gurobi
  collectors remain unchanged;
- Pyomo remains excluded.

Only after this convergence gate yields an approved label policy may work
resume on ADR 0010 gates for parent-grouped splitting, deduplication, sampling,
weighting, and multi-parent replication.

## Planned sequence

1. Review and merge this design-only ADR.
2. Implement an isolated profile-runner and comparison audit.
3. Run a short four-candidate engineering smoke.
4. Run the equal-budget 3600-second pilot only if the smoke passes.
5. Decide whether to stop, expand parent-grouped replication, or approve one
   profile for further independent label generation.

## References

- [PySCIPOpt parameter settings and solver emphasis](https://pyscipopt.readthedocs.io/en/v6.2.0/tutorials/model.html)
- [SCIP parameter and emphasis guidance](https://www.scipopt.org/doc/html/FAQ.php)

