# MVP2 R3 — metrics and reproducibility assessment

26 October 2026 · R2-D4 and metric definitions supporting R2-D5/D6.
Governed by the [R3 contract](mvp2-r3-contract.md).
Reuse the [existing D1 dictionary](methodology-20261019/D1-protocol.md);
this document resolves interpretation and implementation boundaries without
rewriting that dated source or running another experiment.

## Configuration, trajectory, clock and stopping rule

Four different questions must be recorded separately:

| Question | Required evidence | What is not implied |
| --- | --- | --- |
| Is the input/configuration identical? | Model bytes/signature/fingerprint, order, solver version, starts, seed, effective parameters and hardware | Seed42 alone does not establish identity |
| Is the algorithmic trajectory reproducible? | Comparable event/work/node observations under those inputs and a documented algorithm | Similar terminal values do not prove identical paths |
| Is elapsed time repeatable? | Actual clock/environment observations and measurement boundary | Same trajectory does not imply equal seconds |
| Is the terminal state repeatable under TimeLimit? | Recorded stopping rule, follow-up and terminal primal/dual/status | A fixed time cap need not stop at an identical algorithmic point |

Gurobi documents determinism conditional on the same model, parameters,
computer and version, and identifies wall-clock termination as a source of
different terminal points. Parallel execution is not automatically
nondeterministic; changing Threads changes an input.
[Official determinism guidance](https://support.gurobi.com/hc/en-us/articles/360031636051-Is-Gurobi-deterministic)
and [parameter guidelines](https://docs.gurobi.com/projects/optimizer/en/current/concepts/parameters/guidelines.html)
were checked on 26 October 2026.
A model fingerprint helps diagnose identity but is not a replacement for
the full bytes, parameter/start bindings and environment records.

Seed42 remains the principal protocol. Gurobi's
[parameter reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html#parameter:WorkLimit)
describes deterministic work-based stopping under stated conditions; this
is context, not permission to replace PR89 TimeLimit with WorkLimit.
Do not change Method, ConcurrentMIP, Threads, tolerances or any parameter
to obtain a preferred determinism claim. If Work or an effective parameter
was not exported in a historical receipt, label it unavailable, not zero,
an inferred default, or reconstructed runtime.
No new repeated runs are proposed. Identical reruns would not create
independent parents; seed43/44 remain historical, with broader robustness
deferred beyond MVP2.

## Optimization quality and denominator rules

For the same MINIMIZE model, report finite primal zP, dual zD, terminal status,
follow-up, feasibility scope and numerical qualification independently.
A smaller primal and a larger valid lower bound describe different aspects
of progress; neither alone establishes the smallest relative gap.

For finite values, the reported relative gap is
abs(zP-zD)/abs(zP), expressed as a fraction; percent is 100 times that value.
At zP=0, the mathematical convention is zero when zD=0 and infinity otherwise.
Missing incumbent/bound is separate from either case.
The PR89 [frozen temporal recorder](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9ab7823c6886d19e9ec865141a1cd35b3c3c16e5/scripts/evidence/pr89_cpu_temporal.py)
serializes nonfinite/unavailable gap as null (including zero primal with a
nonzero bound), with explicit point state. Keep that raw encoding; do not
rewrite null to zero or invent an observed crossing.

Configured MIPGap=0.0001 is **0.01%**, not 1% or 10%.
The observed-threshold analysis uses fractions 0.10/0.05/0.01/0.0001
(10/5/1/0.01%). Terminal solver-reported target attainment, first observed
crossing and an exact continuous hitting time are distinct.
The efficacy reorganization followed knowledge of prior results; it is not
the original preregistration and must examine all four medium parents/caps.

## Temporal observations and eligibility

PR86's historical callback thresholds 1/5/6/10% are not the new PR89 threshold
set and do not by themselves measure its terminal 0.01% target.
PR89's recorder stores a monotonic wall clock since optimize dispatch,
first observed qualifying point and previous observation. Its bounded
trajectory sampling is distinct from event-level crossing/horizon updates.
Do not interpolate a first hit between observations.

| Recorded condition | Analysis treatment |
| --- | --- |
| Eligible crossing observed | Report observed time, prior observation and threshold; do not claim an exact continuous first hit |
| Target unobserved with adequate follow-up | Right-censored at recorded follow-up, not an exact solution time |
| No incumbent, unavailable bound or lost observations | Preserve unavailable state and cause; inspect point state/coverage before metric eligibility |
| Unqualified vector/numerical comparison | Restrict affected metrics separately; do not relabel as ordinary censoring |
| Terminated before horizon | Preserve terminal value/time and terminated_before_horizon; do not extend the curve |
| Bracket around horizon | Report both actual timestamps and staleness; do not manufacture quality at exactly H |
| Actual observation at horizon | Label exact_observation only when recorded timestamp equals H |

Horizons are 3,600/14,400/28,800/43,200 seconds (1/4/8/12h).
The raw threshold-state label alone is insufficient: the recorder can retain
right_censored alongside a point with an unavailable bound. Review follow-up,
point states and numerical scope together before interpreting a metric.
Keep technical success, scheduler state, feasibility under tolerances,
censoring, numerical sensitivity and missingness as separate dimensions.

M4/M12 are retained in coverage and descriptive reporting with their respective
limitations. More time or OPTIMAL does not establish exact optimality or
certified speedup. Do not change original flags to grant blanket eligibility;
produce a separate review naming qualified rows/metrics and exclusions.

## Comparable time and scaling

| Quantity | Definition | Qualification |
| --- | --- | --- |
| G versus B speedup | T_B / T_G | Same parent, seed, cap and attained target; >1 favors G |
| G versus R speedup | T_R / T_G | Same requirements and R's neural-dependent preparation disclosed |
| Historical G/B time ratio | T_G / T_B | Preserve historical name/values; <1 favors G |
| CPU scaling for method m | S_m(r)=T_m(1)/T_m(r) | Same eligible endpoint, physical cap r |
| CPU parallel efficiency | S_m(r)/r | Different from a between-method benefit |
| GPU loop/job speedup | T_serial1 / T_DDP4 | State clock scope and matched work; do not substitute one clock for another |
| GPU efficiency | speedup/4 | Observed GPU+CPU configuration comparison, not isolated GPU causality |

A timeout runtime cannot stand in for a successful time-to-target.
State how many eligible parent pairs enter a ratio; complete-case pairs do
not represent censored pairs. Pair at parent level and report easy/medium
strata. Do not use 150/210 cells or the binary-variable count as independent n.

## Costs, resources and reproducibility boundary

Separate solver Runtime, monotonic attempt/dispatch clocks, job ElapsedRaw,
queue time, preparation and training. Compute queue only when submission/start
timestamps exist. Shared/reused/amortized cost scenarios are not new cold
measurements. Do not double-count export inside a larger measured interval.
Missing timing remains unavailable and does not authorize a rerun.

Physical reserved core-h = physical requested cap × reserved wall-h.
Slurm TotalCPU is processor accounting, while AllocCPUS can include SMT;
neither is automatically physical reserved capacity or the experimental cap.
Assigned GPU-h = allocated GPUs × job elapsed-h; utilization samples and
energy are different measures. Keep cgroup, process RSS, Slurm step MaxRSS,
GPU allocator and GPU telemetry scopes/cadences separate; do not sum peaks.

The installed environment is recorded as tfm_env with Python3.10.20,
NumPy1.26.4, SciPy1.15.3, Gurobi13.0.1, PyTorch2.1.2+cu121 and PyG2.7.0.
This is documentary installed context, not a new allocation/driver/license
inspection or a reason to upgrade it. Per-job affinity/memory/solver evidence
will be checked in the authorized return.

## What this assessment establishes

Inspected source, existing receipts and official documentation support the
definitions and distinctions above. They do not establish new observed PR89
quality, repeated trajectories, missing work units or a numerical repair.
See the [machine-readable evidence index](mvp2-r3-evidence-index.json) for
source identities and explicitly pending products.
