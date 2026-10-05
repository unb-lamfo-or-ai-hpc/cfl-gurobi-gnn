# Sprint B: prospective CPU comparison and telemetry contract

## Deliverable and authority

This increment follows the explicitly authorized PR68 merge into develop at
`7b35b3a0e88321d4131a588b386b3b3cf3af1c1f`. It supplies a reproducible disabled
proposal compiler and solver-independent telemetry primitives, with offline
regressions. It does **not** supply a licensed Gurobi callback adapter, executable
Slurm launcher, approved resource budget or new optimization result. A merge of
this code must not be interpreted as permission to submit the proposed matrix.
The CLI only reads the pinned public PR66 receipts and writes a fresh proposal
outside the source checkout. There is no solve/submit action or solver import.

Original PR66/PR67/PR68 collectors, thresholds, reports and stored source models
are unchanged. In particular medium16's displayed phases remain unqualified.
Main, Pages, manuscript, Zenodo and the frozen MVP1 stay unchanged. This increment
advances B without declaring A's full historical incumbent/cost reconciliation
complete. Missing historical telemetry cannot be recovered by new solves.

## Proposed first comparison: same pair, longer common cap

Retain the original fitting-pool draw, easy17 and medium1, seed42, original LP
hashes and role-plan/contract provenance from the hash-verified job3468 plan.
Do not inspect outcome tables to draw or replace parents. Test caps1/2/4/8/16;
fresh processes/models/environments, one active attempt at a time, no starts.
Retain Gurobi13.0.1 defaults after reset, in-memory MINIMIZE convention on stored
MAXIMIZE sources, ThreadLimit16, qualified16-physical-core affinity, shared node,
64GiB reservation and SoftMemLimit48 decimal GB. No GPU/exclusive allocation.

The **proposal**, not an approved extension, sets TimeLimit3600 for each attempt,
easy stopping MIPGap0.01 and medium MIPGap0.1. Controls are common across thread
arms *within each parent*. They differ from the historical300s screen, so do not
pool these runs as equal-budget repetitions. Medium will stop if10% is reached;
subsequent5%/1% times may be unobservable. These planned stops also prevent a
uniform fixed3600s terminal-quality comparison; label terminal gap as measured
at the actual stop, not as a common-budget result.

Primary time-to-target is the first sampled10% observation. Easy5%/1% are
secondary; stricter medium targets remain missing if its planned stop occurs.
The target and timing rules must be accepted before execution, not selected
because previous medium results were adverse. A negative comparison is valid.

Within each parent, sort thread caps by SHA256 of
`protocol_id|parent_id|42|cap`, ascending hexadecimal digest. Freeze this order
in the proposal; never redraw an inconvenient or accidentally ascending order.
Easy block precedes medium. This changes the ascending safety-screen schedule
but does not remove order/cache/shared-host effects or provide replication.
Retain comparable load observations and input-cache policy; do not flush caches
or presume isolation. Two parents/one seed support development observations,
not a generally optimal cap or population-level significance.

## Explicit ceilings: optimize, watchdog and allocation are different

| Quantity | Proposed ceiling or interpretation |
| --- | --- |
| Fresh attempts | 2 parents x5 caps x1 seed =10 |
| Optimize budget | 10 x3600s =10h, excluding setup/cleanup |
| Configured-cap optimize product | 2 x(1+2+4+8+16) x1h =62 cap-hours; not actual CPU or reservations |
| Scheduler proposal | Two blocks, five serial attempts each;330min per job; block jobs must not overlap |
| Child watchdog | 3780s per attempt (includes preparation/cleanup), with900s other overhead per block |
| Reservation ceiling at16 physical cores | 2 x5.5h x16 =176 physical core-hours |
| Conditional Slurm ceiling if AllocCPUS32 | 2 x5.5h x32 =352 logical CPU-hours |

These are ceilings, not expected solve times or measured costs. Scheduler policy
and actual allocation support remain unqualified. Preflight/setup must use the
declared overhead or a separately declared cost, not hidden extra jobs. The
short-screen peak3.314GiB does not qualify hour-long safety. A higher-budget
resource review is required before execution. A memory/watchdog/solver failure
pauses the remaining matrix; retain the partial attempt and charge its costs.
No automatic lower cap, extra RAM, retry, substitution or queue resubmission.
Failed3466 and completed3468 remain preserved separately.

Seeds43/44 are disabled follow-ups, not part of this budget. Review safety,
coverage and instrumentation before independently budgeting repetition; do not
require favourable effects. New parents need a new selection receipt.

## Telemetry implemented here, versus licensed adapter still needed

`Telemetry` validates caller-supplied numeric observations. It keeps separate
external monotonic wall/process-CPU clocks for non-nested read/setup,
optimization and cleanup scopes. Process CPU is current-process scope, not the
Slurm aggregate. The future worker must bind terminal status, load, actual
affinity, peak RSS and source/profile identities and publish only allowlisted
fields. This library alone neither observes the HPC nor authenticates a solve.

The proposed worker callback rate is at most one regular observation per solver
second, plus new incumbent and terminal events. No callback is installed here.
Normalize unavailable/sentinel values to null; retain no-incumbent as missing
gap, not zero. Callback MIP bounds must follow their documented semantics; raw
callback bounds and final rounded model attributes are not interchangeable.
Reject backwards solver-runtime observations and nonfinite/bool numeric data.
Store at most10000 samples, count dropped samples and continue tracking first
sampled target observations even after the storage cap. This bounds storage,
not callback execution overhead; licensed runtime qualification remains needed.

The first sampled crossing is not a continuously observed exact crossing.
Previous-sample timestamps describe observation spacing, not a guaranteed
first-crossing interval. Terminal runtime may exceed TimeLimit; preserve the
overshoot and do not clamp the observation. A target first observed afterwards
is explicitly outside budget. Timeouts are right-censored, memory/worker stops
are separate outcomes, and targets below a planned gap stop are not imputed.
The public telemetry output does not qualify root/tree phase costs, a continuous
primal integral, incumbent feasibility or scientific eligibility.

`paired_speedup` computes T1/Tt and efficiency(T1/Tt)/t only for positive,
within-budget sampled crossings with identical original-LP/profile hashes,
seed, target and budget and explicit1-versus-t caps. A hash-shaped string alone
does not qualify provenance: the future result reader must verify source bytes
and actual common controls. Censored/late targets produce null speedups.

`seal_closed_log` reads at most64MiB of a regular non-symlink file, detects
metadata/length changes and returns only byte hash/length. The future worker
must close the solver writer and persist this binding immediately in its own
attempt receipt. This is not an independent signature or retroactive fix to
job3468. Private text/logs, paths, LPs and license contents must not enter public
exports. New private/output files stay below physical `/raid/vrcelestino/data`;
use only the canonical license already documented in the PR66 runbook.

## Next gates and completion boundary

1. Exact-head code/CI review and author approval before merge into develop.
2. Implement and offline-test the licensed worker adapter, fresh-output/error
   receipts, export validator and sequential scheduler launcher; qualify the
   installed Gurobi/scheduler without optimization first.
3. Explicitly approve the exact versioned proposal and resource budget before
   any licensed qualification solve or comparison submission. Keep CLI status
   one-shot; do not occupy the operator terminal with accounting wait loops.
4. Execute only the approved block, independently review receipts/accounting,
   then separately approve replication or further parents if needed.
5. Synthesize paired quality/time/memory/cost curves and a justified resource
   profile with coverage, censoring and shared-host limitations. No monotonic
   speedup, selected universal cap or favourable result is required for closure.

No HPC CLI is required for the current code/proposal review. The future adapter
and runbook must provide complete nonblocking submit/status/collect/receive
steps before an operator action is requested. This proposal does not execute
the older30/90-run matrices, Barrier sensitivity, portfolios, hard campaign,
GPU/DDP training or warm-start evaluation.

Primary references: [Gurobi callback codes](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html),
[MIPGap and Runtime](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/model.html),
and [TimeLimit](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html#timelimit).
These specify observation semantics, not the cause of the historical medium16
footer/API discrepancy. Validate the installed13.0.1 behavior before execution.
