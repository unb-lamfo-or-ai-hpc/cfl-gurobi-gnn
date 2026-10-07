# Sprint B — medium continuation and CPU-profile decision

## Scope and acceptance

PR78 closes B1 as a partial technical delivery, with easy job3489 complete and
medium job3490 interrupted. Its closure is not Sprint B completion. See
[preserved closure](../evidence/pr78/job3491/CLOSURE.md) and the
[precommitted B2 reporting rules](mvp2-delivery-plan-20261006.md).

This delivery combines the remaining bounded medium execution, independent
return review, paired analysis, and a justified development CPU profile. Do not
create another PR for each helper, receipt or CI repair. No new runtime layer is
needed: use reviewed source `80cf7d5b90202ba57c7cb62c5e0d670875cc02ac`,
whose four exact-head checks passed. PR78 closure changed documentation and
public evidence only.

Pending acceptance:

- [ ] Collect and independently validate the new medium return, retaining every
  failure, missing arm and censoring reason. Never repeat easy3489.
- [ ] Implement/test paired descriptive tables, target-time coverage and valid
  within-parent speedups; test missing/censored values and allocation deduplication.
- [ ] Account for successful and failed allocations once, with separate solver,
  process, scheduler CPU and memory scopes; do not infer historical OOM cause.
- [ ] Publish tables/figures and a resource-valid profile decision. Use a strict
  Pareto comparison (no post-hoc practical tie tolerance); retain exact ties
  and declare the final selection rationale. Two parents/one seed support
  development observations, not population-wide significance.
- [ ] Final exact-head CI, review, ready-for-review, then request merge approval.

The Sprint B gate remains open if the resource-valid paired comparison is still
missing. Completing a Slurm job alone does not satisfy it. Scientific reporting
eligibility in the operational receipts remains false; do not modify old receipts.

## Explicit additional budget

The start command below records one additional medium job, at most five solver
calls, 18000 solver seconds and 19800 wall seconds. The conservative reservation
for jobs3489/3490/new is three submissions, eleven slots and 39600 solver seconds:
delta +1 job/+1 slot/+3600 solver seconds against the original experiment ceiling.
This is not a claim that the interrupted3490 exact call count is known. Earlier
failed submissions and no-solver diagnostics remain separate historical costs.

One node, sixteen physical cores,64GiB, shared CPU-only; no GPU/exclusive/requeue,
automatic retry or extension. Soft solver limit48 decimalGB, sampled stop56GiB,
kernel RAM ceiling64GiB. Seed42, medium gap10%, thread order16,8,2,1,4 unchanged.
No new resource budget is recorded by publishing this document. Running the
short explicit approval flag below is the operator's budget confirmation.

## dgx-dasci Bash: install and start once

This supersedes the old instruction to fetch the moving PR78 branch. Fetch the
exact runtime SHA instead. Keep the existing pr78 evidence path because it is
part of the frozen runtime/lock identity, even though review continues in this
successor PR. Do not rename it or create another directory to bypass a stop.

```bash
conda activate tfm_env
(
  set -euo pipefail
  umask 077
  test "$(hostname -s)" = dgx-dasci
  test "${CONDA_DEFAULT_ENV:-}" = tfm_env
  REPO=/raid/vrcelestino/data/cfl-gurobi-gnn
  SHA=80cf7d5b90202ba57c7cb62c5e0d670875cc02ac
  STAGE=/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/medium-continuation-80cf7d5b9020
  if test -e "$STAGE/flow"; then
    printf '%s\n' 'Existing flow: do not start again. Use status/collect below.' >&2
    exit 1
  fi
  if test ! -e "$STAGE"; then
    git -C "$REPO" fetch origin "$SHA"
    test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$SHA"
    mkdir -m 700 "$STAGE"
    git -C "$REPO" -c core.autocrlf=false worktree add --detach "$STAGE/source" "$SHA"
  fi
  test "$(git -C "$STAGE/source" rev-parse HEAD)" = "$SHA"
  test -z "$(git -C "$STAGE/source" status --porcelain --untracked-files=all)"
  bash -n "$STAGE/source/scripts/evidence/operate_pr78_medium.sh"
  bash -n "$STAGE/source/scripts/slurm/dasci/submit_pr78_medium.sbs"
  bash "$STAGE/source/scripts/evidence/operate_pr78_medium.sh" \
    start "$SHA" --approve-additional-medium-budget
)
```

Start runs the frozen offline tests, reviews predecessor returns and exact-runtime
CI, records the explicit bounded approval, and submits/releases once. It returns
the job ID without waiting. On failure preserve the output; do not repeat start.

## One-shot status and terminal collection

```bash
bash /raid/vrcelestino/data/cfl-mvp2-evidence/pr78/medium-continuation-80cf7d5b9020/source/scripts/evidence/operate_pr78_medium.sh \
  status 80cf7d5b90202ba57c7cb62c5e0d670875cc02ac
```

After `terminal=true`, including a failed job:

```bash
bash /raid/vrcelestino/data/cfl-mvp2-evidence/pr78/medium-continuation-80cf7d5b9020/source/scripts/evidence/operate_pr78_medium.sh \
  collect 80cf7d5b90202ba57c7cb62c5e0d670875cc02ac
```

Keep `return_sha256`. Download only `flow/public_return.json`, in one SCP
connection; no raw logs, models or license. The existing Windows receiver
`receive_pr78_medium_workflow.ps1` verifies this hash and the nested contract
using the frozen source and preserved predecessor bytes. Its legacy name does
not imply a second PR78 run. Return receipt/hash/download directory for review.

No additional operator submission is implied after collection, even if the
return is incomplete. No merge of this successor delivery is authorized yet.
