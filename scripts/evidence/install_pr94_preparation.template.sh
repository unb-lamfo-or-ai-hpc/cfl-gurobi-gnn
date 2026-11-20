#!/usr/bin/env bash
# Metadata/source installation only. No sbatch, Gurobi, Torch import or inference.
set -euo pipefail
test "$(hostname -s)" = dgx-dasci
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
COMMIT=__REVIEWED_COMMIT__
BASE=/raid/vrcelestino/data/cfl-mvp2-evidence
CONFIG=${1:?Private configuration file required}
EXPECTED_CONFIG_SHA=${2:?Private configuration SHA256 required}
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]]
[[ $EXPECTED_CONFIG_SHA =~ ^[0-9a-f]{64}$ ]]
case "$CONFIG" in "$BASE"/pr94-inputs-*.private.json) ;; *) echo INVALID_CONFIG_PATH; exit 2;; esac
printf '%s  %s\n' "$EXPECTED_CONFIG_SHA" "$CONFIG" | sha256sum -c -
test -d "$BASE"
STAGE="$BASE/pr94-preparation-${COMMIT:0:12}"
test ! -e "$STAGE"
umask 077
mkdir -- "$STAGE"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 GIT_OPTIONAL_LOCKS=0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
unset PYTHONHOME PYTHONPATH
timeout 600 nice -n 19 git clone --single-branch --branch docs/mvp2-solver-seed-protocol \
    --no-checkout https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git "$STAGE/source"
git -C "$STAGE/source" checkout --detach "$COMMIT"
test "$(git -C "$STAGE/source" rev-parse HEAD)" = "$COMMIT"
python -B - "$STAGE" "$CONFIG" <<'PY'
import json, os, resource, sys
from pathlib import Path
stage=Path(sys.argv[1]).resolve(strict=True)
source=stage/"source"
sys.path.insert(0,str(source/"scripts/evidence"))
import pr94_isolated_preparation as flow
os.nice(19)
soft,hard=resource.getrlimit(resource.RLIMIT_AS)
limit=min([x for x in (16*1024**3,soft,hard) if x!=resource.RLIM_INFINITY])
resource.setrlimit(resource.RLIMIT_AS,(limit,hard))
config=flow.read(Path(sys.argv[2]))
if not config["checkpoint_path"]:
    checkpoint,proof=flow.find_checkpoint()
    config["checkpoint_path"]=str(checkpoint)
else:
    checkpoint=flow.safe_file(config["checkpoint_path"])
    flow.need(flow.file_sha(checkpoint)==flow.CHECKPOINT,"checkpoint_hash")
    proof={"scope":"operator_supplied_exact_checkpoint_bytes","checkpoint_sha256":flow.CHECKPOINT}
flow.write_once(stage/"checkpoint-provenance.json",proof)
request=stage/"inputs-request.private.json"
flow.write_once(request,config)
frozen=flow.freeze(stage,request)
result=flow.inspect(stage)
print("ARQUIVO_HPC="+result["ARQUIVO_HPC"])
print("SHA256="+result["SHA256"])
print("PLAN_SHA256="+frozen["plan_sha256"])
print("MODELOS_CONFERIDOS=6")
print("OTIMIZACOES_NOVAS=0")
print("INFERENCIAS_NOVAS=0")
print("BYTES_ZIP="+str(result["BYTES_ZIP"]))
PY
