#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == batch ]]; then
  SOURCE=${PR80_SOURCE:?missing source}
else
  SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
fi
STAGE=$(dirname "$SOURCE")
case "$STAGE" in
  /raid/vrcelestino/data/cfl-mvp2-evidence/pr80/integrated-*) ;;
  *) echo PR80_BAD_STAGE; exit 2 ;;
esac
test "$(hostname -s)" = dgx-dasci
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export GRB_LICENSE_FILE=/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
unset PYTHONPATH PYTHONHOME
case "${1:-}" in
 submit|submit-remaining)
  test "${CONDA_DEFAULT_ENV:-}" = tfm_env
  PR80_PYTHON=$(command -v python3)
  PR80_SOURCE=$SOURCE
  PR80_COMMIT=$(git -C "$SOURCE" rev-parse HEAD)
  PR80_REUSE_RETURN=
  if [[ "$1" == submit-remaining ]]; then
    PR80_REUSE_RETURN=/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/integrated-e80a7d97f729/public_return.json
    "$PR80_PYTHON" -B "$SOURCE/scripts/evidence/pr80_integrated.py" verify-prior \
      --reuse-return "$PR80_REUSE_RETURN" --output "$STAGE"
  fi
  git -C "$SOURCE" diff --exit-code HEAD
  test ! -e "$STAGE/run"
  test ! -e "$STAGE/job_id.txt"
  mkdir "$STAGE/submission.started"
  export PR80_PYTHON PR80_SOURCE PR80_COMMIT PR80_REUSE_RETURN
  for name in ${!SBATCH_@}; do unset "$name"; done
  sbatch --parsable --partition=batch --nodes=1-1 --ntasks=1 --cpus-per-task=4 \
    --hint=nomultithread --mem=32G --gres=gpu:1 --time=00:45:00 --no-requeue \
    --job-name=cfl_c1_integrated --chdir="$SOURCE" \
    --output="$STAGE/job-%j.out" --error="$STAGE/job-%j.err" \
    "$SOURCE/scripts/evidence/operate_pr80_integrated.sh" batch > "$STAGE/submission.reply"
  JOB=$(cut -d';' -f1 "$STAGE/submission.reply")
  [[ "$JOB" =~ ^[0-9]+$ ]]
  printf '%s\n' "$JOB" > "$STAGE/job_id.txt"
  printf 'PR80_INTEGRATED_JOB=%s\nSTAGE=%s\n' "$JOB" "$STAGE"
  ;;
 batch)
  test "${CONDA_DEFAULT_ENV:-}" = tfm_env
  test "${SLURM_JOB_NUM_NODES:-}" = 1
  test "${SLURM_CPUS_PER_TASK:-}" = 4
  test "${SLURM_MEM_PER_NODE:-}" = 32768
  test "${SLURM_RESTART_COUNT:-0}" = 0
  test "$(git -C "$SOURCE" rev-parse HEAD)" = "$PR80_COMMIT"
  git -C "$SOURCE" diff --exit-code HEAD
  mkdir "$STAGE/batch.started"
  REUSE_ARGS=()
  if [[ -n "${PR80_REUSE_RETURN:-}" ]]; then
    REUSE_ARGS=(--reuse-return "$PR80_REUSE_RETURN")
  fi
  exec timeout 2450s "$PR80_PYTHON" -B "$SOURCE/scripts/evidence/pr80_integrated.py" \
    run --data-root /raid/vrcelestino/data/cfl-gurobi-gnn/data --output "$STAGE/run" "${REUSE_ARGS[@]}"
  ;;
 status|collect)
  JOB=$(cat "$STAGE/job_id.txt")
  [[ "$JOB" =~ ^[0-9]+$ ]]
  if [[ "$1" == status ]]; then
    sacct -j "$JOB" --parsable2 --format=JobID,State,ElapsedRaw,ExitCode,TotalCPU,AllocCPUS,ReqMem,MaxRSS
  else
    if [[ ! -f "$STAGE/accounting.txt" ]]; then
      ACCOUNTING=$(sacct -j "$JOB" --parsable2 --format=JobID,State,ElapsedRaw,ExitCode,TotalCPU,AllocCPUS,ReqMem,MaxRSS)
      STATE=$(printf '%s\n' "$ACCOUNTING" | awk -F'|' -v id="$JOB" '$1==id {print $2}')
      case "$STATE" in COMPLETED|FAILED|TIMEOUT|OUT_OF_MEMORY|CANCELLED*|NODE_FAIL|PREEMPTED) ;; *) echo NOT_TERMINAL; exit 2;; esac
      (set -o noclobber; printf '%s\n' "$ACCOUNTING" > "$STAGE/accounting.txt")
    fi
    python3 -B "$SOURCE/scripts/evidence/pr80_integrated.py" package --output "$STAGE"
  fi
  ;;
 *) echo 'Usage: operate_pr80_integrated.sh submit|submit-remaining|status|collect'; exit 2;;
esac
