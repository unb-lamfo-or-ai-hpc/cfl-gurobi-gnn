# CFL--GNN research context

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
