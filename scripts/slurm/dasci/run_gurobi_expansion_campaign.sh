#!/bin/bash
# Shared job body; invoked from the medium, hard and audit Slurm launchers.
set -euo pipefail
MODE="${1:?Expected medium, hard, or audit}"
INDEX="${2:?Expected task or batch index}"
EXEC_DIR="${EXEC_DIR:-${SLURM_SUBMIT_DIR:-}}"
if [[ -z "${EXEC_DIR}" || ! -f "${EXEC_DIR}/pyproject.toml" ]]; then
    echo "[ERROR] repository root unavailable; submit from the checkout" >&2
    exit 2
fi
: "${DATA_ROOT:?Set DATA_ROOT}"
: "${CAMPAIGN_PLAN_DIR:?Set CAMPAIGN_PLAN_DIR to a directory}"
: "${CAMPAIGN_RUN_ROOT:?Set CAMPAIGN_RUN_ROOT}"
cd "${EXEC_DIR}"
export PYTHONPATH="${EXEC_DIR}/src:${PYTHONPATH:-}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
eval "$(conda shell.bash hook)"
conda activate "${CONDA_ENV:-tfm_env}"
COMMON=(--data_root "${DATA_ROOT}" --campaign_dir "${CAMPAIGN_PLAN_DIR}" --run_root "${CAMPAIGN_RUN_ROOT}")
if [[ "${MODE}" == "audit" ]]; then
    : "${CAMPAIGN_AUDIT_DIR:?Set CAMPAIGN_AUDIT_DIR to a new directory}"
    srun python3 -m cfl_gnn.cli.gurobi_expansion_campaign audit \
        "${COMMON[@]}" --batch "${INDEX}" --output_dir "${CAMPAIGN_AUDIT_DIR}"
elif [[ "${MODE}" == "medium" || "${MODE}" == "hard" ]]; then
    export GRB_LICENSE_FILE="${GRB_LICENSE_FILE:-${EXEC_DIR}/secrets/gurobi.lic}"
    if [[ ! -s "${GRB_LICENSE_FILE}" ]]; then
        echo "[ERROR] missing Gurobi license file" >&2
        exit 2
    fi
    python3 -c 'import gurobipy, pyarrow, scipy, numpy'
    echo "[INFO] phase=${MODE} | task=${INDEX} | Gurobi only | MINIMIZE | seed=42"
    srun python3 -m cfl_gnn.cli.gurobi_expansion_campaign task \
        "${COMMON[@]}" --phase "${MODE}" --task_index "${INDEX}"
else
    echo "[ERROR] invalid campaign mode" >&2
    exit 2
fi
