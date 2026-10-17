# PR86 — 111 reviewed solves and the first medium-parent group

## Reviewed results

Jobs 3586–3591 completed frozen manifest positions 31–36. Their original
[public return](../evidence/pr86/jobs3586-3591/public_return.json) has SHA256
`13a9787e4ae72c255937a8fa614873a2b19e9ed6010bde4f498bda02e36430cd`, source
`30a38c0a1bd7322950483698b766a3d1cc2dbc0c` and plan
`dd725033ae943befb5d89411953b8429289fbb043c582a6b944dfa20357215e7`.
The original validator passed before this continuation was added. The separate
review pins those identities and job IDs, verifies the frozen cells and serial
dependencies, and reconciles feasibility, parameters, memory and costs.

The cumulative [ledger](../evidence/pr86/jobs3586-3591/campaign_results.csv)
now contains **111/210 solves and 37/70 groups** across six historically exposed
easy parents. F0/F3/F6/F14/F27 are complete; F29 has one thread at seeds 42/43.
Remaining: 99 solves and 33 groups. All observed gaps meet the 0.01% target,
with MINIMIZE, valid returned solutions and no memory/callback stop or censoring.
All 12 new external starts were accepted. Receipt bytes and flags stay intact.

| Job | Parent / threads / seed | M0 solver s | M1 solver s | M2 solver s |
| --- | --- | ---: | ---: | ---: |
| 3586 | F27 / 2 / 42 | 136.367 | 126.709 | 89.091 |
| 3587 | F27 / 4 / 42 | 108.395 | 58.203 | 47.599 |
| 3588 | F27 / 8 / 42 | 60.590 | 64.612 | 47.825 |
| 3589 | F27 / 16 / 42 | 67.063 | 61.959 | 99.567 |
| 3590 | F29 / 1 / 42 | 84.238 | 85.674 | 133.965 |
| 3591 | F29 / 1 / 43 | 135.024 | 135.113 | 119.097 |

Across all seven F27 groups, M2 is faster than M0 in six and slower at 16
threads. F29 is mixed: M2 is slower at seed42 and faster at seed43. More
threads do not guarantee improvement. M2's F27/16 gap is 0.00503264%; F29/42
has M1 gap 0.00780740% and M2 gap 0.00887509%; F29/43 M2 gap is 0.00852646%.
All other new gaps are zero. Keep these terminal-quality differences beside
the timings. Slurm elapsed sum is 1847s (30min47s), excluding queues.

- [Complete F27 CPU figure](../evidence/pr86/jobs3586-3591/f27_cpu.svg)
- [Partial F29 CPU figure, seed42](../evidence/pr86/jobs3586-3591/f29_cpu_partial.svg)
- [Review](../evidence/pr86/jobs3586-3591/review.json) and [manifest](../evidence/pr86/jobs3586-3591/manifest.json)

Regenerate offline with `python3 -B scripts/evidence/review_pr86_wave31.py --output NEW_DIRECTORY`.
Preserve the previous snapshots. Seed repeats are nested within parents;
these 111 solves do not establish independent generalization. Preparation
allocation scenarios are scoped estimates; whole-job cold costs remain
unqualified. Sampled cgroup memory and Slurm MaxRSS retain different scopes.

## Next wave: finish F29 and enter the medium stratum

Continue the original manifest at positions 37–42 (zero-based):

| Parent | Threads | Seed |
| --- | ---: | ---: |
| F29 | 1 | 44 |
| F29 | 2 | 42 |
| F29 | 4 | 42 |
| F29 | 8 | 42 |
| F29 | 16 | 42 |
| M0 (CFL_medium_instance_0) | 1 | 42 |

Every job contains methods M0/M1/M2 in their frozen order. Parent M0 denotes
the medium instance; method M0 denotes Gurobi without an external start.
Keep separate parent and method columns. The first five groups finish the
six easy parents; the final group starts the first of four medium parents.
Review this wave before enabling the remaining medium groups. Selection is
fixed by the original manifest and does not depend on GNN benefit.

Reuse the serial executor through `pr86_wave37.py` and `operate_pr86_wave37.sh`.
F29 inputs use private index5; the medium parent uses index6 and its existing
20,000-variable partial starts. Root preparation and GNN guidance from jobs
3520/3521 are reused. Tests check actual input paths, both parent bundles,
all 18 admissions, wrong-parent/dependency rejection, repeat-submission
rejection and exact regeneration of the cumulative outputs.

This wave stays within the approved 210-solve/70-job budget: six sequential
CPU jobs, 18 solves, at most 4h and 64GiB per job, one node and at most 3600s
per solve. Ceilings: 24 serial reservation hours, 18 solver hours and 128
physical-core reservation hours. Successful review would yield 129/210 solves
and 43/70 groups. Duration limits do not predict actual runtime; the medium
group may require substantially more time and memory than the easy groups.

Keep the solver soft limit at 48 decimal GB, sampled stop at 56GiB and kernel
RAM cap no greater than 64GiB. A memory stop or incomplete result pauses the
campaign and is retained for review. No automatic retry, requeue, extension
or dispatch beyond these six jobs. The same tfm_env and MINIMIZE policy apply.
Status and collection are one-shot commands; the receiver uses one SCP
connection and preserves previous transfer attempts.

T1 checks this policy and the medium boundary. T2 checks the preceding policy
and shared queue/first-group behavior; final CI runs the complete evidence
suite and shell syntax checks in Ubuntu/Windows with Python3.10/3.12.
PR86 remains draft. PR87's mandatory 1-GPU/4-GPU full training has a separate
exact budget; PR88 proceeds in parallel. Synchronize develop/main in both
directions after article revision and final release approval.
