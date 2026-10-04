# PR66: shared dgx-dasci operator runbook

This is a defaults-v2 development pilot, not a warm-start or training campaign.
Do not use NPAD, an exclusive node, GPUs, another license, or raw-data uploads.
The historical v1 configuration filename is retained for compatibility; its
`protocol_id` explicitly identifies the amended defaults-v2 policy.

## Publish first, without execution

### Job 3466 receipt recovery

The author-supplied diagnostic transcript establishes that job 3466 qualified
sixteen physical cores and started only `easy-threads1`. The child returned from
`optimize()` and failed while writing strict JSON: the observed default NodeLimit
is positive infinity. Status, terminal gap and optimize time remain unreported;
recover them from the retained private Gurobi log before asserting outcomes.
The parent supervisor retained a failed execution receipt and stopped the matrix.

Infinite parameter defaults now use the explicit JSON string `positive_infinity`
instead of a JSON number or a missing-value null. The equality check against the
installed Gurobi default precedes encoding. The collector accepts this encoding
for NodeLimit and rejects null or unsupported default representations. Preflight
also serializes the parameter receipt without optimization. Regression tests
exercise the real attempt writer and evidence packaging with an infinite default.

Keep the old plan, worktree, logs and failed allocation as immutable evidence.
Install the recovery in a new worktree, verify its published revision and CI,
and run a fresh preflight. Its worker hash changes the plan digest; retain the
same role contract, original LP hashes, easy17/medium1 pair, controls and budget.
Do not apply transferred files directly to the worktree used by job 3466.

The local PowerShell publisher updates the existing draft PR66 into `develop`.
It checks each changed remote file against the original local baseline, allowing
only CRLF/LF equivalence. Conflicting remote changes abort before publication.
It creates one fast-forward GitHub commit; no force-push, merge or main update.
Later revisions use the previous verified publication receipt as the local/remote
baseline. If the remote head differs from that receipt, stop for review rather
than silently overwrite it or reuse the original preparation baseline.
Git inspection uses a temporary child-process configuration trusting only the
resolved checkout. It does not add global safe-directory exceptions or trust the
common repository. PowerShell 5.1 and 7 regression tests exercise the real Git
ownership guard, exact UTF-8 blob reads and cleanup on failure. `-CheckOnly` on
the local publisher runs inspection, Ruff and tests without GitHub writes.
Use its printed `SOURCE_COMMIT` below. Local and published commit IDs may differ
because the earlier PR66 publication used a separate remote commit history.

## Install on dgx-dasci

Activate `tfm_env`. Replace the value of `PR66_SOURCE_COMMIT` with the published
40-character SHA; it is not the PR65 merge or the local unpublished candidate.

```bash
conda activate tfm_env
export PR66_SOURCE_COMMIT="REPLACE_WITH_PUBLISHED_SOURCE_COMMIT"
REPO=/raid/vrcelestino/data/cfl-gurobi-gnn
git -c "safe.directory=${REPO}" -C "${REPO}" fetch origin feature/pr66-reconciliation-thread-pilot
test "$(git -c "safe.directory=${REPO}" -C "${REPO}" rev-parse FETCH_HEAD)" = "${PR66_SOURCE_COMMIT}"
INSTALL=/raid/vrcelestino/data/cfl-mvp2-evidence/pr66-install
mkdir -p "${INSTALL}"
git -c "safe.directory=${REPO}" -C "${REPO}" show "${PR66_SOURCE_COMMIT}:scripts/slurm/dasci/install_pr66_thread_screen.sh" > "${INSTALL}/install.sh"
bash "${INSTALL}/install.sh" "${PR66_SOURCE_COMMIT}"
cd "/raid/vrcelestino/data/cfl-gurobi-gnn-worktrees/pr66-thread-screen-${PR66_SOURCE_COMMIT:0:12}"
bash scripts/slurm/dasci/launch_pr66_thread_screen.sh --preflight
```

The primary dirty checkout is not switched, cleaned or pulled. All new files stay
under `/raid`. The only permitted license is the existing
`/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic`; do not copy it.
The role plan defaults to PR57's training directory. Its expected identifier
`432a42...` is the canonical contract hash, not the digest of formatted JSON
bytes. The worker recomputes that contract using the original PR57 exclusion
rules, matches the declared and expected hashes, requires true readiness gates,
and verifies 54 unique parents (30 easy,24 medium;34 train,10 validation,10 test).
It then records a separate stored-file SHA256 and checks for concurrent changes.
If the plan was relocated, set `PR66_ROLE_PLAN` to its exact location; never
replace the expected canonical contract with a newly observed file hash.

The stored originals declare MAXIMIZE, as verified for all 90 models in PR65.
The existing CFL research convention uses MINIMIZE for their cost objective.
Preflight and every attempt apply that convention in memory only, with unchanged
coefficients, objective constant and constraints. Look for two
`PR66_MODEL_QUALIFIED` lines recording both source and effective senses and the
explicit override flag. Unexpected source senses, continuous-only models and
nonlinear/multi-objective models are rejected before optimization. The original
LP files and their hashes remain intact. This is not a solver-algorithm override.
Retain earlier failed preflight directories; install the corrected published
commit in a new worktree and freeze a fresh plan rather than modifying old pins.

## Submit only when authorized

After reviewing the preflight output, explicitly authorize the initial screen:

```bash
export PR66_SCREEN_AUTHORIZED=yes
bash scripts/slurm/dasci/launch_pr66_thread_screen.sh --submit
```

This is the only step that submits a job. Record `PILOT_JOB`, `OUTPUT` and
`PLAN_SHA256`. It performs ten fresh, sequential solves: 1/2/4/8/16 threads,
same drawn easy/medium pair, seed 42, 300 seconds and 10% gap. Maximum optimization
budget is 3,000 seconds; the single 16-core/64-GiB allocation has a 90-minute
scheduler ceiling. The job refuses an affinity without exactly sixteen physical
cores. It pauses remaining attempts on a solver/resource failure. No extensions
to 3,600 seconds occur automatically. A new launcher invocation is a new job:
never retry submission without checking the queue and prior receipts.

## Inspect and collect

```bash
JOB=REPLACE_WITH_PILOT_JOB
RUN=REPLACE_WITH_OUTPUT_DIRECTORY
squeue -j "${JOB}" --format="%.18i %.20j %.10T %.10M %R"
sacct -j "${JOB}" --format=JobID,State,ExitCode,Elapsed,TotalCPU,MaxRSS,AllocCPUS
tail -n 25 "${RUN}/screen-${JOB}.out" "${RUN}/screen-${JOB}.err"
# Only after the job leaves the queue:
bash scripts/slurm/dasci/collect_pr66_thread_screen.sh "${RUN}"
```

The collection verifies frozen worker/configuration/helper hashes and each
supervisor-declared attempt hash, effective controls and algorithm-default
observations. `COMPLETE_MATRIX=false` is a preserved incomplete experiment,
not a passed ten-run scientific comparison. Archive/member read-back checks and
declared-text sanitization do not certify scientific reporting or binary privacy.
If collection fails, retain the original receipts and private logs for diagnosis.

Copy the package and final scheduler accounting from local PowerShell:

```powershell
$Run = 'REPLACE_WITH_OUTPUT_DIRECTORY'
scp "vrcelestino@dgx-dasci.ujaen.es:$Run/pr66_thread_evidence.tar.gz" "D:/Downloads/"
scp "vrcelestino@dgx-dasci.ujaen.es:$Run/sacct-final.txt" "D:/Downloads/pr66_sacct_final.txt"
Get-FileHash "D:/Downloads/pr66_thread_evidence.tar.gz" -Algorithm SHA256
Get-FileHash "D:/Downloads/pr66_sacct_final.txt" -Algorithm SHA256
```

Compare both with the remote hashes. Attach these small files, not the models,
license or private logs. Slurm parent allocations are charged once for the bundled
job; do not add `.batch`, `.extern` and `.0` CPU allocations as independent jobs.
Threads is a cap, not measured simultaneous utilization. Time-limit rows compare
gap/quality at the budget; they are not time-to-optimality speedup observations.
