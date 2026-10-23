#!/bin/bash
# SPDX-License-Identifier: MIT
# Install a pinned detached checkout; never switch/clean the primary checkout.
set -euo pipefail
test "$(hostname -s)" = dgx-dasci
SOURCE="${1:?pass the published PR66 source commit}"
[[ "${SOURCE}" =~ ^[0-9a-f]{40}$ ]]
REPO=/raid/vrcelestino/data/cfl-gurobi-gnn
ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn-worktrees
REPO="$(realpath "${REPO}")"
git_here() { git -c "safe.directory=${REPO}" -C "${REPO}" "$@"; }
ORIGIN="$(git_here remote get-url origin)"
case "${ORIGIN}" in
  https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git|git@github.com:unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git) ;;
  *) echo '[ERROR] canonical origin required' >&2; exit 1 ;;
esac
git_here fetch origin feature/pr66-reconciliation-thread-pilot
test "$(git_here rev-parse FETCH_HEAD)" = "${SOURCE}"
mkdir -p "${ROOT}"
EXEC="${ROOT}/pr66-thread-screen-${SOURCE:0:12}"
if test ! -e "${EXEC}"; then
  git_here worktree add --detach "${EXEC}" "${SOURCE}"
fi
test "$(git -c "safe.directory=${EXEC}" -C "${EXEC}" rev-parse HEAD)" = "${SOURCE}"
test -z "$(git -c "safe.directory=${EXEC}" -C "${EXEC}" status --porcelain)"
printf 'PR66_PINNED_CHECKOUT_OK\nSOURCE_COMMIT=%s\nEXEC=%s\n' "${SOURCE}" "${EXEC}"
echo NO_PRIMARY_CHECKOUT_CHANGE_NO_JOB_SUBMISSION
