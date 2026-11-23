# Read-only terminal collector. Never print raw native logs: they may contain license metadata.
(
set -euo pipefail
test "$(id -un)" = __NPAD_USER__
case "$(hostname -s)" in service[0-9]*) ;; *) exit 1;; esac
T=/home/__NPAD_USER__/venv313_g14
R=/scratch/global/__NPAD_USER__/cfl-mvp3-evidence/__INSTALL_STAGE_BASENAME__/training-license-qualification
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B - "$R" /home/__NPAD_USER__/venv313 <<'PY'
import hashlib,json,re,subprocess,sys
from pathlib import Path
r=Path(sys.argv[1]);original=Path(sys.argv[2]);job=(r/'job-id.txt').read_text().strip()
assert re.fullmatch('[0-9]+',job)
q=subprocess.run(['sacct','-n','-P','-j',job,'--format=JobID,State,ElapsedRaw,ExitCode,MaxRSS,AllocCPUs,NodeList'],capture_output=True,text=True,timeout=30,check=True)
fields=('JobID','State','ElapsedRaw','ExitCode','MaxRSS','AllocCPUs','NodeList')
rows=[dict(zip(fields,line.split('|')[:len(fields)])) for line in q.stdout.splitlines() if line.strip()]
terminal={'COMPLETED','FAILED','CANCELLED','PREEMPTED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','BOOT_FAIL','DEADLINE','REVOKED'}
assert any(x['JobID']==job for x in rows) and all(x['State'].split()[0].rstrip('+') in terminal for x in rows),'WAIT_FOR_TERMINAL_NO_RESUBMISSION'
f=r/'result.json';result=json.loads(f.read_text()) if f.is_file() else None
if result:assert result['job_id']==job and result['cluster']=='ufrn','RESULT_IDENTITY_MISMATCH'
code="import hashlib,importlib.metadata as m,json;v=sorted((d.metadata.get('Name',''),d.version) for d in m.distributions());print(hashlib.sha256(json.dumps(v,ensure_ascii=True,separators=(',',':')).encode()).hexdigest())"
old=subprocess.run([str(original/'bin/python'),'-I','-B','-c',code],capture_output=True,text=True,check=True,timeout=30).stdout.strip()
logs={p.name:p.stat().st_size for p in r.glob('*.private.log') if p.is_file()}
print(json.dumps({'cluster':'ufrn','job_id':job,'accounting':rows,'result':result,'result_sha256':hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None,'original_venv313_inventory_after':old,'original_inventory_preserved':old=='94e163438088c2e35743c3858e35c60dbfd3b1c8fd05ec1b7ff6a54dce3bc750','private_logs_available_bytes_only':logs,'new_solver_calls_from_collection':0,'new_training_calls_from_collection':0,'new_submissions':0},indent=2))
PY
)
npad_collect_exit=$?
printf 'NPAD_TRAIN_LICENSE_COLLECT_EXIT=%s\n' "$npad_collect_exit"
( exit "$npad_collect_exit" )
