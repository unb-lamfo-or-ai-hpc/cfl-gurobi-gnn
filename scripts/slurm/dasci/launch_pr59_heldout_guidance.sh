#!/bin/bash
set -euo pipefail

EXEC_DIR="${EXEC_DIR:-$PWD}"
cd "$EXEC_DIR"
test -f pyproject.toml

DATA_ROOT="${DATA_ROOT:-/raid/vrcelestino/data/cfl-gurobi-gnn/data}"
PR57_TRAINING_DIR="${PR57_TRAINING_DIR:-${DATA_ROOT}/models/pr57_54/pr57_54_20260928T203822Z}"
PR58_VALIDATION_AUDIT_DIR="${PR58_VALIDATION_AUDIT_DIR:-${DATA_ROOT}/analysis/pr58_validation_guidance/20260930T195857Z_audit}"
BASE_SOURCE_DIR="${BASE_SOURCE_DIR:-${DATA_ROOT}/raw/MILPBench/CFL}"
CANONICAL_GRB_LICENSE_FILE="/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic"

test -s "${PR57_TRAINING_DIR}/pr57_54_training_audit.json"
test -s "${PR57_TRAINING_DIR}/evaluation_recovery/gasse_evaluation_report.json"
test -s "${PR57_TRAINING_DIR}/best_model.pt"
test -s "${PR58_VALIDATION_AUDIT_DIR}/pr58_validation_guidance_report.json"
test -d "$BASE_SOURCE_DIR"
if [[ ! -s "${CANONICAL_GRB_LICENSE_FILE}" ]]; then
    printf '[ERROR] canonical Gurobi license is unreadable: %s\n' \
        "${CANONICAL_GRB_LICENSE_FILE}" >&2
    false
fi

export GRB_LICENSE_FILE="${CANONICAL_GRB_LICENSE_FILE}"
export EXEC_DIR DATA_ROOT PR57_TRAINING_DIR PR58_VALIDATION_AUDIT_DIR
export BASE_SOURCE_DIR GRB_LICENSE_FILE
export PYTHONPATH="${EXEC_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
export PR59_PLAN_DIR="${DATA_ROOT}/analysis/pr59_heldout_guidance/${STAMP}_plan"
export PR59_RUN_ROOT="${DATA_ROOT}/intermediate/pr59_heldout_guidance/${STAMP}"
export PR59_AUDIT_DIR="${DATA_ROOT}/analysis/pr59_heldout_guidance/${STAMP}_audit"

LOG_DIR="${DATA_ROOT}/analysis/pr59_heldout_guidance/${STAMP}_logs"
SUBMISSION_DIR="${DATA_ROOT}/analysis/pr59_heldout_guidance/${STAMP}_submission"
mkdir -p "$LOG_DIR" "$SUBMISSION_DIR" "$PR59_RUN_ROOT"

SOURCE_COMMIT="$(git rev-parse HEAD)"

python3 -m cfl_gnn.cli.run_pr59_heldout_guidance plan \
    --plan_dir "$PR59_PLAN_DIR" \
    --training_dir "$PR57_TRAINING_DIR" \
    --validation_audit_dir "$PR58_VALIDATION_AUDIT_DIR" \
    --mip_root "$BASE_SOURCE_DIR"

BENCHMARK_JOB="$(
    sbatch --parsable --export=ALL \
      --output="${LOG_DIR}/slurm_cfl_pr59_test_%A_%a.out" \
      --error="${LOG_DIR}/slurm_cfl_pr59_test_%A_%a.err" \
      scripts/slurm/dasci/submit_pr59_heldout_guidance.sbs
)"
BENCHMARK_JOB="${BENCHMARK_JOB%%;*}"
[[ "$BENCHMARK_JOB" =~ ^[0-9]+$ ]]

AUDIT_JOB="$(
    sbatch --parsable --dependency="afterany:${BENCHMARK_JOB}" --export=ALL \
      --output="${LOG_DIR}/slurm_cfl_pr59_audit_%j.out" \
      --error="${LOG_DIR}/slurm_cfl_pr59_audit_%j.err" \
      scripts/slurm/dasci/submit_pr59_heldout_guidance_audit.sbs
)"
AUDIT_JOB="${AUDIT_JOB%%;*}"
[[ "$AUDIT_JOB" =~ ^[0-9]+$ ]]

cat > "${SUBMISSION_DIR}/submission.txt" <<RECEIPT
STAMP=${STAMP}
SOURCE_COMMIT=${SOURCE_COMMIT}
BENCHMARK_JOB=${BENCHMARK_JOB}
AUDIT_JOB=${AUDIT_JOB}
PR57_TRAINING_DIR=${PR57_TRAINING_DIR}
PR58_VALIDATION_AUDIT_DIR=${PR58_VALIDATION_AUDIT_DIR}
BASE_SOURCE_DIR=${BASE_SOURCE_DIR}
PR59_PLAN_DIR=${PR59_PLAN_DIR}
PR59_RUN_ROOT=${PR59_RUN_ROOT}
PR59_AUDIT_DIR=${PR59_AUDIT_DIR}
RECEIPT

printf 'SOURCE_COMMIT=%s\n' "$SOURCE_COMMIT"
printf 'BENCHMARK_JOB=%s\n' "$BENCHMARK_JOB"
printf 'AUDIT_JOB=%s\n' "$AUDIT_JOB"
printf 'PLAN=%s\n' "$PR59_PLAN_DIR"
printf 'RUNS=%s\n' "$PR59_RUN_ROOT"
printf 'AUDIT=%s\n' "$PR59_AUDIT_DIR"
printf 'SUBMISSION_RECEIPT=%s\n' "${SUBMISSION_DIR}/submission.txt"
