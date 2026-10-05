# Nonblocking short callback qualification workflow

This follows the merged isolated worker (PR71). It implements orchestration,
not authorization to spend resources, a successful installed qualification,
or the prospective 3600-second comparison. A merge authorizes none of these.

## Proposed budget, separately awaiting human approval

One original training parent, `CFL_easy_instance_17`, seed 42, solver Threads=1;
one optimization call with TimeLimit=60 seconds, the original 1% stopping gap,
default algorithms and SoftMemLimit=48 GiB. The separate child deadline is
240 seconds plus the inherited terminate/kill grace periods. A single batch
job has an outer wall limit of 600 seconds, one node/task, 16 requested CPUs,
64 GiB, `nomultithread`, no GPU or exclusive allocation. The worker still
requires 16 distinct physical cores, and chooses one logical sibling per
core. Slurm accounting may record 32 logical CPUs; do not equate that with
32 physical cores or change the worker's protection.

The reservation ceiling is 2.667 requested CPU-hours (16 x 10/60), potentially
5.333 accounting CPU-hours if the site allocates 32 logical CPUs. This is a
ceiling, not expected runtime, measured consumption or a throughput claim.
The easy parent is a minimal plumbing test, not a replacement of the frozen
easy/medium comparison pair and not an outcome-selected scientific sample.

## State and authority

`prepare` -> unapproved plan -> external human budget approval -> `submit`
-> one-shot `status` -> terminal accounting -> `collect` -> independent review.

Preparation reads the existing PR70 receipt, immutable public identities and
source hashes. It never reads an LP/license, imports Gurobi, optimizes, trains,
submits, or regenerates the installed preflight. It writes a canonical plan
and an **unapproved** `approval.json` template. The template must not be changed
until the human separately approves this exact plan and budget. Production has
no approval-creation command. After explicit approval, the operator records it
in canonical JSON and supplies its SHA256 to `submit`. The record is a local
operator assertion, not cryptographic proof of the human's identity or intent.
Hashes bind bytes and ceilings, not authorization by themselves.

The source head, ten dependency/launcher hashes, PR69 proposal, original parent,
parameters, PR70 receipt and scheduler ceilings are bound into the plan hash.
Approval binds that plan, one submission and one optimizer call. The submitted
request retains the exact eight worker dependency pins. A dirty checkout,
changed plan, missing approval, false approval, duplicate approval claim,
wrong source or unexpected location stops before submission.

## Commands and nonblocking behavior

Use only the prepared detached source on physical `/raid/vrcelestino/data` in
`tfm_env` on `dgx-dasci`. Keep its flow directory outside that checkout. Operator
helpers provide the exact reviewed source head and staging paths.

```bash
# Safe now; PREFLIGHT is the existing reviewed PR70 receipt.
python3 -B "$SOURCE/scripts/evidence/qualification_workflow.py" prepare \
  --directory "$FLOW" --preflight "$PREFLIGHT"

# Only AFTER separate explicit approval and canonical approval recording:
python3 -B "$SOURCE/scripts/evidence/qualification_workflow.py" submit \
  --directory "$FLOW" --approval-sha "$APPROVAL_SHA256"

# Each query returns once; no polling loop, --wait, sleeps or terminal hold.
python3 -B "$SOURCE/scripts/evidence/qualification_workflow.py" status \
  --directory "$FLOW"

# Run after the allocation row is terminal, not just a batch/step row.
python3 -B "$SOURCE/scripts/evidence/qualification_workflow.py" collect \
  --directory "$FLOW"
```

The only optimizer route is `run` inside the matching recorded Slurm JobID.
It invokes the merged worker unchanged. The batch file uses the established
`srun --hint=nomultithread --cpu-bind=verbose` combination; not `bind=cores`.
There is no launcher loop, job array, concurrent experiment or auto-restart.

`submit` first creates a persistent, globally keyed approval claim, writes
the exact request, then calls `sbatch --parsable --hold` once. Its JobID is
written and fsynced before one `scontrol release`. This closes the race where
the batch might start before its submission receipt exists. Interactive
scheduler calls have a 20-second command timeout, not an execution wait.
`SBATCH_*` and `SRUN_*` overrides are removed from the submission environment.

If submission times out, the scheduler may have accepted a held job even when
the caller cannot prove its ID. Preserve the claim, request and staging and
request read-only reconciliation; **never submit again**. If release fails,
the retained JobID permits read-only inspection; this command does not retry
release or delete/cancel anything. A manual release/reconciliation requires
explicit operator direction. Claims remain even after failures.

`status` uses one `sacct --noheader --parsable2` call. Only the exact allocation
JobID determines terminal state. Steps are kept separately; never sum their
CPU/RSS together with allocation totals. Empty accounting is explicitly
unavailable; unknown/ambiguous fields fail closed. CANCELLED suffixes are
normalized without exporting UID/free text. Accounting is evidence from the
scheduler interface, not independent resource attestation.

## Collection and independent review

Collect only after terminal allocation accounting. Missing/incomplete worker
receipts stop collection: a Slurm kill cannot be turned into a fabricated
zero-call result. Private closed logs and child bytes are re-sealed through
the original worker validator. Every present child JobID must match the
submission/accounting ID. A completed allocation with a failed worker is
still paused, not a success. Failures with an intact worker receipt can be
returned for diagnosis while retaining unknown optimization-call counts.

The returned directory contains only `qualification_package.tar.gz` and its
outer SHA256 manifest. The archive contains exactly `accounting.json`,
`attempt.tar.gz`, and `SHA256SUMS.txt`. The nested archive contains the worker's
three existing public files; no raw logs, source LPs, vectors, credentials,
approval free text or home/RAID paths. Hash, canonical schema, compressed and
expanded sizes, member allowlists, duplicates, links, sparse/PAX extensions,
and hidden trailing bytes are checked without filesystem extraction.

```bash
# Offline independent check with an externally received package SHA:
python3 -B scripts/evidence/qualification_workflow.py validate \
  --package qualification_package.tar.gz --expected-sha "$PACKAGE_SHA256"
```

Collection never overwrites an existing return directory; keep partial exports
for read-only diagnosis. Download only the two named public files. Local hash
verification precedes independent nested schema/contract review. Raw Slurm,
solver and console files remain private on RAID.

`ready_for_independent_review` means clean allocation exit plus valid completed
worker, not successful scientific qualification. Every public scientific,
installed-callback and scheduler qualification flag remains false until an
independent review approves a later receipt. No root/tree CPU decomposition,
zero-objective crossing qualification or measured callback-overhead correction
is inferred. The original 3468 medium-16 observation remains unqualified.

## Verification and next gate

Offline tests use synthetic scheduler/process/API data only. They cover
unapproved plans, exact approval/head/parameter pins, duplicate global claims,
hold/write/release ordering, timeout/release ambiguity, JobID binding,
one-shot accounting, missing receipts, private-log tampering, completed and
failed sanitized exports, and archive bounds/allowlists. Require all four
evidence CI arms at the exact published head before operator preparation.

The next external gate is the separately approved short budget. After its
single attempt returns, review the actual installed callback telemetry,
affinity, memory, clocks, sealed logs and accounting. Only that review can
justify a qualified receipt and discussion of the PR69 comparison budget.
It cannot by itself finish Sprint B or approve training/GPU experiments.

References: [Slurm sbatch](https://slurm.schedmd.com/sbatch.html),
[Slurm sacct](https://slurm.schedmd.com/sacct.html).
