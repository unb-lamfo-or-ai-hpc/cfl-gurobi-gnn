#!/bin/bash
# SPDX-License-Identifier: MIT
# Run from an exact, reviewed checkout; never restart start after an error.
set -euo pipefail
umask 077
test "$(hostname -s)" = dgx-dasci
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
test -z "${SLURM_JOB_ID:-}"
test "$#" -ge 2
ACTION=$1
EXPECTED=$2
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]]
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED"
test -z "$(git -C "$SOURCE" status --porcelain --untracked-files=all)"
ROOT=/raid/vrcelestino/data/cfl-mvp2-evidence/pr78
STAGE="$ROOT/medium-continuation-${EXPECTED:0:12}"
test "$SOURCE" = "$STAGE/source"
FLOW="$STAGE/flow"
WORKFLOW="$SOURCE/scripts/evidence/pr78_medium_workflow.py"
export PYTHONDONTWRITEBYTECODE=1
case "$ACTION" in
  start)
    test "$#" -eq 3
    test "$3" = --approve-additional-medium-budget
    test ! -e "$FLOW"
    test -f /home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
    export GRB_LICENSE_FILE=/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
    bash -n "$SOURCE/scripts/slurm/dasci/submit_pr78_medium.sbs"
    cd -- "$SOURCE"
    # Fail before preparation or budget recording if exact-head CI is incomplete.
    python3 -B -c 'import sys; sys.path.insert(0,"scripts/evidence"); from recover_pr78_job3481 import review_ci; review_ci(sys.argv[1]); print("PR78_FOUR_EXACT_HEAD_CI_ARMS_OK")' "$EXPECTED"
    python3 -B -m unittest discover -s tests/evidence -p test_pr78_medium_workflow.py
    OLD="$ROOT/recovery-job3482-v3/flow"
    python3 -B "$WORKFLOW" prepare --directory "$FLOW" \
      --easy-return "$OLD/return-easy" --medium-return "$OLD/return-medium"
    printf '%s\n' 'Explicit new budget: 1 job, at most 5 optimizations / 18000 solver seconds / 19800 wall seconds.' \
      'Campaign reservation: 3 jobs / 11 slots / 39600 solver seconds; delta +1 job / +1 slot / +3600 seconds.' \
      'Medium only, order 16,8,2,1,4; easy is never repeated. No automatic retry, requeue or extension.'
    python3 -B "$WORKFLOW" approve --directory "$FLOW" --approve-additional-medium-budget
    APPROVAL_SHA=$(sha256sum "$FLOW/approval.json")
    APPROVAL_SHA=${APPROVAL_SHA%% *}
    python3 -B "$WORKFLOW" submit --directory "$FLOW" --approval-sha "$APPROVAL_SHA"
    ;;
  status|collect)
    test "$#" -eq 2
    python3 -B "$WORKFLOW" "$ACTION" --directory "$FLOW"
    ;;
  *) printf '%s\n' 'Use start SHA --approve-additional-medium-budget, status SHA, or collect SHA.' >&2; exit 2 ;;
esac
