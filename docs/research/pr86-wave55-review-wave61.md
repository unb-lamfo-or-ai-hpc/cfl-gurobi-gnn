# Jobs3625–3630: complete M4, partial M7; next fixed wave — 17 October 2026

## What was received and verified

Original return SHA256 `2cf7240c097f2b3c850c3b4be58ea4c63390ff98718da41c692f29854238d26a`,
source `48b22795518201447780667ca725191c481b7f86`, plan
`f2c5cb99ff8970f9aef6476e5bf4ad91cae43afc48b711765ed9a9f7fcffb11c`.
The original source-tree validator passed before changes. The separate pinned
review checks the original bytes, source/plan, manifest positions55–60,
predecessor audit/decision, six job identities, serial dependencies, allocations,
18 nested results, models, starts, parameters, sense, per-vector tolerance checks
and memory/callback stops. It never rebuilds historical dependency pins using
new source hashes. Original raw eligibility flags remain false and unchanged.

The receiver mistakenly named the local directory `pr86-next49-2cf7240c097f`.
Its remote source and validator were correctly wave55. The actual local hash
matches; preserve that directory without renaming/redownloading. Only the
future wave55 local destination label is corrected to `next55`. This changes
neither remote paths nor scientific data. The pasted chat mixing a prompt into
JSON is not the evidence source; the actual downloaded bytes are.

Evidence and regenerable outputs: [original return, CSV183, review and figures](../evidence/pr86/jobs3625-3630/).
Offline regeneration (no Gurobi, inference, training or scheduler):

```text
python -B scripts/evidence/review_pr86_wave55.py --output docs/evidence/pr86/jobs3625-3630
python -B -m unittest discover -s tests/evidence -p test_pr86_wave61.py -v
```

## Observations, not a superiority claim

All18 new solves are time-limited/censored for time to target. Both supplied
starts were accepted in each group; all18 stored vectors pass the existing
tolerance checks, and no memory/callback stop was reported. Six jobs sum
66016s =18h20min16s scheduler elapsed, excluding queues; not measured solver
time or CPU work. Sampled cgroup memory, Slurm MaxRSS and internal solver
memory are distinct scopes. Scoped preparation scenarios are not measured
standalone cold whole-job costs.

| Parent / cap / seed | Final gap M0 (%) | M1 (%) | M2 (%) |
| --- | ---: | ---: | ---: |
| M4 /16 /42 | 50.1144 | 31.8299 | 3.2199 |
| M7 /1 /42 | 16.4406 | 19.5460 | 13.9212 |
| M7 /1 /43 | 13.1408 | 18.0446 | 14.7718 |
| M7 /1 /44 | 16.8319 | 14.2143 | 13.2061 |
| M7 /2 /42 | 15.1727 | 14.4868 | 16.8625 |
| M7 /4 /42 | 53.0565 | 44.0727 | 14.2811 |

M7 effects are heterogeneous: M2 has lower gap than M0 in three of five
groups, not all five. All are censored, so near-equal runtimes around3600s do
not establish time-to-target speedup. Caps8/16 remain unobserved. The gap and
sampled-memory SVGs label M7 partial, not interpolated.

M4/16/M2 reports objective4.904624667697033 below the older M4/8/M2 reported
bound4.905362657205728. The cross-run screen now lists four bound/incumbent
comparisons; this is an extension of the already disclosed M4 sensitivity,
not proof of a solver defect or exact integer feasibility. The earlier read-only
audit of four stored vectors is not an audit of this new vector. Keep all21
M4 observations, but no unambiguous optimum/certified speedup claim. No repair,
rounding of stored files, parameter change, rerun or new audit is introduced.
No cross-run conflict was detected among the15 M7 observations in the same
screen; that is not an exact arithmetic certificate or a population claim.

## Denominators and remaining work

183/210 cells and61/70 groups are collected. Of these,162 non-M4 cells have
the scoped identity/tolerance review and21 M4 cells retain explicit numerical
sensitivity. The128 reported target-reaching cells include the disputed M4
gap-zero report; do not call128 certified optima.55 cells are censored.
There are nine historically exposed parents observed, not183 independent
test instances.27 cells/nine groups remain. Preserve all earlier snapshots.

## Why and how to continue

The author approved finishing the unchanged matrix with M4's limitation.
The next six original zero-based positions61–66 are:

| Group | Parent | Physical-core/thread cap | Seed |
| --- | --- | ---: | ---: |
| 61 | M7 | 8 | 42 |
| 62 | M7 | 16 | 42 |
| 63 | M12 | 1 | 42 |
| 64 | M12 | 1 | 43 |
| 65 | M12 | 1 | 44 |
| 66 | M12 | 2 | 42 |

Three frozen-order M0/M1/M2 solves per group; reuse roots3520 and guidance3521,
private parent indices8/9. No additional LP, inference or training. Up to six
serial CPU-only shared-node jobs,4h/64GiB each,3600s/solve:18 solver hours,
24 serial reservation hours and116 physical-core reservation hours within
the210/70 approved ceiling. Keep MINIMIZE and all original parameters, starts,
method order, seeds, one node/task, affinity,48decimalGB soft/56GiB sampled
stop/kernel<=64GiB. No GPU/exclusivity, retry,requeue,extension or overwrite.

`pr86_wave61.py` reuses the existing isolated executor and serial queue; it
binds the installed previous returns and audit plus the author decision.
A new-parent numeric conflict blocks preparation. `afterok` and predecessor
artifact validity protect distinct boundaries. Submission returns six IDs
without waiting. Status is one-shot; collect only after all jobs are terminal;
receiver uses one SCP. No automatic dispatch beyond this wave.

Success would yield201/210 cells and67/70 groups, leaving only M12/4,8,16
at seed42 (nine solves/three jobs), followed by final paired statistics, cost
and figure synthesis in this same PR. Completion is not presumed. Four checks
on the final published source must pass before the pinned execution CLI is
released. PR86 stays draft until the matrix and analysis are complete.
PR87 matched1/4-GPU training needs its own exact budget; PR88 manuscript stays
parallel. Develop/main synchronization remains last, after article revision.
