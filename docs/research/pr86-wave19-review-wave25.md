# PR86 — jobs3562–3567 reviewed; F14/F27 continuation

## What, how and why

The original [return](../evidence/pr86/jobs3562-3567/public_return.json), SHA256
`003a856fec2b9dd81d5ba18bf944389b5f99a2f007827e8cf11bb3535d7886a3`, passed
the original 3cfc6d3 validator before code changes. An interrupted SCP transfer
left an empty local directory; a later successful download preserved that
directory and the remote receipt. No job or collection was repeated. The new
receiver permits a manual transfer into a unique directory after failure,
without overwriting evidence or automatically retrying any connection/job.

The separate offline review pins original bytes, source, plan and six job IDs;
checks the exact frozen manifest cells; and reuses nested feasibility,
parameters, memory and serial-dependency validation. It preserves original
eligibility flags. All18 new cells meet the0.01% gap target, with valid returned
solutions, MINIMIZE and no memory/callback stop. Cumulative **75/210 cells,
25/70 groups, four historically exposed parents**: F0/F3/F6 complete; F14 has
1thread/seeds42,43,44 and2threads/seed42. F14/4,8,16 remain pending.
Scheduler elapsed sums to2122s (35min22s), excluding queues; not solver-time sum.

## Observed results and limits

| Parent / threads / seed | M0 solver s | M1 solver s | M2 solver s |
| --- | ---: | ---: | ---: |
| F6 /8 /42 | 145.424 | 147.236 | 66.387 |
| F6 /16 /42 | 136.727 | 139.094 | 56.366 |
| F14 /1 /42 | 109.180 | 93.012 | 91.704 |
| F14 /1 /43 | 91.766 | 140.504 | 69.753 |
| F14 /1 /44 | 89.742 | 87.954 | 138.154 |
| F14 /2 /42 | 78.081 | 79.638 | 148.156 |

F6's new M2 times are lower than M0. F14 is heterogeneous: M2 is faster in
two groups and slower in two. F6/8 M0 and M1 gap is0.00480195%; F14/1/43 M2
gap is0.00663245%; these are within the target but not zero. Report these
quality differences alongside timings. More threads do not guarantee speedup.
No new cell or model is selected based on whether GNN helps. Seeds are nested
repeats, not independent parents;75 runs do not establish generalization.

- [75-row cumulative ledger](../evidence/pr86/jobs3562-3567/campaign_results.csv)
- [Complete F6 CPU figure](../evidence/pr86/jobs3562-3567/f6_cpu.svg)
- [Partial F14 CPU figure](../evidence/pr86/jobs3562-3567/f14_cpu_partial.svg)
- [Review](../evidence/pr86/jobs3562-3567/review.json) and [manifest](../evidence/pr86/jobs3562-3567/manifest.json)

Regenerate offline: `python3 -B scripts/evidence/review_pr86_wave19.py --output NEW_DIRECTORY`.
Retain prior snapshots. Scoped cold/amortized preparation scenarios are not
measured whole-job cold costs; charge GNN matching to M1. Sampled cgroup peaks
and Slurm MaxRSS retain different scopes. No population-superiority claim.

## Next six groups, unchanged protocol

Frozen positions25–30 (zero-based): F14/4,8,16/seed42, then F27/1/seeds42,43,44.
Three methods/group in the original balanced order;18 solves in6 serial jobs,
each <=3600s/solve,4h/job,64GiB,CPU only,one node,no exclusive request.
Maximum24 serial reservation hours,18solver-hours,124 physical-core reservation
hours, within the approved210/70 ceiling. Success yields93/210 cells,31/70
groups. F27/2,4,8,16 are subsequent groups, not omitted.

Reuse the existing scheduler/executor, roots3520 and guidance3521. F14's private
inputs bind index3; F27 binds index4. No change to scientific parameters,
memory limits, model, preparation or method order. Tests cover the18 admissions,
both parent bundles, private index4, wrong-parent/dependency rejection, repeat
submission rejection and byte-idempotent figure/table regeneration. Held jobs,
afterok plus artifact checks, immutable claims and one-shot status remain.
No automatic dispatch beyond these six groups or retry/requeue/extension.

The original source-pinned operator/receiver remains intact. The new receiver
uses one SCP and preserves previous transfer attempts. No solver/inference/
training is run locally. PR remains draft; no merge. Both develop/main
synchronization directions stay after article revision. PR87 mandatory1GPU
serial/4GPU-DDP has a separate exact budget; PR88 manuscript remains parallel.
