# Controlled Gurobi expansion after the engineering pilot

## Evidence and scope

The PR53 engineering pilot completed two independent optimizations. Its
artifact hashes and sanitization checks passed on DGX-DaSCI. The medium parent
`CFL_medium_instance_3` reached a relative gap of 0.0831145261 after approximately
28,801 seconds and was admitted. `CFL_hard_instance_0` reached 0.6417458425 and
was not admitted. Both runs were right-censored at the eight-hour optimization
limit. Successful execution does not establish optimality or dataset readiness.

PR54 preserves the 39 previously admitted labels and the newly admitted medium
label, including their original model and solution hashes. It does not alter
the PR53 implementation, receipts, or negative hard-instance evidence. The
campaign contains the twenty remaining medium parents and one additional hard
parent. The other twenty-nine hard parents are explicitly deferred. Previously
admitted parents are never sent to the optimizer by this campaign.

| Phase | Population | Gurobi TimeLimit | Slurm wall limit | Reservation |
| --- | ---: | ---: | ---: | --- |
| Medium | Four batches of five | 28,800 s per parent | 12 h per task | 1 CPU, 64 GiB |
| Additional hard | `CFL_hard_instance_1` | 57,600 s | 24 h | 1 CPU, 64 GiB |

The initial submission runs medium indices 0–4 with concurrency one and the
single hard experiment concurrently. This reserves at most 128 GiB for these
two optimization tasks; other jobs and scheduler association limits may reduce
actual concurrency. Neither a GPU nor reduced memory is requested. Two pilot
measurements are insufficient to size the full population. Subsequent medium
batches are reviewed separately; no entire ninety-parent submission is created.

All optimizations use Gurobi, `MINIMIZE`, seed 42, one thread, a node limit of
1,000,000, and a fresh process without a warm start. Relative gap must be at most
0.10, with independent original-model feasibility, integrality, objective, and
bound checks, before a label is admitted. A censored run above that threshold
is a valid unadmitted outcome, not a technical failure. The observed runtime is
measured, not inferred from unavailable MILPBench runtime metadata.

The hard experiment changes both parent identity and time budget relative to
PR53. It therefore does **not** isolate the causal effect of doubling time.
The previous hard outcome remains in the evidence chain and cost accounting.
All results remain development-only; graph construction and scientific claims
are outside this PR.

## Artifacts and restart behavior

The planner verifies the frozen ninety-parent inventory, forty preserved
labels, PR53 aggregate output hashes, both task receipts, and their artifacts.
It writes a content-bound plan with exact phase, task index, batch, budget,
parent identity, split, and data-relative output path for every task.

Plan artifacts:

- `gurobi_expansion_campaign_plan.json`: authoritative contract and population.
- `preserved_parent_label_index.jsonl`: forty retained labels.
- `medium_tasks.jsonl`: twenty tasks, sorted by numeric instance index.
- `hard_tasks.jsonl`: one additional hard task.

Each task retains the shared Gurobi collection plan and report,
`parent_solution.json.gz`, `incumbents.parquet`,
`incumbent_variable_order.json.gz`, and
`gurobi_expansion_campaign_task_report.json`. Run directories are isolated by
budget, solver, category, and parent. The task receipt binds effective solver
parameters, mathematical checks, and artifact hashes to the campaign contract.

The audit writes:

- `gurobi_expansion_campaign_report.json`;
- `campaign_task_metrics.json`;
- `campaign_runtime_outcomes.csv`;
- `admitted_parent_label_index.jsonl`.

Reports distinguish `not_started`, `incomplete`, `failed`, `invalid_receipt`,
`completed_admitted`, and `completed_unadmitted`. A batch gate requires its five
medium tasks and the additional hard task to be technically valid; it does not
require all six labels to be admissible. Unstarted later batches are not marked
as failed. Any observed technical failure prevents a passed gate.

The four time regions are total worker wall time, data reading, model
construction, and `model.optimize()` wall time. The task wall time also includes
export and independent audit before receipt writing. Reported cumulative
optimization cost covers both PR53 pilot attempts and observed tasks in this
new run root only. Earlier research costs and attempts in other roots are
unknown, not zero. These durations must not be described as proof times when
the optimizer is censored.

A completed, technically valid receipt is reused only after contract and
artifact verification, including when its label is inadmissible. Partial or
failed attempts are retained and cannot silently restart or overwrite data.
Do not change branches or implementations while the campaign is running. A
technical recovery requires inspection and a new run root, not deletion.

## DGX-DaSCI execution

Run these Bash commands on DGX-DaSCI, not on a different cluster. The fixed PR53
timestamp identifies existing evidence; never replace it with the current time.
The new PR54 timestamp is generated once for the new campaign.

### Update and test

```bash
cd /home/vrcelestino/discodatos/cfl-gurobi-gnn
conda activate tfm_env
git fetch origin
git switch feature/gurobi-medium-batches-hard16h
git pull --ff-only origin feature/gurobi-medium-batches-hard16h
git rev-parse HEAD
PYTHONPATH=src python3 -m pytest tests/smoke -q
```

Continue only after tests pass. A local optional SCIP backend limitation is not
a waiver for the existing qualified DGX environment.

### Freeze the new campaign

```bash
export EXEC_DIR="$(pwd -P)"
export DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
export GRB_LICENSE_FILE="${EXEC_DIR}/secrets/gurobi.lic"
export CAMPAIGN_NAME="pr54_$(date -u +%Y%m%dT%H%M%SZ)"
export CAMPAIGN_PLAN_DIR="${DATA_ROOT}/analysis/gurobi_expansion_campaign/${CAMPAIGN_NAME}_plan"
export CAMPAIGN_RUN_ROOT="${DATA_ROOT}/intermediate/gurobi_expansion_campaign/${CAMPAIGN_NAME}"
export CAMPAIGN_AUDIT_DIR="${DATA_ROOT}/analysis/gurobi_expansion_campaign/${CAMPAIGN_NAME}_batch0_audit"
export MEDIUM_BATCH=0

python3 -m cfl_gnn.cli.gurobi_expansion_campaign prepare \
  --data_root "${DATA_ROOT}" \
  --pilot_plan_dir "${DATA_ROOT}/analysis/gurobi_expansion/pr53_20260914T152948Z_plan" \
  --pilot_run_root "${DATA_ROOT}/intermediate/gurobi_expansion/pr53_20260914T152948Z" \
  --pilot_audit_dir "${DATA_ROOT}/analysis/gurobi_expansion/pr53_20260914T152948Z_audit" \
  --campaign_dir "${CAMPAIGN_PLAN_DIR}"

jq -e '
  .preserved_parent_population == 40
  and (.preserved | length) == 40
  and (.tasks | length) == 21
  and ([.tasks[] | select(.phase == "medium")] | length) == 20
  and all(.tasks[] | select(.phase == "medium"); .time_limit_seconds == 28800)
  and ([.tasks[] | select(.phase == "hard")] | length) == 1
  and all(.tasks[] | select(.phase == "hard");
    .source_instance_id == "CFL_hard_instance_1" and .time_limit_seconds == 57600)
  and (.deferred | length) == 29
  and .seed == 42 and .objective_sense == "MINIMIZE"
  and .scientific_reporting_eligible == false
' "${CAMPAIGN_PLAN_DIR}/gurobi_expansion_campaign_plan.json" \
  && echo PR54_PLAN_OK || echo PR54_PLAN_FAILED

printf 'PLAN=%s\nRUNS=%s\nAUDIT=%s\n' \
  "${CAMPAIGN_PLAN_DIR}" "${CAMPAIGN_RUN_ROOT}" "${CAMPAIGN_AUDIT_DIR}"
```

Do not submit after `PR54_PLAN_FAILED`. Keep the printed paths for subsequent
sessions. Plan generation verifies hashes but does not execute the solver.

### Submit only the first medium batch and additional hard

The function uses `return`, not `exit`, so failure does not close an interactive
terminal. If submission partially succeeds, record the printed job ID and do
not call the whole function again: already submitted work must not be duplicated.

```bash
submit_pr54_initial() {
  test -s "${CAMPAIGN_PLAN_DIR}/gurobi_expansion_campaign_plan.json" || return 1
  test -s "${GRB_LICENSE_FILE}" || return 1
  MEDIUM_JOB_ID=$(sbatch --parsable --export=ALL --array=0-4%1 \
    scripts/slurm/dasci/submit_gurobi_medium_batch.sbs) || return 1
  MEDIUM_JOB_ID=${MEDIUM_JOB_ID%%;*}
  export MEDIUM_JOB_ID
  printf 'MEDIUM_JOB_ID=%s\n' "${MEDIUM_JOB_ID}"
  HARD_JOB_ID=$(sbatch --parsable --export=ALL \
    scripts/slurm/dasci/submit_gurobi_hard_16h.sbs) || return 1
  HARD_JOB_ID=${HARD_JOB_ID%%;*}
  export HARD_JOB_ID
  printf 'HARD_JOB_ID=%s\n' "${HARD_JOB_ID}"
  CAMPAIGN_AUDIT_JOB_ID=$(sbatch --parsable --export=ALL \
    --dependency="afterany:${MEDIUM_JOB_ID}:${HARD_JOB_ID}" \
    scripts/slurm/dasci/submit_gurobi_expansion_batch_audit.sbs) || return 1
  CAMPAIGN_AUDIT_JOB_ID=${CAMPAIGN_AUDIT_JOB_ID%%;*}
  export CAMPAIGN_AUDIT_JOB_ID
  printf 'AUDIT_JOB_ID=%s\n' "${CAMPAIGN_AUDIT_JOB_ID}"
}
if submit_pr54_initial; then
  echo PR54_SUBMITTED
else
  echo 'PR54_SUBMISSION_INCOMPLETE: inspect printed IDs before retrying.'
fi
```

`afterany` ensures the audit can retain failure evidence rather than remaining
blocked behind a failed solver task. The first medium batch may require about
forty optimization hours sequentially. The separate hard task may require
sixteen. Queue time, export, and audit overhead are additional.

### Review after completion

```bash
sacct -j "${MEDIUM_JOB_ID},${HARD_JOB_ID},${CAMPAIGN_AUDIT_JOB_ID}" \
  --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS,ReqMem

jq '{gate_status,summary,cost_accounting,eligibility,decision}' \
  "${CAMPAIGN_AUDIT_DIR}/gurobi_expansion_campaign_report.json"

jq '.records[] | select(.state != "not_started") | {
  source_instance_id,phase,time_limit_seconds,state,execution_valid,
  label_eligible,right_censored,reason_code,solve,time_regions,mathematical_audit
}' "${CAMPAIGN_AUDIT_DIR}/campaign_task_metrics.json"

python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path
root = Path(os.environ["CAMPAIGN_AUDIT_DIR"]).resolve()
report = json.loads((root / "gurobi_expansion_campaign_report.json").read_text())
for descriptor in report["outputs"].values():
    path = (root / descriptor["relative_path"]).resolve()
    assert path.is_relative_to(root) and path.is_file(), "Unsafe or missing artifact"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == descriptor["sha256"], path.name
    print(path.name + ": OK")
print("PR54_HASHES_OK")
PY

if grep -RInE '/raid/|/home/|[A-Za-z]:\\|secrets/|gurobi\.lic' \
  "${CAMPAIGN_PLAN_DIR}" "${CAMPAIGN_AUDIT_DIR}" \
  --include='*.json' --include='*.jsonl' --include='*.csv'
then
  echo SANITIZATION_FAILED
else
  status=$?
  if test "${status}" -eq 1; then
    echo SANITIZATION_OK
  else
    echo SANITIZATION_NOT_COMPLETED
  fi
fi
```

Review first-batch outcomes before launching further batches. Preserve every
attempt, including an inadmissible hard result. No new graph or training run is
authorized by a passed execution audit alone.

| Medium batch | Array indices (concurrency one) | Audit `--batch` |
| --- | --- | ---: |
| First | `0-4%1` | 0 |
| Second | `5-9%1` | 1 |
| Third | `10-14%1` | 2 |
| Fourth | `15-19%1` | 3 |

Later batches reuse the same immutable plan and run root, update `MEDIUM_BATCH`,
and use a new `CAMPAIGN_AUDIT_DIR`. They do not resubmit the completed hard task.
Each audit revalidates the hard receipt and all observed task evidence. The
maximum number of admitted parents in this campaign is 61, not 90.
