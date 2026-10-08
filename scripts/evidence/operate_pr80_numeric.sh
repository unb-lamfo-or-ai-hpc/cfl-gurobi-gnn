#!/usr/bin/env bash
# One bounded technical audit, never a solver run or automatic retry.
set -euo pipefail
# Slurm executes a spool copy: never derive the source tree from that copy.
if [[ "${1:-}" == batch ]]; then
  SOURCE=${PR80_SOURCE:?missing frozen source}
else
  SOURCE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
fi
STAGE=$(dirname "$SOURCE")
case "$STAGE" in
  /raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-*) ;;
  *) echo 'PR80_UNEXPECTED_STAGE'; exit 2 ;;
esac
test "$(hostname -s)" = dgx-dasci
case "${1:-}" in
  submit)
    test ! -e "$STAGE/submission.started"
    test ! -e "$STAGE/job_id.txt"
    test ! -e "$STAGE/run"
    # Atomic claim remains after any ambiguous scheduler response.
    mkdir "$STAGE/submission.started"
    mkdir "$STAGE/run"
    PR80_PYTHON=$(command -v python3)
    PR80_SOURCE=$SOURCE
    export PR80_PYTHON PR80_SOURCE
    for name in ${!SBATCH_@}; do unset "$name"; done
    sbatch --parsable --partition=batch --nodes=1-1 --ntasks=1 \
      --cpus-per-task=1 --hint=nomultithread --mem=16G --time=00:16:00 \
      --no-requeue --job-name=cfl_c1_numeric --chdir="$SOURCE" \
      --output="$STAGE/run/job-%j.out" --error="$STAGE/run/job-%j.err" \
      "$SOURCE/scripts/evidence/operate_pr80_numeric.sh" batch \
      > "$STAGE/submission.reply"
    JOB=$(cut -d';' -f1 "$STAGE/submission.reply")
    [[ "$JOB" =~ ^[0-9]+$ ]]
    printf '%s\n' "$JOB" > "$STAGE/job_id.txt"
    printf 'PR80_NUMERIC_JOB=%s\nSTAGE=%s\nNO_OPTIMIZATION_NO_TRAINING_NO_AUTOMATIC_RETRY\n' "$JOB" "$STAGE"
    ;;
  batch)
    test "${SLURM_JOB_NUM_NODES:-}" = 1
    test "${SLURM_CPUS_PER_TASK:-}" = 1
    test "${SLURM_MEM_PER_NODE:-}" = 16384
    test "${SLURM_RESTART_COUNT:-0}" = 0
    test -z "${SLURM_JOB_GPUS:-}"
    test -z "${SLURM_STEP_GPUS:-}"
    mkdir "$STAGE/batch.started"
    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
    export NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
    exec "$PR80_PYTHON" -B "$SOURCE/scripts/evidence/audit_sprint_c_numeric.py" \
      collect --data-root /raid/vrcelestino/data/cfl-gurobi-gnn/data \
      --output "$STAGE/run/results"
    ;;
  status)
    JOB=$(cat "$STAGE/job_id.txt")
    [[ "$JOB" =~ ^[0-9]+$ ]]
    sacct -j "$JOB" --format=JobID,State,Elapsed,ExitCode,MaxRSS
    ;;
  collect)
    JOB=$(cat "$STAGE/job_id.txt")
    [[ "$JOB" =~ ^[0-9]+$ ]]
    ACCOUNTING=$(sacct -X -j "$JOB" --noheader --parsable2 --format=JobIDRaw,State,ExitCode)
    STATE=$(printf '%s\n' "$ACCOUNTING" | awk -F'|' -v id="$JOB" '$1==id {print $2}')
    case "$STATE" in
      COMPLETED|FAILED|TIMEOUT|OUT_OF_MEMORY|CANCELLED*) ;;
      *) printf 'NOT_TERMINAL_OR_UNAVAILABLE=%s\n' "$STATE"; exit 2 ;;
    esac
    test -f "$STAGE/run/results/numeric.json"
    sha256sum "$STAGE/run/results/numeric.json"
    printf 'PR80_NUMERIC_OUTPUT=%s\nJOB_STATE=%s\n' "$STAGE/run/results" "$STATE"
    ;;
  *) echo 'Usage: bash operate_pr80_numeric.sh submit|status|collect'; exit 2 ;;
esac
