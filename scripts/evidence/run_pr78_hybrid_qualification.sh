#!/bin/bash
# One separate, no-solver qualification; never an experimental retry.
set -euo pipefail
umask 077
D=/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/hybrid-memory-job3483-v1
SOURCE=/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/recovery-source-173b63d62658
PAYLOAD=7f228eff44a0ed68313508f3708c989e1695d8f8
test "$(hostname -s)" = dgx-dasci
test "${CONDA_DEFAULT_ENV:-}" = tfm_env

case "${1:-}" in
  prepare-submit)
    test -z "${SLURM_JOB_ID:-}"
    mkdir "$D"
    cp -- "$0" "$D/operator.sh"
    for NAME in probe_pr78_executor_gates.py paired_memory_guard_v2.py qualify_pr78_hybrid_memory.py; do
      curl --fail --silent --show-error --location \
        "https://raw.githubusercontent.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/$PAYLOAD/scripts/evidence/$NAME" \
        --output "$D/$NAME"
    done
    printf '%s  %s\n' \
      4922396981eef38ee073f82bce551404377e3fd68cd5db1f8805bb571a5aa872 "$D/probe_pr78_executor_gates.py" \
      faadff7e998d213497237e56c9f373ece0f5fd256a60bb266e4ad279557a238e "$D/paired_memory_guard_v2.py" \
      0cd1e032db9d1f41f7a1d74ba501d2bb3d436c646bdf84ddfc6f0bc722c67240 "$D/qualify_pr78_hybrid_memory.py" \
      | sha256sum -c -
    python3 -B "$D/qualify_pr78_hybrid_memory.py" static --output "$D/static.json"
    for PR78_VAR in ${!SBATCH_@} ${!SRUN_@} ${!SLURM_@}; do unset "$PR78_VAR"; done
    unset BASH_ENV ENV
    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
    mkdir "$D/submission.claim"
    JOB=$(sbatch --parsable --no-requeue --partition=batch \
      --nodes=1 --ntasks=1 --cpus-per-task=16 --hint=nomultithread \
      --mem=64G --time=00:01:00 --job-name=cfl_memory_qual \
      --chdir="$SOURCE" --output="$D/slurm-%j.private.out" --error="$D/slurm-%j.private.err" \
      --wrap="srun --ntasks=1 --cpus-per-task=16 --hint=nomultithread --cpu-bind=verbose python3 -B '$D/qualify_pr78_hybrid_memory.py' allocated --output '$D/qualification.json'")
    [[ "$JOB" =~ ^[0-9]+$ ]]
    printf '%s\n' "$JOB" > "$D/job_id.txt"
    printf 'PR78_MEMORY_QUALIFICATION_JOB=%s\nDIRECTORY=%s\nNO_SOLVER_NO_MATRIX_RETRY\n' "$JOB" "$D"
    ;;
  status)
    JOB=$(cat "$D/job_id.txt")
    [[ "$JOB" =~ ^[0-9]+$ ]]
    sacct -j "$JOB" --format=JobID,State,Elapsed,ExitCode
    ;;
  collect)
    python3 -m json.tool "$D/qualification.json"
    sha256sum "$D/qualification.json"
    ;;
  *)
    printf 'Usage: bash operator.sh prepare-submit|status|collect\n' >&2
    exit 2
    ;;
esac
