# PR78 closure: partial delivery, documented interruption

This is the current closure record. It supersedes statements in earlier runbooks
that keep PR78 draft until a complete paired experiment. It does **not** modify
historical receipts or claim Sprint B is complete. The human authorized this
partial closure, ready-for-review transition and merge into develop on 2026-10-07.

## Accepted delivery and unresolved work

The published [B1 acceptance criterion](../../../research/mvp2-delivery-plan-20261006.md)
allows either reviewed complete results or a documented interruption with an
explicit unresolved gate. This delivery uses the second option.

| Evidence | Disposition |
| --- | --- |
| Easy job3489 | Five validated terminal attempts; preserve without rerun |
| Medium job3490 | One interrupted threads16 receipt, memory_observation_lost; four later caps not attempted; parent incomplete |
| Job3491 | Scoped memory reading and synthetic failure handling qualified in a short no-solver allocation |
| Runtime 80cf7d5b90202ba57c7cb62c5e0d670875cc02ac | Versioned memory correction and one-shot medium-only workflow; four exact-head evidence CI arms passed |

Slurm COMPLETED for job3490 is not experimental completion. Its final child
report is absent and exact optimization-call count is null. SIGTERM and loss of
memory observation are not proof of OOM or of the historical operation that
failed. A conservative budget reservation of one call is not a measured count.
The job3491 qualification is not high-load memory-safety qualification.

## Archived public bytes

Each ZIP contains exactly the six original public return files: accounting,
operator plan and approval, submission, SHA256SUMS.txt and matrix.tar.gz. No raw
log, model or license file is included. Every original member is byte-identical
to the downloaded, nested-contract-validated return. ZIP is only a storage
container and does not replace the original manifest or package identity.

| Archive | SHA-256 |
| --- | --- |
| job3489-public-return.zip | 9ad9e582eb947ae89da00bf770929cf357172ec880b8424749b30361bc2937d6 |
| job3490-public-return.zip | d0b8d349db6d1dc52ac30d45f2d625e4593f85de14a594bda56775444e20e5ff |

Original manifest SHA-256:

- Easy: `06502e632c5ad0806cb5a7c331d72887b9298866a2b59e7b28bde97b1f51e329`.
- Medium: `4068bb9824bcd4dbd49c2327806d9e2a22980053c9a9ddb5e0e245c8e6436227`.

`closure_review.json` binds these returns, original source and approval hashes,
easy review, archive hashes and negative eligibility flags. Original accounting
is included; costs of earlier diagnostic/recovery jobs are not silently erased
or represented as part of these two allocations. No all-project cost is claimed.

Revalidation: unpack each ZIP into a separate fresh directory, preserving the
six member bytes, and use `scripts/evidence/paired_matrix_workflow_v3.py
validate-return --directory DIRECTORY --expected-sha MANIFEST_SHA` from the
reviewed checkout. The read-only continuation compiler also revalidates both
original nested contracts together. No solver or scheduler is needed.

## Verification and release boundary

At runtime head 80cf7d5: full local evidence suite 572 tests, OK with four skips;
new workflow tests also pass on Python3.10; pinned Ruff0.16.8 check/format pass.
[CI run 37661250484](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/37661250484)
passed Ubuntu/Windows Python3.10/3.12, including shell syntax checks. The closure
adds public evidence/documentation only; no runtime bytes are changed. Require
four passing checks at the closure head before merging it.

No new optimization, HPC submission, resource approval or scientific promotion
is implied by this closure. Merge does not authorize a new job. Main, Pages,
the manuscript release and frozen MVP1 remain outside this merge.

## Next integrated delivery: finish Sprint B

The next PR combines the remaining medium execution, public evidence review,
within-parent censored-time/cost/memory analysis and a justified development CPU
profile. Reuse the reviewed runtime at 80cf7d5; do not introduce another executor
or require another no-solver campaign without a demonstrated defect.

One explicit full-medium continuation remains proposed: order16,8,2,1,4,
seed42, gap10%, at most five calls/18000 solver seconds/19800 wall seconds;
one node, sixteen physical cores,64GiB, shared CPU-only. Preserve soft48 decimalGB,
sampled56GiB and kernel<=64GiB limits, all predecessor stops, and no automatic
retry/requeue/extension. The campaign reservation becomes three jobs/eleven
slots/39600 solver seconds; +1 job/+1 slot/+3600 seconds against the old ceiling.
That approval is explicit at the operator command, not inferred from this merge.

For analysis, keep failures/missingness, compare caps within each parent, never
pool easy1% and medium10% target times, and calculate speedups only for comparable
attained targets. Keep allocation costs counted once and resource metrics in
their original scopes. Two parents/one seed support descriptive development
claims, not population significance, GNN gains or general scaling conclusions.
Sprint B closes only with a resource-valid comparison and justified CPU profile;
an unresolved runtime failure must be reported as a blocker, not hidden.
