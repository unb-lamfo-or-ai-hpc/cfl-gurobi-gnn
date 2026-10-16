# Article plan

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
