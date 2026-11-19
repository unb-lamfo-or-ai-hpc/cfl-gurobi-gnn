# RETIRED 19 November 2026. Historical launcher retained below for provenance.
# The author discontinued this campaign; do not copy an older pinned launcher.
printf '%s\n' 'PR98_CAMPAIGN_RETIRED: no new evaluation is authorized.' >&2
return 2 2>/dev/null || exit 2

# Use only after Codex reviews the terminal hard-preparation return.
# 990 NEW evaluations; a separate explicit resource decision is required.
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
  test ! -e "$D/pr98-full-990-v1.claim.json"
  read -r -p 'Cole o PR98_STAGE da preparacao hard ja revisada: ' P
  read -r -p 'Cole o PR98_HARD_RETURN_SHA256 aceito na revisao: ' R
  [[ "$R" =~ ^[0-9a-f]{64}$ ]]
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
  S=$(mktemp -d "$D/mvp2-concurrent-XXXXXXXX")
  printf 'PR98_CAMPAIGN_STAGE=%s\n' "$S"
  git init -q "$S/source"
  GIT_TERMINAL_PROMPT=0 timeout 120 git -C "$S/source" fetch -q --depth=1 --no-tags https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git "$C"
  test "$(git -C "$S/source" rev-parse FETCH_HEAD)" = "$C"
  git -C "$S/source" -c advice.detachedHead=false checkout -q --detach "$C"
  env -u PYTHONHOME -u PYTHONPATH python -B "$S/source/scripts/evidence/pr98_campaign_bindings.py" "$S" "$P" "$R"
  H=$(sha256sum "$S/plan.json" | cut -d' ' -f1)
  printf 'PR98_CAMPAIGN_PLAN_SHA256=%s\n' "$H"
  python -I -B - "$S" <<'PY'
import json
import sys
from pathlib import Path
plan=json.loads((Path(sys.argv[1])/"plan.json").read_text())
print(json.dumps(plan["budget"],indent=2))
assert plan["budget"]["solves"]==990 and plan["budget"]["blocks"]==330
print("3 arrays em hold; ate 4 blocos/32 nucleos fisicos/256 GiB simultaneos; sem GPU.")
print("Cada solve: ate 3600 s; cada bloco B/R/G: ate 4 h; sem retry.")
print("Tetos: 4950 solver-core-h; 6600 core-h reservadas; 84480 GiB-h; preparo contabilizado separadamente.")
print("Saidas: ate 320 GiB; admissao exige 384 GiB livres. Os tetos nao sao previsao de uso.")
PY
  read -r -p 'Para este plano e recursos, digite AUTORIZO CAMPANHA PR98 990: ' A
  test "$A" = 'AUTORIZO CAMPANHA PR98 990'
  python -I -B - "$S" "$H" "$A" <<'PY'
import json
import os
import sys
from pathlib import Path
stage=Path(sys.argv[1])
plan=json.loads((stage/"plan.json").read_text())
approval={"plan_sha256":sys.argv[2],"budget":plan["budget"],
          "execution_approved":True,"decision":sys.argv[3]}
with (stage/"authorization.json").open("x") as stream:
    json.dump(approval,stream,indent=2,sort_keys=True)
    stream.write("\n")
    stream.flush()
    os.fsync(stream.fileno())
PY
  env -u PYTHONHOME -u PYTHONPATH python -B "$S/source/scripts/evidence/mvp2_concurrent_mip.py" queue-held "$S" "$H" pdi batch
  env -u PYTHONHOME -u PYTHONPATH python -B "$S/source/scripts/evidence/mvp2_concurrent_mip.py" release "$S" "$H"
)
pr98_full_exit=$?
printf 'PR98_FULL_CAMPAIGN_CLI_EXIT=%s\n' "$pr98_full_exit"
( exit "$pr98_full_exit" )
