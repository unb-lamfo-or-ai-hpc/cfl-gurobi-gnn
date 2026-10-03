# Computational reconciliation and controlled CPU-thread pilot

## Status and release boundary

This is a prospective MVP 2.0 protocol, not an executed experiment or a
submission authorization. Feature PRs target `develop`. Main, Pages, the private
MVP 1.0 archive and Zenodo draft 23113003 remain unchanged. PR65 closes a
read-only diagnostic after its exact published commit passes CI and review;
subsequent work implements the contracts below before submitting solver jobs.
No hard-instance label campaign or GPU training belongs to this CPU pilot.

The recovered collection covers all 90 original models. The ledger currently
supports 87 report observations across 36 parents: 45 Gurobi and 42 SCIP reports,
with 77 Parquet tables. These are not 87 certified distinct runs or 77 unique
incumbents. Complete 54-parent incumbent totals and full historical costs remain
unknown. Recovery receipts retain the first failed class collection and the
invalid historical JSON rather than relabelling them as successful.

## 1. Reconcile identities before counting or aggregating

Maintain separate registries and explicit relationships:

| Entity | Identity and qualification | Must not be inferred from |
| --- | --- | --- |
| Original model | Canonical parent ID, class, stored LP hash, format and effective objective sense | Class name or filename alone |
| Artifact observation | Stored content hash, schema/adapter version, private source identity | A new path being a new solve |
| Solver attempt | Receipt/run identity, model hash, solver, contract, commit, parameters and seed | Parent ID plus parameter equality |
| Scheduler allocation | Cluster, submission identity, array/task ID and start/end times | Job name or an account-wide job list |
| Phase | Attempt-to-job edges for reading, preparation, optimization, training, evaluation and audit | Every step being an additional allocation |

Implement adapters using retained schema samples and synthetic fixtures first.
Extend canonical parent-solve reports to legacy incumbent `metadata.json`,
confirmation execution receipts and paired worker outcomes only where their
fields have documented semantics. Every extracted field must retain its source
artifact hash, schema version and qualification reason. Missing source fields
remain null; unsupported formats do not become empty successful attempts.

Copied reports with identical content are potential artifact aliases, not proof
of new executions. Conversely, repeated attempts on the same model remain
separate even with identical parameters. Use launch receipts, run identities and
timestamps to decide; preserve ambiguous aliases rather than deduplicating on
parent/solver or hash alone. One job may execute several method attempts, and
one attempt may span multiple recovery jobs.

All recovered stored LPs declare MAXIMIZE, while the existing experiment
convention uses MINIMIZE in memory. Verify each historical attempt's effective
sense against its launcher, parameter/report evidence and objective convention.
When a complete solution vector is available, recompute its objective without
optimization. Successful model reading does not certify historical objective
configuration. Keep stored-byte identity separate from any future canonical
mathematical-model hash: compressed and uncompressed bytes are not interchangeable.

## 2. Attribute computational cost without double counting

Join jobs using explicit submission receipts and corroborating contract,
commit, model and timestamp evidence. Publish join states `matched`, `ambiguous`
and `unmatched`, with reasons. Keep the private path/command map on the HPC;
publish only sanitized provenance. Unmatched account jobs cannot contribute to
an attributed CFL total.

Count each concrete allocation once. An array summary is not an additional
allocation above its tasks; `.batch`, `.extern` and application steps are
diagnostic children, not extra reserved core-hours. Do not add both a job's
aggregate measured CPU time and its child step values. If one allocation bundles
several attempts, report its total once and retain shared overhead; allocate
phase costs only from valid non-overlapping timing evidence, not equal guesses.

Separate these measurements:

- Reserved CPU-hours: actual `AllocCPUS * ElapsedRaw / 3600`; cross-check
  `CPUTimeRAW` when available. Record allocation scope and exclusive reservations.
- Measured CPU-hours: qualified `TotalCPU / 3600`, with task/step provenance.
  Missing or interrupted-process accounting remains explicitly incomplete.
- Wall time: queue delay, reading, construction, root preparation, inference,
  optimize calls, evaluation, audit and packaging in separate fields. Queue
  delay is not solver computation; summed optimize durations are not campaign
  elapsed time when executions overlap.
- Memory: scheduler reservation, sampled application/step MaxRSS and, when
  instrumented, aggregate process memory. Do not sum unrelated MaxRSS peaks or
  present a 64 GiB reservation as measured consumption.
- GPUs: allocated GPU-hours separately from measured utilization. The historical
  one-GPU training allocation is not a multi-GPU scaling result.

Retain failed, cancelled, timed-out and recovery allocations in the cost ledger.
Report covered time windows and missing accounting explicitly. The distinction
between allocated CPU time and measured process CPU time follows the official
[Slurm accounting reference](https://slurm.schedmd.com/sacct.html); signal-killed
steps can have incomplete descendant-process CPU accounting. Missing historical
telemetry cannot be recreated by running new experiments.

## 3. Audit incumbents and actual augmentation usage

Footer counts are only a starting inventory. Read qualified Parquet vectors in
bounded batches, without loading pickle/checkpoint objects, and bind every table
to its original or derived model and variable-order hash. Reject unmapped,
duplicate or incomplete variable columns. Check finite values, variable bounds,
integer domains, constraint residuals and recomputed objectives under documented
tolerances and the verified effective sense. These checks require no optimization.

Distinguish callback events, stored rows, solver-pool solutions, mapped vectors,
feasible vectors, unique full solutions and admitted training labels. Define a
stable full-vector representation for exact duplicate detection; any
tolerance-based near-duplicate grouping is a separate measure. Equal binary
projections do not necessarily mean equal complete solutions. Report counts by
parent, solver and attempt, plus cross-attempt duplicates. A feasible vector
alone does not certify a <=10% gap without a compatible qualified bound.

Use the frozen 54-parent cohort for coverage accounting, not all 90 parents as
an implicit label population. Produce per-parent Gurobi/SCIP counts and missing
reasons. Only report a complete cohort total after all constituent entries are
qualified; otherwise retain partial totals with coverage and an unknown complete
total. Preserve the invalid `models/run_01/experiment_summary.json` unchanged.

For augmentation, track `generated -> independently labelled -> encoded ->
included in plan -> consumed during fitting` separately. Modified MILPs need
their own model identities and feasibility/label evidence. Parent incumbents
do not certify modified-model labels. Membership plans alone do not establish
actual gradient updates: join execution reports, dataset/partition hashes and
epoch/optimizer receipts. Where historical sampling was not logged, actual
derivative consumption remains unknown. Descendants inherit parent roles.

Deliver small sanitized `model_registry`, `attempt_registry`, `artifact_aliases`,
`attempt_job_edges`, `cost_by_phase`, `incumbent_audit`, `derivative_usage` and
`coverage_missing` tables with schemas and manifests. Private paths and raw
vectors stay outside GitHub. Success means traceable, qualified observations and
explicit gaps, not inventing complete historical totals.

## 4. Freeze the pilot cohort and intervention

Select three easy and three medium parents from qualified fitting/development
roles, excluding frozen predictive/optimization test parents. Verify roles
against a specific plan hash before selection. Do not select on historical gap,
warm-start improvement or solve time. Within each class the observed dimensions
are constant, so dimension-based within-class stratification is uninformative.
Instead, order eligible parents by binary-variable fraction, using stored source
hash as a deterministic tie-breaker, and select low, middle and high positions.
Freeze the selected IDs, role provenance, input hashes and numerical ranges in a
selection receipt; stop if three eligible distinct parents are unavailable.

The primary comparison is fresh unguided Gurobi optimization with thread caps
1, 2, 4, 8 and 16. GNN starts, root-LP starts, concurrent portfolios and SCIP
comparisons are separate later experiments. Freeze solver/runtime version,
effective MINIMIZE sense, tolerances, presolve, cuts, heuristics, node settings,
memory guard and root algorithm. Only thread count varies within a comparison.
Use seeds 42, 43 and 44, paired across thread counts.

Before qualification, recover the historical root profile. If it cannot support
a fixed reproducible profile, screen dual simplex and barrier at two threads on
one selected easy and one medium parent, at most 300 seconds per run. Freeze a
valid profile by predeclared compatibility and memory-safety criteria, not the
best gap, before comparative runs. Keep alternative root methods in a separately
named sensitivity arm. Do not mix root-feature preparation with MIP optimization
or infer that historical barrier use caused a deterioration.

Gurobi's `Threads` is a cap; actual parallel use need not reach it. Higher caps
can increase memory or contention. `Method` controls the continuous/root
algorithm; automatic selection can introduce a second intervention.
`ConcurrentMIP` instead partitions threads among independent searches and is
non-deterministic. Keep it at 1 here. Set environment `ThreadLimit` before startup
where supported and verify effective parameters. These distinctions follow the
[official parameter reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html).

## 5. Qualify hardware and memory before expanding execution

Record CPU model, physical/logical cores, sockets, NUMA topology, Slurm allocation,
CPU affinity, software versions and other active workloads. The reported 80 CPUs
do not alone identify 80 available physical cores. Bind one worker to its allocated
CPUs; request `--cpus-per-task=t` and set `Threads=t`, without BLAS/OpenMP
oversubscription. Explicitly verify effective solver thread caps, allocation and
affinity. A rejected/capped setting is not a completed t-thread observation.

Use only the authorized license at
`/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic`; never package it.
Each attempt uses a fresh model/environment and a fresh output directory below
`/raid`, not the home root. No source input is modified and no checkpoint/previous
incumbent is loaded. Record input cache conditions; do not flush system caches.

Begin with a memory-safety screen on one selected easy and one medium parent,
using increasing caps 1/2/4/8/16, seed 42 and at most 300 optimize seconds each.
Run one attempt at a time. Start with the existing 64 GiB per-job reservation;
freeze a common guard with measured headroom for Python, logging and solver
overshoot. Express every limit in bytes and its runtime-native unit. Gurobi's
`SoftMemLimit` uses decimal GB and allows solution retrieval, but can overshoot
between checks; it is not a replacement for the Slurm process-memory boundary.
Record graceful memory stops and scheduler OOM separately. Do not silently lower
threads, increase RAM, or resume an interrupted attempt in the same comparison.

Passing this short screen does not prove an hour-long search will fit. Continue
monitoring all measured runs, retain failures, and pause a resource profile if
its safety margin is violated. A changed guard/reservation is a newly versioned
profile, not a favourable rerun replacing the failed result. Verify topology and
load comparability before relaxing single-attempt concurrency. A whole-node
exclusive reservation can change allocated-core cost and must be accounted for.

## 6. Proposed execution matrix and budget gates

| Stage | Parents x thread caps x seeds/profiles | Runs | Maximum optimize time | Core-hours at the configured caps |
| --- | --- | ---: | ---: | ---: |
| Optional root-profile screen | 2 x 1 cap (2 threads) x 2 methods | 4 | 20 minutes | 0.67 |
| Memory-safety screen | 2 x 5 x 1 | 10 | 50 minutes | 5.17 |
| First comparative block | 6 x 5 x seed 42 | 30 | 30 hours | 186 |
| Remaining comparative blocks | 6 x 5 x seeds 43/44 | 60 | 60 hours | 372 |
| Full comparative pilot | 6 x 5 x 3 | 90 | 90 hours | 558 |

The first 30 runs are included in the 90, not additional runs. These are proposed
optimize-time ceilings, assuming `AllocCPUS=t`; they exclude reading, setup and
audit overhead. With a proposed 65-minute scheduler ceiling per comparative
attempt, allocated time could reach 604.5 core-hours across the 90 runs under
the same allocation assumption. Use measured allocations for actual reporting,
especially if whole-node reservations are required. The optional root screen
and memory screen are separate qualification costs. No stage has been submitted.

Complete resource qualification before authorizing the first comparative block.
Proceed to the other two predeclared seeds only after receipt/instrumentation and
safety checks, not a requirement for favourable gap effects. If a safety failure
stops expansion, retain the partial pilot with its reason and coverage.
Randomize thread order reproducibly within each parent/seed block; keep models,
seeds and fixed parameter profile paired. The increasing order is for safety
screening only. Aim for a quiet, comparable node and initially one active solve;
measure any residual shared-node load rather than assuming isolation.

## 7. Outcomes, interpretation and subsequent gates

Instrument primal/dual trajectories, terminal gap, solver status, actual root and
search times, nodes, sampled RSS, actual CPU time and allocated CPU-hours.
Separate process read/build/cleanup time from the optimize call. Record first
observed crossings of 10%, 5% and 1% gaps with sampling resolution; solve to the
frozen optimality tolerance or the 3,600-second limit. Do not describe tolerance
termination or rounded zero as an exact mathematical zero-gap certificate.

The primary outcomes are terminal gap at the common budget and time to <=10%.
Other targets and solver-tolerance termination are secondary. A target not
reached is right-censored; memory/allocation failures are separate outcomes,
not successful time-limit runs. Compute time-to-target speedup `T1/Tt` and
efficiency `(T1/Tt)/t` only where both paired targets were reached. Do not replace
censored times with 3,600 seconds and treat that as a measured speedup.

Report all parent/seed results, paired differences, medians, resource curves and
coverage for every speedup summary. Parent is the independent unit; seed repeats
are nested observations, not 18 independent parents. Six development parents
support a descriptive resource pilot, not a population-wide significance claim.
Prefer the measured time/quality/memory/core-hour trade-off over a single
"best thread count"; optimal settings may differ by class and budget.

Gate order: corrected PR65 CI/review -> legacy/identity/job reconciliation and
versioned pilot contract -> hardware/root/memory qualification -> comparative
pilot -> review before expansion to all 30 easy or larger transfer cohorts.
Portfolio search, independent-instance throughput and mathematical decomposition
are distinct follow-ups. Benders requires a structural/correctness study; threads
alone do not split a CFL model into independent subproblems.

Serial versus DDP 1/2/4/8-GPU training remains a separate protocol with matched
effective global batch, data membership and optimizer updates. More GPUs can
change an optimization trajectory if those controls differ, but do not guarantee
better predictive quality. Preserve the MVP 1.0 checkpoint as its own comparator.
