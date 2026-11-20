# NPAD: coleta de leitura apos o job tecnico GPU estar terminal.
(
set -euo pipefail
test "$(id -un)" = __NPAD_USER__
case "$(hostname -s)" in service[0-9]*) ;; *) exit 1;; esac
R=/scratch/global/__NPAD_USER__/cfl-mvp3-evidence/__INSTALL_STAGE_BASENAME__/runtime-gpu-qualification
/home/__NPAD_USER__/venv313_g14/bin/python -I -B - "$R" <<'PY'
import hashlib,json,re,subprocess,sys
from pathlib import Path
r=Path(sys.argv[1]);job=(r/'job-id.txt').read_text().strip()
assert re.fullmatch('[0-9]+',job),'AMBIGUOUS_JOB_ID'
p=subprocess.run(['sacct','-n','-P','-j',job,'--format=JobID,State,ElapsedRaw,ExitCode,MaxRSS,AllocCPUs,NodeList'],capture_output=True,text=True,timeout=30,check=True)
fields=('JobID','State','ElapsedRaw','ExitCode','MaxRSS','AllocCPUs','NodeList')
rows=[dict(zip(fields,line.split('|')[:len(fields)])) for line in p.stdout.splitlines() if line.strip()]
terminal={'COMPLETED','FAILED','CANCELLED','PREEMPTED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','BOOT_FAIL','DEADLINE','REVOKED'}
assert any(x['JobID']==job for x in rows) and all(x['State'].split()[0].rstrip('+') in terminal for x in rows),'WAIT_FOR_TERMINAL_NO_RESUBMISSION'
f=r/'result.json';result=json.loads(f.read_text()) if f.is_file() else None
if result:assert result['job_id']==job and result['cluster']=='ufrn','RESULT_IDENTITY_MISMATCH'
print(json.dumps({'cluster':'ufrn','job_id':job,'accounting':rows,'result':result,'result_sha256':hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None,'new_solver_calls':0,'new_training_calls':0,'new_submissions':0},indent=2))
if result is None or result.get('compatibility')!='PASS':
    for log in ('runtime.private.log','slurm-'+job+'.private.err'):
        f=r/log
        if f.is_file():print('LOG='+log+'\n'+f.read_text(errors='replace')[-8000:])
PY
)
printf 'NPAD_GPU_RUNTIME_COLLECT_EXIT=%s\n' "$?"
