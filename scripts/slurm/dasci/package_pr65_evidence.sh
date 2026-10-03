#!/bin/bash
# SPDX-License-Identifier: MIT
# Explicit public allowlist; private inventories and raw cluster logs stay on HPC.
set -euo pipefail
OUTPUT="${1:?provide the exact OUTPUT printed by launch_pr65_evidence.sh}"
test "$(realpath -m "${OUTPUT}")" = "${OUTPUT}"
case "${OUTPUT}" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr65-*) ;; *) exit 1 ;; esac
test -d "${OUTPUT}"
test ! -e "${OUTPUT}/pr65_evidence.tar.gz"
python3 scripts/evidence/collect_computational_ledger.py verify --output "${OUTPUT}/ledger"
python3 scripts/evidence/collect_class_statistics.py verify --output "${OUTPUT}/classes"
python3 - "${OUTPUT}/source_commit.txt" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink() or not re.fullmatch(r'[0-9a-f]{40}\n', path.read_text()):
    raise SystemExit('Source commit receipt is invalid; preserve outputs for inspection')
PY
tar -czf "${OUTPUT}/pr65_evidence.tar.gz" -C "${OUTPUT}" \
  source_commit.txt \
  ledger/parent_solver_ledger.csv ledger/training_membership.csv \
  ledger/incumbent_table_inventory.csv ledger/augmentation_lineage.csv \
  ledger/hardware_usage.csv ledger/missing_evidence.json ledger/ledger_report.json \
  ledger/SHA256SUMS.txt classes/class_instance_statistics.csv \
  classes/class_descriptive_statistics.csv classes/class_statistics_report.json classes/SHA256SUMS.txt
sha256sum "${OUTPUT}/pr65_evidence.tar.gz"
printf 'REMOTE_PACKAGE=vrcelestino@dgx-dasci.ujaen.es:%s/pr65_evidence.tar.gz\n' "${OUTPUT}"
echo PR65_SHAREABLE_PACKAGE_PREPARED_NOT_SCIENTIFIC_CERTIFICATION
