#!/bin/bash
# Submit a bounded-concurrency paired-parent campaign and its progress audit.

set -euo pipefail

EXEC_DIR="${EXEC_DIR:-$(pwd)}"
: "${PARENT_COLLECTION_PLAN_DIR:?Set PARENT_COLLECTION_PLAN_DIR}"
: "${PARENT_COLLECTION_RUN_ROOT:?Set PARENT_COLLECTION_RUN_ROOT}"
: "${PARENT_COLLECTION_PROGRESS_DIR:?Set PARENT_COLLECTION_PROGRESS_DIR}"
: "${BASE_SOURCE_DIR:?Set BASE_SOURCE_DIR to data/raw/MILPBench/CFL}"

PLAN_PATH="${PARENT_COLLECTION_PLAN_DIR}/parent_collection_plan.json"
if [[ ! -s "${PLAN_PATH}" ]]; then
    echo "[ERROR] parent collection plan is unavailable" >&2
    exit 2
fi

PARENT_COUNT=$(jq -er '.available_parent_population' "${PLAN_PATH}")
MAX_PARALLEL_PARENTS="${MAX_PARALLEL_PARENTS:-4}"
if (( PARENT_COUNT < 1 || MAX_PARALLEL_PARENTS < 1 )); then
    echo "[ERROR] parent count and concurrency must be positive" >&2
    exit 2
fi

LAST_INDEX=$((PARENT_COUNT - 1))
PAIR_JOB_ID=$(sbatch --parsable \
    --array="0-${LAST_INDEX}%${MAX_PARALLEL_PARENTS}" \
    --export=ALL \
    "${EXEC_DIR}/scripts/slurm/dasci/submit_paired_parent_collection_array.sbs")
PAIR_JOB_ID=${PAIR_JOB_ID%%;*}

PROGRESS_JOB_ID=$(sbatch --parsable \
    --dependency="afterany:${PAIR_JOB_ID}" \
    --export=ALL \
    "${EXEC_DIR}/scripts/slurm/dasci/submit_parent_collection_progress_audit.sbs")
PROGRESS_JOB_ID=${PROGRESS_JOB_ID%%;*}

echo "PAIR_JOB_ID=${PAIR_JOB_ID}"
echo "PROGRESS_JOB_ID=${PROGRESS_JOB_ID}"
echo "PARENT_COUNT=${PARENT_COUNT}"
echo "MAX_PARALLEL_PARENTS=${MAX_PARALLEL_PARENTS}"
