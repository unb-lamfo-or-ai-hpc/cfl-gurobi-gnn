#!/bin/bash
# SPDX-License-Identifier: MIT
# Two read-only diagnostics. Never alter the primary data checkout or submit solves.
set -euo pipefail
export PR65_EXEC_DIR="$(pwd -P)"
export PR65_DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
unset PR65_ORIGINAL_OUTPUT
ROOT=/raid/vrcelestino/data/cfl-mvp2-evidence
test -f "${PR65_EXEC_DIR}/scripts/evidence/collect_computational_ledger.py"
test -d "${PR65_DATA_ROOT}/raw/MILPBench/CFL"
test -f /home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
python3 -c 'import gurobipy, pyarrow.parquet; print("PR65_RUNTIME_IMPORTS_OK")'
python3 -m unittest discover -s tests/evidence
python3 scripts/evidence/collect_class_statistics.py preflight \
  --raw-root "${PR65_DATA_ROOT}/raw/MILPBench/CFL"
test -z "$(git status --porcelain --untracked-files=no)"
mkdir -p "${ROOT}"
export PR65_OUTPUT
PR65_OUTPUT="$(mktemp -d "${ROOT}/pr65-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
git rev-parse HEAD > "${PR65_OUTPUT}/source_commit.txt"
sacct -u "$(id -un)" -S 2026-09-01 -E now --parsable2 \
  --format=JobID%64,JobName%80,State%32,ExitCode,ElapsedRaw,TotalCPU,AllocCPUS,AllocTRES%200,MaxRSS,ReqMem \
  > "${PR65_OUTPUT}/slurm_accounting.private.txt"
python3 - "${PR65_OUTPUT}/slurm_accounting.private.txt" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, 'scripts/evidence')
from collect_computational_ledger import hardware
rows = hardware(Path(sys.argv[1]).read_text())
if not rows:
    raise SystemExit('No historical Slurm accounting available; inspect before submitting')
print('PR65_ACCOUNTING_PREFLIGHT_OK')
PY
LEDGER_JOB=$(sbatch --parsable --partition=batch --export=ALL \
  --chdir="${PR65_EXEC_DIR}" --output="${PR65_OUTPUT}/ledger-%j.out" \
  --error="${PR65_OUTPUT}/ledger-%j.err" scripts/slurm/dasci/collect_pr65_ledger.sbs)
printf 'LEDGER_JOB=%s\n' "${LEDGER_JOB}" | tee "${PR65_OUTPUT}/submission.txt"
CLASS_JOB=$(sbatch --parsable --partition=batch --export=ALL \
  --chdir="${PR65_EXEC_DIR}" --output="${PR65_OUTPUT}/classes-%j.out" \
  --error="${PR65_OUTPUT}/classes-%j.err" scripts/slurm/dasci/collect_pr65_classes.sbs)
printf 'CLASS_JOB=%s\nOUTPUT=%s\nEXEC=%s\n' "${CLASS_JOB}" "${PR65_OUTPUT}" "${PR65_EXEC_DIR}" \
  | tee -a "${PR65_OUTPUT}/submission.txt"
echo PR65_DIAGNOSTICS_SUBMITTED_NO_OPTIMIZATION_NO_TRAINING
