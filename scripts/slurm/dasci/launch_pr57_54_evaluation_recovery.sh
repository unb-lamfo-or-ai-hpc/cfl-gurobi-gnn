#!/bin/bash
set -euo pipefail

EXEC_DIR="${EXEC_DIR:-$PWD}"
cd "$EXEC_DIR"
test -f pyproject.toml

DATA_ROOT="${DATA_ROOT:-/raid/vrcelestino/data/cfl-gurobi-gnn/data}"
PR57_TRAINING_DIR="${PR57_TRAINING_DIR:-${DATA_ROOT}/models/pr57_54/pr57_54_20260928T203822Z}"
PR57_EVALUATION_DIR="${PR57_EVALUATION_DIR:-${PR57_TRAINING_DIR}/evaluation_recovery}"
EXPECTED_TRAINING_PLAN_SHA="${EXPECTED_TRAINING_PLAN_SHA:-432a42dab9f49f01a31d7b28f658bd14f7c50450ac2d83d1ae3102bcc12f0d40}"

export EXEC_DIR DATA_ROOT PR57_TRAINING_DIR PR57_EVALUATION_DIR
export EXPECTED_TRAINING_PLAN_SHA

test -s "${PR57_TRAINING_DIR}/gasse_training_plan.json"
test -s "${PR57_TRAINING_DIR}/gasse_training_report.json"
test -s "${PR57_TRAINING_DIR}/best_model.pt"

if test -e "${PR57_EVALUATION_DIR}/gasse_evaluation_report.json"; then
    echo "[ERROR] recovery evaluation already completed: ${PR57_EVALUATION_DIR}" >&2
    exit 2
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="${DATA_ROOT}/analysis/pr57_54/evaluation_recovery_logs/${STAMP}"
SUBMISSION_DIR="${DATA_ROOT}/analysis/pr57_54/evaluation_recovery_submissions/${STAMP}"
mkdir -p "$LOG_DIR" "$SUBMISSION_DIR"

SOURCE_COMMIT="$(git rev-parse HEAD)"

EVALUATION_JOB="$(
    sbatch \
      --parsable \
      --export=ALL \
      --output="${LOG_DIR}/slurm_cfl_pr57_eval_%j.out" \
      --error="${LOG_DIR}/slurm_cfl_pr57_eval_%j.err" \
      scripts/slurm/dasci/submit_pr57_54_evaluation_recovery.sbs
)"
EVALUATION_JOB="${EVALUATION_JOB%%;*}"
[[ "$EVALUATION_JOB" =~ ^[0-9]+$ ]]

AUDIT_JOB="$(
    sbatch \
      --parsable \
      --dependency="afterok:${EVALUATION_JOB}" \
      --export=ALL \
      --output="${LOG_DIR}/slurm_cfl_pr57_taudit_%j.out" \
      --error="${LOG_DIR}/slurm_cfl_pr57_taudit_%j.err" \
      scripts/slurm/dasci/submit_pr57_54_training_audit.sbs
)"
AUDIT_JOB="${AUDIT_JOB%%;*}"
[[ "$AUDIT_JOB" =~ ^[0-9]+$ ]]

cat > "${SUBMISSION_DIR}/submission.txt" <<REC
STAMP=${STAMP}
SOURCE_COMMIT=${SOURCE_COMMIT}
EVALUATION_JOB=${EVALUATION_JOB}
AUDIT_JOB=${AUDIT_JOB}
DATA_ROOT=${DATA_ROOT}
PR57_TRAINING_DIR=${PR57_TRAINING_DIR}
PR57_EVALUATION_DIR=${PR57_EVALUATION_DIR}
EXPECTED_TRAINING_PLAN_SHA=${EXPECTED_TRAINING_PLAN_SHA}
REC

printf 'SOURCE_COMMIT=%s\n' "$SOURCE_COMMIT"
printf 'EVALUATION_JOB=%s\n' "$EVALUATION_JOB"
printf 'AUDIT_JOB=%s\n' "$AUDIT_JOB"
printf 'TRAINING_DIR=%s\n' "$PR57_TRAINING_DIR"
printf 'EVALUATION_DIR=%s\n' "$PR57_EVALUATION_DIR"
printf 'SUBMISSION_RECEIPT=%s\n' "${SUBMISSION_DIR}/submission.txt"
