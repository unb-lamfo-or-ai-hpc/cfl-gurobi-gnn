#!/usr/bin/env bash
# Author-operated, isolated evaluation stage. Never change PR89 or PR94 preparation.
set -euo pipefail
if [[ ${1:-} == batch ]]; then
    STAGE=${PR94_EVALUATION_STAGE:?}
else
    SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
    STAGE=$(dirname "$SOURCE")
fi
case "$STAGE" in
    /raid/vrcelestino/data/cfl-mvp2-evidence/pr94-evaluation-????????????) ;;
    *) echo PR94_EVALUATION_INVALID_STAGE >&2; exit 2 ;;
esac
SOURCE="$STAGE/source"
test "$(hostname -s)" = dgx-dasci
test "$(id -un)" = vrcelestino
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
umask 077
ulimit -c 0
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 GIT_OPTIONAL_LOCKS=0
export TMPDIR="$STAGE/runtime/tmp" TMP="$STAGE/runtime/tmp" TEMP="$STAGE/runtime/tmp"
export XDG_CACHE_HOME="$STAGE/runtime/cache" MPLCONFIGDIR="$STAGE/runtime/matplotlib"
export TORCH_HOME="$STAGE/runtime/torch" TORCH_EXTENSIONS_DIR="$STAGE/runtime/extensions"
export CUDA_CACHE_PATH="$STAGE/runtime/cuda" CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
unset PYTHONHOME PYTHONPATH
if [[ -z ${GRB_LICENSE_FILE:-} ]]; then
    export GRB_LICENSE_FILE=/raid/vrcelestino/data/cfl-gurobi-gnn/secrets/gurobi.lic
fi
PYTHON=${PR94_EVALUATION_PYTHON:-$(command -v python)}
case "${1:-}" in
    inspect)
        SHA=${2:?Reviewed guidance metadata SHA256 required}
        [[ $SHA =~ ^[0-9a-f]{64}$ ]]
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_evaluation_workflow.py" freeze \
            --stage "$STAGE" --accepted-guidance-sha256 "$SHA" ;;
    submit)
        SHA=${2:?Reviewed evaluation installation plan SHA256 required}
        [[ $SHA =~ ^[0-9a-f]{64}$ ]]
        if test -e "$STAGE/submission.json"; then
            echo PR94_EVALUATION_EXISTING_SUBMISSION_STATUS_ONLY
            exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_evaluation_workflow.py" status --stage "$STAGE"
        fi
        if test -e /raid/vrcelestino/data/cfl-mvp2-evidence/pr94-full-v2-evaluations.claim.json; then
            echo PR94_EVALUATION_CLAIM_EXISTS_PRESERVE_DIAGNOSE >&2
            exit 3
        fi
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_evaluation_workflow.py" submit \
            --stage "$STAGE" --accepted-plan-sha256 "$SHA" ;;
    status|collect)
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_evaluation_workflow.py" "$1" --stage "$STAGE" ;;
    batch)
        INDEX=${2:?Group index required}
        [[ $INDEX =~ ^[0-9]+$ ]]
        test "${PR94_EVALUATION_STAGE:?}" = "$STAGE"
        exec "$PYTHON" -B "$SOURCE/scripts/evidence/pr94_evaluation_workflow.py" run \
            --stage "$STAGE" --index "$INDEX" ;;
    *) echo 'PR94 evaluation: inspect GUIDANCE_SHA | submit PLAN_SHA | status | collect' >&2; exit 2 ;;
esac
