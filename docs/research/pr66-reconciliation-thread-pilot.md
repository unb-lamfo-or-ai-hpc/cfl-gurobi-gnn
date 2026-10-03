# PR66: reconciliation foundations and a lean DaSCI thread screen

## Release boundary and current status

The author confirms PR65 merged into `develop` at
`929f10e1102e398ecc33a58908f8788c9367e909`. PR66 targets `develop`, never `main`.
The local implementation was provisionally prepared from feature head `39e3baf`
while the connector was unavailable. Fetch and verify the actual merged base
before publishing. No remote PR number is assumed reserved.

This protocol supersedes the six-parent/three-seed pilot and the subsequently
suggested exclusive NPAD allocation. CFL execution is only on shared
`dgx-dasci`. MVP 1.0, Pages, manuscript and unpublished Zenodo remain unchanged.
The licensed Linux worker has not been executed by local unit tests.

## Four historical reconciliation fronts

The PR65 collectors and their qualified hashes are unchanged.
`scripts/evidence/pr66_reconciliation.py` provides tested qualification functions,
not a completed recovery of all historical evidence:

1. Identity: the named parent-report adapter preserves unknown execution identity
   and objective sense. Identical bytes are artifact aliases, not necessarily
   the same solve. Unsupported legacy schemas need sanitized fixtures before
   additional adapters; no empty-success fallback is used.
2. Cost: explicit hash-bound receipt edges join attempts to concrete Slurm jobs.
   Charge bundled jobs once, not once per attempt or child step. Separate reserved
   and reported CPU-hours; exclude unmatched jobs from attributed CFL totals.
   Phase attribution requires qualified non-overlapping timings.
3. Incumbents: check complete variable-order-bound vectors against bounds,
   domains, linear constraints and effective MINIMIZE objective, without solving.
   Exact full-vector identity differs from callback events, table rows and binary
   projections. Feasibility is not gap certification. A bounded HPC Parquet/model
   adapter and complete 54-parent coverage remain necessary. The current function
   accepts an independently qualified projection, not arbitrary historical JSON.
4. Augmentation: plan membership leaves fitting consumption unknown. An explicit
   derivative/update receipt establishes observed use, not exhaustive epoch
   coverage or benefit. Descendant roles must match parents. Callers must verify
   actual dataset/execution provenance, not infer it from paths or hash syntax.

Private maps, full vectors and malformed artifacts stay on the HPC. Complete
solver incumbent totals and historical costs remain unknown until qualified.
New experiments do not reconstruct missing historical telemetry.

## Frozen first-stage design

Use the verified PR57 training plan and its previously qualified SHA256.
Uniformly draw one easy and one medium from sorted `train` parent pools with
Python `random.Random(42)`, easy then medium. Exclude validation, predictive-test
roles and the six frozen optimization-test parents. Freeze pools, roles, sampling
implementation, stored LP hashes, configuration and worker hash before outcomes.
No favorable-result redraws. This fitting-pool screen is not a representative
random sample of all 90 originals.

One job requests one task, 16 CPUs, 64 GiB and `--hint=nomultithread`. There is
no exclusive flag, array or GPU reservation. The worker checks Linux socket/core
IDs within its inherited affinity. Exactly sixteen physical cores must be
accessible; retain one hardware-thread ID per core, inherited by child workers.
Eight cores with sixteen SMT threads, or unbounded affinity, fail before solving.
This does not disable host hyperthreading or isolate the host from other users.

Do not combine the hint with `--cpu-bind=cores`; the official
[srun reference](https://slurm.schedmd.com/srun.html) documents this conflict.
Use `--cpu-bind=verbose` with the hint and qualify actual plugin/topology support.

| Threads cap | First attempt | Second attempt | Optimize cap per attempt | Gap target |
| ---: | --- | --- | ---: | ---: |
| 1 | selected easy | selected medium | 300 s | 10% |
| 2 | same easy | same medium | 300 s | 10% |
| 4 | same easy | same medium | 300 s | 10% |
| 8 | same easy | same medium | 300 s | 10% |
| 16 | same easy | same medium | 300 s | 10% |

Only thread cap varies. Seed 42, Gurobi 13.0.1, effective MINIMIZE and the fixed
parameter map are recorded. Method=2, NodeMethod=1 and Crossover=0 define a new
fixed barrier-root profile, not proof that it is best or that historical barrier
use caused deterioration. ConcurrentMIP=1 excludes portfolio search. Environment
ThreadLimit=16 precedes startup. The
[Gurobi parameter reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html)
describes Threads as a cap, not guaranteed simultaneous utilization.

SoftMemLimit=48 decimal GB leaves headroom inside 64 GiB; it can overshoot between
checks. Pause the remaining matrix on resource/solver failure and retain all
attempts. Do not silently lower caps, increase RAM or substitute another license.
Use only `/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic`.

## Measurements and budget

Retain terminal primal, dual, gap, status, nodes, read/setup and optimize wall
times, process CPU and peak RSS, load averages, hashes and physical-core affinity.
Process CPU excludes import and input hashing; scheduler TotalCPU is separate.
Root/search phase telemetry and complete primal trajectories are not claimed by
this first implementation. Subprocess logs are private, not public artifacts.

Ten runs have at most 3,000 optimize seconds: 50 minutes plus setup and audit.
A child process ceiling of 480 seconds and a 90-minute scheduler ceiling cover
setup/watchdogs; these differ from optimize caps. Sixteen allocated CPUs for
50 minutes reserve 13.33 CPU-hours, not the 5.17 cap-weighted optimize ceiling.
At the full 90-minute allocation ceiling they reserve 24 CPU-hours. Slurm may
account SMT siblings differently: use actual AllocCPUS/AllocTRES and ElapsedRaw,
not requested Threads, and count this bundled allocation once.

With MIPGap=0.1, `OPTIMAL` can mean the gap target was reached. Record that
separately from a reported zero gap at solver tolerances; a rounded display value
is not an exact certificate. No incumbent means missing gap, not zero. Timeouts
above 10% are retained. Ascending cap order, cache and shared-node load limit
scaling interpretation. Two parents and one seed do not establish significance.

## Extension gate

Review the 300-second results before a new, versioned contract. Retain the same
pair and seed and increase budgets only up to 3,600 seconds. Easy can use a
stricter target, such as 5%, 1% or solver-tolerance termination; medium can retain
10% initially or use a declared stricter target if useful. Neither class is
guaranteed to meet it. Declare targets before runs; stopping at 10% cannot supply
an observed later crossing of 5% or 1%.

Extension is disabled in the current executable configuration. Closed models
cannot resume search trees: extended executions are fresh attempts, retaining
both costs. Repeating all ten at 3,600 seconds adds at most ten optimize-hours.
Additional pairs require recorded resource/utility review, not adverse-result
replacement.

## Deployment gates

Before publication, verify the merged `develop` base and run Ruff/evidence tests.
Before submission, qualify runtime, commit, license, role-plan path/hash and
scheduler support. The launcher requires `PR66_SCREEN_AUTHORIZED=yes` and a clean
checkout. Output stays below `/raid/vrcelestino/data/cfl-mvp2-evidence/pr66`.
No NPAD, main, Pages, Zenodo or GNN-training operation is included.
