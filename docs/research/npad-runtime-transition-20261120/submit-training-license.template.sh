# Author CLI: one synthetic GNN-training/native-license qualification before cloning.
# Instantiate placeholders; run once. Preserve failures; do not repeat or remove stage.
(
set -euo pipefail
test "$(id -un)" = __NPAD_USER__
case "$(hostname -s)" in service[0-9]*) ;; *) exit 1;; esac
umask 077
T=/home/__NPAD_USER__/venv313_g14
O=/home/__NPAD_USER__/venv313
S=/scratch/global/__NPAD_USER__/cfl-mvp3-evidence/__INSTALL_STAGE_BASENAME__
R="$S/training-license-qualification"
C=__QUALIFICATION_CI_COMMIT__
test ! -e "$R"
# This bounded wait only observes exact-source CI; no stage or job exists yet.
"$T/bin/python" -I -B - "$C" <<'CI'
import json,sys,time,urllib.request
commit=sys.argv[1]
assert len(commit)==40 and all(c in '0123456789abcdef' for c in commit)
api='https://api.github.com/repos/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/'
deadline=time.monotonic()+1800
expected={'matched-step','verify (ubuntu-latest, 3.10)','verify (ubuntu-latest, 3.12)',
          'verify (windows-latest, 3.10)','verify (windows-latest, 3.12)'}
def get(url):
    req=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'CFL-GNN-author-CLI'})
    with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
while True:
    assert time.monotonic()<deadline,'EXACT_CI_TIMEOUT_PRESERVE_AND_STOP'
    runs=get(api+'runs?head_sha='+commit+'&event=pull_request&per_page=20')['workflow_runs']
    runs=[r for r in runs if r['head_sha']==commit and r['name']=='Public evidence integrity']
    if runs:
        run=max(runs,key=lambda r:r['id'])
        if run['status']=='completed':
            assert run['conclusion']=='success','EXACT_SOURCE_CI_FAILED_STOP'
            jobs=get(api+'runs/'+str(run['id'])+'/jobs?per_page=100')['jobs']
            assert {j['name'] for j in jobs}==expected and len(jobs)==5,'UNEXPECTED_CI_JOB_SET'
            assert all(j['status']=='completed' and j['conclusion']=='success' for j in jobs),'CI_JOB_NOT_PASSED'
            print('NPAD_QUALIFICATION_EXACT_SOURCE_CI_OK='+str(run['id']))
            break
    print('Aguardando CI; nenhum novo estagio ou job criado.',flush=True)
    time.sleep(60)
CI
test -r /home/__NPAD_USER__/model-agrologistic/secrets/gurobi.lic
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B - "$S" "$O" <<'ADMIT'
import hashlib,importlib.metadata as md,json,subprocess,sys
from pathlib import Path
s=Path(sys.argv[1]);original=Path(sys.argv[2])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sys.version_info[:3]==(3,13,15) and sys.prefix=='/home/__NPAD_USER__/venv313_g14'
assert sha(s/'gnn-additions-receipt.json')=='8dfbedf6e5d26d7d6c9a019cde6ffab051c8c06c008b9dcfbdd1598579c2cca0'
assert sha(s/'runtime-gpu-qualification/result.json')=='55972ae2b80b43381a8b985d97621e80cce3f65a92ddfab3b1a9d309b44697c9'
assert (s/'runtime-gpu-qualification/job-id.txt').read_text().strip()=='2278626'
rows=sorted((d.metadata.get('Name',''),d.version) for d in md.distributions())
assert hashlib.sha256(json.dumps(rows,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()=='dafe3bf6020249096a4b8f31574b7a192cb3f3d45175f893e916aedd605dd82d'
code="import hashlib,importlib.metadata as m,json;v=sorted((d.metadata.get('Name',''),d.version) for d in m.distributions());print(hashlib.sha256(json.dumps(v,ensure_ascii=True,separators=(',',':')).encode()).hexdigest())"
actual=subprocess.run([str(original/'bin/python'),'-I','-B','-c',code],capture_output=True,text=True,check=True,timeout=30).stdout.strip()
assert actual=='94e163438088c2e35743c3858e35c60dbfd3b1c8fd05ec1b7ff6a54dce3bc750','ORIGINAL_ENVIRONMENT_CHANGED_STOP'
print('NPAD_AMBOS_AMBIENTES_E_RETORNO_GPU_CONFERIDOS')
ADMIT
mkdir "$R" "$R/source" "$R/tmp" "$R/cache"
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B - "$R" "$C" <<'FETCH'
import hashlib,json,sys,urllib.request
from pathlib import Path
r=Path(sys.argv[1]);commit=sys.argv[2]
base='https://raw.githubusercontent.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/'
files={
 'qualify_training_license.py':(commit,'docs/research/npad-runtime-transition-20261120/qualify_training_license.py','5c0c2b1c3b1787a3f093fcbbc3eef0edc0535ba8a12e732284e5b5952fe971a5'),
 'source/gasse.py':('16c2b29f97356e9ece7d72bbf12c3bf3fbcc289f','src/cfl_gnn/models/gasse.py','e4cfb67cf9f62d0ed7c6f05acd79454541a8d12c9db5ba62643cf7a7f6a9c81f'),
 'source/gasse_calibrated.py':('16c2b29f97356e9ece7d72bbf12c3bf3fbcc289f','src/cfl_gnn/models/gasse_calibrated.py','9ad688b085a28c6a0e5cdd063fbaac60214a3214e2cbf10394b82608a9265eab'),
 'source/matched_gpu.py':('16c2b29f97356e9ece7d72bbf12c3bf3fbcc289f','src/cfl_gnn/training/matched_gpu.py','5c1c00c3a5a4d0041b6a9f10808c8dc6acd4e09b218ebea6b58b79e0713ffc87'),
}
for local,(ref,path,expected) in files.items():
    with urllib.request.urlopen(base+ref+'/'+path,timeout=30) as response:data=response.read(1024*1024)
    assert hashlib.sha256(data).hexdigest()==expected,'DOWNLOADED_SOURCE_MISMATCH:'+local
    with (r/local).open('xb') as stream:stream.write(data)
with (r/'source-receipt.json').open('x') as stream:json.dump({'reviewed_commit':commit,'files':files,'full_repository_clone':False},stream,indent=2)
print('NPAD_QUATRO_ARQUIVOS_HASH_CONFERIDOS_SEM_CLONE')
FETCH
cat > "$R/run.sbatch" <<'BATCH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
R=/scratch/global/__NPAD_USER__/cfl-mvp3-evidence/__INSTALL_STAGE_BASENAME__/training-license-qualification
T=/home/__NPAD_USER__/venv313_g14
( set -C; : > "$R/batch-start.claim" )
cd "$R"
sha256sum -c "$R/code.sha256"
export TMPDIR="$R/tmp" XDG_CACHE_HOME="$R/cache" TORCH_HOME="$R/cache/torch"
export TRITON_CACHE_DIR="$R/cache/triton" CUDA_CACHE_PATH="$R/cache/cuda" MPLCONFIGDIR="$R/cache/matplotlib"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export GRB_LICENSE_FILE=/home/__NPAD_USER__/model-agrologistic/secrets/gurobi.lic
srun --ntasks=1 --cpus-per-task=8 --cpu-bind=cores --kill-on-bad-exit=1 timeout --signal=TERM --kill-after=10s 600s env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH -u VIRTUAL_ENV -u GRB_WLSACCESSID -u GRB_WLSSECRET -u GRB_LICENSEID "$T/bin/python" -I -B "$R/qualify_training_license.py" "$R" > "$R/worker.private.log" 2>&1
BATCH
sha256sum "$R/qualify_training_license.py" "$R/run.sbatch" "$R/source/"*.py > "$R/code.sha256"
printf 'RECURSOS=1 job|1 V100|1 tarefa|8 CPUs|48G|15 min|3 updates sinteticos|1 MILP de licenca ate 30s\n'
sbatch --parsable --job-name=cfl_env_qual --partition=gpu-8-v100 --account=__NPAD_ACCOUNT__ --qos=preempt --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=48G --gres=gpu:1 --time=00:15:00 --no-requeue --chdir="$R" --output="$R/slurm-%j.private.out" --error="$R/slurm-%j.private.err" --export=ALL "$R/run.sbatch" > "$R/submission.private.txt"
J=$(cut -d';' -f1 "$R/submission.private.txt")
case "$J" in ''|*[!0-9]*) echo SUBMISSAO_AMBIGUA_PRESERVAR_NAO_REPETIR >&2;exit 1;; esac
printf '%s\n' "$J" > "$R/job-id.txt"
printf 'JOB_ID=%s\nETAPA_QUALIFICACAO=%s\n' "$J" "$R"
)
npad_qualification_exit=$?
printf 'NPAD_TRAIN_LICENSE_SUBMIT_EXIT=%s\n' "$npad_qualification_exit"
( exit "$npad_qualification_exit" )
