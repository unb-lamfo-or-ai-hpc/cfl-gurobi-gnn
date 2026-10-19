#!/usr/bin/env bash
set -euo pipefail
SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
ACTION=${1:?prepare|submit|status|collect|batch}
STAGE=${2:?PR87 stage directory}
test "$(hostname -s)" = dgx-dasci
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
case "$STAGE" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr87/training-*) ;;
  *) echo PR87_BAD_STAGE >&2; exit 2;; esac
test "$SOURCE" = "$STAGE/source"
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
    exec python3 -B "$SOURCE/scripts/evidence/pr87_workflow.py" run --stage "$STAGE" --index "${3:?run index}" ;;
  *) echo PR87_UNKNOWN_ACTION >&2; exit 2;;
esac
