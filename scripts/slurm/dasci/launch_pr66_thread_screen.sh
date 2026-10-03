#!/bin/bash
# SPDX-License-Identifier: MIT
set -euo pipefail
export PR66_EXEC_DIR="$(pwd -P)"
export PR66_RAW_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data/raw/MILPBench/CFL
ROOT=/raid/vrcelestino/data/cfl-mvp2-evidence/pr66
test "$(hostname -s)" = dgx-dasci
test -s /home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
test -s "${PR66_ROLE_PLAN:?set the qualified PR57 gasse_training_plan.json path}"
test -n "${PR66_ROLE_PLAN_SHA:?set its previously verified SHA256}"
test "${PR66_SCREEN_AUTHORIZED:-no}" = yes
test -z "$(git status --porcelain)"
python3 -m unittest discover -s tests/evidence
mkdir -p "${ROOT}"
# mktemp reserves the parent, not the fresh plan directory required by freeze.
RUN="$(mktemp -d "${ROOT}/screen-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
export PR66_PLAN_DIR="${RUN}/plan"
python3 scripts/evidence/pr66_thread_pilot.py freeze \
  --raw-root "${PR66_RAW_ROOT}" --role-plan "${PR66_ROLE_PLAN}" \
  --expected-role-sha "${PR66_ROLE_PLAN_SHA}" --plan-dir "${PR66_PLAN_DIR}"
export PR66_PLAN_SHA
PR66_PLAN_SHA="$(sha256sum "${PR66_PLAN_DIR}/pilot_plan.json" | cut -d' ' -f1)"
git rev-parse HEAD > "${RUN}/source_commit.txt"
scontrol show config > "${RUN}/slurm_config.private.txt"
lscpu > "${RUN}/topology.private.txt"
JOB=$(sbatch --parsable --export=ALL --chdir="${PR66_EXEC_DIR}" \
  --output="${RUN}/screen-%j.out" --error="${RUN}/screen-%j.err" \
  scripts/slurm/dasci/submit_pr66_thread_screen.sbs)
JOB="${JOB%%;*}"
[[ "${JOB}" =~ ^[0-9]+$ ]]
printf 'PILOT_JOB=%s\nOUTPUT=%s\nPLAN_SHA256=%s\n' "${JOB}" "${RUN}" "${PR66_PLAN_SHA}" \
  | tee "${RUN}/submission.txt"
echo PR66_SCREEN_SUBMITTED_NO_EXTENSION_NO_GPU_NO_EXCLUSIVE
