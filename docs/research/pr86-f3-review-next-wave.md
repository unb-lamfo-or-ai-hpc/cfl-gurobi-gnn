# PR86 — F3 return and next frozen six groups

## What was reviewed

Jobs 3542–3547 completed with exit 0:0. The original public return, SHA256
`f526e0fbdff7fe2402fa1d3a3c7a7d264d77c7f1275574e371547994aa5c747c`,
is preserved byte-identically in
[jobs3542-3547](../evidence/pr86/jobs3542-3547/public_return.json).
The original c327d830 validator passed before code edits. A separate pinned
review checks source/plan, six actual job IDs, frozen cells, nested measurements,
solution feasibility, effective MINIMIZE and held resource/dependency profiles.
It does not regenerate old source pins against a new executor or alter old flags.

All 18 new cells reached the prescribed gap, without a memory/callback stop.
Together with the 21 reviewed F0 cells, the campaign now has **39/210 cells and
13/70 groups**. F0 is complete; F3 still lacks its 16-thread group. Two distinct
historically exposed parents are represented, not 39 independent instances.
The six job elapsed values sum to 1,255 seconds (20 min 55 s), excluding queue
intervals. This is not total solver time or submission-to-completion time.
Slurm AllocCPUS records logical allocation; the physical-core contract is unchanged.

## Useful scientific outputs

- [Cumulative 39-row table](../evidence/pr86/jobs3542-3547/campaign_results.csv),
  with method, seed, cap, solver/quality/cost/memory scopes and receipt hashes.
- [Partial F3 CPU figure](../evidence/pr86/jobs3542-3547/f3_cpu_partial.svg),
  explicitly marking the 16-thread observation as pending, not zero.
- [Review](../evidence/pr86/jobs3542-3547/review.json) and
  [hash manifest](../evidence/pr86/jobs3542-3547/manifest.json).

| F3, seed 42 | M0 solver s | M1 solver s | M2 solver s |
| --- | ---: | ---: | ---: |
| 1 thread | 63.937 | 65.077 | 36.455 |
| 2 threads | 56.803 | 57.546 | 32.728 |
| 4 threads | 73.351 | 71.616 | 43.259 |
| 8 threads | 62.375 | 115.752 | 40.638 |
| 16 threads | pending | pending | pending |

M2 was faster than M0 at the four observed seed-42 caps for this parent.
This does not establish population superiority, an optimal cap, or independent
generalization. No future group or method is selected on the observed benefit.
Seed repeats remain nested within parents. The table's scoped preparation-cost
scenarios are not measured whole-job cold costs; M1 includes GNN-dependent
matching preparation. Sampled cgroup memory is not an exact peak or Slurm MaxRSS.

Regenerate offline into a fresh output directory:

```bash
python3 -B scripts/evidence/review_pr86_campaign.py --output /tmp/pr86-review-next-new
```

## Next six jobs — what, how and why

Use the next manifest positions 13–18 (zero-based), without skipping or repeating:

| Order | Parent | Threads | Seed | Methods |
| --- | --- | ---: | ---: | --- |
| 1 | F3 | 16 | 42 | frozen M0/M1/M2 order |
| 2 | F6 | 1 | 42 | frozen M0/M1/M2 order |
| 3 | F6 | 1 | 43 | frozen M0/M1/M2 order |
| 4 | F6 | 1 | 44 | frozen M0/M1/M2 order |
| 5 | F6 | 2 | 42 | frozen M0/M1/M2 order |
| 6 | F6 | 4 | 42 | frozen M0/M1/M2 order |

This completes F3 and starts F6 while retaining six-job waves. F6/8 and16 threads
remain next; no omission. Eighteen solves in six serial jobs, each <=4h,64GiB,
one node,CPU only: <=24h serial reservation, <=18 solver-hours and
**100 physical-core reservation hours**, inside the already approved 210/70
budget. Success yields 57/210 cells and19/70 groups; no further automatic dispatch.

Reuse the existing scheduler/isolated executor. The new policy fixes only this
next slice and predecessor receipts. Parent-specific private inputs are cached
by parent, not by wave: F3 binds preparation index1; F6 binds index2. Tests check
both the binding and actual per-group bundle arguments at that transition.
Prepare checks both parents; all six admissions are validated before any sbatch.
Held profiles, afterok, predecessor artifact checks and reverse release remain.
Immutable claims prevent repeating a partly submitted wave. One-shot status,
terminal collection, and one-scp receiver remain nonblocking.

No repeated roots, inference, training, package changes, retry, requeue or
resource extension. The agent performs no HPC execution. Preserve failures and
stop instead of automatically replacing runs. Main/develop synchronization stays
postponed until after article review; PR86 remains draft without merge.
