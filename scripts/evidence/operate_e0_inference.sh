#!/usr/bin/env bash
set -euo pipefail
SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
STAGE=$(dirname "$SOURCE")
case "$STAGE" in /raid/vrcelestino/data/cfl-mvp2-evidence/e0/inference-*) ;; *) exit 2;; esac
test "$(hostname -s)" = dgx-dasci
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
unset PYTHONPATH PYTHONHOME
case "${1:-}" in
 submit)
  test "${CONDA_DEFAULT_ENV:-}" = tfm_env
  test ! -e "$STAGE/job_id.txt"
  test ! -e "$STAGE/run"
  E0_PYTHON=$(command -v python3)
  export E0_PYTHON
  "$E0_PYTHON" -B "$SOURCE/scripts/evidence/e0_frozen_inference.py" plan --output "$STAGE/plan.json"
  mkdir "$STAGE/submission.started"
  for name in ${!SBATCH_@}; do unset "$name"; done
  sbatch --parsable --partition=batch --nodes=1-1 --ntasks=1 --cpus-per-task=4 \
    --hint=nomultithread --mem=32G --gres=gpu:1 --time=00:40:00 --no-requeue \
    --job-name=cfl_e0_inference --chdir="$SOURCE" \
    --output="$STAGE/job-%j.out" --error="$STAGE/job-%j.err" \
    "$SOURCE/scripts/evidence/operate_e0_inference.sh" batch > "$STAGE/submission.reply"
  JOB=$(cut -d';' -f1 "$STAGE/submission.reply")
  [[ "$JOB" =~ ^[0-9]+$ ]]
  printf '%s\n' "$JOB" > "$STAGE/job_id.txt"
  printf 'E0_INFERENCE_JOB=%s\nE0_STAGE=%s\n' "$JOB" "$STAGE"
  ;;
 batch)
  test "${CONDA_DEFAULT_ENV:-}" = tfm_env
  test "${SLURM_RESTART_COUNT:-0}" = 0
  mkdir "$STAGE/batch.started"
  exec timeout 2200s "$E0_PYTHON" -B "$SOURCE/scripts/evidence/e0_frozen_inference.py" run \
    --data-root /raid/vrcelestino/data/cfl-gurobi-gnn/data --output "$STAGE/run"
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
    python3 -B "$SOURCE/scripts/evidence/e0_frozen_inference.py" package --output "$STAGE"
  fi
  ;;
 *) echo 'Usage: operate_e0_inference.sh submit|status|collect'; exit 2;;
esac
