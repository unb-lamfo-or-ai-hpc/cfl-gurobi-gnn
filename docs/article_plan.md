# Article plan

## Scientific writing and sensitivity clarification

The [methods explanation](../manuscript/supplement/gnn-methods-audit.md)
has been rewritten around the scientific argument, including the rationale
and evidence limits for fixed hyperparameters. The
[sensitivity assessment](../manuscript/supplement/sensitivity-review-plan.md)
distinguishes solver seeds, root methods, neural training and component
ablations. These remain prospective; the ongoing CPU campaign is unchanged.
The accelerated plan continues S1, S2, S4 and S5 without new execution authority.


## Documentary continuation — 28 October 2026

The [accelerated S1–S6 plan](research/mvp2-20261028-accelerated-plan.md)
targets a complete coauthor-review version by15December2026 and preserves
the14January2027 submission deadline. S1/S2/S4/S5 advance now in PR92;
the CPU-dependent S3 closeout and mandatory final A–D audit remain gated.
The [GNN audit](../manuscript/supplement/gnn-methods-audit.md) and
[conditional Appendix B register](../manuscript/supplement/human-ai-traceability.md)
record actual methods, critical references and evidence gaps. No experiment,
checkpoint, campaign parameter or raw result is changed.



## Current completion plan — 26 October 2026, R3

The [R3 contract and S1–S6 plan](research/mvp2-r3-contract.md) supersedes older
calendar and transfer requirements. Deadline: **14 January 2027** for MVP2
completion and author-approved article submission. Methods and writing proceed
in parallel with the still-running PR89 campaign; no pending results are filled.

Next coherent PR: contract, B/R/G formalization, dataset/model provenance and
metrics/reproducibility, reusing PR80/85/86/87/88. Close the existing PR89 after
its authorized return/review. Then integrate CPU/GPU synthesis, R2-D8, manuscript
and supplements in one editorial delivery, followed by an explicitly approved
develop-to-main scientific release. Do not reserve PR numbers or create
separate PRs per helper or result wave.

| Sprint | Target window | Product / acceptance |
| --- | --- | --- |
| S1 | 26–31 October | Transfer/contract/plan; R2-D1/D7, one operational owner |
| S2 | 1–15 November, anticipatable | R2-D2/D3/D4, source-linked methods/provenance/reproducibility |
| S3 | 16–30 November, anticipatable | PR89 and R2-D5/D6, all 60 cells explained with metric eligibility |
| S4 | 1–15 December | CPU/GPU synthesis, SO/C evidence matrix, R2-D8 |
| S5 | 16–31 December, writing now | Complete manuscript/supplements for coauthor review |
| S6 | 1–14 January 2027 | Final corrections, approved release and submission |

Reuse the PR90 Pages review version and PR88 figures. PR90 does not include
future PR89 results or authorize later publication. Keep the GPU speed/quality
tradeoff, small historically exposed sample, numerical limits and bounded
costs explicit. Claims need traceable evidence and verified literature.
IA assistance transparency is separate from the optional Human–AI study.

Internal targets are full text by 31 December, approval by 7 January and
submission by 10 January, with 11–14 January contingency. Queue/failure risks
and coauthor turnaround remain uncertain; no old 78h23m ETA is reused.
No new seeds, hard instances, checkpoint search or corrective training is
required. Post-MVP P1–P5 remain planned, not authorized.
See the [evidence index](research/mvp2-r3-evidence-index.json) for pending products.

## Historical editorial plans — original dated text preserved

Dated proposals below are retained, including superseded December deadlines,
CPU approval holds and final-before-transfer conditions. The R3 plan governs
current scheduling and ownership; it does not rewrite their original evidence.


## Current editorial contract — PR88, D1–D6, updated 20 October

Use [D3 figures](research/methodology-20261019/D3-figures.md),
[D4 directed Related Work](research/methodology-20261019/D4-related-work.md),
[D5 claim/evidence matrix](research/methodology-20261019/D5-contributions.md)
and [D6 decision memo](research/methodology-20261019/D6-decision-memo.md).
Keep the three Related Work subheads; no first-GNN/MIP or causal selector claim.
Principal analysis150seed42; retain60other-seed rows and repeatability figure as
historical only. Separate historic six-medium evidence from current ten exposed
parents. CPU12h has no results. GPU1/DDP4 is complete and merged at32be9821;
incorporate measured speed/quality/cost tradeoffs and comparative BCE histories.
Do not fill missing CPU figures/metrics. Describe negative outcomes rigorously.

Schedule remains D26Oct–13Nov,E9–20Nov,F16Nov–11Dec; milestones15Nov/15Dec/31Dec.
The proposedCPU780hserial reservation plus queues is a critical calendar risk,
not a promised completion date. Write in parallel, escalate prospective scope
choices before execution; main synchronization after article review only.
PR87 completed GPU delivery: [review](research/pr87-completed-pair-review.md)
and [seven tables/four vector figures](evidence/pr87/jobs3673-3674/) supply the
mandatory full-training serial1GPU/DDP4 comparison. Report seed42 matched work,
2.167x loop/1.831x job speedup, increased assigned GPU-h and selected macro F1
loss0.032468 beyond the frozen margin. Do not claim quality preservation,
statistical noninferiority, independent generalization or solver benefit from
these new checkpoints. The raw scientific flag remains unchanged. PR88 should
integrate this tradeoff and exact runtime alongside its D1–D6 methodology.
Additional CPU work remains separately budget-gated; no new GPU campaign is
required by this closeout. Final develop/main synchronization remains last.

20October:3671FAILED/3672CANCELLED are operational adverse evidence, not completed
serial/DDP results. Preserve their [failed receipt and diagnosis](research/pr87-job3671-failure.md).
No GPU speedup/quality figure can be filled from this pair. Slurm-copy and receipt
fixes leave the scientific protocol intact; no retry or CPU campaign approval.

19October revision: PR88 owns D1–D6, targeted Related Work, seed42 main views
and claim/evidence mapping. This PR87 only supplies matched-work GPU evidence
AFTER specific execution authorization. Do not publish GPU speedup/quality as
observed from synthetic CI. Main CPU analysis150seed42;60other-seed rows and
repeatability figures historical. GPU allocation hours and utilization/time
scopes differ; one pair gives no training-seed uncertainty. See the
[separate package](research/pr87-gpu-authorization-package.md). Article work
continues in parallel; develop/main synchronization after manuscript review.

19October PR87 scope frozen by author: one seed42 pair,1GPU serial versus4GPU
DDP. [Final preparation protocol](research/pr87-matched-gpu-protocol.md) fixes
equal batch/work, initialization, quality and bounded resources. Report a paired
case, not training-seed variance. Required outputs:1/4GPU synchronized loop and
whole-job timing/speedup/efficiency, resource utilization/memory, selected/terminal
predictive quality and cost scopes. No result exists yet for that pair.
PR86 CPU delivery is merged; its tables/figures are final scoped evidence.
PR88 manuscript proceeds alongside GPU; release/main only after article review.

19 October [CPU closeout](research/pr86-final-analysis.md): the planned210/70
are collected and analytically consolidated. Use the [final source tables and
six figures](evidence/pr86/final-210/) instead of partial-wave plots for final
CPU claims. Preserve earlier figures as dated evidence. Main takeaways:
heterogeneous GNN effects; compareLP too; preparation accounting can reverse a
solver-only benefit; pointwise exploratory uncertainty and numerical sensitivity
remain visible. No135certified optima, no time-to-target speedup from timeouts,
no population claim. PR87 matched1GPU/DDP4 remains mandatory and budget-gated;
PR88 writing/review can proceed in parallel. Release/main after article revision.

18 October [installed M12 diagnostic table](research/pr86-m12-audit-final-nine.md)
distinguishes four GNN vectors passing the rounded-copy check from two controls
failing original-unit rows in that copy. It is not an exact certificate and
does not retroactively qualify M4. Keep M4/M12 sensitive strata visible. The
author approved only the nine original remaining solves with those limitations;
201/210 remains the observed count,not a completed matrix. Final paired CPU,
quality,censoring,memory,seed and cost assets follow210-row reconciliation,
then the CPU-delivery balance and detailed Project01/chat01.02 coauthor prompt.
PR87 matched1/4GPU remains mandatory; main synchronization is still last.

18 October: [CSV201,complete M7 and partial M12 CPU figures](research/pr86-wave61-numeric-review.md).
M7 has heterogeneous final gaps; all21 observations censored. M12's four reported
M2 target terminations need numerical delimitation before performance claims.
Keep168 previous/non-M4/M12 scoped cells,21M4 sensitive and12M12 pending separate.
Nine original solves remain; final synthesis and Sprint balance are not complete.
After reconciliation prepare the detailed Project01/chat01.02 coauthor prompt,
with achieved MVP2 outputs,limitations,remaining mandatory1/4GPU comparison,
figure/table inventory and evidence-linked claims. No independent generalization
or assumed GNN superiority. Main synchronization remains after article revision.

17 October: [CSV183 and M4/M7 gap/memory figures](research/pr86-wave55-review-wave61.md)
complete M4 and show partial M7.128 reported target-reaching cells include
the disputed M4 report;55 are censored. Separate21 M4-sensitive observations
from162 non-M4 scoped-reviewed cells. Heterogeneous terminal gaps, not timeout
runtime ratios, describe M7 so far. M7/8,16 and all M12 remain unobserved;
27 solves/nine groups remain. The next six groups would leave only nine solves;
final uncertainty/cost synthesis follows full coverage. Mandatory1/4-GPU training,
parallel manuscript and final develop/main synchronization after article review
are unchanged. No augmentation or new hyperparameter search.

The [installed M4 numerical review](research/pr86-m4-numeric-return-wave55.md)
adds a reproducible four-vector diagnostic table and165-row collected ledger
with explicit numerical-scope labels. All four rounded vectors fail original
row tolerance; normalized residuals and extended precision do not certify an
optimum. The author approved finishing the original matrix without reruns or
parameter changes. Preserve M4 in reporting, but do not silently pool its
reported zero-gap runtime into qualified speedup/time-to-target aggregates.
147 previous scoped reviews and18 numerically sensitive observations are
different denominators.45 original solves remain; C–F sprint order is unchanged.

The [M4 numeric-review inventory](research/pr86-wave49-numeric-review.md)
adds18 preserved observations, not18 newly qualified performance claims.
165 cells are collected;147 have the previous scoped review. A reported
zero-gap M2/8 result conflicts with three tolerance-feasible incumbents under
the same model identity. Until the stored-solution audit resolves or delimits
this issue, do not present that status as unambiguous optimality or GNN speedup.
Keep negative/inconsistent results, tolerances and numerical limitations visible.
The45 unexecuted cells await the numerical gate; remaining sprint order is unchanged.

Current [147-row ledger and complete M0 CPU/quality/memory figures](research/pr86-wave43-review-wave49.md)
cover all six easy parents and the first medium parent. Of147 solves,127
reached the target and20 are censored. M2/16 reached gap zero on M0, but
GNN effects at lower caps/seeds are heterogeneous. Preserve that contrast,
not a blanket speedup claim. Sampled job memory and Slurm/internal-solver
memory retain different scopes. M4 follows in the original manifest order.
Final paired uncertainty/cost synthesis awaits full coverage; snapshots persist.

Current [129-row ledger and F29/medium figures](research/pr86-wave37-review-wave43.md)
complete all six exposed easy parents (126 target-reaching solves) and add
one medium group (three time-limited solves). Keep strata and censoring
explicit; do not use near-equal timeout runtimes as time-to-target speedup.
For the medium parent M0, method M2 has the best incumbent but method M0
the smallest gap: show both objective and bound. The next wave completes
that parent's remaining six groups without changing the protocol or budget.
Final uncertainty/cost synthesis follows full coverage; earlier assets remain snapshots.

Current [111-row ledger, complete F27 and partial F29 CPU figures](research/pr86-wave31-review-wave37.md)
cover the six exposed easy parents, with F29 still partial. Preserve F27's
slower M2 result at16 threads and F29's mixed seed results, alongside gaps.
Medium-parent evidence has not yet been observed in this controlled matrix.
The next wave starts that stratum after finishing F29; future article tables
must distinguish parent M0 from method M0. Earlier assets remain snapshots.

Current [93-row cumulative table, completeF14 and partialF27 CPU figures](research/pr86-wave25-review-wave31.md)
cover five exposed parents. F14's seven groups include three lower and four
higher M2 times than M0; F27 has three one-thread seeds so far. Show the
nonzero within-target gaps with timings. Retain all prior assets, scope cost
scenarios explicitly and avoid overall performance claims before full coverage.
The mandatory1/4-GPU comparison and final article/release sequence continue.

Latest [75-row table, completeF6 and partialF14 CPU figures](research/pr86-wave19-review-wave25.md)
preserve the mixed timing effects and nonzero within-target gaps. F14/4,8,16
are pending, not interpolated. Scope, sample limitations, mandatory1/4-GPU
comparison and manuscript/release sequence are unchanged. Old figures remain
dated evidence, not overwritten. Synchronize main only after article review.

Latest assets: [57-cell cumulative ledger, completeF3 and partialF6 figures](research/pr86-wave13-review-wave19.md).
Retain method/seed heterogeneity and F6/1/seed42 M2's small nonzero gap beside
runtime. F6/8,16 are pending, not zero/interpolated. Scope and release order
unchanged; no population speedup claim or whole-job cold-cost qualification.

Latest PR86 asset: [39-cell cumulative ledger and partial F3 CPU figure](research/pr86-f3-review-next-wave.md).
F3/16 is still pending; no interpolated/zero-filled result. Keep F0 and F3
separate, preserve seed nesting and report scoped costs, not whole-job cold time.
The release sequence below remains unchanged: synchronize main only after
article revision. PR87 matched1/4-GPU comparison remains mandatory.

## Author revision — 13 October

Keep development on develop and research branches. **Do not synchronize develop
and main in either direction before the article revision is complete.** Final
branch reconciliation, release PR and merge are the last delivery, with explicit
approval; not a prerequisite for PR86/87 experiments or manuscript writing.

Sprint C audit is closed through PR85. Sprint D: complete the210-cell PR86
comparison in reviewed bounded waves (21 F0 cells now reconciled), implement
mandatory matched1-GPU/4-GPU DDP PR87 with its own exact budget, and write PR88
methods/sample/claim index in parallel. Sprint E: parent-paired CPU/quality/cost
and GPU analyses, seed uncertainty and reproducible publication tables/figures.
Sprint F: integrate results, revise with coauthors, check numerical consistency
and journal requirements; only THEN reconcile/release develop/main. December
2026 submission remains the priority. No augmentation or new architecture.

The [F0 CPU table and SVG](research/pr86-f0-review-f3-wave.md) are the first
prospective main-matrix assets: one-parent descriptions, not final article-wide
estimates. Keep solver time distinct from modeled scoped preparation costs.

Latest PR86 evidence: [job3522 and serial wave](research/pr86-job3522-six-job-wave.md)
provides the first three prospective solver observations, not a ten-parent
conclusion. The six-job continuation completes F0's frozen CPU caps and one-thread
repeats before remaining parents; final comparison figures must retain parent
denominators and the scope of preparation-cost estimates.

Approved planning revision: 2026-10-10. Target: submission by December 2026,
preferably by 11 December with the remainder of December as contingency.
Implementation/resource authorizations remain separate.

12 October evidence update: [job3520](research/pr86-job3520-and-guidance.md)
adds a regenerable ten-parent root-preparation cost table. Capture/export/
supervisor/batch scopes are nested as documented, not additive totals.
This is a methods/cost asset, not yet a three-arm performance result.

Job3521 now adds the [ten-parent preparation table and static SVG](research/pr86-job3521-review-and-main-budget.md),
binding roots, graph construction, inference and both start assemblies.
The ledger separates shared/residual costs and explicitly modeled allocations;
it does not establish standalone cold cost or speedup. CPU scaling/result
figures still require the main matrix, whose exact ceiling the author approved
on 12 October. First-group execution/review precedes remaining dispatch; no
main results are inferred from preparation and no additional preparation is needed.

11 October update: PR83/84 merged; PR85 scope and implementation approved,
with mandatory correction from source MAXIMIZE to effective MINIMIZE for
cost-minimizing CFL. PR86/87 protocols accepted preliminarily, with no exact
HPC execution budget approved. PR85's documentary audit is now complete with
explicit limitations; see its [closure](research/pr85-closure.md). This does
not clear the remaining execution gates. PR85 was subsequently merged by the
author at `bb3f28f8`; PR86 implementation continues without HPC authorization.

## Proposed narrative

1. Introduce CFL, the computational bottleneck, and the gap between generic
   MILP solving and learned graph guidance.
2. Define the parent-level dataset, graph construction, labels, split, and
   leakage controls before presenting results.
3. Describe the GNN architecture and training protocol, including the two
   hidden layers of 32 units only as a documented hyperparameter, not as an
   unexplained result.
4. Define the three solver arms and distinguish root-relaxation preparation
   from GNN inference and from Gurobi optimization.
5. Report quality, time, preparation cost, CPU thread scaling, GPU allocation,
   memory, and exclusions with tables and figures generated from public
   manifests.
6. Discuss limitations, reproducibility, HPC implementation, and the exact
   claims supported by qualified pairs.

## Required outputs

- cohort/partition table with F/M identifiers and train/validation/test counts;
- descriptive sample table: parents, artifacts, bytes, labels, instances,
  attempts, qualified results, and exclusions;
- three-arm paired solver table by parent and thread cap;
- CPU scaling figure for 1/2/4/8/16 threads;
- mandatory 1-GPU serial versus 4-GPU DDP training-time, speedup, efficiency,
  utilization and final-predictive-quality figures, once qualified;
- preparation-versus-solver-cost figure;
- gap, incumbent quality, runtime, and memory summaries;
- a manifest linking every public row and figure to source commit and receipt.

## Prioritized roadmap

| Sprint / target window | Deliverable | Dependency and acceptance |
| --- | --- | --- |
| C / 10-23 October | Close PR83 limitation; relocate/consolidate PR84; PR85 scientific audit | PR85 scope approved before code; partitions/provenance and mathematical sense established or specific claims blocked |
| D / 26 October-13 November | PR86 three-method CPU comparison; PR87 mandatory 1/4-GPU full training; start PR88 manuscript in parallel | Separate budgets approved; PR85 gates satisfied; matched execution and complete accounting, no presumed speedup |
| E / 9-20 November | Repeatability, uncertainty, end-to-end costs; final tables and figures in PR86/87/88 | Parent-paired analysis, missing/censored data visible, row-to-receipt traceability |
| F / 16 November-11 December | PR88 integrated manuscript, coauthor review, journal formatting and release review | Every scientific claim linked to qualified evidence; numerical and bibliographic consistency; explicit release/merge approvals |

Overlapping windows allow analysis and writing alongside execution; they are
targets, not claims that budgets or results already exist. PR identifiers 85-88
are planned deliverables, not PRs created by this document. Approximate hands-on
effort: PR83 closure 0.5-1 day; PR84 1-2 days; PR85 2-3 days; PR86 3-5 days;
PR87 2-3 days excluding substantive unexpected compatibility work; PR88 5-8 days,
plus coauthor turnaround and HPC queues. The [detailed protocol](research/submission-protocol-20261010.md)
specifies the resource estimates and stopping conditions.

No augmentation, new architecture, broad refactor or hyperparameter search is
required for this minimum article. Four-GPU training is mandatory; eight-GPU
scaling and enlarged cohorts are deferred. Negative/heterogeneous outcomes
remain valid. Poor comparability is not repaired by adding more runs.

## Manuscript evidence inventory

PR88 should begin its introduction, formulation, sample and methods alongside
Sprint D, without filling missing results with anticipated benefits. Required
publication assets are:

1. Population/admission/split table (90 -> 54, 34/10/10) and per-parent descriptive
   statistics: variables by domain, constraints, nonzeros, density, coefficient
   scales, root gap and label quality where qualified; unavailable entries explicit.
2. Checkpoint/normalization/threshold provenance table and predictive metrics
   by parent and difficulty, including the limitation of historically exposed tests.
3. M0/M1/M2 result table; CPU curves for 1/2/4/8/16 threads; quality, certified
   termination or censoring, memory and parent-paired time ratios/uncertainty.
4. Serial/4-GPU DDP table and figures: matched work, full training wall time,
   speedup, efficiency, GPU-hours, resource utilization and final F1/PR-AUC.
5. Preparation/inference/solver/export cost decomposition, cold and cache-amortized
   scenarios, repetition summaries, exclusions/failures and limitations.
6. Machine-readable source tables, vector figures and a claim/evidence index
   binding each row/figure to protocol, commit, source hashes and review status.

## Submission discipline

The manuscript must not call an observation a result when its receipt is
unqualified. Failed or unavailable historical runs are described as limitations.
The article should state the installed environment (including PyTorch and
CUDA versions) exactly as used; package upgrades are not required for the MVP.
The final release should be synchronized to protected `main` only after the
authors review the complete evidence and approve that release PR.

## First PR86 implementation checkpoint — 11 October

The [controlled-comparison proposal](research/pr86-controlled-comparison.md)
now generates the prospective 210-row matrix and resource arithmetic offline.
It creates no scientific result. Figures/tables will distinguish solver time
from cold and amortized preparation costs, retain every planned cell's final
state, and bind metrics to receipts. PR85 is independently reviewable; merging
it alone does not clear scientific execution gates. Mandatory serial/4-GPU
training and manuscript work retain separate budgets and acceptance criteria.

Post-merge PR85 continuation: [PR86 preparation](research/pr86-starts-and-costs.md)
adds a reproducible 18-row historical cost-coverage table and a tested ten-parent
start binder. These are coverage/implementation assets, not newly observed
CPU-scaling or end-to-end results. The prospective three-method executor and
approved execution budget remain prerequisites for the planned result figures.

The [installed review](research/pr86-installed-binding-review.md) adds the
ten-parent start-coverage table (including the lower medium coverage imposed
by the cap) and an 18-row historical supervised-attempt cost table. These can
support the methods/measurement explanation; they add no prospective performance
result and do not establish whole-job end-to-end speedup.

The [prospective instrumentation](research/pr86-prospective-instrumentation.md)
adds the parameter and timing contracts for future CPU/cost figures, not their
data. Figure generators must keep solver, supervised attempt and batch-level
scopes distinct, preserve stopped runs and avoid treating unknown preparation
or timing-tail writes as zero. The C–F roadmap and separate budgets are unchanged.
