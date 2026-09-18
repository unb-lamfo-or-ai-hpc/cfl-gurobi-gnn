# Representative-data and partial-start recovery roadmap

## Research question and current evidence

Can learned partial assignments improve primal quality, terminal MIP gap, or
time to a predeclared quality target over Gurobi and non-neural starts, including
online preparation costs? Engineering validity and start acceptance are not
evidence of acceleration. PR56 produced mixed/negative results on two medium
instances: both guided primal objectives were worse, both first-observed times
to 10% gap were later, and all four runs were time-censored. Its artifacts and
historical score policy remain immutable.

## Approved three-sprint sequence

1. Reconcile original medium labels and qualify assignment identity, calibration,
   selection, abstention, and completion effort. Continue unstarted originals in
   controlled eight-hour batches only after inventory review; failed-quality
   attempts require a separately versioned rescue decision. Diagnose hard cases
   separately; the previous hard1 run had 81.4751% gap at sixteen hours.
2. Train on the training folds of easy plus medium originals for at least100
   epochs, and test controlled augmentation from Gurobi and SCIP incumbents.
   Keep Gurobi graph authority and independent Gurobi labels fixed to isolate
   the augmentation source: original-only, +Gurobi-derived, +SCIP-derived.
   Retain train-only descendants, equal parent mass and measured diversity.
3. Freeze policy before held-out paired benchmarking against unguided and
   non-neural starts. Report gap, primal/dual progress, first-observed quality
   thresholds, censoring and complete costs; retain negative findings. Only then
   revisit the manuscript. The two PR56 targets are development-exposed parents.

## PR57 delivery boundary

This first increment reads the PR54 campaign and the PR56 audit. It verifies
original descriptors, receipts and declared artifacts, preserves admitted
labels without replacing them, proposes continuation batches containing only
unstarted medium originals, and separates unadmitted/incomplete/corrupt cases.
Existing eligible PR56 **unguided** solutions are identified for review, not
automatically promoted into another label schema or moved across folds.

No optimization, training, scheduler submission, empirical calibration fit,
corrected prediction export, hard campaign, or scientific certification occurs.
The report deliberately keeps training_ready and calibration_qualified false.
The new selection kernel is isolated: the PR56 production adapter is unchanged.

Outputs: medium_reconciliation_report.json, preserved_label_index.jsonl,
medium_continuation_tasks.jsonl, medium_rescue_review.jsonl,
source_task_states.jsonl, pr56_control_reuse_review.jsonl and
historical_prediction_diagnostics.jsonl. The report binds output hashes and
source descriptors; raw vectors, private logs and license contents are not
copied into the outputs. Existing output directories are never overwritten.

## Assignment qualification

The historical decision uses a validation F1 threshold near0.997535 whereas its
ranking uses max(p,1-p). For example, p=.99 submits zero with score.99. The new
kernel ranks by the probability of the actual assignment and permits abstention,
a fractional cap and an absolute cap. Permuting input rows must not change the
variable-name assignment map. A name is only a deterministic tie-breaker.

Positive-weighted BCE outputs are not calibrated posterior probabilities.
For constant weight w, at the population optimum, eta=q/[w(1-q)+q]. This identity
is a diagnostic correction, not a calibration certificate. An empirical
calibrator must be fitted on original validation parents (or explicitly grouped
out-of-fold training predictions), with untouched test parents. This increment
implements the validation-parent boundary only. It must not be bypassed to use
in-sample training predictions as calibration evidence. Assess reliability,
class-specific performance and risk versus coverage at the parent level before
selecting coverage or fitting a learned acceptance head.

Native partial MIP starts do not permanently fix variable bounds. Limit their
completion effort explicitly in the future runner. Gurobi13 adds StartTimeLimit
and StartWorkLimit; earlier versions provide StartNodeLimit, which is not a
wall-time cap. The current tool reports version-level capabilities from the
recorded solver version; runtime API probing and a selected budget remain
required before execution. It does not upgrade or reconfigure a solver.

## Augmentation and evaluation cautions

Different local-branching radii around an optimal center retain that optimum;
graph differences alone do not demonstrate label diversity. Measure Hamming
diversity and parent-level redundancy before accepting synthetic samples.
Multiple feasible incumbents can supply multiple learning targets on one graph;
do not serialize an identical graph per incumbent. Admission at10%objective gap
does not imply90%variable-label accuracy. Compare learned starts against simple
zero-only/matched-support and relaxation-derived controls, selected on validation
under comparable completion budgets. Individual variables are not independent
experimental units. Neither a failed budget nor a large gap proves infeasibility.

## HPC preflight

Activate tfm_env and use a new output directory under
data/analysis/medium_reconciliation. Run the smoke suite, then submit
scripts/slurm/dasci/submit_medium_reconciliation.sbs with DATA_ROOT,
CAMPAIGN_PLAN_DIR, CAMPAIGN_RUN_ROOT, MEDIUM_AUDIT_DIR, MEDIUM_RUN_ROOT and
RECONCILIATION_DIR exported. The first three inputs refer to the existing PR54
campaign, and the next two to PR56. All inputs are directories, not JSON files.
No license is consumed by this audit; the launcher requests8GiB and no GPU.
Review counts, hashes, sanitization, raw-score diagnostics and recorded solver
capabilities before preparing medium submission commands. Do not recompute
historical experiments using a changed implementation contract.

## Reconciliation evidence and first continuation

The operator-reported DGX job3365 completed successfully. The inventory contains
42 admitted parents (30 easy,12 medium),15 unstarted medium originals and three
medium quality-rescue reviews. Both eligible PR56 unguided labels are already
admitted: they do not increase the population. The three rescue cases are
medium5,6,9, with terminal gaps12.1671%,10.5629%,11.5974%, respectively.
No rescue or additional hard run is included in the continuation.

The historical prediction audit found zero selected high-score assignments to
zero on both PR56 targets. All selected assignments were zero, but originated
from low raw scores. Consequently, the decision/confidence inconsistency cannot
be attributed as the direct cause of these selected starts or their negative
outcomes. Correcting it is methodologically necessary, not an established remedy.
The recorded Gurobi version is13.0.1; runtime completion-budget qualification and
empirical calibration remain pending. Class imbalance, assignment coverage and
completion effort require investigation without selecting on exposed test data.

The next five originals are medium10,11,12,13,14. Their PR54 task indices are
5,6,7,8,9 and the original campaign audit batch is1 (not0). Preserve seed42,
MINIMIZE,one thread,28800seconds per solve,64GiB per task,12hours Slurm wall time
and concurrencyone. These are independent original solves, not guided runs.
No incumbent import, parameter tuning or label replacement is introduced.

`prepare_medium_continuation` rechecks source/output hashes, declared-text
sanitization, the immutable PR54 implementation, admitted-label identity and live
unstarted task state. It emits `medium_continuation_preflight.json` only; it does
not submit or solve. The opt-in Bash helper
`scripts/slurm/dasci/submit_reviewed_medium_continuation.sh` invokes that gate,
checks the source commit and tracked working tree, prevents duplicate helper
submissions, tests scheduler acceptance and submits exactly one sequential batch
plus an afterany audit. Run it with bash, not source. Job identifiers are persisted
immediately, including when the dependent audit submission fails. Do not rerun
the array in that case. Retain the source checkout while jobs are queued/running.

The submission record contains operational paths and is not a publication
artifact. Sanitization here covers the seven reconciliation text files, not raw
solver logs or binary payloads. The execution and audit reuse the frozen PR54
implementation and run root; completed receipts remain immutable. The original
campaign report still counts40 preserved labels, with all later admissions in
its cumulative new-label count. The PR57 preflight independently preserves42.
Review each batch before another submission; regenerate reconciliation after
live task state changes. The three remaining quality rescues require a separate
budget decision. PR57 remains draft pending collection and calibration gates.

## Primary methodological references

- Gasse et al.(2019), [Exact Combinatorial Optimization with Graph Convolutional
  Neural Networks](https://arxiv.org/abs/1906.01629): branching-policy learning,
  not direct evidence for our binary assignment task.
- Nair et al.(2021), [Solving Mixed Integer Programs Using Neural Networks](https://arxiv.org/abs/2012.13349):
  solution-distribution learning, selective assignment and sub-MIP completion;
  our native-start pipeline is not a literal reproduction.
- Guo et al.(2017), [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html).
- Gurobi [warm-start documentation](https://docs.gurobi.com/projects/optimizer/en/current/features/warmstart.html)
  and [version13 release changes](https://docs.gurobi.com/projects/optimizer/en/current/reference/releasenotes/changes.html).
