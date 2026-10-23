# Explicit medium-only continuation

This is a new, separately bounded execution, not a restart of job 3490.
The successful easy return (3489), interrupted medium return (3490), all old
approvals and stop markers remain unchanged. PR78 stays draft pending installed
execution, independent return review and exact-head CI. No merge is authorized.

## Budget and scientific boundary

The `start` command's short `--approve-additional-medium-budget` option explicitly
approves one additional medium submission: at most five optimization calls,
18,000 solver seconds and 19,800 wall seconds. Together with jobs 3489 and 3490,
the conservative reservation becomes three submissions, eleven optimization slots
and 39,600 solver seconds: **+1 submission, +1 slot and +3,600 solver seconds**
against the original campaign ceiling. Historical unknown counts remain unknown;
a reserved slot is not a measured optimization count. Earlier technical jobs are
outside this successor-campaign ledger.

Medium order stays **16, 8, 2, 1, 4**, seed 42, target gap 10%. Easy is never run by
this adapter. Each job requests one node, sixteen physical cores and 64 GiB,
CPU-only, shared allocation, no GPU, no requeue. The existing 48 decimal GB solver
soft limit, 56 GiB sampled stop and kernel RAM limit at most 64 GiB remain intact.
Job3491 qualified controller reading and synthetic failure handling in a short,
low-memory allocation; it did not qualify high-load memory safety or establish
the historical cause of job3490. No scientific promotion is made here.

## Operational sequence

Use the exact new commit SHA supplied in the handoff, after four GitHub Actions
evidence arms have passed at that SHA. A fresh checkout must be at
`/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/medium-continuation-SHA12/source`.
The operator verifies its own checkout and refuses a dirty or different source.

1. Publish the tested commit without force-push; inspect exact-head CI once.
2. On dgx-dasci activate `tfm_env`, install the pinned checkout and run
   `bash SOURCE/scripts/evidence/operate_pr78_medium.sh start SHA --approve-additional-medium-budget`.
   This option is the human's explicit additional-budget approval; omission fails
   before preparing, approving or submitting anything. No long typed phrase.
3. Query once whenever desired:
   `bash SOURCE/scripts/evidence/operate_pr78_medium.sh status SHA`.
   There is no polling loop and the terminal is not held until completion.
4. After `terminal=true`, run
   `bash SOURCE/scripts/evidence/operate_pr78_medium.sh collect SHA`.
   Nonterminal collection returns without claiming a collection. A successfully
   collected return can be read again without a scheduler query.
5. Download **only `flow/public_return.json`** in one SFTP session. Compare its
   SHA-256 with the collection output, then use `validate-return` with the copied
   original public predecessor returns. Send the hash and sanitized result for
   independent review. Never transfer raw logs, LP files or license material.

If any step fails after preparation, preserve everything and return the sanitized
output; do not repeat `start`, create another flow as a workaround, cancel a job
automatically, release it manually, change old approvals, or resubmit.

## Failure and export contract

The exclusive campaign reservation is keyed by the exact job3490 public return
hash, independent of new source, plan or directory. Approval cannot be recreated
by choosing a different output. Submission is claimed before `sbatch`; the job ID
is persisted before held-profile validation and release. Unknown submission or
release results stop the workflow rather than retrying. Source and dependency
bytes, predecessor nested contracts, exact-head CI, current site profile, held
allocation and physical affinity are checked at their respective boundaries.

The same isolated watchdog executes each child. A failed or memory-stopped child
prevents later attempts; out-of-order child execution and replay are rejected.
Collection rechecks closed private-log fingerprints locally, validates every
request/receipt against the new plan and exports an exact-schema JSON bundle.
Slurm `COMPLETED` alone cannot make a missing or partial parent eligible.
`scientific_reporting_eligible` remains false even for a complete valid return.

## Verification

Offline tests cover explicit approval, cross-directory deduplication, exact
budgets, tampered plans/approvals, uncertain submission, held-profile mismatch,
one-shot accounting, nonterminal collection, missing receipts, full five-child
synthetic execution, memory observation loss, log tampering, export mutation,
out-of-order/replayed children and repeated batch execution. These synthetic
tests do not submit Slurm jobs or call the solver. Installed production execution
and independent scientific review are still pending.
