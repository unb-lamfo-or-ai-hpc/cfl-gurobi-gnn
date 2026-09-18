#!/bin/bash
# Invoke with bash in a separate pinned worktree; do not update the active checkout.
set -Eeuo pipefail
trap 'code=$?; echo "[ERROR] queue stopped at line $LINENO (exit $code); inspect submission.txt before retrying" >&2; exit "$code"' ERR
: "${EXEC_DIR:?Set pinned worktree root}"
: "${DATA_ROOT:?}"
: "${CAMPAIGN_PLAN_DIR:?}"
: "${CAMPAIGN_RUN_ROOT:?}"
: "${REVIEWED_PREFLIGHT:?Set the accepted first-batch preflight JSON path}"
: "${PREDECESSOR_AUDIT_DIR:?Set audit3369 output directory}"
: "${PREDECESSOR_AUDIT_JOB:?Set audit3369 job ID}"
: "${PR57_QUEUE_COMMIT:?Set exact queue commit}"
: "${MEDIUM_QUEUE_DIR:?Set a new queue directory}"
: "${GRB_LICENSE_FILE:?Set original checkout license path}"
cd "${EXEC_DIR}"
ACTUAL_COMMIT=$(git rev-parse HEAD)
if [[ "${ACTUAL_COMMIT}" != "${PR57_QUEUE_COMMIT}" ]]; then
    echo "[ERROR] SOURCE_COMMIT_MISMATCH: expected=${PR57_QUEUE_COMMIT} actual=${ACTUAL_COMMIT}" >&2
    exit 2
fi
DIRTY=$(git status --porcelain --untracked-files=no)
if [[ -n "${DIRTY}" ]]; then
    printf '[ERROR] DIRTY_TRACKED_FILES: no files were reverted; no new jobs submitted.\n%s\n' "${DIRTY}" >&2
    exit 2
fi
echo "[INFO] PR57_QUEUE_CHECKOUT_OK | commit=${ACTUAL_COMMIT}"
for command in flock sbatch scontrol jq conda; do command -v "${command}" >/dev/null; done
test -s "${GRB_LICENSE_FILE}"
[[ "${PREDECESSOR_AUDIT_JOB}" =~ ^[0-9]+$ ]]
# Fail if the predecessor is unknown; the runtime gate also verifies its artifacts.
scontrol show job "${PREDECESSOR_AUDIT_JOB}" >/dev/null
exec 9>"${CAMPAIGN_RUN_ROOT}/.pr57-medium-submission.lock"
flock -n 9
# Fixed marker across timestamps prevents accidental duplicate chains.
MARKER="${CAMPAIGN_RUN_ROOT}/.pr57-remaining-medium-queue"
if [[ -e "${MARKER}" ]]; then
    echo "[ERROR] remaining queue already reserved; inspect its submission record" >&2
    exit 2
fi
eval "$(conda shell.bash hook)"
conda activate "${CONDA_ENV:-tfm_env}"
export PYTHONPATH="${EXEC_DIR}/src"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c 'import gurobipy, pyarrow, scipy, numpy'
python3 -m cfl_gnn.cli.remaining_medium_queue prepare \
    --data_root "${DATA_ROOT}" --campaign_dir "${CAMPAIGN_PLAN_DIR}" \
    --run_root "${CAMPAIGN_RUN_ROOT}" --reviewed_preflight "${REVIEWED_PREFLIGHT}" \
    --predecessor_audit_dir "${PREDECESSOR_AUDIT_DIR}" --output_dir "${MEDIUM_QUEUE_DIR}"
PLAN="${MEDIUM_QUEUE_DIR}/remaining_medium_queue_plan.json"
WORKER=scripts/slurm/dasci/submit_remaining_medium_task.sbs
AUDITOR=scripts/slurm/dasci/submit_gurobi_expansion_batch_audit.sbs
WORKER_ARGS=(--partition=batch --nodes=1 --cpus-per-task=1 --mem=64G --time=12:00:00 --job-name=cfl_medium8h --kill-on-invalid-dep=yes)
AUDIT_ARGS=(--partition=batch --nodes=1 --cpus-per-task=1 --mem=4G --time=00:30:00)
sbatch --test-only "${WORKER_ARGS[@]}" --array=10-14%1 --export=ALL "${WORKER}"
sbatch --test-only "${AUDIT_ARGS[@]}" --export=ALL "${AUDITOR}"
mkdir "${MARKER}"
printf 'QUEUE=%s\nCOMMIT=%s\nPREDECESSOR_AUDIT_JOB=%s\n' \
    "${MEDIUM_QUEUE_DIR}" "${PR57_QUEUE_COMMIT}" "${PREDECESSOR_AUDIT_JOB}" \
    | tee "${MARKER}/submission.txt" "${MEDIUM_QUEUE_DIR}/submission.txt"
DEPENDENCY="${PREDECESSOR_AUDIT_JOB}"
for BATCH in 2 3; do
    ARRAY=$(jq -er --argjson batch "${BATCH}" '[.tasks[] | select(.batch_index==$batch) | .task_index | tostring] | join(",") + "%1"' "${PLAN}")
    RELATIVE_AUDIT=$(jq -er --arg batch "${BATCH}" '.audit_dirs[$batch]' "${PLAN}")
    export MEDIUM_BATCH="${BATCH}" CAMPAIGN_AUDIT_DIR="${DATA_ROOT}/${RELATIVE_AUDIT}"
    MEDIUM_JOB=$(sbatch --parsable "${WORKER_ARGS[@]}" --array="${ARRAY}" --dependency="afterok:${DEPENDENCY}" --export=ALL "${WORKER}")
    MEDIUM_JOB=${MEDIUM_JOB%%;*}
    [[ "${MEDIUM_JOB}" =~ ^[0-9]+$ ]]
    printf 'BATCH_%s_MEDIUM_JOB=%s\nBATCH_%s_AUDIT_DIR=%s\n' "${BATCH}" "${MEDIUM_JOB}" "${BATCH}" "${CAMPAIGN_AUDIT_DIR}" \
        | tee -a "${MARKER}/submission.txt" "${MEDIUM_QUEUE_DIR}/submission.txt"
    AUDIT_JOB=$(sbatch --parsable "${AUDIT_ARGS[@]}" --dependency="afterany:${MEDIUM_JOB}" --export=ALL "${AUDITOR}")
    AUDIT_JOB=${AUDIT_JOB%%;*}
    [[ "${AUDIT_JOB}" =~ ^[0-9]+$ ]]
    printf 'BATCH_%s_AUDIT_JOB=%s\n' "${BATCH}" "${AUDIT_JOB}" \
        | tee -a "${MARKER}/submission.txt" "${MEDIUM_QUEUE_DIR}/submission.txt"
    DEPENDENCY="${AUDIT_JOB}"
done
echo "PR57_REMAINING_QUEUE_SUBMITTED"
