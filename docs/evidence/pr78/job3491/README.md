# Job 3491: scoped memory gate and diagnostic integration

## Evidence and limits of inference

The operator reported Slurm COMPLETED/0:0, six elapsed seconds (five for the
Python step), with no solver calls. The pasted qualification JSON was rebuilt
using the producer's canonical encoding; its bytes reproduce the operator's
SHA256 `c8bb9a0213f1067e8258cb0c0074a087e742e0c048cabb44f20960217942013e`.
This is hash-matched operator-supplied evidence, not a direct inspection of HPC.

All six qualification stages passed, including 16 physical cores, the 64 GiB
job cap, 20 samples, an unrelated synthetic mount, a classified missing usage
read and a final real sample. The sampled peak was 21,856,256 bytes. This short,
no-solver qualification is not a high-memory stress test, a historical memory
reconciliation, or proof of why job3490 lost memory observation.

The candidate source is preserved verbatim as `paired_memory_guard_v4.py` here,
SHA256 `e66696aadeced1d7cbdbeed6a232bb380765b11887667747c85d5345d99a6695`.
It is an immutable qualified payload, not reformatted production source.
`pr78_scoped_evidence.py` verifies its hash, qualification receipt and all frozen
guard dependencies before loading it. Existing guard and executor bytes remain
untouched. The archived candidate protocol retains its original name; that
name and `candidate_integrated_into_executor=false` in the historical receipt
describe the qualification time, not an edited retrospective claim.

## Implemented integration

- `paired_memory_runtime_v2.py` uses that exact candidate and reuses the frozen
  watchdog's process termination, deadlines and 56 GiB threshold. A narrow
  sampling wrapper retains a sanitized failure diagnostic when the watchdog
  reports `memory_observation_lost`.
- `paired_matrix_executor_v3.py` is a separate executor protocol. It binds the
  job3491 evidence and new runtime dependencies; child processes import v3.
  Guard receipts carry `memory_failure_diagnostic`, required on observation
  loss and forbidden otherwise. Export validation rejects unknown fields,
  arbitrary stage/type text, unsafe errno/depth values and private text.
- V2 executors, V3 workflow, installed files, old approvals and claims are not
  replaced. The current scheduler workflow still imports the old executor.
  **This commit does not enable a new submission or an automatic retry.**

The full mount table is not required to remain byte-identical. The selected
memory controller is re-resolved, and mounts covering its job hierarchy are
compared, including ancestors and descendants that could shadow control files.
Unrelated mounts and line ordering are tolerated. Changed/ambiguous memory
mounts, changed membership, hierarchy/limit drift and unreadable usage still
stop. Diagnostics contain a fixed stage, allowlisted exception type and errno,
and a bounded depth; no path, exception message or raw log is exported.

## Preserve the incomplete paired experiment

Easy job3489 has five validated terminal attempts. Its manifest SHA is
`06502e632c5ad0806cb5a7c331d72887b9298866a2b59e7b28bde97b1f51e329`.
Medium job3490 has one interrupted receipt, for threads16; the frozen medium
order is 16,8,2,1,4. Its return SHA is
`4068bb9824bcd4dbd49c2327806d9e2a22980053c9a9ddb5e0e245c8e6436227`.
The attempt records observation loss and SIGTERM (-15), not a proved memory
threshold exceedance. Its private-artifact diagnostic SHA is
`b532de54f4fbe75e31166705eb0522ca09264aea66ead3cbbd8e9d728afa4b2f`.
The diagnostic reports optimizer/root markers but no terminal summary or final
child report. Exact historical optimize-call count remains unqualified; do not
infer zero calls or relabel this as a completed scientific result.

## Next gate: explicit bounded continuation accounting

The read-only continuation compiler and both scope/budget options are now
documented in [continuation-plan.md](continuation-plan.md). It verifies the two
downloaded nested returns without enabling execution. The corrected V3 executor
protocol label is distinct from historical V2; installed source is unchanged.

### Verification of this integration

Local full evidence suite: 540 tests, no failures/errors, four platform skips,
Python 3.13, with temporary fixtures in the permitted workspace. Ruff 0.16.8
check and format check passed across scripts/evidence and tests/evidence.
The new coverage includes all 26 candidate hierarchy cases, 19 versioned
executor/export cases and four sanitized-watchdog cases. No real Gurobi
optimization or HPC job was run by this verification.

The initial full-suite attempt with the sandbox's default temporary directory
was not a pass: 539 tests, one failure, ten errors and four skips, with denied
temporary-file replacement and Git initialization. The final run moved only
test temporaries into the allowed workspace; production protections and tests
were not weakened. Exact-head Ubuntu/Windows Python 3.10/3.12 CI remains a
separate required publication gate.

Do not rerun easy. Do not erase the failed medium claim. Before a successor
submission, implement a medium-only workflow with fresh provenance and a
conservative budget ledger. Reserve one consumed optimize slot for job3490,
without changing the historical exact-count field. Five easy calls plus that
reservation leave at most four calls under the original ten-call ceiling;
those could cover unattempted caps 8,2,1,4 but not retry threads16 as well.
Repeating all five medium caps would require an explicitly accounted additional
slot and additional solver-time/submission ceilings. It must not be smuggled
into the original approval. Decide the continuation scope before generating
the approval-bound scheduler handoff. Numerical memory limits, no automatic
retry/requeue, shared CPU-only allocation and no scientific promotion remain.

The two successor-parent submission slots were used by jobs3489 and3490.
Thus even the four-unattempted-caps option needs an explicitly accounted new
submission; remaining optimize slots alone do not authorize another job.

This source publication requires no HPC command, resource approval or merge.
Run exact-head CI on all four platforms/Python combinations before using it in
a successor workflow. The PR stays draft while the paired delivery is incomplete.
