#!/bin/bash
# Run with bash, never source: failure must not terminate an interactive shell.
set -Eeuo pipefail
# Report the location, not BASH_COMMAND: commands may contain private values.
trap 'code=$?; printf "[ERROR] continuation stopped at line %s (exit %s); inspect prior messages and any submission record before retrying.\n" "$LINENO" "$code" >&2; exit "$code"' ERR
: "${EXEC_DIR:?Set EXEC_DIR to the repository root}"
: "${DATA_ROOT:?Set DATA_ROOT}"
: "${CAMPAIGN_PLAN_DIR:?Set the existing PR54 plan directory}"
: "${CAMPAIGN_RUN_ROOT:?Set the existing PR54 run root}"
: "${RECONCILIATION_DIR:?Set the passed PR57 reconciliation directory}"
: "${PR57_EXPECTED_COMMIT:?Set the reviewed source commit}"
cd "${EXEC_DIR}"
ACTUAL_COMMIT=$(git rev-parse HEAD)
if [[ "${ACTUAL_COMMIT}" != "${PR57_EXPECTED_COMMIT}" ]]; then
    echo "[ERROR] SOURCE_COMMIT_MISMATCH: expected=${PR57_EXPECTED_COMMIT} actual=${ACTUAL_COMMIT}" >&2
    exit 2
fi
# This one manuscript-only file is not an input to the collection contract.
# Preserve the operator's edit; all other tracked changes remain blocking.
DIRTY=$(git status --porcelain --untracked-files=no -- . ':(exclude)manuscript/.gitignore')
if [[ -n "${DIRTY}" ]]; then
    printf '[ERROR] DIRTY_TRACKED_FILES: review these changes; nothing was reverted.\n%s\n' "${DIRTY}" >&2
    exit 2
fi
if [[ -n "$(git status --porcelain --untracked-files=no -- manuscript/.gitignore)" ]]; then
    echo "[WARNING] preserved unrelated manuscript/.gitignore modification; collection source remains protected."
fi
echo "[INFO] PR57_CHECKOUT_OK | commit=${ACTUAL_COMMIT}"
for command in flock sbatch squeue jq conda; do
    if ! command -v "${command}" >/dev/null; then
        echo "[ERROR] REQUIRED_COMMAND_MISSING: ${command}" >&2
        exit 2
    fi
done
if [[ ! -d "${CAMPAIGN_RUN_ROOT}" ]]; then
    echo "[ERROR] CAMPAIGN_RUN_ROOT is missing or is not a directory" >&2
    exit 2
fi
# Serialize this submission path; the receipt prevents a duplicate invocation.
exec 9>"${CAMPAIGN_RUN_ROOT}/.pr57-medium-submission.lock"
if ! flock -n 9; then
    echo "[ERROR] SUBMISSION_LOCK_UNAVAILABLE: another submission may be active" >&2
    exit 2
fi
CONTINUATION_BATCH="${CONTINUATION_BATCH:-0}"
[[ "${CONTINUATION_BATCH}" =~ ^[0-2]$ ]]
SUBMISSION_DIR="${RECONCILIATION_DIR}/submission_batch_${CONTINUATION_BATCH}"
if [[ -e "${SUBMISSION_DIR}" ]]; then
    echo "[ERROR] submission record already exists; inspect it before retrying" >&2
    exit 2
fi
ACTIVE=$(squeue -h -u "$(id -un)" -o '%j' --name=cfl_medium8h)
if [[ -n "${ACTIVE}" ]]; then
    echo "[ERROR] another cfl_medium8h job is queued or running; review before submitting" >&2
    exit 2
fi
eval "$(conda shell.bash hook)"
conda activate "${CONDA_ENV:-tfm_env}"
export PYTHONPATH="${EXEC_DIR}/src:${PYTHONPATH:-}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export GRB_LICENSE_FILE="${GRB_LICENSE_FILE:-${EXEC_DIR}/secrets/gurobi.lic}"
if [[ ! -s "${GRB_LICENSE_FILE}" ]]; then
    echo "[ERROR] GUROBI_LICENSE_FILE_MISSING_OR_EMPTY: check GRB_LICENSE_FILE" >&2
    exit 2
fi
python3 -c 'import gurobipy, pyarrow, scipy, numpy'
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
PREFLIGHT_DIR="${DATA_ROOT}/analysis/medium_continuation/pr57_batch${CONTINUATION_BATCH}_${STAMP}"
export CAMPAIGN_AUDIT_DIR="${DATA_ROOT}/analysis/gurobi_expansion_campaign/pr57_batch${CONTINUATION_BATCH}_${STAMP}_audit"
test ! -e "${CAMPAIGN_AUDIT_DIR}"
python3 -m cfl_gnn.cli.prepare_medium_continuation \
    --data_root "${DATA_ROOT}" --campaign_dir "${CAMPAIGN_PLAN_DIR}" \
    --run_root "${CAMPAIGN_RUN_ROOT}" --reconciliation_dir "${RECONCILIATION_DIR}" \
    --output_dir "${PREFLIGHT_DIR}" --continuation_batch "${CONTINUATION_BATCH}"
PREFLIGHT="${PREFLIGHT_DIR}/medium_continuation_preflight.json"
ARRAY=$(jq -er '.slurm_array' "${PREFLIGHT}")
export MEDIUM_BATCH
MEDIUM_BATCH=$(jq -er '.original_campaign_batch' "${PREFLIGHT}")
WORKER=scripts/slurm/dasci/submit_gurobi_medium_batch.sbs
AUDITOR=scripts/slurm/dasci/submit_gurobi_expansion_batch_audit.sbs
WORKER_ARGS=(--partition=batch --nodes=1 --cpus-per-task=1 --mem=64G --time=12:00:00 --job-name=cfl_medium8h)
AUDIT_ARGS=(--partition=batch --nodes=1 --cpus-per-task=1 --mem=4G --time=00:30:00)
sbatch --test-only "${WORKER_ARGS[@]}" --array="${ARRAY}" --export=ALL "${WORKER}"
sbatch --test-only "${AUDIT_ARGS[@]}" --export=ALL "${AUDITOR}"
mkdir "${SUBMISSION_DIR}"
printf 'COMMIT=%s\nPREFLIGHT=%s\nRUNS=%s\nAUDIT=%s\n' \
    "${PR57_EXPECTED_COMMIT}" "${PREFLIGHT}" "${CAMPAIGN_RUN_ROOT}" "${CAMPAIGN_AUDIT_DIR}" \
    | tee "${SUBMISSION_DIR}/submission.txt"
PAIR_JOB=$(sbatch --parsable "${WORKER_ARGS[@]}" --array="${ARRAY}" --export=ALL "${WORKER}")
PAIR_JOB=${PAIR_JOB%%;*}
[[ "${PAIR_JOB}" =~ ^[0-9]+$ ]]
printf 'MEDIUM_JOB_ID=%s\n' "${PAIR_JOB}" | tee -a "${SUBMISSION_DIR}/submission.txt"
AUDIT_JOB=$(sbatch --parsable "${AUDIT_ARGS[@]}" --dependency="afterany:${PAIR_JOB}" --export=ALL "${AUDITOR}")
AUDIT_JOB=${AUDIT_JOB%%;*}
[[ "${AUDIT_JOB}" =~ ^[0-9]+$ ]]
printf 'AUDIT_JOB_ID=%s\nPR57_SUBMITTED\n' "${AUDIT_JOB}" | tee -a "${SUBMISSION_DIR}/submission.txt"
# If audit submission fails, preserve the medium job and this receipt; do not resubmit the array.
