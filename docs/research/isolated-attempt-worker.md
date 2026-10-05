# Sprint B: isolated qualification worker and sealed result exports

## Delivery and non-authority

This increment follows the authorized PR70 merge into develop at
`775790afc404ec3ac890cd486e27315802592777`. It implements one fresh Python
process/model/environment, callback integration, disjoint phase clocks, a
process-group watchdog, post-disposal log binding, and an independent public
receipt/archive validator. It provides **no Slurm launcher, matrix runner,
approval compiler, authorized request, retry, installation or new experiment**.
The public CLI only validates or exports existing evidence; it cannot solve.

The narrow executable library entry is `supervise_one(request, output)` for a
future reviewed operator workflow. That workflow must first obtain the human's
explicit resource approval and verify the approval record, exact public head,
CI, dependency bytes, allocator/walltime and source/role contracts. This module
does not create or independently establish human approval. Code merge and a
passing no-optimization preflight do not authorize execution. The schema's
boolean/reference alone cannot establish human intent: an unsigned request is
an operator assertion bound to a retained approval-record
SHA, **not a cryptographic authorization certificate or remote attestation**.
Do not generate or execute a request until that external authority gate passes.

The only accepted protocol is `single_attempt_callback_qualification_v1`:
one optimization call, 1–300 approved optimize seconds, an independent child
deadline of optimize budget +180 seconds, and ten-second TERM/KILL wait grace
periods. The approval record's SHA is a persistent, globally unique claim across
output directories. Requests with the same approval reference cannot be reused,
even with changed limits or source. Fresh output and child/worker claims also
prevent re-entry. Claims are intentionally retained on failures, including
launch failure. Do not remove them or automatically retry.

The approved request must bind exact source Git SHA, all eight dependency byte
hashes (including this worker), immutable PR69 proposal semantic SHA and the
independently reviewed PR70 installed preflight receipt SHA
`f8077c9c2abcb77ca3b1bf36133bb07b5bfe43b05bea9395da6e39908956fb00`.
Only the original easy17/medium1 fitting instances, seed42 and their frozen
cap/stop identities can be selected. This **separate qualification experiment**
uses its approved shorter TimeLimit and is not a row of the disabled 3600-second
comparison. The PR69 proposal bytes/flags remain unchanged. No one-hour
comparison, replication or population-scaling execution is enabled here.

## Worker lifecycle and clocks

The supervisor validates canonical dgx-dasci/tfm_env, single-node Slurm CPU
allocation, 16 CPUs per task, 64-GiB requested node memory, no job/step GPU IDs,
entirely clean pinned source (including untracked files) below physical RAID,
and fresh output below physical
`/raid/vrcelestino/data/cfl-mvp2-evidence`. The child repeats the gate and verifies
the retained approval claim's request and output-path digest. A second child or
worker entry is refused before licensing/model loading. The canonical PR66
physical-core mask retains one logical processor for each of exactly16 physical
cores. Actual allocator topology/cost and higher-budget memory qualification
still require review; environment variables alone do not certify the scheduler.

The child uses the canonical license guard and Gurobi13.0.1, reads one frozen
original LP, checks source bytes/linear-MIP structure, applies the established
MAX-to-MIN objective convention in memory, resets parameters and checks the
thirteen defaults against the PR70 installed preflight values. It sets only the
approved cap/seed/TimeLimit/gap/SoftMemLimit plus operational logging. A fresh
empty environment has ThreadLimit16; there is no checkpoint or warm start.
`model.optimize(callback)` is invoked once. No vector, candidate assignment,
node relaxation, cut or start is read/injected.

Read/setup, optimize-call and model/environment disposal have distinct external
wall/current-process CPU intervals. The phase recorder is separate from callback
telemetry, allowing cleanup to be timed after terminal telemetry is finalized.
Terminal attributes are read after the timed optimize call, while the model
still exists. Terminal inspection, source rehashing, log sealing and receipt
serialization are **outside those three phase intervals**; phase durations
must not be reported as complete process wall time. Current-process CPU since
Python startup and Linux process peak RSS are separate observations, not Slurm
aggregate costs. Slurm job identity is retained for future accounting linkage.
Solver Runtime and measured callback overhead remain separate and no overhead
is subtracted. Root/tree costs, continuous first crossing and primal integral
are not qualified.

ExitStack disposes model before environment even after read/optimize faults.
Only after successful disposal is the bounded private Gurobi log hashed with
size. Cleanup failure cannot certify a closed writer and receives no sealed-log
digest. The original LP is rehashed; model bytes are never rewritten. The child
persists a strict allowlisted receipt with fixed failure codes, not exception
messages. The parent waits for actual child exit, closes its console writer,
seals the private whole-process console and binds the exact child receipt bytes.
It re-seals the solver log before accepting the child's digest.

## Failure and watchdog semantics

The batch-task supervisor starts a new child session, waits with the independent
deadline and targets only that child's process group. Timeout requests TERM,
then KILL if the child does not exit within the grace period; exit is reaped.
A Python-level supervisor interruption kills/reaps before propagating. Process
creation/file I/O/sealing are not bounded by the child wait timeout; the future
operator workflow must also bind an adequate outer Slurm wall limit. An OS kill
of the supervisor can leave incomplete private evidence/no final receipt; this
requires read-only external reconciliation, not a retry.

Only a validated child with gap-target or time-limit stop is `completed`.
Memory/other stops, callback faults, cleanup/source/log failures pause the
remaining workflow. Watchdog and nonzero-process exits have **unknown** actual
optimization count (`null`), never a fabricated zero. One approved call is an
upper bound, not evidence it occurred. An invalid/oversized/truncated child
receipt is not accepted as a result; the original private files remain intact.
No remaining matrix is actually launched by this module.

Storage exhaustion is deliberately fail-closed for full exports. Although the
PR70 adapter continues tracking aggregate crossings after its10000-sample cap,
those missing events cannot be independently reconstructed from the exported
prefix. A child with dropped samples is rejected/preserved and no successful
result is exported. This does not change the adapter, old collectors, original
tolerances or medium16's unqualified state.

## Independent validation and public export

The validator enforces strict canonical JSON, no duplicate keys/nonfinite
numbers, allowlisted schemas, original proposal/attempt/source dependencies,
exact effective parameters/defaults, affine-mask shape, clocks/counters,
terminal status/bounds/gap consistency, disjoint phases and qualification flags.
It independently rebuilds retained samples, terminal observation, overshoot and
first-sampled10/5/1% target states using PR69's definitions. Hashes bind logs to
receipts; they are **not a numerical footer/API timing reconciliation**, a proof
of incumbent feasibility/uniqueness or a signed authenticity certificate.

Export revalidates the retained child bytes and closed private logs before
writing a fresh archive. Exactly three regular public members are permitted:
`request.json`, `attempt_receipt.json`, `SHA256SUMS.txt`. The outer package has a
separate SHA256 manifest. No raw log, LP, license content/path, exception text or
solution vector is copied. Failure packages remain failure packages; a valid
checksum never grants scientific eligibility. Scientific, live-callback and
affinity/higher-budget-memory qualification flags stay false in every receipt.

Archive review requires an independently supplied outer SHA, bounds compressed
and decompressed bytes, reads without extraction, rejects extra/duplicate/path
traversal/link/sparse/PAX members and hidden trailing data, and then runs the same
inner hash/schema/contract validator. Use the exact pinned worker version whose
dependency bytes are bound in the request, not a later mutable checkout.

The following are **non-solving interfaces**, not executable placeholders for
new HPC runs:

```text
isolated_attempt_worker.py validate --directory EXISTING_PUBLIC_RECEIPT_DIRECTORY
isolated_attempt_worker.py validate --package EXISTING_PACKAGE --expected-package-sha VERIFIED_OUTER_SHA
isolated_attempt_worker.py export --directory EXISTING_PRIVATE_ATTEMPT --output FRESH_RETURN_DIRECTORY
```

## Remaining gates

Offline fake-Gurobi/process tests and exact-head four-arm CI qualify code paths,
not installed licensed callback execution. A tiny separately budgeted licensed
fault/overhead qualification still needs explicit human approval and a frozen
operator workflow before any CLI hand-off. Next build/review that approval and
nonblocking single-job submission/status/collect/receive workflow, reconcile
actual Slurm accounting and assess qualification receipts independently. Only
then consider a separately approved comparison/replication resource budget.
Sprint B, historical incumbent certification and scientific reporting remain
incomplete. Main/MVP1/Pages/Zenodo/manuscript/presentation and jobs3466/3468 are
preserved; no new solve or training result is claimed.

Implementation references: [Gurobi environment lifetime](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/env.html),
[Model.optimize and disposal](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html),
[Python subprocess sessions/timeouts](https://docs.python.org/3.10/library/subprocess.html),
and [POSIX process-group signals](https://docs.python.org/3.10/library/os.html#os.killpg).
