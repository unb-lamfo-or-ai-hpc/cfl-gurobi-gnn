#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:?prepare|submit|status|collect|batch}
STAGE=${2:?PR87 stage directory}
test "$(hostname -s)" = dgx-dasci || { echo PR87_ENTRY_HOST_MISMATCH >&2; exit 2; }
test "${CONDA_DEFAULT_ENV:-}" = tfm_env || { echo PR87_ENTRY_ENV_MISMATCH >&2; exit 2; }
case "$STAGE" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr87/training-*) ;;
  *) echo PR87_BAD_STAGE >&2; exit 2;; esac
# Slurm executes a spooled copy, so BASH_SOURCE no longer locates the checkout.
# Batch uses the stage passed at submission; Python still verifies its commit,
# plan, allocation and authorization before starting a training subprocess.
if test "$ACTION" = batch; then
  SOURCE="$STAGE/source"
else
  SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
  test "$SOURCE" = "$STAGE/source" || { echo PR87_ENTRY_SOURCE_MISMATCH >&2; exit 2; }
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export PYTHONPATH="$SOURCE/src"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
export PYTHONHASHSEED=42
unset PYTHONHOME
case "$ACTION" in
  prepare|status|collect)
    exec python3 -B "$SOURCE/scripts/evidence/pr87_workflow.py" "$ACTION" --stage "$STAGE" ;;
  submit)
    exec python3 -B "$SOURCE/scripts/evidence/pr87_workflow.py" submit --stage "$STAGE" --approved-plan-sha256 "${3:?approved plan SHA256}" --authorization "${4:?separate approved GPU receipt}" --authorization-sha256 "${5:?authorization SHA256}" ;;
  batch)
    echo PR87_BATCH_DISPATCH_FROM_STAGE
    exec python3 -B "$SOURCE/scripts/evidence/pr87_workflow.py" run --stage "$STAGE" --index "${3:?run index}" ;;
  *) echo PR87_UNKNOWN_ACTION >&2; exit 2;;
esac
