# PR78 paired execution runbook — 2026-10-06

> Historical instructions: the budget was subsequently approved and job 3481
> was submitted, held, and reported cancelled by the operator. Do not rerun the
> starters below. The [current diagnosis and revised interaction contract](pr78-job3481-recovery.md)
> supersede the false-approval checkpoint and interactive confirmation below.

## Verified checkpoint and authority

PR77 is merged into develop at `eaeb9aed1ca24680c8e2f0fab1b0cdabae58f7e8`.
Its reviewed source remains `30f80577fa7302348ed3807551e3b2c660779faf`.
PR78 planning head `47b697476f84832b03dd84bc0804f7b6a59e0610`
passed all four evidence CI arms in run 37515548319. Any later head has its own CI.

This runbook does not assert execution, approve resources or authorize merge.
PR78 stays draft until paired execution/evidence is independently reviewed.
The [delivery plan](mvp2-delivery-plan-20261006.md) contains the remaining sprints;
its earlier PR77-pending paragraph is a historical checkpoint superseded here.

Reuse the installed PR76 flow and thirteen pinned runtime dependencies.
Do not prepare again, pull develop into that source or rerun previous jobs/probes.
The production source remains `ad4800505bae78032e8fdbaa449a7afd2f12a080`.

- Operator plan: `c7f5aa69c775088e7d383a942d9ee66f2b053dfe656e5d123e80e546692f70a2`.
- Matrix plan: `b24dbe0924a2c6f03f7f162cf2f85bfd327f4a0bd99048b98200b6f22e5a575b`.
- Installed PR76 receipt: `0249a1de5cb6d06422932d7ffa5568a2077ceb0c6f51099a5675a6f33fdeca14`.
- Installed PR77 receipt: `bdbb0f75358d6c15523a05bec9c97d72fb49c90c1ab08c4f72d2b275ce501286`.

## Prompt failure and bounded continuation

The first transferred helper (SHA256
`6b2077bcb8cea56a1d4bcf28e9af8fa62a7d53047a8c4f8f71835e31037a58e7`)
failed opening `/dev/tty` in Python `r+` mode with
`io.UnsupportedOperation: File or stream is not seekable`.
The reported traceback occurred before the confirmation read, authorization
generation, budget-stage creation, recording or submission. The original
seekable StringIO mock did not reproduce the terminal property.

The v2 handoff opens output in `w` and input in `r`, separately. Six offline
tests now cover the original nonseekable failure, refusal leaving false gates,
explicit recording of exact approval hashes using nonseekable streams, replay,
prior-budget-stage refusal, and bounded single-easy submission structure.
They are synthetic wrapper tests, not additional HPC qualification or solver runs.
Before asking for confirmation, the v2 helper rechecks the original false
approvals, clean pinned source, absence of submission state and budget stage.
Unexpected state stops for review; it does not remove claims or resume jobs.

Retain the original helper on HPC. Transfer v2 to a new
`pr78/install-prompt-fix-v2` directory; this is correction of a pre-submission
CLI failure, not an optimization retry. No resource approval is inferred from
the error report. Status, collection, return validation and medium review gates
below remain unchanged. No merge is authorized.

## Resource envelope and stopping policy

Two distinct sequential parent jobs, at most five fresh-process attempts each:
easy `CFL_easy_instance_17`, order 8/2/4/1/16 threads, target gap 1%;
medium `CFL_medium_instance_1`, order 16/8/2/1/4 threads, target gap 10%.
Seed 42, effective MINIMIZE, Gurobi 13.0.1 defaults, no GNN/warm start.
Each optimize call is bounded by 3600 seconds; child deadline 3780 seconds.
Each allocation: batch, one node/task, 16 physical cores, 64 GiB,
330 minutes, no GPU/exclusive/requeue/retry.

Ceilings: 10 solver hours and 11 allocation hours, excluding queue/review.
176 requested physical-core reservation hours are a ceiling, not observed CPU use.
If Slurm accounts 32 logical CPUs, its corresponding ceiling is 352 logical CPU
hours; the two scopes must not be equated.

Keep solver SoftMemLimit 48 decimal GB, sampled job-leaf interruption at 56 GiB,
0.25-second sampling, and the fail-closed finite kernel-limit/affinity/swap gates.
Historical RSS and installed synthetic probes do not qualify real allocations.
Missing or invalid gates stop before model/license access. Preserve failed and
partial evidence; never remove claims or STOP files to force continuation.

New files stay on the physical RAID evidence tree. The existing license remains
at `/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic`; do not copy,
print or export it. Only the named public receipts are transferred.

## 1. dgx-dasci Bash: explicit budget confirmation and easy submission once

The byte-preserving local helper has SHA256
`170f41a9ff6afab644e0064269393131fc54742ea24c60cbc5689531733ad521`.
For the prepared workstation copy, execute `outputs/send_pr78_easy_v2.ps1` in local
Windows PowerShell. It verifies that hash, creates a fresh physical RAID
`pr78/install-prompt-fix-v2` directory, then transfers only `start_pr78_easy_v2.sh`.
It does not log in to GitHub, alter any approval, or submit a job. A pre-existing
installation directory or failed transfer stops without an automatic overwrite.
The wrapper's embedded Python and refusal/recording/replay behaviour passed six
temporary synthetic local tests, and both PowerShell files parsed. Local MSYS
Bash syntax checking was unavailable due to Windows sandbox restrictions; run
`bash -n` on the received helper before invoking it on dgx-dasci.

Activate `tfm_env` first. Save the following as `start_pr78_easy_v2.sh` on the
local workstation if using SCP, or execute its contents in Bash on dgx-dasci.
It does not assume the general permission to advance PR78 approved resources.
The terminal asks for the separate exact-budget confirmation; an empty/different
answer exits without recording or submitting. The CI/probe flags refer to the
independently reviewed original runtime, not an unreviewed future source.
Recording uses PR77's qualified implementation; submission uses PR76's original
implementation. There is no automatic recovery after a partially recorded budget.

```bash
#!/usr/bin/env bash
# Corrected CLI prompt; original failed before approval. Execute once on dgx-dasci.
set -euo pipefail
umask 077
PR78_FLOW=/raid/vrcelestino/data/cfl-mvp2-evidence/pr76/operator-ad4800505bae/flow
PR78_BUDGET_SOURCE=/raid/vrcelestino/data/cfl-mvp2-evidence/pr77/installed-budget-30f80577fa73/source
PR78_OPERATOR_SHA=2c117f2bc9325673f80a633e185f33709ae90de2faf37b0c020030f913c2971d

# Verify the already-qualified budget recorder; do not reinstall or reprepare.
printf '%s  %s\n' \
  517cc195670d51e7d19581188d22844d948a3080555546d76e19d93069449735 \
  "$PR78_BUDGET_SOURCE/scripts/evidence/paired_budget_authorization.py" |
  sha256sum --check --strict

python3 -B - "$PR78_BUDGET_SOURCE" "$PR78_FLOW" <<'PY'
import os
import subprocess
import sys
from pathlib import Path

source = Path(sys.argv[1])
directory = Path(sys.argv[2])
expected_head = "30f80577fa7302348ed3807551e3b2c660779faf"
command = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
if subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() != expected_head:
    raise SystemExit("PR78_STOP_WRONG_BUDGET_SOURCE")
if subprocess.check_output(command + ["status", "--porcelain", "--untracked-files=all"], text=True):
    raise SystemExit("PR78_STOP_DIRTY_BUDGET_SOURCE")
sys.path.insert(0, str(source / "scripts/evidence"))
import paired_budget_authorization as budget

os.umask(0o077)
directory, plan, execution = budget.frozen_flow(directory)
stage = budget.flow.matrix.adapter.EVIDENCE_ROOT / "pr78/budget-ad4800505bae"
if stage.exists() or stage.is_symlink():
    raise SystemExit("PR78_STOP_PRIOR_BUDGET_STAGE_PRESERVE_FOR_REVIEW")
print("PR78_ORIGINAL_FALSE_APPROVALS_AND_NO_SUBMISSION_STATE_VERIFIED")
print("Frozen budget: <=2 sequential jobs, <=10 optimize calls, <=36000 solver seconds.")
print("Each job: batch, 16 physical cores, 64 GiB, <=19800 seconds; CPU only/shared node.")
print("Easy gap=1%; medium gap=10%; seed=42; original parents and thread order unchanged.")
print("Memory gates mandatory: solver soft=48 decimal GB; sampled stop=56 GiB; kernel <=64 GiB.")
print("No requeue, retry, extension, raw-log export or scientific promotion.")
print("Medium requires a separate independent review of the easy return.")
print("This explicit confirmation records the resource budget AND permits one easy submission.")
phrase = "APPROVE PR78 FROZEN BUDGET AND SUBMIT EASY ONCE"
with open("/dev/tty", "w", encoding="utf-8") as tty_output:
    tty_output.write("Type exactly: " + phrase + "\n> ")
    tty_output.flush()
with open("/dev/tty", "r", encoding="utf-8") as tty_input:
    answer = tty_input.readline().rstrip("\n")
if answer != phrase:
    raise SystemExit("PR78_BUDGET_NOT_APPROVED_NO_SUBMISSION")
authorization = budget.template(directory)
for name in (
    "explicit_resource_budget_and_submission_approved",
    "exact_head_four_ci_arms_reviewed",
    "installed_no_solver_probes_reviewed",
):
    authorization[name] = True
if stage.resolve() != stage:
    raise SystemExit("PR78_STOP_NONPHYSICAL_STAGE")
stage.parent.mkdir(mode=0o700, exist_ok=True)
if stage.parent.resolve() != stage.parent:
    raise SystemExit("PR78_STOP_NONPHYSICAL_PARENT")
stage.mkdir(mode=0o700, exist_ok=False)
budget.flow.sync_dir(stage.parent)
path = stage / "explicit_budget_authorization.json"
budget.flow.write(path, authorization)
sha = budget.flow.digest(path)
result = budget.record(directory, path, sha)
budget.flow.write(stage / "budget_recording.json", result)
if result["operator_approval_sha256"] != "2c117f2bc9325673f80a633e185f33709ae90de2faf37b0c020030f913c2971d":
    raise SystemExit("PR78_STOP_UNEXPECTED_OPERATOR_APPROVAL")
print(budget.contract.encoded(result).decode(), end="")
print("PR78_BUDGET_RECORDED_NO_SUBMISSION_YET")
PY

# No --wait; no loop; exactly one submission through the original qualified source.
python3 -B "$PR78_FLOW/../source/scripts/evidence/paired_matrix_workflow.py" submit \
  --directory "$PR78_FLOW" --parent easy --approval-sha "$PR78_OPERATOR_SHA"
printf '%s\n' 'PR78_EASY_SUBMISSION_RETURNED_NO_WAIT_NO_AUTOMATIC_MEDIUM'
```

This command returns after submission. Do not rerun it if any step fails:
preserve the output and claims for review. If recording succeeded but submission
was never entered, a reviewer must check this before any manual continuation.

## 2. dgx-dasci Bash: one-shot status and later terminal collection

These commands are separate; neither waits for job completion. Re-establish
variables in a new shell. Query status whenever desired. Collect only after
terminal=true; collection itself performs one query and returns immediately if
nonterminal. Slurm COMPLETED alone is not proof of a valid complete matrix.

```bash
conda activate tfm_env
PR78_FLOW=/raid/vrcelestino/data/cfl-mvp2-evidence/pr76/operator-ad4800505bae/flow
python3 -B "$PR78_FLOW/../source/scripts/evidence/paired_matrix_workflow.py" status \
  --directory "$PR78_FLOW" --parent easy
```

After terminal=true:

```bash
python3 -B "$PR78_FLOW/../source/scripts/evidence/paired_matrix_workflow.py" collect \
  --directory "$PR78_FLOW" --parent easy
```

Record the printed `return_sha256`, job ID and readiness flag. The sealed return
is `FLOW/return-easy`. Collection is read-only/idempotent once that return exists;
a failed partial collection is NOT automatically resumed.

## 3. Local Windows PowerShell: public return download and nested validation

Save this block as `outputs/receive_pr78_parent.ps1` beneath the task directory.
It uses the retained clean PR77 checkout for the existing cross-platform
validator. No extraction, private log transfer, scheduler call, approval or
scientific review occurs on the workstation. A failed/partial return without a
matrix archive can still be downloaded and validated as a negative disposition.

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('easy','medium')][string]$Parent,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReturnSha
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$TaskRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $TaskRoot 'work/pr77-installed-operator-budget'
$Validator = Join-Path $Source 'scripts/evidence/paired_matrix_workflow.py'
$Python = 'C:/Users/cvict/miniconda3/python.exe'
$Head = & git -C $Source rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $Head.Trim() -ne '30f80577fa7302348ed3807551e3b2c660779faf') {
    throw 'Wrong local validator source; preserve checkout.'
}
$Dirty = & git -C $Source status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0 -or $Dirty) { throw 'Local validator checkout is dirty.' }
if ((Get-FileHash -LiteralPath $Validator -Algorithm SHA256).Hash.ToLowerInvariant() -ne '3154af8765aeaf50aed1f5df13b86bc138d5fe1b49b7a69d28d490495392df67') {
    throw 'Validator dependency pin mismatch.'
}
$Remote = "vrcelestino@dgx-dasci.ujaen.es:/raid/vrcelestino/data/cfl-mvp2-evidence/pr76/operator-ad4800505bae/flow/return-$Parent"
$Destination = Join-Path $PSScriptRoot ("pr78-" + $Parent + "-" + $ExpectedReturnSha.Substring(0,12))
if (Test-Path -LiteralPath $Destination) { throw 'Destination exists: preserve it; no automatic retry or overwrite.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
& scp "$Remote/SHA256SUMS.txt" "$Destination/"
if ($LASTEXITCODE -ne 0) { throw 'Manifest transfer failed: preserve partial directory.' }
$Manifest = Join-Path $Destination 'SHA256SUMS.txt'
if ((Get-FileHash -LiteralPath $Manifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedReturnSha) { throw 'Return SHA mismatch.' }
$Names = @()
foreach ($Line in (Get-Content -LiteralPath $Manifest)) {
    if ($Line -cnotmatch '^[0-9a-f]{64}  (accounting.json|operator_approval.json|operator_plan.json|submission.json|matrix.tar.gz)$') {
        throw 'Unexpected manifest member; no private or raw-log download permitted.'
    }
    $Name = $Matches[1]
    if ($Names -contains $Name) { throw 'Duplicate manifest member.' }
    $Names += $Name
}
foreach ($Required in @('accounting.json','operator_approval.json','operator_plan.json','submission.json')) {
    if ($Names -notcontains $Required) { throw 'Missing public receipt member.' }
}
$Sources = @($Names | ForEach-Object { "$Remote/$_" })
& scp @Sources "$Destination/"
if ($LASTEXITCODE -ne 0) { throw 'Public return transfer failed; preserve partial directory; no retry.' }
& $Python -B $Validator validate-return --directory $Destination --expected-sha $ExpectedReturnSha
if ($LASTEXITCODE -ne 0) { throw 'Nested contract validation failed; preserve evidence; no medium submission.' }
$Accounting = Get-Content -Raw -LiteralPath (Join-Path $Destination 'accounting.json') | ConvertFrom-Json
if ($Accounting.parent -ne $Parent) { throw 'Unexpected parent in return.' }
Write-Host "PR78_DOWNLOAD_HASH_AND_NESTED_CONTRACT_OK: $Destination"
Write-Host "READY_FOR_INDEPENDENT_REVIEW=$($Accounting.ready_for_independent_review)"
Write-Host 'Return this directory and collection receipt. Validation is not independent scientific review; do not create easy.review.json yourself.'
```

Invoke locally, not in Bash or on service0:

```powershell
& "C:/Users/cvict/Documents/Codex/2026-10-03/github-plugin-github-openai-curated-remote-8/outputs/receive_pr78_parent.ps1" `
  -Parent easy -ExpectedReturnSha (Read-Host "Paste easy return_sha256")
```

Return the collection receipt and downloaded directory for independent review.
Automatic nested validation is not that review. In this same PR archive safe
receipts, all hashes, accounting, model/parameter identities, memory gate results,
attempt completeness, censoring and unresolved discrepancies. No raw logs.

## 4. Medium gate: commands prepared, NOT permitted before easy review

The independent reviewer must inspect the actual returned bytes, not only a
pasted success message, then provide the hash-bound `easy.review.json` if it
passes. This runbook intentionally does not mint a positive review in advance.
The operator validates that review against return-easy and freshly checks easy
accounting before admitting medium. Preserve any failure; do not relax checks.

Only after that review file has been supplied, transferred and hash checked:

```bash
conda activate tfm_env
PR78_FLOW=/raid/vrcelestino/data/cfl-mvp2-evidence/pr76/operator-ad4800505bae/flow
read -r -p 'Paste the independently supplied EASY_REVIEW_SHA256: ' PR78_EASY_REVIEW_SHA
printf '%s  %s\n' "$PR78_EASY_REVIEW_SHA" "$PR78_FLOW/easy.review.json" |
  sha256sum --check --strict &&
python3 -B "$PR78_FLOW/../source/scripts/evidence/paired_matrix_workflow.py" submit \
  --directory "$PR78_FLOW" --parent medium \
  --approval-sha 2c117f2bc9325673f80a633e185f33709ae90de2faf37b0c020030f913c2971d \
  --easy-review-sha "$PR78_EASY_REVIEW_SHA"
```

Then one-shot status, later terminal collection, and local receiver with
`-Parent medium`:

```bash
python3 -B "$PR78_FLOW/../source/scripts/evidence/paired_matrix_workflow.py" status \
  --directory "$PR78_FLOW" --parent medium
# Run the following separately, only after terminal=true.
python3 -B "$PR78_FLOW/../source/scripts/evidence/paired_matrix_workflow.py" collect \
  --directory "$PR78_FLOW" --parent medium
```

## Delivery closure

No merge permission is requested before the PR is complete and ready for review.
Keep interruption/failure dispositions in this delivery; do not create a PR per
helper/receipt. Actual complete paired returns and accounting review enable the
next Sprint B delivery: within-parent censored-time analysis and resource profile
selection. Two fitting parents and one seed support descriptive conclusions only.
Do not pool 1%/10% target times or claim continuous first crossings, historical
memory reconciliation, root/tree CPU phase qualification or GNN gains from this
CPU-only pilot. Scientific promotion requires its own evidence-backed review.
