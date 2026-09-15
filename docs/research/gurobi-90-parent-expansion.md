# Gurobi-only expansion of the CFL parent population

## Scope and scientific boundary

The approved development cohort contains 39 admitted original parents (30 easy
and nine medium). The target inventory contains 90 parents. Consequently,
51 parents remain pending: 21 medium and 30 hard. An original LP file being
available is not equivalent to an independently validated training label.

No per-instance solver runtime was recovered from the inspected MILPBench
feature files or the three original distribution archives. The campaign must
therefore measure runtime, rather than present a guessed runtime as a feature
provided by MILPBench. The eight-hour budget is an empirical experiment; it does
not guarantee a gap below 10%. The previous four-hour failures do not establish
mathematical infeasibility.

This pilot always forces `MINIMIZE`, retains the original objective sense in
provenance, uses Gurobi only, and does not modify the SCIP backend's existing
minimization policy. It does not concern the separate NPAD hub-location project.

## Four-sprint delivery plan

| Sprint | Deliverable | Exit evidence | Indicative active effort |
| --- | --- | --- | --- |
| 1: eight-hour pilot | Frozen inventory, preservation of 39 labels, sequential medium/hard Gurobi tasks, independent final-vector audit and runtime receipts | Two technically audited attempts, measured memory and wall time, explicit admission or non-admission | 1–2 working days plus queues and up to 16 solver-hours |
| 2: pending-parent campaign | Expand task manifests to the remaining parents after resource review; isolate every retry; record missingness and cumulative observed costs | A disposition for every one of the 90 parents; no forced admission of unresolved parents | 2–3 working days plus the dominant HPC execution time |
| 3: graph and dataset consolidation | Gurobi-authoritative root-relaxation graphs for admitted originals; preserve parent folds; descriptive instance/graph outputs; curate Zenodo packages | Hash-valid model/label/graph lineage, reproducible manifests, dataset rights and archive review | 2–3 working days after admitted artifacts are available |
| 4: extended experiments and manuscript | Repeat matched-cohort GNN experiments and evaluation, report full training/validation curves and solver outcomes; extend the manuscript and data statement | Reproducible tables/figures, explicit exclusions and censoring, co-author review | 3–5 working days plus training and solver execution |

These are planning estimates, not a promised completion date. At eight hours
each, 51 pending parents represent at most 408 nominal solver-hours for one
attempt per parent (excluding parsing, audit, queues and retries). Later
parallelism must respect measured peak memory, association limits and license
capacity. The first pilot requests one CPU and 64 GiB per task and runs serially.
No GPUs are requested. Its Slurm allowance is 12 hours per task in `batch`.

The current PR implements Sprint 1 only. The CLI intentionally cannot submit or
execute all 51 pending parents. `CFL_medium_instance_3` is a previously rejected
medium parent; `CFL_hard_instance_0` is the first hard pilot. Selection is frozen
before observing the new results, not based on which instance converges fastest.

## Runtime, admission and preservation

- Each pilot starts a fresh Gurobi process without a warm start: seed 42,
  `TimeLimit=28800`, `NodeLimit=1000000`, one thread, default solver profile.
  The node limit remains an independent stopping condition and is reported.
- Admission requires the named final solution to pass an independent original
  matrix/domain/integrality/objective audit, consistent minimization bounds and
  gap, valid collection provenance, and relative MIP gap at most 0.10.
- A technically valid time-limited attempt may be inadmissible. A time limit
  without a feasible solution does not imply infeasibility. A technical failure
  is never converted to a successful label receipt.
- Primary recorded outcomes are terminal relative MIP gap and the external wall
  time around `model.optimize()`. Incumbents retain their original discovery
  times and gap snapshots in the parent solution and Parquet stream.
- Four time regions retain the shared kernel's explicit semantics: worker total
  through outcome extraction; input identity/hash reading; model parsing,
  configuration and callback assembly; and optimization only. In particular,
  model-file parsing belongs to the assembly region. The worker total excludes
  final solution serialization. A separate `task_wall_time_seconds` includes
  collection, exports and independent audit, ending before receipt writing.
  Slurm elapsed time and MaxRSS are separate scheduler measurements.
- Incumbent snapshots alone do not locate the exact first time a gap threshold
  was crossed through dual-bound improvement. This PR makes no exact
  time-to-gap claim. A subsequent instrumentation extension may sample bound
  progress with explicit sampling/censoring semantics.
- Gap and runtime fields are post-solve dataset metadata, not automatically GNN
  input features. Unknown historical accumulated runtime is `null`, never zero.
  Retry cost accounting must retain earlier attempts, not replace their timings.
- The old cohort, graphs, raw inputs and source reports remain read-only.
  New output directories are mandatory. A hash-valid completed attempt can be
  reused without resolving, even when its terminal gap remains above policy.
  Failed/partial attempts are retained; a reviewed retry requires a new run root.

## Artifact contract

All portable manifests use paths relative to an explicitly supplied data or run
root. No pickle deserialization is needed by the planner.

| Location | Outputs |
| --- | --- |
| New plan directory | `gurobi_expansion_plan.json`: all 90 source descriptors, 39 preserved label/report descriptors, 51 pending dispositions, two pilot tasks, implementation hashes and frozen budget |
| Each successful collection directory | `gurobi_parent_solve_plan.json`, `gurobi_parent_solve_report.json`, `parent_solution.json.gz`, `incumbents.parquet`, `incumbent_variable_order.json.gz` |
| Each finished task wrapper | `gurobi_expansion_task_report.json`: checksummed receipt, collection hashes, independent mathematical audit, eligibility, censoring, four times and task overhead |
| New aggregate audit directory | `gurobi_expansion_audit_report.json`, `pilot_task_metrics.json`, `pilot_runtime_outcomes.csv` |
| Slurm submission directory | `slurm_cfl_90_pilot_<array>_<task>.out`, `slurm_cfl_90_audit_<job>.out` |

An interrupted process may leave only partial local artifacts. The aggregate
reports missing or invalid receipts without deleting these files. A passed
aggregate means both pilot executions are auditable, **not** that both labels
are admissible or that the 90-parent dataset is complete. All new reports keep
dataset/scientific reporting eligibility disabled at this stage.

## DGX-DaSCI execution

Run the following in the Linux shell on `dgx-dasci`, not on an NPAD service node
or in local Windows PowerShell. Preserve unrelated working-tree changes before
switching branches. Do not copy JSON filenames into variables ending in `_DIR`.

### Update and test

```bash
cd /home/vrcelestino/discodatos/cfl-gurobi-gnn
conda activate tfm_env
git status --short
git fetch origin
git switch feature/gurobi-90-parent-runtime-campaign
git pull --ff-only origin feature/gurobi-90-parent-runtime-campaign
git rev-parse HEAD
PYTHONPATH=src python3 -m pytest tests/smoke -q
```

Do not continue if the checkout or tests fail. No solver jobs are launched by
the following planner, which also validates all 90 source file hashes.

### Prepare the immutable plan

```bash
export EXEC_DIR="$(pwd -P)"
export DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
export SOURCE_CAMPAIGN_DIR="${DATA_ROOT}/analysis/confirmation_execution/pr50_20260912T121753Z"
export REVISION_DIR="${DATA_ROOT}/analysis/confirmation_revision/pr50_39_20260913T135218Z"
export EXPANSION_NAME="pr53_$(date -u +%Y%m%dT%H%M%SZ)"
export EXPANSION_PLAN_DIR="${DATA_ROOT}/analysis/gurobi_expansion/${EXPANSION_NAME}_plan"
export EXPANSION_RUN_ROOT="${DATA_ROOT}/intermediate/gurobi_expansion/${EXPANSION_NAME}"
export EXPANSION_AUDIT_DIR="${DATA_ROOT}/analysis/gurobi_expansion/${EXPANSION_NAME}_audit"
export GRB_LICENSE_FILE="${EXEC_DIR}/secrets/gurobi.lic"
export PYTHONPATH="${EXEC_DIR}/src:${PYTHONPATH:-}"

python3 -m cfl_gnn.cli.gurobi_expansion prepare \
  --data_root "${DATA_ROOT}" \
  --source_campaign_dir "${SOURCE_CAMPAIGN_DIR}" \
  --revision_dir "${REVISION_DIR}" \
  --campaign_dir "${EXPANSION_PLAN_DIR}"

jq -e '
  .planned_parent_population == 90
  and (.preserved | length) == 39
  and ([.inventory[] | select(.disposition == "pending")] | length) == 51
  and (.tasks | length) == 2
  and .time_limit_seconds == 28800
  and .objective_sense == "MINIMIZE"
  and .solver == "gurobi"
  and .seed == 42
' "${EXPANSION_PLAN_DIR}/gurobi_expansion_plan.json" \
  && echo PR53_PLAN_OK || echo PR53_PLAN_FAILED
```

Stop before submission unless this returns `PR53_PLAN_OK`. An old campaign
implementation mismatch must be investigated; never edit an old recorded hash
to bypass it. Preserve this shell session and the printed plan directory for
later recovery.

### Submit two sequential tasks and an audit

The function uses `return`, not `exit`, so preflight failure does not close the
interactive terminal. `afterany` allows the aggregate audit to report technical
failures as well as successful tasks. Do not repeatedly run the submission
function while its first submission is pending or running.

```bash
submit_cfl_expansion_pilot() {
  test -s "${EXPANSION_PLAN_DIR}/gurobi_expansion_plan.json" || return 1
  test -s "${GRB_LICENSE_FILE}" || return 1
  python3 -c 'import gurobipy, pyarrow, scipy, numpy' || return 1
  EXPANSION_ARRAY_JOB=$(sbatch --parsable --array=0-1%1 --export=ALL \
    scripts/slurm/dasci/submit_gurobi_expansion_pilot.sbs) || return 1
  EXPANSION_ARRAY_JOB=${EXPANSION_ARRAY_JOB%%;*}
  export EXPANSION_ARRAY_JOB
  echo "EXPANSION_ARRAY_JOB=${EXPANSION_ARRAY_JOB}"
  EXPANSION_AUDIT_JOB=$(sbatch --parsable \
    --dependency="afterany:${EXPANSION_ARRAY_JOB}" --export=ALL \
    scripts/slurm/dasci/submit_gurobi_expansion_audit.sbs) || return 1
  EXPANSION_AUDIT_JOB=${EXPANSION_AUDIT_JOB%%;*}
  export EXPANSION_AUDIT_JOB
  printf 'EXPANSION_AUDIT_JOB=%s\nPLAN=%s\nRUNS=%s\nAUDIT=%s\n' \
    "${EXPANSION_AUDIT_JOB}" "${EXPANSION_PLAN_DIR}" \
    "${EXPANSION_RUN_ROOT}" "${EXPANSION_AUDIT_DIR}"
}
submit_cfl_expansion_pilot
```

If only the audit submission fails, submit that audit separately with the
printed array ID; do not submit the solver array again. If account limits reject
64 GiB/12 hours, retain the scheduler message and review the actual DGX limits;
do not substitute a QoS from another cluster.

### Return pilot evidence

```bash
sacct -j "${EXPANSION_ARRAY_JOB},${EXPANSION_AUDIT_JOB}" \
  --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS,ReqMem

jq '{gate_status,summary,eligibility,decision,outputs}' \
  "${EXPANSION_AUDIT_DIR}/gurobi_expansion_audit_report.json"

jq '.records[] | {source_instance_id,execution_valid,label_eligible,
  reason_code,right_censored,solve,time_regions,task_wall_time_seconds,
  mathematical_audit,error_type}' \
  "${EXPANSION_AUDIT_DIR}/pilot_task_metrics.json"
```

Return these outputs and any failing task log after reviewing the logs for
private paths and license information. Do not commit binary data, license files
or raw runtime logs with `git add -f`.

## Zenodo curation and subsequent experiments

The existing CFL Zenodo draft is a separate, unpublished deposit. A later
sprint will index, deduplicate by content hash and package the relevant
`data/intermediate` and `data/bipartite_graphs` artifacts, excluding obsolete or
regenerable copies only after review. The approximately 161 GiB graph directory
must not be treated as a ready-to-upload archive. Review deposition limits,
upstream data redistribution rights and package selection before uploading.
The repository's MIT code license does not automatically relicense third-party
MILPBench source data. No upload, publication, deletion or DOI claim is made by
this PR.

Once label and graph inventories are audited, repeat the frozen parent-grouped
training/validation/test protocol. Synthetic samples remain train-only and
inherit their parent fold. A later SCIP comparison must use explicitly matched
cohorts and budgets; these two Gurobi pilot attempts do not supply that comparison.
Runtime and gap results, unresolved parents, selection effects and censoring
must all remain visible in the extended manuscript.
