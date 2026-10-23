#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == batch ]]; then
  SOURCE=${E0_SOURCE:?missing submitted source}
else
  SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
fi
STAGE=$(dirname "$SOURCE")
case "$STAGE" in /raid/vrcelestino/data/cfl-mvp2-evidence/e0/solve-*) ;; *) exit 2;; esac
test "$(hostname -s)" = dgx-dasci
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export GRB_LICENSE_FILE=/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
unset PYTHONPATH PYTHONHOME
case "${1:-}" in
 submit)
  test "${CONDA_DEFAULT_ENV:-}" = tfm_env
  test -r "$GRB_LICENSE_FILE"
  test ! -e "$STAGE/job_id.txt"
  test ! -e "$STAGE/run"
  E0_SOURCE=$SOURCE
  E0_PYTHON=$(command -v python3)
  export E0_SOURCE E0_PYTHON
  "$E0_PYTHON" -B "$SOURCE/scripts/evidence/e0_three_method_executor.py" plan --stage "$STAGE"
  # Executing this explicit submit command authorizes this documented one-job budget.
  # The claim is retained on any error; never repeat sbatch automatically.
  mkdir "$STAGE/submission.started"
  for name in ${!SBATCH_@}; do unset "$name"; done
  sbatch --parsable --export=ALL --partition=batch --nodes=1-1 --ntasks=1 \
    --cpus-per-task=1 --hint=nomultithread --mem=64G --time=20:00:00 --no-requeue \
    --job-name=cfl_e0_three --chdir="$SOURCE" \
    --output="$STAGE/job-%j.out" --error="$STAGE/job-%j.err" \
    "$SOURCE/scripts/evidence/operate_e0_solves.sh" batch > "$STAGE/submission.reply"
  JOB=$(cut -d';' -f1 "$STAGE/submission.reply")
  [[ "$JOB" =~ ^[0-9]+$ ]]
  printf '%s\n' "$JOB" > "$STAGE/job_id.txt"
  printf 'E0_SOLVE_JOB=%s\nE0_SOLVE_STAGE=%s\n' "$JOB" "$STAGE"
  ;;
 batch)
  test "${CONDA_DEFAULT_ENV:-}" = tfm_env
  test "${SLURM_RESTART_COUNT:-0}" = 0
  mkdir "$STAGE/batch.started"
  exec timeout --signal=TERM --kill-after=15s 71400s "$E0_PYTHON" -B \
    "$SOURCE/scripts/evidence/e0_three_method_executor.py" run --stage "$STAGE"
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
    python3 -B "$SOURCE/scripts/evidence/e0_three_method_executor.py" collect --stage "$STAGE"
  fi
  ;;
 *) echo 'Usage: operate_e0_solves.sh submit|status|collect'; exit 2;;
esac
