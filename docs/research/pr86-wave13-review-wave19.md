# PR86 — jobs3555–3560 reviewed; next frozen F6/F14 wave

## What and why

The original return SHA256
`01a1a077c00c4a81cb38285652153e751ced77e60a02be1ce2b787a52a7cbd8b`
is preserved byte-for-byte in [jobs3555–3560](../evidence/pr86/jobs3555-3560/public_return.json).
The original 09172bc validator passed before edits. The separate review pins
the source commit and plan, checks the exact six job IDs and manifest cells,
and reuses nested solution, parameter, memory and launch/dependency validators.
It never rebuilds historical source pins or rewrites old eligibility flags.

All18 new cells meet the prescribed gap, with valid returned solutions,
effective MINIMIZE and no memory/callback stop. Campaign total: **57/210 cells,
19/70 groups, three historically exposed parents**. F0 and F3 are complete;
F6 has1/2/4 threads, plus one-thread seeds43/44. F6/8,16 remain pending.
The six scheduler elapsed times sum to1311s (21min51s); this excludes queues
and is not summed solver time or measured submission-to-completion time.

## Observations, not a superiority claim

| Parent / cap / seed | M0 solver s | M1 solver s | M2 solver s |
| --- | ---: | ---: | ---: |
| F3 /16 /42 | 61.539 | 116.723 | 42.744 |
| F6 /1 /42 | 59.817 | 61.722 | 95.542 |
| F6 /1 /43 | 59.641 | 58.904 | 43.117 |
| F6 /1 /44 | 63.760 | 65.409 | 49.444 |
| F6 /2 /42 | 55.251 | 58.787 | 43.442 |
| F6 /4 /42 | 70.116 | 70.216 | 52.764 |

F3 M2 is faster than M0 at all five seed42 caps. F6 is heterogeneous: M2 is
slower at1thread/seed42 and faster in the other four observed configurations.
F6 M2/1/seed42 terminates with gap0.00528966%, within0.01%, not an exact-zero-gap
claim. Preserve that quality difference alongside runtime. No method, seed,
cap or next parent is selected by these observations. Seeds are nested within
parents;57 runs are not57 independent instances, and the test parents are exposed.

## Reproducible outputs

- [Cumulative57-row CSV](../evidence/pr86/jobs3555-3560/campaign_results.csv).
- [Complete F3 CPU figure](../evidence/pr86/jobs3555-3560/f3_cpu.svg).
- [Partial F6 CPU figure](../evidence/pr86/jobs3555-3560/f6_cpu_partial.svg), with8/16 explicitly pending.
- [Review](../evidence/pr86/jobs3555-3560/review.json) and [manifest](../evidence/pr86/jobs3555-3560/manifest.json).

Regenerate offline with `python3 -B scripts/evidence/review_pr86_wave13.py --output NEW_DIRECTORY`.
Scoped preparation/cold/amortized scenarios retain M1's GNN matching cost;
they are not measurements of full standalone cold executions. Sampled cgroup
memory and Slurm MaxRSS are distinct; neither proves the exact physical peak.
Previous F0 and partialF3 assets remain historical snapshots, not overwritten.

## Next six jobs — how and why

Continue positions19–24 (zero-based) in the original frozen manifest:

| Order | Parent | Physical thread cap | Seed |
| --- | --- | ---: | ---: |
| 1 | F6 | 8 | 42 |
| 2 | F6 | 16 | 42 |
| 3 | F14 | 1 | 42 |
| 4 | F14 | 1 | 43 |
| 5 | F14 | 1 | 44 |
| 6 | F14 | 2 | 42 |

Three methods/group in frozen balanced order:18 solves,6 serial jobs, each
<=4h,64GiB,one node,CPU only. Envelope <=24 serial reservation hours,
18solver-hours and116 physical-core reservation hours, within approved210/70.
Success yields75/210 cells,25/70 groups. F14/4,8,16 are later, not omitted.

Reuse the same serial scheduler/executor and no-solver preparation artifacts.
Only the explicit next-slice policy, pinned predecessor review, operator and
receiver are added. F6 binds preparation index2; F14 binds index3. Tests cover
real eighteen-cell admission, both parents' bundle arguments, private index3,
wrong-model/dependency rejection, no repeat submission and output regeneration.
All admissions precede sbatch; held profiles, afterok, artifact gates, immutable
claims, reverse release, memory limits and one-shot status/collect remain.
One SCP downloads one sanitized return. No automatic dispatch beyond six jobs.

No new roots, inference, training, package upgrades, retry, requeue or extension.
The agent does not execute HPC. Failures preserve evidence and pause progression.
PR86 remains draft, no merge. Main/develop synchronization in both directions
remains deferred until after article review. PR87 matched1GPU/4GPU-DDP remains
mandatory with its separate exact budget; PR88 manuscript proceeds in parallel.
