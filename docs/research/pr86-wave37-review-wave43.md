# PR86 — six easy parents complete; first medium observations

## What was reviewed

Jobs 3592–3597 completed frozen manifest positions 37–42. The original
[public return](../evidence/pr86/jobs3592-3597/public_return.json) has SHA256
`fca3de37c0122955c6df593b5f11f7fef81a1dd2af3754de92c45cb60fb4cc94`, source
`880399c098d5ce0a6b46956f9c5cb85c473e3f66` and plan
`f45b286f9e44fb17cf2bb5fec26897baf33b67c7ea4dd8f595c0c28287824fa4`.
The original validator passed before code changes. The separate review pins
these identities and job IDs, checks the original manifest and serial
dependencies, and reconciles nested results, feasibility, memory and costs.

The cumulative [ledger](../evidence/pr86/jobs3592-3597/campaign_results.csv)
contains **129/210 solves and 43/70 groups**, with no missing or duplicate
cells in that prefix. The six exposed easy parents F0/F3/F6/F14/F27/F29 are
complete: 126 solves, all meeting the 0.01% gap target. The medium parent
CFL_medium_instance_0 (alias M0) has one group, at one thread and seed 42.
Its three solves reached the time limit without the target: valid terminal
observations, not successful time-to-target events. Remaining: 81 solves,
27 groups. All new returned solutions pass feasibility and MINIMIZE checks;
all 12 external starts were accepted, with no memory or callback stop.

| Job | Parent / threads / seed | M0 solver s | M1 solver s | M2 solver s |
| --- | --- | ---: | ---: | ---: |
| 3592 | F29 / 1 / 44 | 79.498 | 73.036 | 117.788 |
| 3593 | F29 / 2 / 42 | 72.049 | 64.954 | 110.558 |
| 3594 | F29 / 4 / 42 | 139.256 | 149.949 | 159.445 |
| 3595 | F29 / 8 / 42 | 130.572 | 151.306 | 66.842 |
| 3596 | F29 / 16 / 42 | 121.356 | 77.994 | 64.118 |
| 3597 | M0 / 1 / 42 | 3600.127* | 3600.122* | 3600.175* |

`*` Right-censored time to the target. The configured TimeLimit is 3600 s;
preserve the actual reported runtime rather than clipping it to that value.
Do not treat the tiny differences between these three terminal runtimes as
time-to-target speedup. All five new F29 groups have zero terminal gap; earlier
F29 seed-42/43 gaps remain in the ledger. Across F29's seven groups, M2 is
faster than M0 in three and slower in four. These are nested groups of one
parent, not seven independent instances. Slurm elapsed sum for this wave is
12737 s (3 h 32 min 17 s), excluding queue time.

## How to read the first medium result

Parent M0 and method M0 are different identifiers: retain separate columns.
Under MINIMIZE, a lower incumbent objective is better; a larger lower bound
is stronger. Relative gap depends on both, not just incumbent quality.

| Method | Incumbent objective | Dual bound | Terminal gap | Target reached |
| --- | ---: | ---: | ---: | --- |
| M0: no external start | 4.666372 | 4.350445 | 6.7703% | No |
| M1: LP-matched start | 4.710175 | 4.305867 | 8.5837% | No |
| M2: frozen GNN start | 4.655592 | 4.323023 | 7.1434% | No |

M2 found the best incumbent of these three observations, but M0 has the
strongest bound and smallest gap. Thus neither a blanket GNN advantage nor
a time-to-target acceleration follows. This is one exposed medium parent,
one seed and one thread cap; retain the quality/censoring distinctions before
aggregating strata. The memory guard passed; sampled cgroup peaks and Slurm
MaxRSS have distinct scopes and are not interchangeable.

New reproducible assets:

- [Complete F29 CPU figure](../evidence/pr86/jobs3592-3597/f29_cpu.svg).
- [Partial medium terminal-quality figure](../evidence/pr86/jobs3592-3597/m0_quality_partial.svg), explicitly marking the three censored times.
- [Review](../evidence/pr86/jobs3592-3597/review.json) and [manifest](../evidence/pr86/jobs3592-3597/manifest.json), alongside the cumulative CSV.

Regenerate offline with `python3 -B scripts/evidence/review_pr86_wave37.py --output NEW_DIRECTORY`.
Preserve the original bytes and false eligibility flags; this separate review
qualifies only named descriptive observations. Preparation allocation scenarios
remain scoped estimates, not measured whole-job cold costs. Do not pool exposed
parents as independent generalization evidence or count seeds as new parents.

## Next wave: complete the medium parent M0

Continue the original manifest at positions 43–48 (zero-based):

| Parent | Threads | Seed |
| --- | ---: | ---: |
| M0 (CFL_medium_instance_0) | 1 | 43 |
| M0 (CFL_medium_instance_0) | 1 | 44 |
| M0 (CFL_medium_instance_0) | 2 | 42 |
| M0 (CFL_medium_instance_0) | 4 | 42 |
| M0 (CFL_medium_instance_0) | 8 | 42 |
| M0 (CFL_medium_instance_0) | 16 | 42 |

Each job runs M0/M1/M2 in the previously frozen order. Selection does not
depend on the observed GNN benefit or on a target being reached. A valid
time-limited return does not authorize a rerun or longer limit; it also does
not, by itself, stop the planned campaign. Memory, feasibility, provenance or
callback failures still stop it. Review this six-job return before more parents.

Reuse the existing serial engine through `pr86_wave43.py` and
`operate_pr86_wave43.sh`. Private index 6 supplies this parent's model and
existing 20000-variable starts. Root/guidance jobs 3520/3521 are reused;
no new root capture, inference, training, selection or package upgrade.

Within the already approved 210-solve/70-job campaign: six serial CPU jobs,
18 solves, at most 3600 s per solve, 4 h and 64 GiB per job, one node.
Wave ceilings: 18 solver hours, 24 serial reservation hours and 128 physical
core-reservation hours. Time limits are ceilings, not predicted durations;
the first medium group took about three hours. Successful review of the next
six groups would give 147/210 solves and 49/70 groups, with M0's seven groups
accounted for whether target-reaching or censored.

Keep solver soft memory at 48 decimal GB, sampled stop at 56 GiB and kernel
RAM cap no greater than 64 GiB. No automatic retry, requeue, extension,
overwrite or dispatch beyond these six jobs. Status/collect are one-shot;
the receiver uses one SCP connection and preserves earlier transfers.

T1 covers exact prefix/identities, censoring, figure regeneration, private
index 6, all 18 admissions, wrong bindings/dependencies and duplicate claims.
T2 covers the prior wave and shared queue/first-group contracts. Final CI
checks the complete evidence suite and shell syntax on Ubuntu/Windows with
Python 3.10/3.12. PR86 remains draft; no merge. PR87's mandatory 1-GPU serial
versus 4-GPU DDP training needs its exact budget; PR88 proceeds in parallel.
Synchronize develop/main only after article revision and release approval.
