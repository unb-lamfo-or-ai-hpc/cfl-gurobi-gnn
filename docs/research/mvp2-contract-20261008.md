# MVP 2.0: sample, methods, computational contract and next actions

**Current checkpoint, 9 October:** all 54 parents and four validation forwards
have been reviewed from Job3503. Read the [closure](pr80-closure-job3503.md) and
[accepted results-first plan](mvp2-results-plan-20261009.md). Pending-runtime
statuses and submission blocks below are retained history, not current actions.
E0 execution remains a separate admitted-manifest decision; no automatic run.

Approved planning direction: 8 October 2026. This is the current reading entry
point for PR80 and Sprints C-F. It supersedes the scheduling priority of older
roadmaps, not their immutable experimental records or their execution budgets.
Code/data identifiers remain unchanged. F0-F29 and M0-M29 are display aliases.

**Current execution amendment:** retain `tfm_env` and its installed versions;
remove the auditor's artificial minimum-PyTorch gate. The
[integrated PR80 runbook](pr80-integrated-existing-runtime.md) replaces earlier
numeric-only, environment-upgrade and CPU-venv commands. One allocation produces
the 54-parent numerical/descriptive audit and, conditionally, four frozen-model
validation forwards on F1/M11. No new training, normalization fitting or solver
optimization is included. This bounded forward evaluation precedes E0 solves;
it does not remove the later CPU/GPU experimental comparison.

**Job3501 update:** 30 easy parents passed numerical checks; 24 medium parents
were blocked only by the reader's 32 MiB expanded-JSON ceiling. No inference
was attempted. The current runbook raises that bounded reading capacity and
uses a hash-bound continuation of only the 24 unfinished audits, retaining the
30 completed rows unchanged. Neither these 24 blocked rows nor the valid easy
rows are to be mislabeled as mathematical failures. No package upgrade is needed.

## 1. What, how and why

**Question:** when does a learned partial start improve CFL optimization on
instances not used to fit the predictor, and when does that improvement justify
its complete computational cost?

First complete the data review and evaluate existing frozen models (E0).
Then compare matched training, GPU scaling, augmentation and CPU resource
profiles. CPU/GPU evaluation is a required MVP2 deliverable, not optional
editorial decoration. Early evaluation does not remove these later experiments.

**Current state:** Sprint B closed in PR79. PR80 metadata and selected artifact
hashes/roles have been reviewed. Installed numerical admission is still pending.
Job 3500 returned a runtime-blocked numerical receipt: the first parent failed
the PyTorch minimum-version gate and the other 53 were not attempted. See the
[diagnosis and current inventory CLI](pr80-job3500-runtime-diagnosis.md).
Do not repeat the historical section 7A submission. Local unit-test receipts
are synthetic fixtures and must never be reported as HPC evidence.
PR80 stays draft; training and E0 solver execution are not admitted yet.

## 2. Population, sample and information boundaries

The benchmark population contains 90 originals: 30 easy, 30 medium and 30 hard.
The historical learning cohort contains 54 admitted labels: 30 easy and 24
medium, with no hard labels. This is a quality-selected subset, not a random
sample of the 90. Rejection by label gap is not mathematical infeasibility.

| Learning role | Easy | Medium | Total |
| --- | ---: | ---: | ---: |
| Training | 18 | 16 | 34 |
| Validation | 6 | 4 | 10 |
| Predictive test | 6 | 4 | 10 |
| Total | 30 | 24 | 54 |

The easy-only cohort shares the same 30 easy parents and roles (18/6/6).
It does not add 30 independent observations to the mixed cohort.
Canonical source: [90-parent split](../../configs/splits/cfl_90_seed42_folds.csv).
Fold 0 is test, fold 1 validation, folds 2-4 training for this rotation.

| Cohort / role | Exact admitted display identifiers |
| --- | --- |
| Easy training | F2, F5, F7, F8, F13, F15, F16, F17, F18, F19, F20, F21, F22, F23, F24, F25, F26, F28 |
| Easy validation | F1, F4, F9, F10, F11, F12 |
| Easy predictive test | F0, F3, F6, F14, F27, F29 |
| Medium training | M1, M2, M3, M8, M10, M15, M16, M18, M21, M22, M23, M24, M25, M27, M28, M29 |
| Medium predictive validation | M11, M14, M17, M19 |
| Medium predictive test | M0, M4, M7, M12 |

Separate solver populations are not the predictive partitions:

| Population | Identifiers | Interpretation |
| --- | --- | --- |
| Historical guidance validation | M5, M6, M11, M14, M17, M19 | Used to qualify the guidance policy |
| Historical optimization test | M0, M4, M7, M9, M12, M20 | Frozen policy evaluated without target labels as inputs |
| Label-excluded medium parents | M5, M6, M9, M13, M20, M26 | Difficulty-selected, historically inspected subgroup |

M5/M6 retain validation roles; M9/M20 retain test roles; M13/M26 retain training
roles but are absent from the admitted mixed fitting cohort. Audit all model,
normalization and selection dependencies before calling them unseen by a model.
Do not move any parent into a new test fold. M5/M6 already influenced policy
qualification; M9/M20 already have solver outcomes. They cannot become a new
untouched confirmation set for a policy changed after seeing those outcomes.

E0 must reconcile M13/M26 coverage before declaring additional solves necessary.
Original roles follow descendants. Parent is the independent unit; variables,
seeds and descendants are related observations, not independent sample size.

Sources: [label inventory](../evidence/mvp1/parent_coverage.json),
[experimental populations](../../manuscript/index.qmd),
[solver outcomes](../../manuscript/results/current/table_solver_outcomes.csv).

### Descriptive statistics: available and still required

The counts above are current descriptive results, not a claim that all
distributional analyses are finished. Report the following by difficulty and
role, with the source digest, denominator, missing count and computation rule:

- Variables by type, constraints, nonzeros/edges, density and graph degrees.
- Coefficient/bound scales, clipping and transformed-feature distributions.
- Label prevalence and declared gaps, distinguishing numerical label admission.
- Runtime, primal/dual bounds, gap, memory, start acceptance and censoring.
- Count, median, quartiles, minimum/maximum; means where useful. State the
  quantile convention. Use one record per parent for structural summaries and
  parent/method/seed/thread for run summaries; never pool different budgets.

Do not invent zeros for absent labels/telemetry or infer uncensored attainment
times from time limits. Numerical distribution tables require the installed
review; their pending state is a PR80 closure item. Exploratory PCA/UMAP plots
do not establish difficulty or improve the GNN by themselves. Any learned input
transform must fit training parents only and define out-of-sample application.

### Corrections to the meeting/presentation interpretation

- Predictive test is six easy plus four medium, not six medium plus four easy.
- Historical GNN gap wins against unguided control are 4/6 on validation and
  5/6 on test. These are not win counts against the LP comparator.
- GNN zero-gap optimization times: M19 about 671 s (validation), M12 about
  702 s and M20 about 1,585 s (test). M12 is not 62 s.
- Historical labeling did not use only 3,600 s: the
  [PR54 record](pr54-batch0-engineering-closure.md) includes 28,800 s attempts.
- Epoch 34 is the selected checkpoint from a 100-epoch run, not an early stop
  at epoch 34. A feasible incumbent, gap <=10%, and optimal termination differ.
- 87 reports and 77 Parquet files are artifact counts, not unique incumbents.
  Full unique feasible incumbent totals remain unavailable.

## 3. Three methods, all using Gurobi

| Method | Start construction | Main solve |
| --- | --- | --- |
| Unguided | No externally supplied assignment | Fresh Gurobi model with its own internal algorithms |
| Root-LP matched | Gurobi root-relaxation values rank selected binary assignments | Fresh Gurobi model receives a partial 0/1 Start |
| GNN | Graph features feed the frozen GNN; predicted scores select binary assignments | Fresh Gurobi model receives a partial 0/1 Start |

The LP values come from Gurobi, not the GNN. The
[capture implementation](../../src/cfl_gnn/graph/gurobi_graph_artifact.py)
observes the first optimal root MIPNODE relaxation, records cbGetNodeRel in
original variable order and terminates that preparation. It is not a claim of
optimality for the integer problem and not a generic model.relax fallback.
Preparation uses one thread, seed 42, Presolve=0, NodeLimit=1 and <=600 s.
If the required observation is unavailable, preserve the failure; no zero vector.

The GNN itself also uses this root vector as a graph feature. The method is
hybrid Gurobi/GNN, not a replacement of Gurobi. Root preparation cost therefore
belongs in a cold GNN application. Do not apply preparation's Presolve=0 to the
main solve by accident: they are separate parameter maps.

### Exactly how binary values are selected

For n binary variables, K=min(n,20000,max(1,floor(0.10*n))). The
[selector](../../src/cfl_gnn/experiments/pr58_guidance.py) first sorts predicted
ones by decreasing probability. If there are more than K, keep the first K.
Otherwise fill remaining places with predicted zeros by decreasing confidence
(1-p). Break ties by variable name. The historical policy abstains when there
are no predicted positives. Never supply fractional binary Start values.
Unspecified variables remain undefined; the solver attempts completion/repair.
Start submission does not fix bounds or guarantee acceptance or feasibility.

The matched LP comparator receives the GNN's actual support size K' and count
r of ones: choose the r highest LP values as ones and the K'-r lowest remaining
values as zeros. Thus its ranking source is LP but its coverage is matched to
GNN. It is not a fully autonomous LP heuristic. Disclose this dependence and
do not claim the comparator's end-to-end cost excludes any work needed to
derive its matched coverage. Report shared preparation once for campaign cost,
and separately disclose required preparation for standalone application costs.

Sensitivity experiments use validation only, not known test wins. Preserve the
historical 10%/20,000 policy as a reference. Test truncated positives, zero fill,
ties and abstention before proposing a bounded alternative support policy.

## 4. Reproducible hyperparameters and execution environment

Source of truth: executable config + exact code + effective runtime receipt.
Documentation summarizes these; unknown effective settings remain unknown.

| Component | Historical reference | Required runtime record |
| --- | --- | --- |
| Architecture | Gasse-v2 alternating prenorm, 2 layers, hidden size 32, 7/5/1 input channels | Architecture/config/checkpoint hashes, feature transforms |
| Training | 100 epochs, lr=0.001, seed=42, gradient clip norm=1.0 | All optimizer parameters, versions, deterministic settings |
| Sampling | 4 draws per parent/epoch, balanced cycle, graph batch size 1 in serial code | Actual draws, graph order, optimizer updates, effective global batch |
| Loss | Weighted BCE, weight computed from training data | Exact positive weight and its estimation population |
| Selection | Minimum validation weighted BCE; threshold by maximum validation F1 | Selected epoch, exact threshold, candidate grid and tie rule |
| Root preparation | One thread, seed 42, Presolve=0, <=600 s, NodeLimit=1 | Effective solver parameter map and capture status |
| Historical main solve | One thread, seed 42, <=3,600 s, MIPGap=1e-4 | Defaults/version plus overrides, start configuration, status |
| E0 | Frozen historical policy, initially one thread | Exact checkpoint and compatibility checks before release |
| E1/E2 CPU | Threads 1/2/4/8/16, paired instance/seed/profile | Physical affinity, allocation, measured CPU and RAM |
| C3 GPU | 1 GPU then 2, conditionally 4/8 | Devices, CUDA/framework, precision, communication, global batch |

References: [training config](../../configs/training/gasse_pr57_54_v1.json),
[training implementation](../../src/cfl_gnn/training/gasse_reconnected.py),
[guidance config](../../configs/experiments/pr58_validation_guidance_v1.json).
Adam is instantiated with explicit lr; other defaults must be resolved against
the installed PyTorch version, not guessed or silently changed. Historical
100-epoch evidence is not a license to increase future work budgets.

Gap <=10% is a reporting target and label-admission threshold; it is not the
historical main-solve stopping tolerance. Keep preparation, inference, start
construction, optimization and verification times distinct. Report cold and
reused-model costs with explicit amortization assumptions. Training CPU/GPU
work is separate from Gurobi CPU work; do not imply Gurobi ran on a GPU.

## 5. Sprint sequence and compulsory computational evaluation

| Delivery | What / how | Why and exit condition |
| --- | --- | --- |
| C1 / PR80 | Verify numerical inputs, sample/roles, representation and methods | Qualified coverage, exclusions, descriptive tables and reproducible settings |
| E0 (advanced) | Evaluate existing frozen models before new training | Complete historical coverage and bounded transfer evidence, no silent reruns |
| C2 | Easy-only versus mixed training under matched rules | Per-parent quality and full cost, no confounded architectural changes |
| C3 | Serial 1-GPU versus 2-GPU DDP, then qualified 4/8 | Same global batch, parent mass and optimizer updates; speed/efficiency/memory |
| D | Train-parent-only changed MILPs, independent labels, matched augmentation | Real diversity, preserved roles, yield/rejections and equal parent influence |
| E1/E2 | Frozen methods at all five CPU thread caps, qualified hard expansion | Paired resource curves, quality/cost, failures and censored outcomes |
| F | Writing in parallel; final synthesis, coauthor review and public release | Reproducible tables, bounded claims, rights-reviewed artifacts |

CPU caps 1/2/4/8/16 are retained; do not repeat Sprint B without a new reason.
GPU variation is compulsory, with 1-vs-2 as the first scaling comparison.
Four/eight-GPU expansion requires measured feasibility and its own bounded
budget, not an assumption that reserved GPUs imply useful work. If a level is
unavailable or unsafe, report that limitation rather than claiming its result.
Measure wall time, speedup, parallel efficiency, CPU/GPU-hours, utilization,
communication and host/device peak memory. Equal epochs alone do not guarantee
equal optimization work under DDP.

Defer embedding-size searches, multiple seeds and >3,600 s sensitivities from
the critical path. A single seed limits robustness claims. Positive results
are not required for closure; valid negative findings are retained. D remains
planned but does not block early E0. No eight-GPU or 30-hard campaign is implied
by this planning approval.

## 6. E0 execution manifest: blocked, not a submission command

| Group | Existing evidence / prospective action | Upper bound if all listed gaps are confirmed |
| --- | --- | ---: |
| Ten predictive-test parents | Reconcile M0/M4/M7/M12; check missing F0/F3/F6/F14/F27/F29 | Six easy x three methods = 18 solves |
| Six label-excluded medium | Preserve M5/M6 validation and M9/M20 test; audit M13/M26 coverage | Two medium x three methods = 6 solves |
| Hard | Choose three parents by predeclared structural criteria, before outcomes | Three x three methods = 9 solves |

These are conditional ceilings, not an admitted run list. At <=3,600 s each,
18+6 means <=24 solver-hours before preparation and overhead; the proposed hard
pilot adds <=9. Capture, inference, memory feasibility and Slurm wall budgets
must be costed separately. Reused records must match method/model/version,
resources and time policy; historical runs are not contemporaneous controls
under a changed protocol. Do not add diagnostic root optimizations invisibly
to a maximum optimization-call count.

E0 release requires all of:

1. Installed PR80 numerical return, independent review, admitted/excluded IDs.
2. Frozen historical checkpoint, threshold, prenorm provenance and safe inference.
3. Exact missing-coverage list, canonical roles and declared prior exposure.
4. Frozen three-method params, order and paired resource profile.
5. Explicit separate caps for main solves, root captures, GPU inference, memory,
   total wall budget, submissions and stop conditions.
6. Tested nonblocking submit/status/collect/receive commands, source hashes,
   no automatic retry, no hidden expansion and sanitized exports.

No optimizer command is released by this document. The next CLI is the read-only
numerical audit below. Its outcome is necessary input to E0, not bureaucracy
that can be replaced by a successful software test.

## 7. Immediate operator action: installed numerical audit

Use the already reviewed runtime commit
`13bcc3ef50f894c117af2565eec8b4e071aa3144`, whose four evidence CI arms passed.
Documentation-only follow-ups do not change these executable bytes. Fetch this
exact commit, not a moving branch head. No source/approval rebasing is needed.
If the stage already exists, do not submit again: inspect its status/receipt.

One technical allocation: batch, one node, one CPU, 16 GiB, 16 minutes, no GPU.
The numerical auditor reads existing models/artifacts without optimize, presolve,
relax, training or root capture. It uses a 900 s processing limit and one bounded
child at a time. Original data are never edited; no dependencies are installed.

### A. Bash on dgx-dasci, first execution only

```bash
conda activate tfm_env
(
  set -euo pipefail
  test "$(hostname -s)" = dgx-dasci
  REPO=/raid/vrcelestino/data/cfl-gurobi-gnn
  STAGE=/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-13bcc3ef50f8
  SHA=13bcc3ef50f894c117af2565eec8b4e071aa3144
  test ! -e "$STAGE"
  git -C "$REPO" fetch origin "$SHA"
  test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$SHA"
  mkdir "$STAGE"
  git -C "$REPO" worktree add --detach "$STAGE/source" "$SHA"
  mkdir "$STAGE/tmp"
  export TMPDIR="$STAGE/tmp"
  cd "$STAGE/source"
  git diff --exit-code HEAD
  printf '%s  %s\n' 70f26f232215503477dcc71841a8d3e5da399f32fb666076072a8b1272a56101 scripts/evidence/audit_sprint_c_numeric.py | sha256sum -c -
  python3 -B -m unittest discover -s tests/evidence -p 'test_sprint_c*.py' > "$STAGE/offline-tests.txt" 2>&1 || {
    printf 'PR80_OFFLINE_TESTS_FAILED: preserve %s/offline-tests.txt\n' "$STAGE"
    exit 2
  }
  printf 'PR80_OFFLINE_TESTS_OK\n'
  bash -n scripts/evidence/operate_pr80_numeric.sh
  bash scripts/evidence/operate_pr80_numeric.sh submit
)
```

### B. One-shot status and terminal collection, not a polling loop

```bash
OP=/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-13bcc3ef50f8/source/scripts/evidence/operate_pr80_numeric.sh
bash "$OP" status
# Only after a terminal scheduler state:
bash "$OP" collect
```

Collection emits SHA256 of numeric.json (64 hex characters, not the Git SHA).
If the stage exists without a job ID, preserve it and report that state; do not
delete the submission claim or resubmit. Failed jobs/partial audits also require
review, not automatic repetition. A completed job is not automatic admission.

### C. Windows PowerShell, one SCP connection

Use the prepared `receive_pr80_numeric.ps1` supplied with this handoff, or this
self-contained equivalent. Both download only numeric.json, check its hash and
scope, and preserve failures. No local Codex folder is necessary for this form.

```powershell
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Expected = (Read-Host 'Cole SHA256 de numeric.json: 64 caracteres').Trim().ToLowerInvariant()
if ($Expected -notmatch '^[0-9a-f]{64}$') { throw 'SHA256 invalido; nao use o commit Git.' }
$Destination = Join-Path (Get-Location) ('pr80-numeric-' + $Expected.Substring(0,12))
if (Test-Path -LiteralPath $Destination) { throw 'Destino existente: preservar, sem repetir.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
$File = Join-Path $Destination 'numeric.json'
scp 'vrcelestino@dgx-dasci.ujaen.es:/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-13bcc3ef50f8/run/results/numeric.json' $File
if ($LASTEXITCODE -ne 0) { throw 'SCP falhou: preservar, sem retry automatico.' }
if ((Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected) { throw 'Hash divergente.' }
$Result = Get-Content -LiteralPath $File -Raw | ConvertFrom-Json
if ($Result.schema_version -ne 1 -or $Result.protocol_id -ne 'sprint_c_numeric_readonly_v1' -or
    $Result.source_artifact_receipt_sha256 -ne 'e0b51fce0ad3e207c1f0a72b1b5678c89974f8fe856a1918a7b189b0ae981681' -or
    $Result.implementation_sha256 -ne '70f26f232215503477dcc71841a8d3e5da399f32fb666076072a8b1272a56101' -or
    $Result.training_admitted -cne $false -or $Result.scientific_reporting_eligible -cne $false -or
    $Result.raw_logs_included -cne $false -or $Result.optimization_runs_added -ne 0 -or $Result.submissions_added -ne 0 -or
    @($Result.parents.PSObject.Properties).Count -ne 54 -or
    $Result.cohorts.easy.parents -ne 30 -or $Result.cohorts.mixed.parents -ne 54 -or
    $Result.limits.wall_seconds -ne 900 -or $Result.limits.child_seconds -ne 90 -or
    $Result.limits.child_address_space_bytes -ne 17179869184 -or $Result.limits.cpu_affinity_count -ne 1) {
    throw 'Contrato inesperado: preservar para revisao.'
}
$States = @($Result.parents.PSObject.Properties | ForEach-Object { $_.Value.state })
[pscustomobject]@{
    receipt_sha256 = $Expected
    easy_numeric_checks_passed = $Result.cohorts.easy.numeric_checks_passed
    mixed_numeric_checks_passed = $Result.cohorts.mixed.numeric_checks_passed
    parents_passed = @($States | Where-Object { $_ -eq 'numeric_checks_passed' }).Count
    parents_unqualified_or_not_attempted = @($States | Where-Object { $_ -ne 'numeric_checks_passed' }).Count
    training_admitted = $false
    downloaded_directory = $Destination
} | ConvertTo-Json
Write-Host 'PR80_NUMERIC_TRANSFER_HASH_AND_SCOPE_OK: return receipt and accounting; no retry or merge.'
```

Independent numerical-audit source is
[audit_sprint_c_numeric.py](../../scripts/evidence/audit_sprint_c_numeric.py).
The receiver's successful transfer does not change training_admitted=false.
Return job/accounting output and the sanitized receipt for independent review.
No raw logs, passwords, license content or private paths are published.

## 8. Documentation and PR completion contract

Every experimental branch must update repository docs, not only a chat:

- Before execution: question, what/how/why, exact sample/model, parameters,
  budget, analysis, stopping rules and complete operator instructions.
- At closure: actual execution IDs/configurations, evidence and limitations,
  failed/censored cases, tests versus scientific validation, decision and next
  step. Link readable summaries to immutable machine-readable artifacts.
- PR descriptions point here and to experiment reports; comments are updates,
  not the sole specification. Merge is requested only after completion/ready.

This consolidated document is the current entry point; split it into linked
sample/method/resource pages when adding results, without duplicating configs.
Historical documents remain preserved. Publish sanitized outputs only, not
meeting personal details, private HPC logs or licenses.

### PR80 remaining closure checklist

- [x] Review metadata and selected bytes/roles; preserve original receipts.
- [x] Establish exact sample identities, method explanation and CPU/GPU contract.
- [x] Prepare and test bounded numeric auditor; qualify pinned runtime CI.
- [ ] Receive installed numeric report and independently review all 54 parents.
- [ ] Complete descriptive numerical tables, exclusions and representation decision.
- [ ] Reconcile E0 coverage/checkpoint provenance and freeze its resource manifest.
- [ ] Publish closure report, exact-head CI and ready-for-review state.
- [ ] Obtain merge authorization; no merge is performed by this plan.

## 9. Coauthor meeting: 22 October 2026

Prepare a new approximately 18-slide Spanish presentation, after incorporating
available receipts. Explain the scientific story rather than enumerating PRs:
question and MVP1 legacy; population/splits; descriptive sample statistics;
three-method pipeline; reproducible settings; A-B findings/limitations; C1
audit; existing versus new E0 outcomes; CPU/GPU design and measured results;
C-F roadmap and decisions. Clearly label planned, executed and reviewed work.
Target: consolidated PR80, explicit E0 coverage and resource design, and available
new findings. Do not promise completed GPU/hard campaigns by that date.

F runs in parallel for table templates and editorial review. Final release
requires coauthor review, rights/privacy checks and a verified actual deposit.
No journal acceptance, 200 GB quota or public DOI is presumed.

## Job3502 amendment: preserve 39 observations; finish 15 pending audits

The integrated return SHA256 is
`83366f115e15fbbf6a548cf404abf27f4b05d6ecff04fa5cc43d673c1fbef2c4`.
Thirty easy observations were reused and nine medium observations newly passed.
Fifteen medium labels stopped at the objective-sense string check. The auditor
now accepts the two historical minimization spellings, without changing the
mathematical contract. Continue only these 15 audits, then the four already
planned validation forwards if all qualify. No training, optimization, package
upgrade or automatic retry. See [current execution details](pr80-integrated-existing-runtime.md).

