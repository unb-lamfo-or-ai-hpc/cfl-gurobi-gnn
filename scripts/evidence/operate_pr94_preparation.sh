#!/usr/bin/env bash
# PR94 only. No modifications to the installed PR89 source or its jobs.
set -euo pipefail
if [[ ${1:-} == batch ]]; then
    STAGE=${PR94_STAGE:?}
    KIND=${PR94_KIND:?}
    PYTHON=${PR94_PYTHON:?}
else
    SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
    STAGE=$(dirname "$SOURCE")
    PYTHON=$(command -v python)
fi
case "$STAGE" in
    /raid/vrcelestino/data/cfl-mvp2-evidence/pr94-preparation-????????????) ;;
    *) echo PR94_INVALID_STAGE >&2; exit 2 ;;
esac
SOURCE="$STAGE/source"
test "$(hostname -s)" = dgx-dasci
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
test -d "$SOURCE"
umask 077
ulimit -c 0
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 GIT_OPTIONAL_LOCKS=0
export TMPDIR="$STAGE/runtime/tmp" TMP="$STAGE/runtime/tmp" TEMP="$STAGE/runtime/tmp"
export XDG_CACHE_HOME="$STAGE/runtime/cache" CUDA_CACHE_PATH="$STAGE/runtime/cuda"
export TORCH_HOME="$STAGE/runtime/torch" TORCH_EXTENSIONS_DIR="$STAGE/runtime/extensions"
export MPLCONFIGDIR="$STAGE/runtime/matplotlib"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
unset PYTHONHOME PYTHONPATH
if [[ -z ${GRB_LICENSE_FILE:-} ]]; then
    export GRB_LICENSE_FILE=/raid/vrcelestino/data/cfl-gurobi-gnn/secrets/gurobi.lic
fi
case "${1:-}" in
    freeze)
        CONFIG=${2:?Private input config path required}
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_isolated_preparation.py" freeze \
            --stage "$STAGE" --private-config "$CONFIG" ;;
    inspect)
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_isolated_preparation.py" inspect --stage "$STAGE" ;;
    submit-roots|submit-guidance)
        KIND=${1#submit-}
        SHA=${2:?Reviewed plan SHA256 required}
        [[ $SHA =~ ^[0-9a-f]{64}$ ]]
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_isolated_preparation.py" submit \
            --stage "$STAGE" --kind "$KIND" --approved-plan-sha256 "$SHA" ;;
    review-roots)
        SHA=${2:?Accepted root return SHA256 required}
        [[ $SHA =~ ^[0-9a-f]{64}$ ]]
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_isolated_preparation.py" review-roots \
            --stage "$STAGE" --accepted-root-return-sha256 "$SHA" ;;
    status-roots|status-guidance|collect-roots|collect-guidance)
        ACTION=${1%%-*}
        KIND=${1#*-}
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_isolated_preparation.py" "$ACTION" \
            --stage "$STAGE" --kind "$KIND" ;;
    batch)
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_isolated_preparation.py" run \
            --stage "$STAGE" --kind "$KIND" ;;
    *) echo 'PR94: freeze CONFIG | inspect | submit-roots/guidance PLAN_SHA | review-roots RETURN_SHA | status-roots/guidance | collect-roots/guidance' >&2; exit 2 ;;
esac
