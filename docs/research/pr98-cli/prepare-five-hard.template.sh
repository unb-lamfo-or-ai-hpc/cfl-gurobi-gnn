# Five new hard preparations; no evaluation or training.
conda activate tfm_env
export GRB_LICENSE_FILE=/raid/vrcelestino/data/cfl-gurobi-gnn/secrets/gurobi.lic
(
  set -euo pipefail
  test "$(hostname -s)" = dgx-dasci
  test "$(id -un)" = vrcelestino
  test "$CONDA_DEFAULT_ENV" = tfm_env
  umask 077
  export GIT_OPTIONAL_LOCKS=0
  C=REVIEWED_SOURCE_COMMIT_REQUIRED
  [[ "$C" =~ ^[0-9a-f]{40}$ ]]
  D=/raid/vrcelestino/data/cfl-mvp2-evidence
  test ! -e "$D/pr98-hard-five-preparation.claim.json"
  python -I -B - "$C" <<'PY'
import json
import sys
import time
import urllib.request
commit=sys.argv[1]
api="https://api.github.com/repos/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/"
deadline=time.monotonic()+1800
def get(url):
    request=urllib.request.Request(url,headers={"Accept":"application/vnd.github+json","User-Agent":"CFL-GNN-author-CLI"})
    with urllib.request.urlopen(request,timeout=20) as response:
        return json.load(response)
while True:
    assert time.monotonic()<deadline,"CI_TIMEOUT_STOP"
    runs=get(api+"runs?head_sha="+commit+"&event=pull_request&per_page=20")
    selected=[r for r in runs["workflow_runs"] if r["head_sha"]==commit and r["name"]=="Public evidence integrity"]
    if selected:
        run=max(selected,key=lambda r:r["id"])
        if run["status"]=="completed":
            assert run["conclusion"]=="success","CI_FAILED_STOP"
            jobs=get(api+"runs/"+str(run["id"])+"/jobs?per_page=100")
            assert jobs["total_count"]==len(jobs["jobs"])==5
            assert all(j["status"]=="completed" and j["conclusion"]=="success" for j in jobs["jobs"])
            names={j["name"] for j in jobs["jobs"]}
            assert "matched-step" in names
            for system in ("ubuntu-latest","windows-latest"):
                for version in ("3.10","3.12"):
                    assert sum(system in n and version in n for n in names)==1
            print("PR98_EXACT_SOURCE_CI_OK="+str(run["id"]),flush=True)
            break
    print("Aguardando CI da fonte fixada; nenhum novo job HPC submetido.",flush=True)
    time.sleep(60)
PY
  S=$(mktemp -d "$D/pr98-hard.XXXXXXXX")
  printf 'PR98_STAGE=%s\n' "$S"
  git init -q "$S/source"
  GIT_TERMINAL_PROMPT=0 timeout 120 git -C "$S/source" fetch -q --depth=1 --no-tags https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git "$C"
  test "$(git -C "$S/source" rev-parse FETCH_HEAD)" = "$C"
  git -C "$S/source" -c advice.detachedHead=false checkout -q --detach "$C"
  timeout 600 nice -n 10 python -I -B "$S/source/scripts/evidence/pr98_hard_inputs.py" "$S" "$C"
  P=$(sha256sum "$S/preflight.json" | cut -d' ' -f1)
  env -u PYTHONHOME -u PYTHONPATH python -B "$S/source/scripts/evidence/pr98_hard_preparation.py" freeze "$S" "$P"
  H=$(sha256sum "$S/plan.json" | cut -d' ' -f1)
  printf 'PR98_HARD_PLAN_SHA256=%s\n' "$H"
  printf '%s\n' 'Preparacao proposta: H0/H5/H10/H15/H20, uma raiz e um forward por instancia.'
  printf '%s\n' 'Reutiliza H25 do job 3906. Nao treina nem executa avaliacoes B/R/G.'
  printf '%s\n' 'Um job: ate 3 h, 4 nucleos fisicos, 64 GiB, 1 V100; sem retry.'
  read -r -p 'Para submeter, digite AUTORIZO PREPARACAO CINCO HARD PR98: ' A
  test "$A" = 'AUTORIZO PREPARACAO CINCO HARD PR98'
  env -u PYTHONHOME -u PYTHONPATH python -B "$S/source/scripts/evidence/pr98_hard_preparation.py" submit "$S" "$H" --decision "$A"
)
pr98_prep_exit=$?
printf 'PR98_HARD_PREPARATION_CLI_EXIT=%s\n' "$pr98_prep_exit"
( exit "$pr98_prep_exit" )
