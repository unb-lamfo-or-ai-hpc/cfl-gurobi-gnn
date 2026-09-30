#!/bin/bash
set -euo pipefail

EXEC_DIR="${EXEC_DIR:-$PWD}"
cd "$EXEC_DIR"
test -f pyproject.toml

DATA_ROOT="${DATA_ROOT:-/home/vrcelestino/discodatos/cfl-gurobi-gnn/data}"

export EXEC_DIR
export DATA_ROOT

export EVIDENCE_PACKAGE="${EVIDENCE_PACKAGE:-${DATA_ROOT}/evidence/pr57/current/pr57-batch3-evidence-beu0_rbn/pr57_batch3_evidence.tar.gz}"

export OLD_GRAPH_ROOT="${OLD_GRAPH_ROOT:-${DATA_ROOT}/bipartite_graphs/confirmation/pr50_20260913T135218Z}"

export PR57_DATASET_DIR="${PR57_DATASET_DIR:-${DATA_ROOT}/bipartite_graphs/pr57/pr57_54_parent_v1}"

export EXPECTED_TRAINING_PLAN_SHA="${EXPECTED_TRAINING_PLAN_SHA:-432a42dab9f49f01a31d7b28f658bd14f7c50450ac2d83d1ae3102bcc12f0d40}"

test -s "$EVIDENCE_PACKAGE"
test -s "$PR57_DATASET_DIR/pr57_54_graph_report.json"
test -s "$PR57_DATASET_DIR/pr57_54_graph_manifest.jsonl"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

export PR57_TRAINING_DIR="${DATA_ROOT}/models/pr57_54/pr57_54_${STAMP}"

LOG_DIR="${DATA_ROOT}/analysis/pr57_54/training_logs/${STAMP}"
SUBMISSION_DIR="${DATA_ROOT}/analysis/pr57_54/submissions/${STAMP}"

mkdir -p "$LOG_DIR" "$SUBMISSION_DIR"

SOURCE_COMMIT="$(git rev-parse HEAD)"

printf 'SOURCE_COMMIT=%s\n' "$SOURCE_COMMIT"
printf 'DATASET=%s\n' "$PR57_DATASET_DIR"
printf 'TRAINING=%s\n' "$PR57_TRAINING_DIR"
printf 'EXPECTED_TRAINING_PLAN_SHA=%s\n' "$EXPECTED_TRAINING_PLAN_SHA"

TRAIN_JOB="$(
    sbatch \
      --parsable \
      --export=ALL \
      --output="${LOG_DIR}/slurm_cfl_pr57_train_%j.out" \
      --error="${LOG_DIR}/slurm_cfl_pr57_train_%j.err" \
      scripts/slurm/dasci/submit_pr57_54_training.sbs
)"
TRAIN_JOB="${TRAIN_JOB%%;*}"

[[ "$TRAIN_JOB" =~ ^[0-9]+$ ]]

AUDIT_JOB="$(
    sbatch \
      --parsable \
      --dependency="afterany:${TRAIN_JOB}" \
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
TRAIN_JOB=${TRAIN_JOB}
AUDIT_JOB=${AUDIT_JOB}
DATA_ROOT=${DATA_ROOT}
EVIDENCE_PACKAGE=${EVIDENCE_PACKAGE}
OLD_GRAPH_ROOT=${OLD_GRAPH_ROOT}
PR57_DATASET_DIR=${PR57_DATASET_DIR}
PR57_TRAINING_DIR=${PR57_TRAINING_DIR}
EXPECTED_TRAINING_PLAN_SHA=${EXPECTED_TRAINING_PLAN_SHA}
REC

printf '\nTRAIN_JOB=%s\n' "$TRAIN_JOB"
printf 'AUDIT_JOB=%s\n' "$AUDIT_JOB"
printf 'TRAINING_DIR=%s\n' "$PR57_TRAINING_DIR"
printf 'SUBMISSION_RECEIPT=%s\n' "${SUBMISSION_DIR}/submission.txt"
