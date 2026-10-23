# PR86 — F0 review and next six F3 groups

## What was observed

The author returned six complete jobs3523–3528 on13 October. Their original
945KiB public return is preserved without text conversion at
[public_return.json](../evidence/pr86/jobs3523-3528/public_return.json), SHA256
`55b5b60e835cde8af5ab11e9735b052c0c53fa13cdd222f912d192eac65c1024`.
It passed its original source-tree validator before any edits. The new offline
review pins those bytes/source/plan, checks actual accounting, exact six IDs,
held dependency/resource profiles and nested three-method receipts. The prior
job3522 bytes are pinned separately. Neither historical plan is regenerated
against changed source dependencies.

All21 F0 cells completed at gap<=0.0001 (0.01%), with independent solution
checks and MINIMIZE, no memory stop or callback error. Six-wave Slurm elapsed
sum:3824s (1h03m44s), excluding queue intervals, not a solver-time total or
submission-to-completion measurement. The prior3522 adds546s separately.
The squeue NODES=2 display for some pending jobs is not a two-node allocation
measurement: the preserved held profiles admit only NumNodes=1-1. No resource
contract was changed to explain that display.

## Reproducible useful outputs

- [21-row source table](../evidence/pr86/jobs3523-3528/f0_results.csv): parent,
  method, seed, cap, order, solver/gap/objective, start status, attempt/preparation
  scopes, sampled memory and row-to-child/return hashes.
- [CPU curve](../evidence/pr86/jobs3523-3528/f0_cpu.svg), seed42 only.
- [Review](../evidence/pr86/jobs3523-3528/review.json) and
  [output hash manifest](../evidence/pr86/jobs3523-3528/manifest.json).

Regenerate offline, no solver:

```bash
python3 -B scripts/evidence/review_pr86_f0.py --output /tmp/pr86-f0-review-new
```

Use a fresh output directory; changed existing outputs are refused.

| Threads, seed42 | M0 solver s | M1 solver s | M2 solver s |
| --- | ---: | ---: | ---: |
| 1 | 100.705 | 109.595 | 306.390 |
| 2 | 85.633 | 88.896 | 247.591 |
| 4 | 326.385 | 322.737 | 214.758 |
| 8 | 288.287 | 257.380 | 195.833 |
| 16 | 257.247 | 294.714 | 188.714 |

For seeds42/43/44 at one thread, ranges are M0:100.576–106.400s,
M1:103.675–115.485s, M2:210.424–306.390s. More threads did not monotonically
reduce runtime; M2 was faster than M0 at4/8/16 caps but slower at1/2.
These are observations on ONE parent. Do not select a new cap/model/policy
using this test result or claim population speedup. Remaining63 groups stay
in their predefined order. Seeds are nested repeats, not independent parents.

Cost columns named `scoped_*_scenario_seconds` combine measured supervised
attempt time with already-qualified scoped preparation, optionally amortized
over seven uses. They are NOT measured standalone cold whole-job costs. M1
includes its GNN-dependent support preparation. Sampled cgroup memory is not
Slurm MaxRSS or an exact peak. Original scientific flags remain false; this
separate review qualifies only the named descriptive measurements.

## Next delivery, same PR86

Reuse the tested serial submission engine with an explicit policy object;
no duplicated scheduler/executor or removal of held/profile/predecessor gates.
Generalize parent selection through the frozen manifest and guidance parent ID:
F3 must bind run/1 artifacts and its own model/root/checkpoint/start hashes,
not F0's run/0 files. Offline tests reject wrong-parent binding and changed
dependencies. No model, method, threshold, environment or scientific cap changes.

Next six groups are F3/threads1/seeds42,43,44, then F3/threads2,4,8/seed42.
Three methods per job in the frozen order. 18 calls, <=18 solver-hours,
six4h jobs (<=24 serial reserved hours), <=68 physical-core reserved hours,
64GiB/job, CPUonly, one node, shared, no retry/requeue. Included in210/70;
success makes39/210 and13/70. F3/threads16 belongs to the following wave,
not silently omitted. No further wave is dispatched by this operator.

Prepare/submit verify the installed F0 original return before scheduler writes.
Submit all held, record all IDs/profiles, release tail-to-head with afterok;
each successor validates its predecessor before solving. Partial submission
or release is preserved and stops, never retried. One-shot status and terminal
collection; receiver uses one scp. No HPC action or merge occurs in this delivery.

## Revised release sequencing

Per13 October author instruction, defer both directions of develop/main
synchronization until AFTER article revision. Continue PR86 evidence, mandatory
PR87 matched serial/DDP training with its own budget, and PR88 writing. Complete
Sprint E figures/statistics and Sprint F coauthor/journal review first; final
release reconciliation remains separately approved. Preserve historical records.
