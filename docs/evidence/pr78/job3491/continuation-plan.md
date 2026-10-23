# Medium-only continuation: verified inputs and explicit budget delta

## Implemented, without enabling execution

`scripts/evidence/pr78_medium_continuation_plan.py` compiles and validates a
read-only proposal from the **two actual downloaded public return directories**.
It invokes the frozen V3 operator / V2 executor validators, checks both fixed
return-manifest hashes and nested archives, and binds jobs3489/3490, the original
approval hashes and the easy review. It does not read private logs, models or a
license, query Slurm, create files or claims, record an approval, or submit jobs.

The new executor now identifies itself as `paired_matrix_isolated_executor_v3`.
The earlier integration inadvertently retained the V2 protocol string despite
having a different diagnostic schema. Its dependency hashes already differed;
this corrects the protocol label before any installation or execution of V3.
The old V2 identifier, installed source and historical receipts are unchanged.
Regression tests require different identifiers and reject a V2-labelled V3 plan.

The last published integration head at review time was
`a65059eac19415f7e6fc3419d35c16b64ccd3581`; all four evidence checks passed in
[run 37640046426](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/37640046426).
That CI result does **not** qualify a later continuation commit. Each newly
published head still needs its own four checks.

## Decision proposed for completion

Recommend `full-medium`: one explicitly authorized successor job, at most five
serial calls, retaining the frozen order **16,8,2,1,4**, seed42, original medium
LP, MINIMIZE override, default algorithm policy, one-hour per-call solver cap
and 10% stopping gap. This replaces no historical artifact: the interrupted
threads16 observation remains recorded separately, not selected away or counted
as a successful result. It is an operator-approved new attempt, not automatic
retry. Easy job3489 is never rerun.

The conservative alternative `unattempted-only` executes **8,2,1,4** and keeps
their original order indices 1,2,3,4. Even if all four succeed, threads16 remains
unresolved and the paired matrix cannot be called complete. The proposal makes
that limitation machine-readable; it cannot silently substitute one scope for
the other after hashing.

| Proposed scope | New calls | New solver cap | New wall cap | Remaining missing cap on success |
| --- | ---: | ---: | ---: | --- |
| `full-medium` | 5 | 18,000 s | 19,800 s | none, subject to independent review |
| `unattempted-only` | 4 | 14,400 s | 16,020 s | threads16 |

Both reserve 16 physical cores, 64 GiB, one task and one node, no GPU, no
exclusive allocation and no requeue. Wall limits include 3,780 seconds per
child plus 900 seconds per block. The 48 decimal-GB solver soft limit, sampled
56 GiB stop and at-most-64 GiB kernel RAM limit remain unchanged.

## Budget accounting is not a runtime measurement

This ledger covers the successor campaign **jobs3489 and3490 plus the proposed
continuation**. Earlier diagnostic/recovery jobs remain in the historical
record and are explicitly outside this scoped budget; no all-project cost
claim is made.

The two original successor submission slots have been consumed. The five easy
calls are qualified. Reserve one additional slot for the interrupted medium
attempt while preserving its historical `exact_optimization_call_count=null`.
Reserve each of these six slots at the full 3,600-second cap; this is a
conservative budget reservation, **not** measured consumption or an exact
historical count. Unused actual elapsed time is not used to justify extra calls.

- `full-medium` proposes cumulative ceilings of 3 submissions, 11 optimization
  slots and 39,600 solver seconds: relative to the original approval, **one new
  submission, one additional optimization slot and 3,600 additional solver
  seconds** require explicit authorization.
- `unattempted-only` keeps 10 slots and 36,000 solver seconds but still requires
  **one new submission**. Having four unused slots is not submission permission.

Every emitted proposal retains `resource_budget_approved=false`,
`execution_enabled=false`, `scheduler_adapter_implemented=false`,
`exact_head_ci_reviewed=false`, `automatic_retry=false` and
`scientific_reporting_eligible=false`. Old approved JSON is evidence only and
cannot authorize the proposed continuation.

## Offline interface

From a clean checkout, with canonical absolute paths to the downloaded public
directories, the following prints a proposal only. It is not an HPC handoff:

```text
python -B scripts/evidence/pr78_medium_continuation_plan.py preview --scope full-medium --easy-return <absolute-easy-return-directory> --medium-return <absolute-medium-return-directory>
python -B scripts/evidence/pr78_medium_continuation_plan.py validate --plan <saved-proposal.json> --easy-return <absolute-easy-return-directory> --medium-return <absolute-medium-return-directory>
```

The CLI has no submit, run or approve action. Preview checks a clean local Git
head. Validation reopens both returns and recomputes all dependencies and the
canonical proposal, rejecting changed scope, extra keys, altered budgets,
boolean/numeric substitutions and promoted eligibility. It does not need the
HPC, a scheduler or network access. Untrusted archives are validated in memory
by the existing bounded validator, not extracted.

## Next implementation gate, not yet delivered by this proposal

Implement the medium-only scheduler adapter and its child claim/export path;
the existing two-parent workflow is **not** compatible with this proposal and
must not be repointed to it. The adapter must:

1. Revalidate both predecessor returns and qualified runtime dependencies;
   reject easy execution and keep old directories, approvals and STOP markers.
2. Bind a fresh approval to the exact proposal, source, CI, budget and scope.
   Deduplicate authorization/claims by the **job3490 predecessor return**, not
   just by the new plan hash or directory, so two scopes cannot both consume
   additional budget. Fail closed on crashes or uncertain submission.
3. Submit at most once, validate the held single-node allocation and release
   only that job; status is one query and collection occurs only after terminal
   accounting. No polling loop, auto retry, requeue or extension.
4. Use the scoped memory runtime and export its sanitized failure diagnostic;
   preserve interrupted results and distinguish supervisor completion from
   successful completion of all attempts.
5. Collect and independently validate nested public evidence and its new
   provenance before any scientific eligibility or PR readiness assessment.

Only after implementation, tests and exact-head CI should a bounded operator
handoff be provided. No new HPC job, resource approval or merge is requested by
this proposal. PR78 remains draft.

## Verification of this change

- Full offline evidence suite: **556 tests, zero failures/errors, four platform
  skips**, Python3.13, using permitted workspace test temporaries.
- New continuation tests: **16 passed on Python3.10**. Both actual downloaded
  job3489/job3490 returns also passed the nested validators for both scopes.
- Ruff0.16.8 check and format check: passed across all 76 evidence Python files.
- An optimized-Python (`-O`) trial was rejected at import by the existing MVP1
  receipt verifier, which requires assertions enabled. It is not an optimized
  test pass; that protection was retained. Use normal Python with `-B`, not `-O`.
- No solver, scheduler query, HPC submission or merge was performed. New-head
  remote CI remains required after publication.
