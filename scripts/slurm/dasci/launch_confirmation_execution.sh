#!/bin/bash
# Run as a child script from the repository root; failures never close the shell.
set -euo pipefail
if [[ "$#" != 1 ]]; then
    echo "Usage: bash scripts/slurm/dasci/launch_confirmation_execution.sh INVENTORY_JSON" >&2
    exit 2
fi
export EXEC_DIR="$PWD"
test -f pyproject.toml
test -s "$1"
command -v sbatch >/dev/null
export DATA_ROOT="${DATA_ROOT:-${EXEC_DIR}/data}"
test -d "${DATA_ROOT}/raw/MILPBench/CFL"
export GRB_LICENSE_FILE="${GRB_LICENSE_FILE:-${EXEC_DIR}/secrets/gurobi.lic}"
test -s "${GRB_LICENSE_FILE}"
export PYTHONPATH="${EXEC_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
CFL_REQUIRE_SOLVER_TESTS=1 python3 -m pytest tests/smoke -q
export CONFIRMATION_EXECUTION_DIR="${DATA_ROOT}/analysis/confirmation_execution/pr50_$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m cfl_gnn.cli.run_confirmation_cohort prepare \
    --inventory "$1" --data_root "${DATA_ROOT}" \
    --campaign_dir "${CONFIRMATION_EXECUTION_DIR}"
export REPAIR_LABELS="${REPAIR_LABELS:-1}"
SOURCE_JOB_ID=$(sbatch --parsable --array=0-41%4 --export=ALL \
    scripts/slurm/dasci/submit_confirmation_sources.sbs)
SOURCE_JOB_ID=${SOURCE_JOB_ID%%;*}
if [[ ! "$SOURCE_JOB_ID" =~ ^[0-9]+$ ]]; then
    echo "Invalid source job id; audit not submitted" >&2
    exit 2
fi
# Persist the successful array id even if audit submission fails afterward.
printf '%s\n' "$SOURCE_JOB_ID" > "${CONFIRMATION_EXECUTION_DIR}/source_job_id.txt"
printf 'SOURCE_JOB_ID=%s\nCAMPAIGN=%s\n' "$SOURCE_JOB_ID" "$CONFIRMATION_EXECUTION_DIR"
AUDIT_JOB_ID=$(sbatch --parsable --dependency="afterany:${SOURCE_JOB_ID}" --export=ALL \
    scripts/slurm/dasci/submit_confirmation_sources_audit.sbs)
AUDIT_JOB_ID=${AUDIT_JOB_ID%%;*}
[[ "$AUDIT_JOB_ID" =~ ^[0-9]+$ ]]
printf '%s\n' "$AUDIT_JOB_ID" > "${CONFIRMATION_EXECUTION_DIR}/audit_job_id.txt"
printf 'AUDIT_JOB_ID=%s\n' "$AUDIT_JOB_ID"
