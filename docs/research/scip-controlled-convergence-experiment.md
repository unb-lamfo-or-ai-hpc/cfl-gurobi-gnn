# Controlled SCIP convergence experiment

## Purpose

This implementation operationalizes ADR 0011. It compares the precommitted
`default`, `feasibility`, and `optimality` SCIP emphasis profiles under equal
resource limits. It does not tune individual parameters or select a profile.

## Inputs

The runner requires the exact root and node MIPs accepted by the graph audit,
the passed graph-audit report, and both the plan and report from a completed
schema-v3 independent-label run. Names, SHA-256 values, and upstream contract
hashes are validated before execution.

Every `(candidate, profile, seed)` combination runs in a fresh Python process
and fresh PySCIPOpt model. The emphasis profile is applied before the locked
time, node, thread, seed, and display controls. Each worker persists the full
effective SCIP parameter map, its SHA-256 fingerprint, and the SCIP and
PySCIPOpt versions.

## Outputs

- `scip_convergence_experiment_plan.json`;
- `scip_convergence_experiment_report.json`;
- `per_profile_candidate_metrics.jsonl`;
- `paired_profile_comparison.jsonl`;
- compressed solution and provenance artifacts under `profile_solutions/`.

The paired table always uses `default` as the control. Negative terminal-gap
differences favor the treatment profile. Execution time to optimality is `null`
when either paired run is right-censored.

## Gate semantics

The experiment gate is an engineering gate. It passes when every planned run
completes with independently valid feasible evidence or a valid optimal label,
parameter fingerprints are intact, and each profile has one consistent
effective parameter map across candidates.

An individual run may be `inconclusive` because its time limit expired with a
feasible solution. This does not fail the engineering experiment and does not
make the solution a label. Individual `label_eligible=true` still requires the
complete schema-v3 optimality contract.

The report always records:

- `profile_selection_eligible=false`;
- `dataset_eligible=false`;
- `scientific_reporting_eligible=false`.

The one-parent smoke cannot select a solver profile or support an inferential
claim.

## DaSCI stages

Use the same launcher for both stages. The first run must use
`EXPERIMENT_STAGE=engineering_smoke` and `TIME_LIMIT=300`. It schedules twelve
runs (three profiles by four candidates) with at most four concurrent,
single-threaded SCIP processes.

Only after reviewing a passed smoke may the pilot use
`EXPERIMENT_STAGE=equal_budget_pilot` and `TIME_LIMIT=3600`. With four workers,
the twelve one-hour runs require approximately three hours plus overhead.

The implementation does not alter graph construction, parent folds, training,
evaluation, Gurobi collectors, or any dataset. Pyomo remains excluded.
