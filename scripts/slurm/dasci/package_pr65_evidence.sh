#!/bin/bash
# SPDX-License-Identifier: MIT
# Explicit public allowlist; private inventories and raw cluster logs stay on HPC.
set -euo pipefail
OUTPUT="${1:?provide the exact OUTPUT printed by launch_pr65_evidence.sh}"
test "$(realpath -m "${OUTPUT}")" = "${OUTPUT}"
case "${OUTPUT}" in /raid/vrcelestino/data/cfl-mvp2-evidence/pr65-*) ;; *) exit 1 ;; esac
test -d "${OUTPUT}"
CLASS_ROOT="${2:-${OUTPUT}}"
test "$(realpath -m "${CLASS_ROOT}")" = "${CLASS_ROOT}"
if [ "${CLASS_ROOT}" != "${OUTPUT}" ]; then
  case "${CLASS_ROOT}" in "${OUTPUT}"/classes-recovery-*) ;; *) exit 1 ;; esac
fi
test ! -e "${CLASS_ROOT}/pr65_evidence.tar.gz"
python3 scripts/evidence/collect_computational_ledger.py verify --output "${OUTPUT}/ledger"
python3 scripts/evidence/collect_class_statistics.py verify --output "${CLASS_ROOT}/classes"
python3 - "${CLASS_ROOT}/source_commit.txt" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink() or not re.fullmatch(r'[0-9a-f]{40}\n', path.read_text()):
    raise SystemExit('Source commit receipt is invalid; preserve outputs for inspection')
PY
RECOVERY_FILES=()
if [ "${CLASS_ROOT}" != "${OUTPUT}" ]; then
  python3 scripts/evidence/collect_class_statistics.py verify --output "${OUTPUT}/classes"
  python3 - "${OUTPUT}" "${CLASS_ROOT}" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path
original, recovery = map(Path, sys.argv[1:])
def source(root):
    path = root / 'source_commit.txt'
    text = path.read_text()
    if path.is_symlink() or not re.fullmatch(r'[0-9a-f]{40}\n', text):
        raise SystemExit('Invalid source receipt; preserve outputs')
    return text.strip()
report = json.loads((recovery / 'classes/class_statistics_report.json').read_text())
if report.get('gate_status') != 'complete_model_read' or report.get('observed_parents') != 90:
    raise SystemExit('Class recovery is incomplete; preserve diagnostics')
receipt = {
    'schema_version': 1,
    'scope': 'class_only_recovery_reusing_unchanged_ledger',
    'ledger_source_commit': source(original),
    'classes_source_commit': source(recovery),
    'reused_ledger_report_sha256': hashlib.sha256((original / 'ledger/ledger_report.json').read_bytes()).hexdigest(),
    'superseded_class_report_sha256': hashlib.sha256((original / 'classes/class_statistics_report.json').read_bytes()).hexdigest(),
    'optimization_runs': 0,
    'training_runs': 0,
}
with (recovery / 'recovery_receipt.json').open('x', encoding='utf-8') as stream:
    json.dump(receipt, stream, indent=2, sort_keys=True)
    stream.write('\n')
PY
  RECOVERY_FILES=(recovery_receipt.json)
fi
tar -czf "${CLASS_ROOT}/pr65_evidence.tar.gz" -C "${OUTPUT}" \
  ledger/parent_solver_ledger.csv ledger/training_membership.csv \
  ledger/incumbent_table_inventory.csv ledger/augmentation_lineage.csv \
  ledger/hardware_usage.csv ledger/missing_evidence.json ledger/ledger_report.json \
  ledger/SHA256SUMS.txt -C "${CLASS_ROOT}" source_commit.txt \
  classes/class_instance_statistics.csv \
  classes/class_descriptive_statistics.csv classes/class_statistics_report.json \
  classes/SHA256SUMS.txt "${RECOVERY_FILES[@]}"
sha256sum "${CLASS_ROOT}/pr65_evidence.tar.gz"
printf 'REMOTE_PACKAGE=vrcelestino@dgx-dasci.ujaen.es:%s/pr65_evidence.tar.gz\n' "${CLASS_ROOT}"
echo PR65_SHAREABLE_PACKAGE_PREPARED_NOT_SCIENTIFIC_CERTIFICATION
