# CFL--GNN research context

## Current Sprint/PR delivery — 28 October 2026

The [canonical plan](research/mvp2-closeout-plan.md) now uses Sprints and PRs.
PR92 delivered the independent methods and preliminary-review stage and was
merged with explicit author approval at `ac2dccb8bd56af6b03b866db5199d19944b7a28b`.
PR93 now targets develop and carries synthesis and final CPU integration.
Its [supplement guide](../manuscript/supplement/README.md) records the independent
claim reconciliation and reader-oriented explanations. PR93 remains a draft;
the qualified return and final audit are still required.

The [coauthor brief](research/coauthor-review-brief.md) is prepared for
author-controlled circulation and preliminary feedback by 15 November.
It includes the first-pass audit record. The complete post-qualification
audit remains mandatory. Targets are manuscript 15 December, final approval
7 January, intended submission 10 January and absolute deadline 14 January.

D0 remains reception/reconciliation of 60 planned cells, not the later metric
qualification date. Missing returns or blocks require a recorded human
decision, not a silent date change or retry. Additional experiments stay
outside the current Sprints.

## Documentary continuation — 28 October 2026

The [accelerated S1–S6 plan](research/mvp2-20261028-accelerated-plan.md)
targets a complete coauthor-review version by15December2026 and preserves
the14January2027 submission deadline. S1/S2/S4/S5 continue in PR93 after PR92’s independent-stage delivery;
the CPU-dependent S3 closeout and mandatory final A–D audit remain gated.
The [GNN audit](../manuscript/supplement/gnn-methods-audit.md) and
[conditional Appendix B register](research/human-ai-traceability-review.md)
record actual methods, critical references and evidence gaps. No experiment,
checkpoint, campaign parameter or raw result is changed.



## Governing continuation — 26 October 2026, R3

Read the [R3 contract](research/mvp2-r3-contract.md),
[methods and models](research/mvp2-r3-methods-and-models.md), and
[metrics/reproducibility assessment](research/mvp2-r3-metrics-and-reproducibility.md).
They consolidate the prior audits and the author-approved ongoing PR89 handoff.

B/R/G are aliases for historical M0/M1/M2, not renamed receipts. R ranks stored
root-LP scores, matching G's cardinality and one-count, not necessarily indices.
G uses the original mixed PR86 checkpoint; newer PR87 models do not replace it.
MINIMIZE and the accepted formulation remain frozen; M4/M12 limitations persist.

The principal analysis remains 150 seed42 rows, with all 210 originals retained.
Ten historically exposed test parents support retrospective comparisons, not
independent generalization. GPU matched training is already complete, with
measured speedup and F1 loss 0.032468; no corrective training is needed.
The CPU budget was separately approved on 20 October and 60 jobs submitted.
PR89 remains active, with no final scientific return yet received.

R2-D1–R2-D8 and overlapping S1–S6 lead to the 14 January 2027 deadline.
Class-aware causal benefit, multiseed robustness and independent generalization
are not established or automatically required for MVP2.
The [evidence index](research/mvp2-r3-evidence-index.json) separates documentary
coverage, existing scoped results and pending CPU closeout.

## Historical context — original dated text preserved

The following dated descriptions retain their provenance. Their old CPU-budget,
transfer and scheduling holds are superseded by the governing R3 contract.


## Governing revision — 19 October 2026

[D1–D6](research/methodology-20261019/README.md) is the current methodological
contract. Preserve original210PR86 observations; principal analysis150seed42,
60other-seed observations historical only. Ten exposed test parents support
retrospective comparisons, not independent generalization. MINIMIZE override and
accepted MILPBench formulation persist. M1 is GNN-budget-matched root-LP guidance,
not an independent LP heuristic. Class-aware novelty/causality not established
by this comparison. Costs, censoring, target equality and memory scopes must be
explicit. PR87 GPU is completed and merged at32be9821 on20October; the new
CPU12h package still awaits separate execution approval.
No new architecture, seed search, expansion or experiment is authorized here.
PR87 installed closeout: the [completed seed42 pair](research/pr87-completed-pair-review.md)
has matched recorded work and2.167x loop/1.831x job speedup, but worse selected
macro F1 by0.032468, exceeding the predeclared0.02 descriptive loss margin.
Assigned GPU-h increase; CPU resources also scale. This is a speed/quality/cost
tradeoff in one case, not preserved predictive quality, seed robustness or isolated
GPU causality. Predictive references remain the historically exposed10parents.
Original receipt flags and jobs3671/3672 are preserved. No tuning/retry is needed
to make a negative observation scientifically reportable. CPU budget remains
separate and unauthorized. The dated operational holds below are superseded.

20October: the first approved GPU pair3671/3672 failed/cancelled before producing
result or supervisor reports; this is not a GPU performance/quality observation.
See [source/receipt diagnosis](research/pr87-job3671-failure.md). Fix only the Slurm
entry boundary and failed-receipt classification; preserve seed42/data/model/work.
Historical exact failure-gate confirmation requires private read-only inspection.
No new job/training/solve/merge or CPU authorization in this correction.

19 October methodology revision: approved preparation only. PR88 consolidates
D1–D6 and seed42-only main analysis, preserving210 originals and60other-seed
records as history. Here PR87 retains matched100epochs/globalbatch4 and the
same scientific training parameters, but changes its authority contract to v2:
new specific GPU receipt required before submission, launch and review.
The [GPU package](research/pr87-gpu-authorization-package.md) is independent of
the CPU12h proposal. Neither execution nor merge is authorized by this revision.

PR87 author revision19October: compare only seed42 serial1GPU and DDP4, not
three seeds. [Matched learning work and acceptance](research/pr87-matched-gpu-protocol.md)
separate technical completeness from positive performance. One paired case
does not support training-seed uncertainty or statistical noninferiority.
No new architecture/data/hyperparameter search; CPU PR86 is already merged.

19 October: [final210-cell CPU review](research/pr86-final-analysis.md) completes
the planned comparison, not an independent test or the entire MVP2. Effects
depend on parent, CPU cap and cost scope; M2/M1 remains an essential comparison.
Uncertainty is exploratory with six exposed easy parents; medium censoring and
M4/M12 sensitivity prevent certified-speedup aggregates there. Same-parent seed
repeats do not enlarge the independent sample. The required1GPU/DDP4 training
comparison and manuscript remain; no superiority assumption or new search.

## Research question

Can a graph neural network (GNN) learn useful guidance for capacitated
facility-location (CFL) mixed-integer programs, and can that guidance improve
the quality reached or the time required by Gurobi under a controlled,
reproducible protocol?

The relevant comparison is not only whether a method finds an optimum. It is
also the incumbent quality, primal/dual bounds, relative gap, runtime, memory,
thread/GPU allocation, and the cost of preparing the guidance.

## Scientific object

Each parent instance is an indivisible experimental unit. Derived artifacts
must retain their parent ID and may only be generated from training parents.
The project uses the explicit easy/medium/hard cohorts and the 34/10/10
parent-level train/validation/test contract. Instance labels in tables should
use the stable notation `F0`--`F29` for easy parents and `M0`--`M29` for medium
parents whenever a cohort-level presentation is intended.

The population has 90 parents (30 per difficulty). The admitted sample has
54 parents: 30 easy and 24 medium, selected through the historical label-quality
gate, not random population sampling. Training contains 18 easy + 16 medium;
validation 6 + 4; test 6 + 4. No hard parent is admitted to this sample.
The ten test parents have historical exposure: future comparisons on them are
retrospective controlled evaluations, not independent generalization evidence.
M13/M26 are excluded canonical training parents, not additional test cases.

## Three solver methods

The controlled solver comparison has three distinct arms:

1. Gurobi without an external start;
2. Gurobi with a partial start obtained from a verified root LP relaxation;
3. Gurobi with a partial start produced by the frozen GNN.

The relaxation start is not a GNN prediction and does not mean that Gurobi is
absent from the experiment: the root relaxation is an explicitly measured
Gurobi preparation step. Its source, cost, variable order, feasibility checks,
and partial-start policy must be reported separately from the GNN arm.

In the existing E0 implementation, the LP-matched comparator uses the GNN's
supplied support size and positive-count budget. Its scores are LP-derived,
but this matching makes it dependent on GNN preparation. It must not be
presented as an independent LP-only baseline with that cost omitted. The GNN
also uses root-LP features. Three method arms do not mean three independent
data-generation pipelines.

The authors confirmed on 11 October that the source `MAXIMIZE` declaration is
a benchmark error for the intended cost-minimizing CFL. Effective `MINIMIZE`
is mandatory, preserving coefficients, feasible region and original bytes.
This is a correction, not equivalence to the original maximization. PR85
reconciles that policy with existing receipts. Its [closure](research/pr85-closure.md)
also binds two representative LP structures and frozen training reports;
independent historical fit replay remains unqualified. The 12 October author
decision accepts the benchmark CFL formulation except for MAXIMIZE and removes
renewed economic mapping/generator certification as an execution prerequisite.
This frozen premise applies through the final sprint; model identity and
MINIMIZE enforcement remain mandatory implementation checks.

## Current project boundary

The MVP is a scientific prototype, not a production service. Reproducibility
and honest qualification take priority over package modernization or broad
automation. The repository records code and sanitized evidence; HPC keeps
private paths and large raw logs.

Neither predictive improvement nor solver speedup is assumed. E0 job3506 found
GNN faster in 3/6 easy parents, but a geometric solver-time ratio GNN/M0 of
1.1802; this does not support consistent acceleration. Missing preparation
times prevent a historical end-to-end speedup claim. See the
[current checkpoint](current_status.md) and [approved roadmap](article_plan.md).

PR86's [offline proposal](research/pr86-controlled-comparison.md) distinguishes
M1's matched support cardinality/positive count from equality of variable IDs,
and charges GNN-dependent preparation to it. Effective MINIMIZE is mandatory
under the author-approved cost-objective correction. This does not erase
historical receipt contents or approve execution. The frozen formulation
decision supersedes the former semantic-mapping gate, not provenance checks.

PR85 is now merged at `bb3f28f8078abde5ed4d95461f04fe675be2f37e`.
The [PR86 continuation](research/pr86-starts-and-costs.md) reuses job3505's
existing predictions/roots for ten-parent variable binding. This is not another
inference or root solve. Existing E0 timing coverage is decomposed without
double-counting export; unmeasured preparation remains unknown.

The installed [ten-parent binding review](research/pr86-installed-binding-review.md)
now reconciles receipt `45eab23962f8`: six easy starts cover 10% of binary
variables; four medium starts hit the 20,000 cap (about 1.68–1.74%). This is
variable/start identity evidence, not solver acceptance or new performance.
Existing job3506 supervisor timings support a separately scoped attempt-cost
table; historical guided preparation and whole-job end-to-end costs remain unknown.

The [prospective solver/instrumentation core](research/pr86-prospective-instrumentation.md)
explicitly sets the proposed caps/seeds instead of silently inheriting the
historical one-thread/seed-42 defaults. Synthetic tests are implementation
evidence only. The historical sources, results and eligibility flags are unchanged.
