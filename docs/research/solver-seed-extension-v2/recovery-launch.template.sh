# Roteiro unico: autor no Bash do dgx-dasci, tfm_env ativo.
# Aguarda somente a CI; nenhuma nova tentativa automatica de experimento.
(
set -euo pipefail
COMMIT=__REVIEWED_SOURCE_COMMIT__
CI_RUN=__REVIEWED_CI_RUN__
GUIDANCE_SHA=7722bacdbb308f7fe8a17c26504cde1f00989eac8d66c2ff68a321a17a73f5a4
test "$(hostname -s)" = dgx-dasci
test "$(id -un)" = vrcelestino
test "${CONDA_DEFAULT_ENV:-}" = tfm_env
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]]
[[ $CI_RUN =~ ^[0-9]+$ ]]
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 GIT_OPTIONAL_LOCKS=0
export GIT_TERMINAL_PROMPT=0
python -B - "$COMMIT" "$CI_RUN" <<'PY'
import json
import sys
import time
import urllib.request

def verify_ci(run, jobs, commit, run_id):
    if run.get('head_sha') != commit or run.get('id') != run_id or run.get('name') != 'Public evidence integrity' or run.get('repository', {}).get('full_name') != 'unb-lamfo-or-ai-hpc/cfl-gurobi-gnn':
        raise SystemExit('PR94_CI_IDENTITY_MISMATCH_NO_LAUNCH')
    if run.get('status') != 'completed':
        return False
    if run.get('conclusion') != 'success':
        raise SystemExit('PR94_CI_NOT_SUCCESS_NO_LAUNCH')
    expected = {'matched-step', 'verify (ubuntu-latest, 3.10)', 'verify (ubuntu-latest, 3.12)', 'verify (windows-latest, 3.10)', 'verify (windows-latest, 3.12)'}
    rows = jobs.get('jobs', []) if isinstance(jobs, dict) else []
    if len(rows) != 5 or {r.get('name') for r in rows} != expected or not all(r.get('status') == 'completed' and r.get('conclusion') == 'success' and r.get('head_sha') == commit for r in rows):
        raise SystemExit('PR94_CI_REQUIRED_JOBS_NOT_PASSED_NO_LAUNCH')
    return True

def get(url):
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'CFL-GNN-PR94-entry-recovery'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2 * 1024**2 + 1)
    if len(raw) > 2 * 1024**2:
        raise SystemExit('PR94_CI_RESPONSE_LIMIT_NO_LAUNCH')
    return json.loads(raw)

commit, run_id = sys.argv[1], int(sys.argv[2])
url = 'https://api.github.com/repos/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/' + str(run_id)
deadline = time.monotonic() + 1800
while time.monotonic() < deadline:
    run = get(url)
    jobs = get(url + '/jobs?per_page=100') if run.get('status') == 'completed' and run.get('conclusion') == 'success' else None
    if verify_ci(run, jobs, commit, run_id):
        print('PR94_CI_GATE=SUCCESS_ALL_FIVE_JOBS', flush=True)
        break
    print('PR94_CI_WAIT=' + str(run.get('status')), flush=True)
    time.sleep(min(60, max(0, deadline - time.monotonic())))
else:
    raise SystemExit('PR94_CI_WAIT_EXPIRED_NO_STAGE_NO_SUBMISSION')
PY
EVIDENCE=/raid/vrcelestino/data/cfl-mvp2-evidence
test -d "$EVIDENCE"
S="$EVIDENCE/pr94-evaluation-${COMMIT:0:12}"
if test -e "$S"; then
    if test -f "$S/submission.json" && test -d "$S/source"; then
        test "$(git -C "$S/source" rev-parse HEAD)" = "$COMMIT"
        echo PR94_RECOVERY_EXISTING_SUBMISSION_STATUS_ONLY
        bash "$S/source/scripts/evidence/operate_pr94_evaluation.sh" status
        exit 0
    fi
    echo PR94_RECOVERY_STAGE_EXISTS_PRESERVE_DIAGNOSE >&2
    exit 3
fi
if test -e "$EVIDENCE/pr94-full-v2-entry-recovery-1.claim.json"; then
    echo PR94_RECOVERY_CLAIM_EXISTS_PRESERVE_DIAGNOSE >&2
    exit 3
fi
python -B -c 'import shutil,sys; assert shutil.disk_usage(sys.argv[1]).free >= 320*1024**3, "PR94_RECOVERY_NEEDS_320_GiB_FREE"' "$EVIDENCE"
umask 077
mkdir "$S"
mkdir "$S/claims" "$S/run" "$S/runtime"
mkdir "$S/runtime/tmp" "$S/runtime/cache" "$S/runtime/matplotlib"
mkdir "$S/runtime/torch" "$S/runtime/extensions" "$S/runtime/cuda"
export TMPDIR="$S/runtime/tmp" TMP="$S/runtime/tmp" TEMP="$S/runtime/tmp"
export XDG_CACHE_HOME="$S/runtime/cache"
git clone --no-checkout https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git "$S/source"
git -C "$S/source" checkout --detach "$COMMIT"
test "$(git -C "$S/source" rev-parse HEAD)" = "$COMMIT"
nice -n 10 bash "$S/source/scripts/evidence/operate_pr94_evaluation.sh" inspect "$GUIDANCE_SHA"
bash "$S/source/scripts/evidence/operate_pr94_evaluation.sh" recover-submit
)
pr94_recovery_exit=$?
printf 'PR94_RECOVERY_CLI_EXIT=%s\n' "$pr94_recovery_exit"
