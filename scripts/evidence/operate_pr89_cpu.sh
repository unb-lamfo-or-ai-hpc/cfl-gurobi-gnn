#!/usr/bin/env bash
set -euo pipefail
ACTION=${1:?prepare|authorize|submit|status|collect|batch}
STAGE=${2:?stage directory}
test "$(hostname -s)" = dgx-dasci || { echo PR89_HOST_MISMATCH >&2; exit 2; }
test "${CONDA_DEFAULT_ENV:-}" = tfm_env || { echo PR89_ENV_MISMATCH >&2; exit 2; }
case "$STAGE" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr89/cpu12h-*) ;;
  *) echo PR89_STAGE_MISMATCH >&2; exit 2;; esac
# Slurm runs a spooled copy: locate code from the explicit frozen stage.
SOURCE="$STAGE/source"
if test "$ACTION" != batch; then
  test "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)" = "$SOURCE" || exit 2
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export PYTHONPATH="$SOURCE/src" PYTHONHASHSEED=42
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
unset PYTHONHOME
case "$ACTION" in
  prepare|status|collect)
    exec python3 -B "$SOURCE/scripts/evidence/pr89_cpu_workflow.py" "$ACTION" --stage "$STAGE" ;;
  authorize)
    exec python3 -B "$SOURCE/scripts/evidence/pr89_cpu_workflow.py" authorize --stage "$STAGE" --approved-plan-sha256 "${3:?plan SHA256}" --decision-reference "2026-10-20 author approved complete CPU package, 60 fresh solves, no retry" ;;
  submit)
    exec python3 -B "$SOURCE/scripts/evidence/pr89_cpu_workflow.py" submit --stage "$STAGE" --authorization-sha256 "${3:?authorization SHA256}" --count "${4:?number of sequential jobs}" ;;
  batch)
    exec python3 -B "$SOURCE/scripts/evidence/pr89_cpu_workflow.py" run --stage "$STAGE" --index "${3:?cell index}" ;;
  *) echo PR89_ACTION_NOT_RELEASED >&2; exit 2;;
esac
