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
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
unset PYTHONPATH PYTHONHOME
case "${1:-}" in
  prepare)
    # Fresh private CPU audit environment. Never mutate tfm_env or reuse a partial install.
    test ! -e "$STAGE/venv"
    test ! -e "$STAGE/environment.started"
    test ! -e "$STAGE/submission.started"
    python3 -B -c 'import sys; assert sys.version_info[:2] == (3, 10)'
    mkdir "$STAGE/environment.started" "$STAGE/tmp"
    export TMPDIR="$STAGE/tmp"
    python3 -B -m venv "$STAGE/venv"
    timeout 900s "$STAGE/venv/bin/python3" -m pip --isolated install \
      --index-url https://pypi.org/simple --no-cache-dir --retries 0 --timeout 30 \
      --only-binary=:all: pip==25.3
    timeout 900s "$STAGE/venv/bin/python3" -m pip --isolated install \
      --index-url https://pypi.org/simple --no-cache-dir --retries 0 --timeout 30 \
      --only-binary=:all: --report "$STAGE/install-report.private.json" \
      'https://download-r2.pytorch.org/whl/cpu/torch-2.10.0%2Bcpu-cp310-cp310-manylinux_2_28_x86_64.whl#sha256=a280ffaea7b9c828e0c1b9b3bd502d9b6a649dc9416997b69b84544bd469f215' \
      torch-geometric==2.7.0 numpy==1.26.4 scipy==1.15.3 gurobipy==13.0.1 packaging==26.0
    "$STAGE/venv/bin/python3" -m pip --isolated check
    "$STAGE/venv/bin/python3" -m pip --isolated freeze --all > "$STAGE/environment.freeze.txt"
    timeout 90s "$STAGE/venv/bin/python3" -B "$SOURCE/scripts/evidence/sprint_c_runtime.py" \
      --output "$STAGE/runtime-prepared.json"
    ;;
  submit)
    test ! -e "$STAGE/submission.started"
    test ! -e "$STAGE/job_id.txt"
    test ! -e "$STAGE/run"
    PR80_PYTHON="$STAGE/venv/bin/python3"
    test -x "$PR80_PYTHON"
    # A failed preflight stops before the scheduler claim or any submission.
    timeout 90s "$PR80_PYTHON" -B "$SOURCE/scripts/evidence/sprint_c_runtime.py" \
      --output "$STAGE/runtime-presubmit.json"
    # Atomic claim remains after any ambiguous scheduler response.
    mkdir "$STAGE/submission.started"
    mkdir "$STAGE/run"
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
    test "$PR80_PYTHON" = "$STAGE/venv/bin/python3"
    timeout 30s "$PR80_PYTHON" -B "$SOURCE/scripts/evidence/sprint_c_runtime.py" \
      --output "$STAGE/runtime-batch.json"
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
    "$STAGE/venv/bin/python3" -B "$SOURCE/scripts/evidence/sprint_c_runtime.py" --package "$STAGE"
    ;;
  *) echo 'Usage: bash operate_pr80_numeric.sh prepare|submit|status|collect'; exit 2 ;;
esac
