# PR86 — complete medium M0 matrix; next parent M4

## What and how we reviewed

Jobs 3598–3603 completed original manifest positions 43–48. The immutable
[public return](../evidence/pr86/jobs3598-3603/public_return.json) has SHA256
`17503f14d5a49aca0e8cb71c591578db7e4191fd183a03edfb04650ebe4a29f6`, source
`33a5cb91d1225c8d5a63402a640f9800533b58bd` and plan
`e5787839233e4bc11c8712016c03df3874b92b76c345cd22eacb7cb5af1a3570`.
The original validator passed before edits. The new review pins these
identities and job IDs, verifies original cells and serial dependencies, and
checks nested solutions, objective sense, memory/callback stops and costs.

The cumulative [147-row ledger](../evidence/pr86/jobs3598-3603/campaign_results.csv)
exactly covers the first 49 groups: **147/210 solves, 49/70 groups**, with
63 solves/21 groups remaining. Six easy parents are complete (126 solves
reaching the 0.01% gap target); medium parent CFL_medium_instance_0, alias M0,
is also complete (21 solves, one target-reaching and 20 time-limited).
All new solutions pass feasibility and MINIMIZE checks, all 12 external starts
were accepted, with no memory/callback stop. COMPLETED means the jobs finished,
not that every solve reached the target. Original flags and bytes stay intact.

## Results: quality and censoring, not timeout speedup

| Parent M0 / threads / seed | Method M0 gap | Method M1 gap | Method M2 gap |
| --- | ---: | ---: | ---: |
| 1 / 42 (prior job 3597) | 6.7703% | 8.5837% | 7.1434% |
| 1 / 43 | 7.5857% | 7.2607% | 8.7534% |
| 1 / 44 | 7.2937% | 7.0040% | 7.5870% |
| 2 / 42 | 6.0395% | 3.0401% | 9.6946% |
| 4 / 42 | 39.0629% | 29.9969% | 2.3491% |
| 8 / 42 | 38.3974% | 42.7398% | 1.2570% |
| 16 / 42 | 46.5501% | 36.8552% | 0.0000% |

At 16 threads, M2 terminated in **3204.179 s**, with incumbent and dual bound
both 4.60832019037079 and gap zero. The other 20 observations of this parent
are right-censored for time to target at their recorded time-limit termination.
The reported duration is terminal solver runtime, not an independently
qualified true first-crossing timestamp for the target.
Do not compute an exact time-to-target speedup by dividing their ~3600 s
runtimes by M2's completed time. Preserve actual runtimes, including modest
overshoot beyond the configured TimeLimit, rather than clipping timestamps.

M2's gap is worse than method M0 at one thread in all three seeds and at two
threads, but better at 4/8/16 threads. Its incumbent is 4.60832019037079 at all
three higher caps; its bounds improve across those caps. This is heterogeneous
behavior for one exposed medium parent, not population-level superiority.
Increasing CPU threads is not guaranteed to improve quality under a fixed
time budget. Do not infer the cause of this nonmonotonic behavior from terminal
receipts alone, or select future cases/parameters according to GNN benefit.

The 16-thread sampled job-memory peaks were 33.219/33.309/16.956 decimal GB
for methods M0/M1/M2 respectively. These observations stayed below the 56 GiB
sampled stop; no memory stop occurred. Sampled cgroup memory, Slurm MaxRSS
and Gurobi internal memory are different scopes; do not equate them or use
this case to qualify a larger memory budget. Slurm elapsed sum for the six
new jobs is 65637 s (18 h 13 min 57 s), excluding queues. This is not solver
time, nor an independently measured cold end-to-end cost for each method.

## Reproducible outputs

- [Complete M0 terminal-gap CPU figure](../evidence/pr86/jobs3598-3603/m0_gap_cpu.svg): five caps at seed 42; table/CSV also retain seeds 43/44.
- [Complete M0 sampled-memory CPU figure](../evidence/pr86/jobs3598-3603/m0_memory_cpu.svg): job-scoped GiB, with the 56/64 GiB limits distinguished from solver memory.
- [Review](../evidence/pr86/jobs3598-3603/review.json), [manifest](../evidence/pr86/jobs3598-3603/manifest.json) and cumulative CSV link all rows to original receipts.

Regenerate offline with `python3 -B scripts/evidence/review_pr86_wave43.py --output NEW_DIRECTORY`.
Markers distinguish censored and target-reaching observations; no timeout
runtime is silently promoted to completed time to target. Keep the earlier
figures as dated snapshots. The separate review qualifies named descriptive
metrics only; it does not rewrite raw eligibility flags. Preparation cost
allocation scenarios remain distinct from whole-job cold measurement. Seeds
are nested repeats, not independent parents; final parent-paired uncertainty
and manuscript-wide claims await the full matrix.

## Next six jobs: first six groups of medium parent M4

Continue frozen positions 49–54 (zero-based):

| Parent | Threads | Seed |
| --- | ---: | ---: |
| M4 (CFL_medium_instance_4) | 1 | 42 |
| M4 (CFL_medium_instance_4) | 1 | 43 |
| M4 (CFL_medium_instance_4) | 1 | 44 |
| M4 (CFL_medium_instance_4) | 2 | 42 |
| M4 (CFL_medium_instance_4) | 4 | 42 |
| M4 (CFL_medium_instance_4) | 8 | 42 |

Each job runs methods M0/M1/M2 in their original order. M4/16 follows later;
it is not omitted or replaced. Reuse the serial engine through `pr86_wave49.py`
and `operate_pr86_wave49.sh`; private index 7 supplies this parent's existing
model and 20000-variable partial starts. Root/guidance jobs 3520/3521, tfm_env,
MINIMIZE and all other parameters stay fixed. No root recapture, inference,
training, support adjustment or package upgrade.

Within the approved 210-solve/70-job budget: six sequential CPU jobs, 18 solves,
at most 3600 s per solve, 4 h and 64 GiB per job, one node. Wave ceilings are
18 solver hours, 24 serial reservation hours and **68 physical core-reservation
hours**. Successful review would yield 165/210 solves and 55/70 groups; M4/16
would still be pending. Review this return before dispatching another wave.
No predicted duration or speedup for M4 is inferred from M0.

Retain solver soft memory 48 decimal GB, sampled job stop 56 GiB and kernel
RAM cap <=64 GiB. Memory/provenance/feasibility/callback failures pause the
campaign. A valid TIME_LIMIT is retained as censoring, not retried. No automatic
retry, requeue, extension, overwrite or subsequent dispatch. Status/collect
are one-shot and the receiver uses one SCP connection, preserving prior transfers.

T1 verifies the 147-cell prefix, hashes, complete medium figures/censoring,
private index 7, all 18 admissions, wrong bindings/dependencies and repeat
claims. T2 covers the prior policy plus shared queue/first-group boundaries;
final CI covers the full evidence suite and shell syntax on Ubuntu/Windows,
Python 3.10/3.12. PR86 remains draft. PR87's mandatory 1-GPU serial/4-GPU DDP
training requires its exact budget; PR88 proceeds in parallel. Synchronize
develop/main only after article revision and final release approval.
