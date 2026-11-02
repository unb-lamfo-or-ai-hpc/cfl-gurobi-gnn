#!/usr/bin/env bash
# Run by the author only, after exact-head CI and review of guidance3784.
# Installs/inspects only: no scientific calls or scheduler mutations.
set -euo pipefail
COMMIT=${1:?Reviewed evaluation source commit required}
GUIDANCE_SHA=${2:?Reviewed guidance metadata member SHA256 required}
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]]
[[ $GUIDANCE_SHA =~ ^[0-9a-f]{64}$ ]]
test "$(hostname -s)" = dgx-dasci
test "$(id -un)" = vrcelestino
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
EVIDENCE=/raid/vrcelestino/data/cfl-mvp2-evidence
test -d "$EVIDENCE"
S="$EVIDENCE/pr94-evaluation-${COMMIT:0:12}"
if test -e "$S"; then
    echo PR94_EVALUATION_STAGE_EXISTS_PRESERVE_DIAGNOSE >&2
    exit 3
fi
python -B -c 'import shutil,sys; assert shutil.disk_usage(sys.argv[1]).free >= 320*1024**3, "PR94_EVALUATION_NEEDS_320_GiB_FREE"' "$EVIDENCE"
umask 077
mkdir "$S"
mkdir "$S/claims" "$S/run" "$S/runtime"
mkdir "$S/runtime/tmp" "$S/runtime/cache" "$S/runtime/matplotlib"
mkdir "$S/runtime/torch" "$S/runtime/extensions" "$S/runtime/cuda"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 GIT_OPTIONAL_LOCKS=0
export TMPDIR="$S/runtime/tmp" TMP="$S/runtime/tmp" TEMP="$S/runtime/tmp"
export XDG_CACHE_HOME="$S/runtime/cache"
git clone --no-checkout https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git "$S/source"
git -C "$S/source" checkout --detach "$COMMIT"
test "$(git -C "$S/source" rev-parse HEAD)" = "$COMMIT"
nice -n 10 bash "$S/source/scripts/evidence/operate_pr94_evaluation.sh" inspect "$GUIDANCE_SHA"
