# PR66: bounded CPU screen, job 3468

## Receipt qualification

Job 3468 completed with Slurm exit 0:0 on shared dgx-dasci. The ten fresh serial
attempts are complete and their plan, reports, parameters, worker/dependency
hashes, algorithm defaults and CSV projection were checked independently after
download. The executed source is `f4766f974c773510838435cff42287ef657f030e`.
The plan SHA256 is
`7cfd6bf270e04f96c0745ebf61ae427a949d24a85b571879d9c746af1f75b152`.
The downloaded package SHA256 is
`f8a3c0945b90365729bc47eb1f7e0875772f6669262df002db849da524085716`.

Evidence is preserved in `../evidence/pr66/job3468/`. `SHA256SUMS.txt` binds the
original package payloads. `executed_config.json` preserves the exact published
configuration bytes, including its final blank line. These bytes differ from
the earlier local config serialization but their parsed JSON values are equal.
The receipt verifier keeps its original byte-hash guards; no received hash or
measurement was changed to accommodate the local serialization difference.
`screen_review.json` contains explicitly scoped derived accounting.

The fitting-parent pair remained easy 17 and medium 1. Every attempt reports
Gurobi 13.0.1, effective MINIMIZE with the source MAXIMIZE override, unchanged
model structure, seed 42, 300 optimize seconds, a 10% relative-gap tolerance and
SoftMemLimit 48 decimal GB. Physical affinity qualified sixteen distinct cores.
No GPU, exclusive allocation, training or warm-start was involved.

## Observations

Time is the measured optimize call, not the complete preparation cost. RSS is
the individual worker process peak in GiB (2^30 bytes). Gap is percent, not a
percentage-point difference. Every medium attempt terminated at its time limit.

| Threads cap | Easy time (s) | Easy gap (%) | Easy RSS (GiB) | Medium time (s) | Medium gap (%) | Medium RSS (GiB) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 53.486 | 9.948 | 0.249 | 300.559 | 87.875 | 2.116 |
| 2 | 49.614 | 9.980 | 0.493 | 300.080 | 87.881 | 2.277 |
| 4 | 59.389 | 9.768 | 0.731 | 300.098 | 88.300 | 2.322 |
| 8 | 58.208 | 9.800 | 0.986 | 300.133 | 90.631 | 2.672 |
| 16 | 54.843 | 9.394 | 1.249 | 300.203 | 90.513 | 3.314 |

All five easy attempts reached the configured gap tolerance. Gurobi status 2
here does not establish an exact optimum: terminal gaps remain approximately
9.4–10%. None of the five medium attempts reached 10%; status 9/time_limit is a
valid censored outcome, not a failed worker. Their reported node_count is 1.
That counter alone cannot identify time spent in presolve, root LP, cuts or
heuristics; private phase logs would be needed for such an attribution.

The easy two-thread call was descriptively the fastest, but four/eight/sixteen
threads did not consistently improve its time. Its one-thread worker used
53.807 CPU seconds versus 77.153 at two threads and 383.347 at sixteen. Medium
terminal gaps did not improve consistently with higher caps. This screen does
not justify choosing a universally optimal thread count or estimating medium
time-to-target speedup from censored runs.

No worker memory termination or scheduler OOM occurred. The largest reported
worker peak was 3,558,862,848 bytes (3.314 GiB). This qualifies the short screen
only; it does not authorize a smaller reservation or prove safety during a
one-hour search or on other parents.

## Accounting without step duplication

Parent allocation elapsed 1,794 seconds (29m54s). Slurm TotalCPU was 2,803.115
seconds (46m43.115s), or 0.779 CPU-hours. The worker receipts sum to 2,795.692 CPU
seconds, with a narrower scope excluding imports/source hashing. Their optimize
wall times sum to 1,776.613 seconds. Do not add CPU time to wall time or interpret
the difference between scopes as an independently instrumented phase.

Slurm reports AllocCPUS=32, while the affinity-qualified reservation is sixteen
physical cores. Report both units explicitly:

- Scheduler allocated logical-CPU time: 32 x 1,794 / 3,600 = 15.947 CPU-hours.
- Qualified physical-core reservation time: 16 x 1,794 / 3,600 = 7.973 core-hours.
- Configured-cap optimize-time product: sum(cap x optimize time)/3,600 = 3.066
  cap-hours. This is neither actual CPU consumption nor scheduler allocation.

The single parent allocation is charged once. Batch, extern and srun step rows
are not extra reservations. Slurm step MaxRSS=3,456,600K and the worker peak are
different telemetry observations, not peaks to add together. The original
sacct byte receipt and download hashes remain in the private downloaded bundle.

## Recovery and remaining gates

Failed job 3466 remains preserved. Its receipt-serialization recovery passed
this real bounded execution. The temporary operator helper also needed a
collection fix: awk numeric ID equality matched `3468.0` to `3468`. The corrected
nonblocking successor uses textual equality, excludes steps and fails on
conflicting parent records. Eighteen local synthetic helper tests passed; the
original transferred helper is retained rather than overwritten.

This completes the bounded receipt/memory qualification component of PR66.
It does not complete all historical attempt/cost joins or incumbent uniqueness
audits. Each report's solution_count is a solver count, not certification of
distinct full feasible incumbent vectors. Integrity qualification does not
enable scientific_reporting_eligible, which remains false.

The sample comprises two fitting parents, one seed, a shared node and an
increasing safety-screen order. Cache/load/order effects are not controlled as
in a randomized replicated scaling study. No warm-start efficacy was tested.
The six frozen optimization-test parents were not used by this screen.

Next: publish these receipts and this review to the existing PR66, require the
four evidence CI arms at the new SHA, and request the author's merge decision.
Do not silently expand to the proposed 30/90-run matrices. Subsequent CPU
comparisons and serial/DDP learning require separately frozen designs, resource
qualification and approved budgets. Main, Pages, Zenodo and MVP 1.0 stay unchanged.
