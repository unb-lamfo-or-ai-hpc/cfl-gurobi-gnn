#!/usr/bin/env bash
# No polling, automatic retry, package installation or implicit authorization.
set -euo pipefail
if [[ ${1:-} == batch ]]; then
  SOURCE=${PR86_SOURCE:?}
  STAGE=${PR86_STAGE:?}
else
  SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
  STAGE=$(dirname "$SOURCE")
fi
case "$STAGE" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr86/roots-*) ;;
  *) echo PR86_BAD_ROOT_STAGE >&2; exit 2;; esac
test "$(hostname -s)" = dgx-dasci
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
test "$SOURCE" = "$STAGE/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export GRB_LICENSE_FILE=/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
unset PYTHONHOME PYTHONPATH
case "${1:-}" in
 prepare|status|collect)
  exec python3 -B "$SOURCE/scripts/evidence/pr86_root_preparation.py" "$1" --stage "$STAGE" ;;
 submit)
  SHA=${2:?Expected the approved plan SHA256, not a confirmation phrase}
  [[ $SHA =~ ^[0-9a-f]{64}$ ]]
  exec python3 -B "$SOURCE/scripts/evidence/pr86_root_preparation.py" submit \
    --stage "$STAGE" --approved-plan-sha256 "$SHA" ;;
 batch)
  exec "${PR86_PYTHON:?}" -B "$SOURCE/scripts/evidence/pr86_root_preparation.py" run --stage "$STAGE" ;;
 *) echo 'Usage: operate_pr86_roots.sh prepare|submit PLAN_SHA256|status|collect' >&2; exit 2;;
esac
