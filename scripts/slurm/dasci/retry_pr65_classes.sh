#!/bin/bash
# SPDX-License-Identifier: MIT
# Retry only original model reading; preserve the previous ledger and package.
set -euo pipefail
ORIGINAL="${1:?provide the original PR65 OUTPUT}"
test "$(realpath -m "${ORIGINAL}")" = "${ORIGINAL}"
case "${ORIGINAL}" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr65-*) ;; *) exit 1 ;; esac
export PR65_EXEC_DIR="$(pwd -P)"
export PR65_DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
test -f /home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
test -z "$(git status --porcelain --untracked-files=no)"
python3 -m unittest discover -s tests/evidence
python3 scripts/evidence/collect_computational_ledger.py verify --output "${ORIGINAL}/ledger"
python3 scripts/evidence/collect_class_statistics.py verify --output "${ORIGINAL}/classes"
python3 scripts/evidence/collect_class_statistics.py preflight \
  --raw-root "${PR65_DATA_ROOT}/raw/MILPBench/CFL"
export PR65_OUTPUT PR65_ORIGINAL_OUTPUT="${ORIGINAL}"
PR65_OUTPUT="$(mktemp -d "${ORIGINAL}/classes-recovery-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
git rev-parse HEAD > "${PR65_OUTPUT}/source_commit.txt"
CLASS_JOB=$(sbatch --parsable --partition=batch --export=ALL \
  --chdir="${PR65_EXEC_DIR}" --output="${PR65_OUTPUT}/classes-%j.out" \
  --error="${PR65_OUTPUT}/classes-%j.err" scripts/slurm/dasci/collect_pr65_classes.sbs)
printf 'CLASS_JOB=%s\nCLASS_RECOVERY=%s\nORIGINAL_OUTPUT=%s\n' \
  "${CLASS_JOB}" "${PR65_OUTPUT}" "${ORIGINAL}" | tee "${PR65_OUTPUT}/submission.txt"
echo PR65_CLASS_ONLY_RECOVERY_SUBMITTED_NO_OPTIMIZATION_NO_TRAINING
