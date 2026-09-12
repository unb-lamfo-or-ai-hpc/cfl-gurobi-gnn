#!/bin/bash
# Invoke as a child script only after the source array and its audit have ended.
set -euo pipefail
if [[ "$#" != 1 ]]; then
    echo "Usage: bash scripts/slurm/dasci/launch_confirmation_training.sh CAMPAIGN_DIR" >&2
    exit 2
fi
export EXEC_DIR="$PWD"
test -f pyproject.toml
export DATA_ROOT="${DATA_ROOT:-${EXEC_DIR}/data}"
export CONFIRMATION_EXECUTION_DIR="$1"
test -s "$CONFIRMATION_EXECUTION_DIR/confirmation_execution_report.json"
export PYTHONPATH="${EXEC_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
export GRB_LICENSE_FILE="${GRB_LICENSE_FILE:-${EXEC_DIR}/secrets/gurobi.lic}"
test -s "$GRB_LICENSE_FILE"
CFL_REQUIRE_SOLVER_TESTS=1 python3 -m pytest tests/smoke -q
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
export CONFIRMATION_DATASET_DIR="${DATA_ROOT}/bipartite_graphs/confirmation/pr50_${STAMP}"
export CONFIRMATION_TRAINING_DIR="${DATA_ROOT}/models/confirmation/pr50_${STAMP}"
python3 -m cfl_gnn.cli.run_confirmation_training preflight \
    --campaign_dir "$CONFIRMATION_EXECUTION_DIR" --dataset_dir "$CONFIRMATION_DATASET_DIR"
GRAPH_JOB=$(sbatch --parsable --array=0-41%2 --export=ALL scripts/slurm/dasci/submit_confirmation_graphs.sbs)
GRAPH_JOB=${GRAPH_JOB%%;*}
[[ "$GRAPH_JOB" =~ ^[0-9]+$ ]]
printf 'GRAPH_JOB=%s\nDATASET=%s\nTRAINING=%s\n' "$GRAPH_JOB" "$CONFIRMATION_DATASET_DIR" "$CONFIRMATION_TRAINING_DIR"
AUDIT_JOB=$(sbatch --parsable --dependency="afterany:${GRAPH_JOB}" --export=ALL scripts/slurm/dasci/submit_confirmation_graph_audit.sbs)
AUDIT_JOB=${AUDIT_JOB%%;*}
[[ "$AUDIT_JOB" =~ ^[0-9]+$ ]]
printf 'GRAPH_AUDIT_JOB=%s\n' "$AUDIT_JOB"
TRAIN_JOB=$(sbatch --parsable --dependency="afterok:${AUDIT_JOB}" --export=ALL scripts/slurm/dasci/submit_confirmation_training.sbs)
TRAIN_JOB=${TRAIN_JOB%%;*}
[[ "$TRAIN_JOB" =~ ^[0-9]+$ ]]
printf 'TRAIN_AND_EVALUATION_JOB=%s\n' "$TRAIN_JOB"
