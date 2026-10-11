#!/usr/bin/env bash
# One bounded read-only preparation. No scheduler, solver, training or inference.
set -euo pipefail
trap 'echo PR86_BINDING_STOPPED_PRESERVE_OUTPUT_NO_RETRY >&2' ERR
SHA=${1:?Expected the frozen source commit, not an approval phrase}
[[ $SHA =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname -s) == dgx-dasci ]]
[[ ${CONDA_DEFAULT_ENV:-} == tfm_env ]]
STAGE=/raid/vrcelestino/data/cfl-mvp2-evidence/pr86/bindings-${SHA:0:12}
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
[[ $SOURCE == "$STAGE/source" ]]
[[ $(<"$STAGE/source_commit.txt") == "$SHA" ]]
[[ ! -e "$STAGE/prepared" ]]
(
  umask 077
  ulimit -v 16777216
  export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
  timeout --signal=TERM --kill-after=5s 660s python -B \
    "$SOURCE/scripts/evidence/bind_pr86_existing_starts.py" prepare \
    --data-root /raid/vrcelestino/data/cfl-gurobi-gnn/data \
    --inference-stage /raid/vrcelestino/data/cfl-mvp2-evidence/e0/inference-d6e7b20c1dfd \
    --output "$STAGE/prepared" --source-commit "$SHA"
)
(cd "$STAGE/prepared/public" && sha256sum -c SHA256SUMS.txt)
echo "PR86_PUBLIC_OUTPUT=$STAGE/prepared/public"
echo PR86_TEN_BINDINGS_PREPARED_NO_JOB_NO_SOLVER_NO_INFERENCE_NO_TRAINING
