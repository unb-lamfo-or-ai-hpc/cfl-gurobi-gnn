# Run after all 330 array tasks are terminal; no solves or queue changes.
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
  read -r -p 'Cole o PR98_CAMPAIGN_STAGE: ' S
  test "$(git -C "$S/source" rev-parse HEAD)" = "$C"
  H=$(sha256sum "$S/plan.json" | cut -d' ' -f1)
  env -u PYTHONHOME -u PYTHONPATH python -B "$S/source/scripts/evidence/mvp2_concurrent_mip.py" collect "$S" "$H"
)
pr98_terminal_exit=$?
printf 'PR98_FULL_COLLECT_EXIT=%s\n' "$pr98_terminal_exit"
( exit "$pr98_terminal_exit" )
