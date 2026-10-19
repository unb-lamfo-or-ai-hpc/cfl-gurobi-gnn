# PR86: reviewed first group and six-job serial wave

## What, how and why

The author requested three to six four-hour jobs queued together for unattended
serial execution. This delivery fixes **six**, the next six groups of the existing
manifest. It adds no scientific method, parent, seed or optimization budget.
Keep this implementation in PR86; PR87 remains the separately budgeted mandatory
one-GPU serial versus four-GPU DDP training comparison.

The original first-group return is preserved at
[job3522/public_return.json](../evidence/pr86/job3522/public_return.json), SHA256
`dd1a553b453289b23dbed3d52bd4bd7e0ac93eb2b4283597b788e406fcab6825`.
It was validated on original source `5c1c174ca0f5d643ca02c6bd289e289a649dba15`
before edits. `pr86_six_job_queue.review_first` checks those exact pinned bytes
and rechecks nested cell/parameter/result/cost identities against the historical
plan, not a recomputed source manifest from a later checkout.

## Observations, not a general superiority claim

Job3522 completed, exit 0:0, Slurm 546 seconds, batch MaxRSS 468.50M.
Three optimization calls, F0 / one thread / seed42, same mathematical model
signature and parameter hash. MINIMIZE enforced; independent returned solution
checks passed. No callback error or memory stop. Both partial starts accepted,
14,800 binary assignments each. The original scientific-eligibility flag remains
false; the separate review qualifies the following descriptive observations only.

| Method | Solver seconds | Terminal gap (%) | Primal objective |
| --- | ---: | ---: | ---: |
| M0, no external start | 100.704520 | 0 | 6.130863210247613 |
| M1, LP-matched start | 109.595202 | 0 | 6.130863210247613 |
| M2, frozen GNN start | 306.389532 | 0.00826476 | 6.130863210247613 |

All met the frozen 0.01% tolerance; do not describe M2 as an exact zero-gap
certificate. M2 was slower in this one parent/seed. This is not evidence of
population-level inferiority or superiority. Solver time excludes preparation.
The scoped guided costs are in `prepared_costs.json`, not the unprepared
`attempt.json` measurement, whose preparation fields intentionally remain null.
Whole-job standalone cold cost remains unqualified; shared/export allocations
are the explicit scenarios described in the job3521 review.

## Frozen wave, included in 210 calls / 70 jobs

| Position | Parent | Threads / physical cores | Seed | Method order |
| --- | --- | ---: | ---: | --- |
| 1 | F0 | 1 | 43 | M1, M2, M0 |
| 2 | F0 | 1 | 44 | M2, M0, M1 |
| 3 | F0 | 2 | 42 | M1, M2, M0 |
| 4 | F0 | 4 | 42 | M2, M0, M1 |
| 5 | F0 | 8 | 42 | M0, M1, M2 |
| 6 | F0 | 16 | 42 | M1, M2, M0 |

Each job: one node, batch, shared node, 64 GiB, zero GPU, no requeue,
four-hour wall cap, three sequential solves capped at 3,600 s each, 3,780 s
child deadline. Memory: solver soft 48 decimal GB, sampled stop 56 GiB,
kernel RAM cap <=64 GiB. `tfm_env` unchanged. No repeated root, inference or
training. This wave: **18 solves, <=18 solver-hours, <=24 serial reservation
hours, <=128 physical-core reservation hours**. Successful completion would
make 21/210 solves and 7/70 jobs, leaving 189/63; it does not dispatch them.
Actual wall time may be much shorter, and queueing may make completion later.
Six submitted jobs are not six simultaneously allocated jobs. Node availability,
QOS and user limits remain scheduler decisions; no reservation/priority bypass.

## Nonblocking submission and failure boundaries

`prepare` checks installed first-group return and existing private artifacts.
`submit PLAN_SHA` records this already-authorized wave and a durable global claim.
It checks all six three-method admission bundles before calling sbatch.
All jobs are submitted held; job n uses `afterok` on job n-1. Their exact IDs,
resource profiles and dependencies are recorded before any job is released.
Release proceeds **tail to head** so the first job cannot start before the full
chain is recorded. Each worker verifies its ID, source, allocation, memory and
frozen cell bundles; after the first wave job, it rehashes and validates its
predecessor's artifacts and closed log bindings before invoking the solver.
The predecessor exits zero only after that artifact gate succeeds.

The Slurm [sbatch contract](https://slurm.schedmd.com/sbatch.html) defines
`afterok`, `--hold` and `--kill-on-invalid-dep=yes`. The latter asks the scheduler
to cancel a dependent job that can never run after predecessor failure. Merely
using an array concurrency cap would not guarantee failure propagation, so this
delivery uses explicit dependencies. No controller needs to poll on the login
node or keep the user's SSH session open.

Any ambiguous submission or partial release stops the operator without retry.
Earlier accepted IDs remain preserved; a partial submission leaves them held.
Do not repeat `submit`, delete claims, manually release a subset, or remove
dependencies. Use `status` and return the diagnostic output for a scoped recovery
decision. A site limit rejecting the sixth job is not permission to automatically
retry it or silently change the frozen wave. No destructive cleanup is performed.

Once all six jobs are terminal, `collect` emits one allowlisted public return
with original nested JSON bytes/hashes, actual accounting and held dependency
profiles. Offline review checks each group independently and reconciles unique
job IDs, exact order and resources. Failed/cancelled groups remain visible,
not replaced with zero-cost successes. One scp downloads one file with one
password prompt. No raw logs, solutions, predictions or license are exported.

## Acceptance and remaining work

Offline tests cover six real admission bundles, counterbalanced order, full
nested exports, dependency tampering, resource mismatch, ambiguous submission,
partial release, first-group byte preservation and predecessor-gate failure.
Synthetic tests are not proof of installed scheduler success. Four exact-head
CI checks must pass before the source-pinned CLI is delivered for HPC execution.
The user, not the agent, executes that CLI. No merge is authorized by this wave.

After its independent return review, continue with remaining parents without
repeating these cells. Then regenerate CPU scaling, repeated-seed and cost
tables/figures and qualify claims at the parent level. Preserve exposed-test
limitations, censored runs and heterogeneous/negative results.
