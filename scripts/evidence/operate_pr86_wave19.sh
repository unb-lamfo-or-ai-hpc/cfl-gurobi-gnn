#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == batch ]]; then
  SOURCE=${PR86_SOURCE:?}
  STAGE=${PR86_STAGE:?}
else
  SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
  STAGE=$(dirname "$SOURCE")
fi
case "$STAGE" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr86/next-19-*) ;;
  *) echo PR86_BAD_NEXT_STAGE >&2; exit 2;; esac
test "$(hostname -s)" = dgx-dasci
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
test "$SOURCE" = "$STAGE/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export GRB_LICENSE_FILE=/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
unset PYTHONHOME PYTHONPATH
case "${1:-}" in
 prepare|status|collect)
  exec python3 -B "$SOURCE/scripts/evidence/pr86_wave19.py" "$1" --stage "$STAGE" ;;
 submit)
  SHA=${2:?Expected approved plan SHA256}
  [[ $SHA =~ ^[0-9a-f]{64}$ ]]
  exec python3 -B "$SOURCE/scripts/evidence/pr86_wave19.py" submit --stage "$STAGE" --approved-plan-sha256 "$SHA" ;;
 batch)
  INDEX=${2:?Group index}
  [[ $INDEX =~ ^[0-5]$ ]]
  exec "${PR86_PYTHON:?}" -B "$SOURCE/scripts/evidence/pr86_wave19.py" run --stage "$STAGE" --index "$INDEX" ;;
 *) echo 'Usage: operate_pr86_wave19.sh prepare|submit PLAN_SHA256|status|collect' >&2; exit 2;;
esac
