# Draft protocol: frozen-predictor solver-seed extension

Prepared 1 November 2026 under the approved [Sprint/PR plan](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/32be4435a80c9b8f308e2e317d642ef63ffaf2dc/docs/research/mvp2-closeout-plan.md).
This package is reviewable planning metadata, not an executable campaign.
Planning approval persists. No HPC preparation, inference, optimization,
training, submission or retry has been performed for this extension.

## Scientific question and scope

Evaluate how B/R/G outcomes vary across optimizer seeds under one common
resource/stopping condition, while keeping the neural predictor fixed.
This is a sensitivity study of solver search, not a comparison of GNN
architectures, a training-seed ablation or evidence of a new graph architecture.
Its contributions remain conditional optimization effects and computational
cost within stated measurement boundaries.

The existing R3 principal study, PR89 CPU12h campaign and this extension
retain separate identities. In particular, PR89's 12h seed42 endpoints cannot
serve as matched one-hour repetitions with seeds43/44. PR89 stays untouched.

The design has 16 evaluation parents: six easy and ten medium. The six easy
IDs are F0/F3/F6/F14/F27/F29; the existing medium IDs are M0/M4/M7/M12.
Six additional candidates are M5/M6/M9/M13/M20/M26. The [cohort](cohort.csv)
preserves canonical names, folds, roles, admission and exposure. M5/M6 have
validation/guidance exposure, M9/M20 historical optimization-test exposure,
and M13/M26 prior audit exposure despite being outside admitted training.
None is asserted to be an untouched external generalization sample.
Candidates are not replaced according to favorable outcomes.

## Frozen learning and preparation

Keep the admitted54-parent split34/10/10: the fitted training partition is34,
not54. Retain the original CPU checkpoint
a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028,
its train-fitted normalization and validation-selected threshold
0.9991843104362488. The later GPU weights do not replace it. No new labels
are generated, and test labels cannot select starts or settings.

Preparation uses the reviewed root/feature/frozen-inference/Start mechanism.
The planned root cap is600seconds, one physical thread and seed42; exact
source and parameter binding must be closed before release. Capture the
eligible root-node relaxation through the existing callback interface rather
than introducing a different relaxation solve. The MINIMIZE override remains
the only accepted formulation correction. Preserve coefficients, domains and
constraints; no generator recertification is introduced.

G's support rule remains K=min(n,20000,max(1,floor(0.10n))). It ranks predicted
ones first and confident zeros second, with original-name tie resolution.
R uses the same actual(k,q) and ranks the stored LP values. It is therefore
a G-dependent matched control, including computational preparation.
Unselected Start values stay undefined; no bound fixing or restricted search.
If G abstains, record the abstention rather than altering the threshold,
forcing a positive assignment or choosing another instance.

One identified graph/root/Start binding per parent is fixed across solver
seeds42/43/44. Record model, graph, root, checkpoint, score and assignment hashes.
A failed preparation blocks its dependent operations and receives a disposition;
it does not authorize retries, replacements or an improvised B-only campaign.

The prospective scalar parameter values are listed in resources.json for review, including Gurobi13.0.1, MINIMIZE, Method=-1, MIPGap=1e-4, FeasibilityTol=1e-6 and IntFeasTol=1e-5. Only the declared per-cell optimizer seed changes; the draft array is not a solver API argument. Effective values, version, source and physical allocation must be verified before execution release.

## Cells and conditional reuse

[planned-cells.csv](planned-cells.csv) contains144 unique evaluation units:
16 parents ×3 methods ×3 optimizer seeds, with one physical thread and a
3600-second solver limit. It distinguishes historical IDs from future job IDs.

[historical-reuse.csv](historical-reuse.csv) identifies90 existing PR86
one-thread cells from the210-row archive. Those are identified candidates,
not90 newly admitted scientific comparisons. Eighteen concern M4/M12 and
retain explicit numerical restrictions. The [documentary compatibility review](compatibility-review.json) now confirms the recorded parameter hashes, model hashes, solver/Python versions and receipt/child links for all90. It identifies the prospective Start bindings from job3521, not the older E0 binding generation. The closed210-cell review is reused; no private vector or old experiment was rerun. This establishes archival identity compatibility, not admission for every metric or verification of a future deployment.

The other54 cells are new-solve candidates for the six additional medium
parents. [manifest.json](manifest.json) binds source hashes, planned outputs
and release flags. Existing method order positions are preserved in the
reuse ledger. New order must be frozen in the final execution manifest,
referencing the approved planning-matrix order; no randomization or
counterbalancing is claimed by this draft.

The parent inventory leaves six model hashes empty, but the broader historical E0 inventory already identifies original-file digests for M13 and M26. Those two historical digests are now retained in the cohort; their current bytes still require confirmation. Four other model digests remain unidentified in the reviewed records. The earlier inspection did not admit the M13/M26 root caches for inference; that finding is reused without rescanning caches. The [bounded read-only preflight](preflight-medium.md) checks only the six canonical original files, with no solver, inference or model generation.

If reuse fails, retain the reason and revise the resource accounting for a
specific decision. Do not automatically rerun the90 legacy cells.

## Numerical qualification and outcomes

The M12 audit establishes why solver-accepted and exactly integer-feasible
points must be distinguished. It does not authorize tighter tolerances.
Preserve original solver parameters/tolerances and archived eligibility flags.

For each stored result, bind its vector to the original model, recompute
objective/rows/bounds/integrality and examine an integer-rounded diagnostic
copy without modifying or repairing the original. Classify:
- original-tolerance checks and the scope of the independent check;
- integer-rounding sensitivity or an unresolved primal/dual inconsistency;
- exact primal verification when actually performed;
- availability and eligibility of each reported metric.

Ordinary tolerance-qualified comparisons are not exact certificates. A
rounding-sensitive point, crossed bounds requiring investigation, missing
vector or failed identity check cannot silently become an eligible exact
comparator. Preserve such rows in coverage and diagnostic cost reporting;
do not relabel numerical ineligibility as time censoring. Targeted rational
arithmetic may diagnose existing points without another solve. It proves
global optimality only if an actual sufficient proof is supplied; none is
claimed here.

Terminal return under a3600s setting is not exact common-time quality. Keep actual Runtime/follow-up and stopping status; do not truncate a recorded overrun or substitute first-observed crossing time for terminal return when pooling endpoint definitions.

The primary question is within-parent/seed terminal primal quality under
the common one-hour protocol and a stated numerical-eligibility screen.
For finite nonzero B, report100(P_method-P_B)/abs(P_B); negative favors the
method in MINIMIZE. If B is zero/unavailable, keep an absolute difference or
undefined state, not an invented denominator. Report quality eligibility
and its denominator alongside the comparison.

Complementary outcomes are reported primal/dual/gap trajectories, first
observed10%,5%,1% and0.01% crossings, actual follow-up, censoring, start
acceptance/abstention, Runtime, available printed work/iterations, memory,
job elapsed and delimited preparation costs. Threshold times remain first
observations with their brackets, not exact continuous hitting times.
A target unobserved at the time limit is right-censored, not a3600-second successful solve. The current summary exposes recorded first-observed10% crossings for79/90 cells and1%/5% for57/90. The recorded terminal0.01% return is a different endpoint. Historical threshold coverage must be checked separately: a target absent from the old recorder remains unavailable. Do not reconstruct a missing crossing by interpolating a sparse trajectory or present a new four-target recorder as if it had run on the legacy cells.

Do not borrow bounds between runs to improve a gap or count gap zero as an
exact certificate. Retain all seeds, adverse outcomes, missingness and
failures. No favorable-seed selection or automatic retry is allowed.

## Statistical interpretation and difficulty

Pair methods within parent/seed/cap. Seed is nested within parent;30 medium
parent-seed records are not30 independent instances. Lead with per-parent
contrasts, seed ranges, coverage, numerical restrictions and censoring.
Three seeds support sensitivity description, not guaranteed statistical power,
independent generalization or a neural-component ablation.

Inventory structural variables/binaries/rows/nonzeros/sparsity/coefficient
ranges before new outcomes, from identified inputs. Call performance-based
groups empirical computational difficulty. Use B's per-seed target bands
(0.01% attained;10% only;10% not attained;unavailable), keeping numerical
eligibility separate. Outcome-based bands are exploratory, not independent
evidence of a difficulty interaction. No new predictor, pilot solve, clustering
or learned-embedding analysis is introduced.

Positive eligible paired time ratios may have a geometric-mean descriptive
summary, with nonattainment and exclusions explicit. No automatic cell-level
t-test, pooled independence assumption or certified-speedup claim follows.

## Cost and resources

[resources.json](resources.json) states the conditional optimizer ceiling:
54 one-hour solves plus six600-second roots =55hours. This is not a complete
job reservation or a release budget. Full RAM/affinity admission, preparation,
frozen inference, Start assembly, job wall, audit/export overhead, serial
dependencies and reservation core-hours remain unresolved.

Historical supervised attempts, amortized preparation scenarios and new job
elapsed times have different boundaries. Reuse of solver observations does
not make all cost scopes compatible. Keep incomparable cold/job costs separate;
do not reinterpret old amortization as newly measured whole-job expenditure.
No energy or active-utilization estimate is invented. The previous prospective guidance stage used one GPU; the new inference device and GPU reservation remain explicitly unpriced. Do not assume CPU-only preparation or silently port inference to another device. No GPU allocation has been performed for this extension.

## Exit gate and next implementation work

The draft contains no scheduler script or dispatch/solve command. All assigned
new job IDs are empty and execution flags are false. Before a concrete CLI
release, finish:
1. Six input identities/sizes and any reusable preparation inventory.
2. Fixed preparation/Start bindings, abstention/failure handling and source.
3. Ninety-cell metric-admission decisions using the completed documentary identity review.
4. Complete memory/affinity/job-wall/resource accounting.
5. Executor/collector changes and proportional negative/admission tests.
6. Explicit frozen manifest and the author's CLI intervention.

No further general planning approval is requested. A material change in
scope/resources is reported rather than silently implemented. Merges retain
specific approval. This protocol can be prepared while PR93 closes the current
study; it does not depend on generating intermediate review PDFs.
