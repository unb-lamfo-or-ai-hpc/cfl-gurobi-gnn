#!/bin/bash
set -euo pipefail

EXEC_DIR="${EXEC_DIR:-$PWD}"
cd "$EXEC_DIR"
test -f pyproject.toml

DATA_ROOT="${DATA_ROOT:-/raid/vrcelestino/data/cfl-gurobi-gnn/data}"
PR57_TRAINING_DIR="${PR57_TRAINING_DIR:-${DATA_ROOT}/models/pr57_54/pr57_54_20260928T203822Z}"
BASE_SOURCE_DIR="${BASE_SOURCE_DIR:-${DATA_ROOT}/raw/MILPBench/CFL}"

test -s "${PR57_TRAINING_DIR}/pr57_54_training_audit.json"
test -s "${PR57_TRAINING_DIR}/evaluation_recovery/gasse_evaluation_report.json"
test -s "${PR57_TRAINING_DIR}/best_model.pt"
test -d "$BASE_SOURCE_DIR"

export EXEC_DIR DATA_ROOT PR57_TRAINING_DIR BASE_SOURCE_DIR
export PYTHONPATH="${EXEC_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
export PR58_PLAN_DIR="${DATA_ROOT}/analysis/pr58_validation_guidance/${STAMP}_plan"
export PR58_RUN_ROOT="${DATA_ROOT}/intermediate/pr58_validation_guidance/${STAMP}"
export PR58_AUDIT_DIR="${DATA_ROOT}/analysis/pr58_validation_guidance/${STAMP}_audit"

LOG_DIR="${DATA_ROOT}/analysis/pr58_validation_guidance/${STAMP}_logs"
SUBMISSION_DIR="${DATA_ROOT}/analysis/pr58_validation_guidance/${STAMP}_submission"
mkdir -p "$LOG_DIR" "$SUBMISSION_DIR" "$PR58_RUN_ROOT"

SOURCE_COMMIT="$(git rev-parse HEAD)"

python3 -m cfl_gnn.cli.run_pr58_validation_guidance plan \
    --plan_dir "$PR58_PLAN_DIR" \
    --training_dir "$PR57_TRAINING_DIR" \
    --mip_root "$BASE_SOURCE_DIR"

VALIDATION_JOB="$(
    sbatch --parsable --export=ALL \
      --output="${LOG_DIR}/slurm_cfl_pr58_validation_%A_%a.out" \
      --error="${LOG_DIR}/slurm_cfl_pr58_validation_%A_%a.err" \
      scripts/slurm/dasci/submit_pr58_validation_guidance.sbs
)"
VALIDATION_JOB="${VALIDATION_JOB%%;*}"
[[ "$VALIDATION_JOB" =~ ^[0-9]+$ ]]

AUDIT_JOB="$(
    sbatch --parsable --dependency="afterany:${VALIDATION_JOB}" --export=ALL \
      --output="${LOG_DIR}/slurm_cfl_pr58_audit_%j.out" \
      --error="${LOG_DIR}/slurm_cfl_pr58_audit_%j.err" \
      scripts/slurm/dasci/submit_pr58_validation_guidance_audit.sbs
)"
AUDIT_JOB="${AUDIT_JOB%%;*}"
[[ "$AUDIT_JOB" =~ ^[0-9]+$ ]]

cat > "${SUBMISSION_DIR}/submission.txt" <<RECEIPT
STAMP=${STAMP}
SOURCE_COMMIT=${SOURCE_COMMIT}
VALIDATION_JOB=${VALIDATION_JOB}
AUDIT_JOB=${AUDIT_JOB}
PR57_TRAINING_DIR=${PR57_TRAINING_DIR}
BASE_SOURCE_DIR=${BASE_SOURCE_DIR}
PR58_PLAN_DIR=${PR58_PLAN_DIR}
PR58_RUN_ROOT=${PR58_RUN_ROOT}
PR58_AUDIT_DIR=${PR58_AUDIT_DIR}
RECEIPT

printf 'SOURCE_COMMIT=%s\n' "$SOURCE_COMMIT"
printf 'VALIDATION_JOB=%s\n' "$VALIDATION_JOB"
printf 'AUDIT_JOB=%s\n' "$AUDIT_JOB"
printf 'PLAN=%s\n' "$PR58_PLAN_DIR"
printf 'RUNS=%s\n' "$PR58_RUN_ROOT"
printf 'AUDIT=%s\n' "$PR58_AUDIT_DIR"
printf 'SUBMISSION_RECEIPT=%s\n' "${SUBMISSION_DIR}/submission.txt"
