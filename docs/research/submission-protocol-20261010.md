# Submission protocol and authorization gates — 10 October 2026

## Status and independence

The authors approved this roadmap with mandatory 1-GPU serial versus 4-GPU
DDP training. Only documentary closure of PR83 and consolidation of PR84 are
authorized now, without merge. PR85 needs scope approval before implementation;
PR86/87 need separately approved protocols and exact HPC budgets before execution.
PR88 is planned to start alongside Sprint D; this document does not create it.
Historical receipts, checkpoints and output bytes remain unchanged.

This revision supersedes older scheduling proposals (including the proposed
two-GPU comparison), not historical experiments. No new experiment is needed
to close M13/M26's documented limitation. PR83 and PR84 do not depend on one
another's code changes and remain independently reviewable.

## PR85 — final scope for approval

**What:** an auditable account of what the existing evidence can support,
before committing to comparative HPC experiments.

**How:** read existing manifests, split CSV, model/normalizer/threshold hashes,
training reports, frozen inference and solver returns. Produce a per-parent
provenance/eligibility matrix and reproducible, offline audit checks. Do not
deserialize untrusted checkpoints casually, retrain, optimize or generate new
labels. If additional private bytes must be checked, present a narrowly scoped
read-only CLI for separate execution approval.

Required audit:

- Reconcile population 90, admitted 54 (30 easy + 24 medium), and splits
  34/10/10 (18+16 / 6+4 / 6+4 easy+medium). Verify parent disjointness and
  derived-artifact ancestry, duplicate inputs and the label-quality selection.
  Retain the canonical split; display aliases F/M do not rename inputs.
- Reconstruct exposure history. The test set is F0,F3,F6,F14,F27,F29 and
  M0,M4,M7,M12; all ten are historically exposed. M13/M26 remain excluded
  canonical training parents, not new test instances.
- Bind the easy-only and mixed frozen checkpoints to training parents,
  architecture, preprocessing, training-only prenormalization/positive weights,
  validation-based checkpoint/threshold selection and all selected artifacts.
  Mark unknown provenance as unknown, not verified.
- Reconcile the 20 frozen forwards and recompute available confusion-matrix
  metrics per parent/cohort. Distinguish micro versus parent-macro averaging.
  Independently recompute PR-AUC/calibration only if the necessary probabilities
  and labels are available with approved provenance; summary parity is not
  independent rescoring. Report class imbalance and reference-label quality.
- Verify the mathematical formulation: identify the actual CFL variant,
  objective terms/constants/units, variable domains, demand/capacity/linking
  constraints and assignment semantics. Trace source `MAXIMIZE` to executed
  `MINIMIZE`; a sense override without a justified coefficient/constant mapping
  is not equivalence. Check the correspondence of original, parsed model,
  graph features, labels, checkpoint outputs and warm-start variable order.
  Re-evaluate existing incumbents/constraint residuals where available, without
  invoking optimization. If a sign/constraint mismatch exists, quarantine
  affected claims before proposing the smallest separate corrective action.

**Acceptance:** every admitted parent has a documented partition and exposure
role; both checkpoint chains are either verified or explicitly limited;
predictive metrics have declared denominators/provenance; intended equations
and executed objective sense are reconciled, or the affected new comparison
and article claims are blocked. A documented blocker is an honest audit result,
not permission to run more experiments. Publish checks, tables and explanations
in `docs/`, including what/how/why and limitations. Estimated effort: 2-3 days.

**Not included:** training, new solver runs, relabeling, dataset expansion,
new architecture/hyperparameter search, broad refactoring or a fresh test split
that would be misrepresented as historically untouched.

## PR86 — proposed computational comparison (not execution-approved)

### Design and methods

After PR85's formulation/provenance gates, use the same ten historically exposed
parents for a retrospective controlled comparison. Three arms:

- M0: Gurobi without an external MIP start.
- M1: partial binary start ranked from root-LP values, with the existing matched
  support and positive-count budget. This is a GNN-dependent matched control,
  not a cost-free independent LP heuristic.
- M2: partial binary start from the frozen audited GNN; choose the checkpoint
  through provenance/validation rules, not the solver test outcomes.

Keep the historical support rule unless the audit invalidates it:
`K=min(n_binary,20000,max(1,floor(0.10*n_binary)))`; abstain when required by
the existing policy. Unspecified binary/continuous variables stay undefined,
not fixed. Record positive/zero counts and solver start acceptance/repair.
Document the root capture policy separately from the main solve; the existing
GNN uses root-LP features, and a MIPNODE root capture is not interchangeable
with a generic call to `model.relax()` without an explicit protocol change.

Preliminary matrix: ten parents x three methods x five thread caps
`{1,2,4,8,16}` at seed 42 = 150 solves. At one thread only, repeat all ten
parents and three methods at seeds 43 and 44 = 60 additional solves.
Total **210 solves**, subject to approval; three seeds do not provide
repeatability evidence at every thread cap. Extra seeds at other caps are
outside this budget. Counterbalance method order in the three one-thread seed
blocks; freeze deterministic balanced order for remaining cells. Record actual
order, node sharing and resource contention rather than claiming their absence.

Propose `TimeLimit=3600` s and `MIPGap=1e-4` (0.01%) for all arms, with identical
remaining parameters and a validated minimization convention. The budget and
parameter manifest must be approved together. Reuse qualified historical rows
as historical context only; do not silently mix different gap/limit settings
into this controlled matrix or claim old elapsed time was newly measured.

### Costs, statistics and outputs

Record preparation/root capture, feature loading, GNN inference, start assembly,
solver and export separately. Show both cold end-to-end and cache-amortized
costs, explicitly charging GNN-dependent matching to M1. Measure newly required
preparation prospectively; do not invent historical root costs. Propose at most
one fixed-seed root preparation per parent, shared identically across methods
and solver seeds. List these calls separately from the 210 main solves.

Report primal/bound/gap, time to first incumbent, final runtime/status, start
behavior, CPU work, resident memory and sampled job-scoped memory separately.
Early certified completion is retained; time-limited runs are censored for
time-to-target analysis, not treated as exact completion times. Use common
quality targets and quality at the budget horizon where observable; never
interpolate unrecorded trajectories. Report parent-paired ratios and effects,
easy/medium strata, and parent-cluster uncertainty. Seeds are nested repeats,
not extra independent instances. With only four medium parents, intervals
will be weak; avoid treating 210 runs as sample size 210 for generalization.

### Preliminary HPC envelope and stop policy

Single DGX node, CPU only; at most 16 physical cores, one logical processor
per selected core, no GPU/exclusive-node request. Retain `tfm_env` and report
actual installed versions. Propose 64 GiB RAM per job, Gurobi soft memory limit
48 decimal GB, sampled job-scoped stop at 56 GiB, kernel RAM cap no greater
than 64 GiB. Validate actual cgroup scope; failures stop execution, not guards.
No requeue, automatic retry, extension, concurrent solver children or overwrite.

Worst-case main solver runtime: 210 h (8.75 days sequential), plus preparation,
I/O and queues. Ten root captures capped at 600 s add at most 1 h 40 min solver
time. The thread-cap weighted upper bound is 990 core-hours for main solver
capacity, **not measured CPU consumption**. Reserving 16 physical cores throughout
all 210 maximum-length solves would instead cost 3360 reserved core-hours, plus
overhead. Scheduler logical `AllocCPUS` is not the physical-core count. Propose
per-parent/cap groups of at most three 3600-s solves with a 4-hour job wall cap;
repeat-seed groups follow the same bound. Exact job count, reservation policy,
child deadlines and aggregate overhead ceiling must be frozen before approval.

**Acceptance:** all planned cells are accounted for as qualified/failed/censored;
paired comparisons meet identical contracts; preparation cost and dependencies
are visible; tables/CPU figures regenerate from sanitized receipts; no speedup
claim depends on omitted costs. Memory stop or incomplete provenance pauses
remaining work. Failure is reportable and does not trigger replacement runs.

**Risks:** missing preparation, formulation mismatch, checkpoint exposure,
shared-node noise, 8.75-day worst case and limited statistical power. Reduce
the approved matrix prospectively if needed; never select omissions by observed
GNN benefit. Estimated implementation/analysis: 3-5 person-days plus HPC.

## PR87 — mandatory serial/4-GPU training protocol (not execution-approved)

### Matched learning work

Reuse the parent-aware paths in `src/cfl_gnn/training/gasse_reconnected.py`,
which already has serial and `run_distributed_training` implementations and
deterministic parent-balanced schedules. Do not invoke the historical
graph-random-split CLI in `training/distributed.py`. Inspection confirms the
current per-rank graph batch is one: unchanged, its four-rank global batch
would be four while historical serial updates used one. Therefore direct
reexecution does **not** satisfy the matched-batch requirement.

Propose the audited mixed cohort (34 train, 10 validation, 10 exposed test),
the same Gasse v2 architecture (two layers, hidden dimension 32), Adam,
learning rate 0.001, clipping norm 1, and fixed 100 full epochs. No search.
Use global batch four in **both** modes: serial accumulation of four graphs
and one graph per each of four DDP ranks. Apply one optimizer step and one
gradient clip per global batch in both; make per-graph loss weighting and
DDP averaging equivalent despite graph-size differences.

Four parent draws per epoch give 136 draws and 34 updates per epoch in both
configurations: 3400 updates and 13 600 draws over 100 epochs. This matched
batch is a documented departure from the historical serial batch-one model,
not a claim of reproducing that checkpoint. Both modes begin from the same
untrained initialized parameter/buffer state per seed, with its hash recorded;
no asymmetric warm start from a trained model. Preserve graph hashes,
train-only normalization/prenorm, loss weights, sampling order and precision
policy. Validate global update schedules offline before any training.

Perform full validation consistently and choose the checkpoint/threshold using
validation only; score both selected models on the same exposed test parents.
Record terminal-epoch metrics too. Freeze epoch count, no differing early stops.
DDP evaluation must handle unequal validation shard lengths safely and neither
duplicate nor omit observations. Disclose nondeterministic reductions and
numerical differences; identical seeds do not promise bitwise identical GPUs.

### Budget proposal and measurement

Minimum useful experiment: one paired full run at initialization seed 42
(two training jobs), not a short throughput benchmark. Preferred, if affordable:
three paired seeds 42/43/44 (six jobs), with no additional hardware configuration.
One pair supports a measured case study, not training-seed uncertainty.
Select the number of pairs **before** execution and results inspection.

Provisional requested resources: 1 V100/4 physical CPU cores versus 4 V100s/16
physical CPU cores on the same DGX, same common 128 GiB host-memory ceiling
and at most 32 GiB device RAM per GPU. Document this CPU-resource scaling as
part of the training-system comparison; do not call it isolated GPU causality.
Fix loader policy and sampled monitoring overhead. Host/device memory adequacy
for full training remains to be established from existing qualified records;
inference memory is not evidence of training memory. A lower cap requires an
approved adjustment, not an unrecorded reduction of learning work.

Let `B` be the approved per-job wall cap in hours for the fixed 100-epoch run.
For one pair the hard reservation envelope is at most `2B` sequential wall
hours, `5B` GPU-hours and `20B` physical-core-hours; three pairs at most `6B`,
`15B` and `60B`, respectively. Example **ceiling proposal**, not a feasibility
claim: `B=12` h gives 24 h / 60 GPU-h / 240 core-h for one pair, or 72 h /
180 GPU-h / 720 core-h for three. Existing historical logs inspected here do
not establish whole-run duration for this exact matched protocol. Before
authorization, bind B to available full-training timing/memory evidence or
explicitly accept this bounded feasibility risk. No extra pilot job is silently
added. If the cap interrupts a run, preserve it as incomplete: no automatic
retry, epoch reduction, extension or short-benchmark substitution.

Measure synchronized GPU-aware training-loop time and full job wall time
including loading, normalization, validation, checkpointing and teardown.
Report `S=T_serial/T_DDP4`, `efficiency=S/4`, throughput in the same global
draws/updates, GPU/CPU utilization, communication where observable, sampled
memory peaks, device allocator peaks and assigned GPU-hours. No invented
communication decomposition. Also report parent-macro and micro F1, precision,
recall, PR-AUC and available calibration metrics, plus validation loss.

**Acceptance:** same input/split/architecture/initialization/global batches and
update counts; all parents evaluated once per evaluation pass; complete full
training and final predictive assessment in both modes; traceable timings,
resource measurements and numerical differences. Predeclare a practical
quality-loss tolerance (proposal: 0.02 absolute parent-macro F1 and PR-AUC)
before execution. Exceeding it is a negative result to analyze, not permission
to tune or discard the pair. With one pair no non-inferiority claim; with three
report paired seed differences and their limited precision. Speedup below one
or worsened quality is scientifically valid.

**Risks:** global-batch/gradient mismatch, prenorm differences, evaluation
collectives with unequal shards, GPU memory pressure, CPU/I/O bottlenecks,
non-bitwise reductions and unknown full-training duration. Restrict code work
to necessary matching/instrumentation of the existing pipeline. Estimated
hands-on effort 2-3 days, excluding unexpected substantive compatibility work.

## PR88 and publication gate

Begin sample/formulation/methods and the claim/evidence index alongside Sprint D.
Keep observations, hypotheses, limitations and required evidence separate.
Use the [article asset plan](../article_plan.md), never infer results from jobs
that have not run. Target submission by December 2026. Main synchronization,
merges and resource execution remain separately authorized decisions.
