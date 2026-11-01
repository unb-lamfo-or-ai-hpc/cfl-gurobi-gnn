# MVP2 completion by Sprints and pull requests

## Sprint plan approved — 1 November 2026

The author approved the revised Sprint/PR plan and instructed autonomous continuation. The approved planning basis is ten medium plus six easy optimization parents; the 54-parent learning corpus, 34/10/10 split, CPU checkpoint and threshold stay frozen. Advance the recommended one-thread, one-hour solver-seed extension (42/43/44), including conditional reuse, preparation and empirical difficulty assessment, toward a concrete reviewable manifest. The wider-resource alternatives remain alternatives, not cumulative approved work.

Planning approval is recorded and must not be requested again. It does not start jobs: finish the exact identities, compatibility checks, preparation/host-memory/job-wall accounting and applicable offline checks before the author's CLI intervention. The 55 optimizer-hour ceiling includes six 600-second roots and 54 one-hour solves if all 90 historical cells are reusable; it is not a complete reserved-resource budget. If reuse or numerical review changes that design materially, report the change and its impact rather than silently expanding execution. No new training, root-method/hyperparameter experiment, merge, publication or submission is authorized. PR89 remains governed by its original execution/collection authority.

The [planning matrix](mvp2-proposed-job-matrix-20261031.csv) now records planning_approved=true with approval date 2026-11-01 while preserving execution_authorized=false, automatic_retry=false and empty job IDs. Its 60 units are six preparations plus 54 proposed solves, not another submission of PR89's 60 cells.

### Current operational priority and evidence boundary

The author supplied a dgx-dasci sacct snapshot on 1 November; its exact query time was not supplied. Relative to the already received 3675–3724 archive, jobs 3725–3728 are newly reported COMPLETED/0:0. Job 3729 is RUNNING (03:22:10); 3730–3734 are PENDING. This supports 54 jobs reported complete across the two snapshots, but **only 50 result cells have been received and checked**. No failure was reported in this snapshot. Scheduler state is not scientific qualification.

| New terminal job | Instance | Physical thread cap | Method | Slurm elapsed |
| --- | --- | ---: | --- | --- |
| 3725 | M12 | 2 | B (M0) | 01:49:05 |
| 3726 | M12 | 4 | G (M2) | 00:10:46 |
| 3727 | M12 | 4 | B (M0) | 06:03:11 |
| 3728 | M12 | 4 | R (M1) | 05:47:09 |

The existing frozen map establishes these identities. Elapsed is the scheduler clock, not solver Runtime or a solution speedup. M12's numerical restrictions remain. The [delta collection runbook](runbooks/pr89-delta-20261101.md) prepares receipt of these four only; it neither reads running-result files nor recollects the earlier 50. Keep the 31 October article cutoff and sealed evidence unchanged until the delta ZIP is transferred, hashed and reconciled. The D0/full qualification gate still requires all 60 dispositions.

### Work advancing before the next experimental PR

S1 records this approval and operational handoff. S2 can prepare the next substantive PR's input/checkpoint manifest, structural-feature inventory and frozen-predictor preparation interface, with labels confined to their independent audit. Keep M5/M6 guidance-validation exposure, M9/M20 optimization-test exposure and M13/M26 audit exposure explicit; no candidate is declared untouched. S4/S5 integrate only receipt-checked observations, preserving both the historical and principal populations. S3 continues collection and metric-specific review of PR89. S6 retains the final audit and specific human release/submission gates. Complete the current article/appendices after PR89, obtain develop merge approval, then use the separately approved main release path. The 15 December coauthor target and 14 January maximum submission deadline remain unchanged.


## Proposed continuation and difficulty analysis — 31 October 2026

This addendum records the author's new request and a concrete proposal for review. It supersedes the earlier interpretation that six new labelled training parents were required. It does **not** change the running PR89 contract or authorize new HPC execution. Earlier dates and no-new-experiment statements below describe the previously approved scope; the proposed extension must pass its own protocol/resource gate.

### Populations and frozen learning

The intended optimization evaluation grows from four to **ten medium instances**, alongside the existing six easy instances: **16 evaluation parents**. It does not turn 60 PR89 cells into 60 instances and does not expand the admitted learning corpus. The GNN remains frozen on its 54-parent 34/10/10 split, checkpoint SHA256 a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028 and validation-selected threshold 0.9991843104362488. Solver seeds 42/43/44 vary optimizer search, not neural training.

The four current medium parents are M0/M4/M7/M12. Six proposed additions are M5/M6/M9/M13/M20/M26, the six medium parents outside the admitted label-quality sample in the [fixed parent inventory](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/90b6f540cfb17aab9efeb06a5e49aa381262461e/docs/evidence/e0/pr85/parents.csv). Keep their original canonical folds/roles:

| Candidate | Canonical fold/role | Proposed evaluation role | Exposure qualification |
| --- | --- | --- | --- |
| M5, M6 | 1 / validation | optimization test extension | Outside admitted 54; not asserted untouched |
| M9, M20 | 0 / test | optimization test extension | Also observed in the earlier six-medium optimization study |
| M13, M26 | 2 / train | optimization test extension | Outside actual admitted training; retain earlier audit exposure |

These are candidates subject to source/model/numerical review, not qualified new observations. A canonical role remains a historical identity even where an excluded parent enters a later, explicitly defined evaluation. Do not claim an independent untouched generalization test, rewrite the old split, select replacements for favourable results, or silently drop M4/M12. If input preparation fails, retain the disposition and seek a specific decision.

Six new qualified root/feature/Start bindings may be needed; reuse them if already available and compatible. No new training labels or six mandatory 12-hour reference solves are required merely to run a frozen predictor. If the current preparation code requires labels for an ancillary audit, separate that audit from prediction in the next implementation PR; never invent labels or use unqualified incumbents as ground truth.

### Proposed matched solver-seed comparison

Interpret three repeats as **one run for each solver seed 42, 43 and 44**, per parent/method/resource condition. Freeze the model, threshold, graph/Start, solver settings and stopping definition across these seeds. Three seeds describe sensitivity; they do not guarantee statistical power or constitute a neural-component ablation. GNN retraining, root-method changes and hyperparameter search remain outside MVP2.

Recommend a parsimonious extension at **one physical thread and a one-hour solver limit**, with B/R/G on all 16 parents. The [historical 210-row archive](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/90b6f540cfb17aab9efeb06a5e49aa381262461e/docs/evidence/pr86/final-210/campaign_results.csv) already contains 90 one-thread cells for the old ten parents at these three seeds. Reuse is conditional on exact protocol, input/Start, checkpoint, clocks and resource compatibility and metric eligibility. Historical seeds43/44 were excluded from the principal R3 analysis; any new secondary reanalysis must state that retrospective status and must not rewrite that original analysis.

| Proposed matched design | Total solve cells | Potentially reusable | New solves | New optimizer-time ceiling including six 600-second roots |
| --- | ---: | ---: | ---: | ---: |
| One thread, all parents at 1 h | 144 | 90 | 54 | **55 h** |
| Caps 1 and 16, all at 1 h | 288 | 120 | 168 | 169 h |
| All five caps, all at 1 h | 720 | 210 | 510 | 511 h |
| One thread, medium at 12 h and easy at 1 h | 144 | 66 | 78 | 937 h |

These are upper bounds on optimizer time, not elapsed-calendar predictions or Slurm allocations. Preparation/inference, orchestration, job wall and queueing are additional scopes that the execution manifest must price explicitly. The [draft matrix](mvp2-proposed-job-matrix-20261031.csv) enumerates six root/preparation units and 54 new one-hour solves; every row is nonauthorized and has no assigned job ID. If reuse fails, do not automatically rerun the 90 historical cells: a fresh 144-cell, one-hour design would instead require up to 145 optimizer-hours including roots and its own decision. Do not combine 12-hour seed42 PR89 endpoints with one-hour seeds43/44 as matched repetitions.

The primary proposed outcome is within-parent B/R/G terminal quality under the common one-hour stopping rule, recording actual follow-up, primal, dual and numerical eligibility; target attainment at 10% and 0.01% and time-to-target are separate outcomes. A time limit with no target crossing is right-censoring, never a solution time. PR89 remains a separate 12-hour seed42 study. This economical design cannot establish twelve-hour seed robustness.

### Classifying the ten medium instances

Call this **empirical computational difficulty**, not a change in theoretical problem complexity. The medium label does not establish homogeneous workloads. Use two complementary descriptions, following the distinction between structural features and observed solver performance in the [MIPLIB selection methodology](https://miplib.zib.de/Selection_Methodology.html):

1. Before new outcomes, inventory variables/binaries/rows/nonzeros, sparsity and coefficient ranges from identified input models. Preserve the existing formulation; no generator or semantic re-certification is introduced. Report continuous features and per-instance profiles. With ten parents, do not fit a new difficulty predictor or force three equal-sized clusters. This stage is metadata extraction only; missing features stay unavailable.
2. Report B's empirical target attainment, gap, primal/dual progress and runtime at the fixed cap/budget. Use transparent endpoint bands: attained 0.01%; attained 10% but not 0.01%; did not attain 10%; unavailable. These describe B at this protocol, not an intrinsic ordering of all CFL instances. For three seeds, report the counts in each band rather than forcing a parent into one stable class. M4/M12 numerical eligibility is an independent flag, not a difficulty class.

Use structural profiles for explanatory comparisons. A band based on the same B runtime used as denominator in G/B is outcome-dependent and mathematically coupled to the contrast; it supports exploratory description, not confirmation that G works better on harder instances. If independent historical calibration is reused, disclose its exposure and provenance. Do not spend an unapproved pilot budget to invent independent labels. Six new cases cannot receive measured difficulty classes before their qualified observations exist.

### Statistical presentation and Table 2

Keep geometric means of positive, attained paired time ratios as a secondary descriptive summary. Different absolute difficulties do not invalidate the dimensionless ratio; it gives equal relative weight to parents, not the weighting implicit in total runtime. Table 2 currently concerns the six easy instances, not medium. Individual effects and final gaps must accompany the aggregate: the article now gives per-parent/method maximum final easy gaps over caps, and Appendix B gives all 90 final gaps and runtimes.

For medium, lead with ten per-instance B/R/G contrasts, eligibility denominators, target coverage, censoring and primal/dual values. Use distributions/time-to-target profiles that retain nonattainment, rather than averaging time limits as solutions or silently discarding failed pairs. The [performance-profile method](https://doi.org/10.1007/s101070100263) motivates relative comparisons with explicit unsolved mass; it does not turn ten purposively selected parents into a representative population.

The experimental unit is the parent, with solver seed nested within parent. Pair methods within parent/seed/cap; summarize seed variability before any across-parent inference. Do not treat 30 medium parent-seed observations or 144 method cells as independent instances. Small strata and only three seeds restrict distributional and interaction claims. Any intervals/resampling must preserve parent clusters and censoring; no automatic cell-level t-tests or causal class-aware claim. Gurobi's [comparison guidance](https://support.gurobi.com/hc/en-us/articles/26992650628369-How-can-I-make-accurate-comparisons) supports multiple seeds while stressing that an adequate count depends on variation and solving cost.

### Sprint and PR sequence

| Sprint | Work and review boundary | PR delivery |
| --- | --- | --- |
| S1 | Record this proposed scope, exposure and conditional budget; preserve original campaign authority | Planning in PR93; execution protocol reviewed in the next substantive PR |
| S2 | Finish independent methods/bibliography/appendix audit now; inventory six inputs and difficulty features offline where available | PR93 for reader-facing corrections; next PR for frozen-predictor preparation and exact manifest |
| S3 | Receive/reconcile all 60 PR89 cells, record dispositions and metric eligibility, complete its scientific closeout | Existing PR89 evidence integrated in PR93; no changes to installed campaign |
| S4 | First finish the current evidence synthesis; later analyze the proposed seed extension separately if executed | PR93 baseline synthesis; subsequent experimental-results PR after qualified receipts |
| S5 | Finalize current article and separate appendices after PR89; audit all claims and historical cohorts | Review PR93, then request develop merge; use a distinct develop-to-main release PR and publication approval, verify Pages/PDFs |
| S6 | Integrate approved extension results, complete final audit and December/January scientific-editorial review | Results/release scope as needed; explicit approval for every merge/publication/submission |

A release of the qualified current study can precede the extension; it must not claim ten medium results before they exist. Later updates retain versioned provenance. Do not reserve PR numbers or create one PR per minor correction. January remains primarily editorial: complete manuscript to coauthors by 15 December, intended final approval 7 January, intended submission 10 January, maximum 14 January 2027. For the extension, aim for qualified receipts by 30 November and synthesis in early December; these dates depend on approved resources, queueing, numerical review and final scope. If the extension jeopardizes the dates, present the defensible current-study version and the explicit scope tradeoff to the authors rather than silently expanding resources or claims.

The final audit remains mandatory: software and B/R/G identity, all experimental evidence and numerical dispositions, article claims/numbers, and appendices/editorial package. Earlier independent review does not substitute for this gate. The next operational priority is final receipt of PR89 jobs 3725–3734 once terminal; jobs3723/3724 were already included in the 50-cell ZIP and must not be collected again as new evidence. No agent HPC access, new solve, training, inference, submission, retry, merge or publication occurs through this planning revision.


## Approved scientific/editorial revision — 30 October 2026

The author approved the detailed diagnostic and its implementation in PR93.
The approved title is **Evaluating Graph Neural Network-Based Partial Warm Starts for Capacitated Facility Location Problems**.
Only C2 (conditional optimization effects) and C3 (computational economics)
are scientific contribution claims; C1 is a methodological obligation.
Earlier candidate C1–C3 framing below is superseded in this respect, without
changing historical evidence or the installed experimental contract.
See the [revision record](pr93-editorial-revision-20261030.md) for the approved diagnostic, locations,
implementation and validation boundaries.

S1/S2/S4/S5 advance with existing evidence. PR89, its source, settings,
resources and sequence remain intact; S3 requires its reconciled 60-cell
return and metric-specific qualification. Further seeds, methods, models,
training and ablations remain future work. The final audit, merge,
publication and editorial submission retain their human gates.
No coauthor communication or new experimental execution is authorized here.


28 October 2026 · revised after the author's conditional approval.
This is the canonical delivery plan; the
[accelerated-plan index](mvp2-20261028-accelerated-plan.md) points here rather
than maintaining another timetable. Scientific scope remains R3.

The earlier D0–D+10 structure was an estimate, not a guarantee. Scheduling is
now expressed through Sprints, PRs and dated milestones. **D0 remains an
evidence event**, as defined below; it is not silently redefined or moved
to the date of later scientific qualification.

## Delivery boundaries

**PR92 closes the independent methods and preliminary-review stage.** It
contains the readable methods and limitations, existing CPU/GPU exposition,
claim provenance, the preliminary coauthor brief and the first-pass audit
record. It can be ready for review while PR89 is running. It is not the final
article, R2-D8 closeout or publication approval.

**[PR93](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/93) carries final synthesis and article integration.** It
can start immediately with existing-evidence synthesis and the audit items
independent of the CPU campaign. Qualified PR89 results, final figures/tables,
the final scientific supplement, R2-D8 and the second-pass audit belong there.
PR92 was merged into develop with explicit author approval on 28 October,
at `ac2dccb8bd56af6b03b866db5199d19944b7a28b`. PR93 now targets develop.
It remains a draft; its merge needs separate approval.

**PR89 remains untouched during execution.** Its source, resources, seeds,
models, parameters, sequence and collection contract remain frozen. The
receiver retains exclusive operational responsibility. Human intervention is
required for every HPC/PowerShell operation; no retry, cancellation or new
preparation is implicit in this plan.

A later release PR is justified only for an independently reviewable release/
publication scope. Its identity will be determined then. Do not create a PR
for every minor correction or invent future PR numbers.

## Sprint-to-PR map

| Sprint | Delivery and timing | PR responsibility | Exit criterion |
| --- | --- | --- | --- |
| S1 — governance and completion record | Close the independent planning/scope work now; maintain decisions through completion | PR92, then PR93 | One current plan, explicit supersessions and no confusion between a partial PR and MVP2 completion |
| S2 — methods and independent audit | Consolidate methods/model/data/reproducibility now; preliminary author feedback sought by 15 November | PR92 supplies the brief and first-pass record; PR93 resolves further independent findings | Fixed choices, validation selection, B/R/G dependencies and known limitations are source-linked; no new experiment |
| S3 — existing CPU campaign | Triggered by the authorized return, reconciliation and subsequent metric-specific qualification | Existing PR89 campaign; qualified evidence integrated in PR93 | All60 cells have explicit dispositions; failures, absences, censoring and M4/M12 eligibility remain visible |
| S4 — scientific synthesis | Start now with existing CPU/GPU evidence; finish after PR89 qualification | Synthesis PR | R2-D8 and SO1–SO8/C1–C3 assessment distinguish findings, limitations and unachieved objectives |
| S5 — article and scientific supplement | Preliminary brief now; complete manuscript to coauthors by 15 December | PR92 closes preliminary preparation; PR93 delivers the complete version | Consistent argument, all numbers traceable, figures interpreted, supplement explicitly packaged |
| S6 — final review and submission | December revisions; final approval target 7 January; submission target 10 January; absolute deadline 14 January | Final integration/release scope, with separately approved merges/publication/submission | Author scientific/editorial decisions, closed final audit and verified submission package |

S1, S2, S4 and S5 overlap; they do not wait for the campaign. Only the existing
PR89 experiment is still running. The sensitivity document's options B–E
and separate four-hour diagnostic design remain **limitations and future
work outside S1–S6**. Option A means completing the existing study.
No new training, model, seed, inference, solve or resource budget is introduced.

## D0 and the subsequent scientific qualification gate

D0 records reception of the final authorized return and reconciliation of
the 60 planned cells, irrespective of favourable or adverse outcomes.
It is not the date at which all metrics become eligible or all runs succeed.
The original collection gate still applies; this document does not authorize
premature collection while jobs remain active.

The subsequent scientific closeout requires an explicit disposition for every
cell and eligibility for each named metric. Keep scheduler state, solver
status, primal/dual values, gap, observed follow-up, censoring, failure,
missingness and numerical restrictions separate. Do not convert missing
observations to zero, numeric ineligibility to ordinary censoring, or an
observed crossing to an exact continuous first-hit time.

If a cell has no return or a dependency is blocked, record the absence/block
and the evidence available. Ask for a specific human decision. Preserve the
recorded reception/reconciliation dates; do not silently reset D0 to conceal
the problem or declare scientific qualification complete. No automatic retry
or change to the queue, tolerances, source or protocol is allowed.

M4/M12 remain in coverage and retain metric-specific restrictions. A
COMPLETED scheduler state or a longer run does not certify exact optimality.
Raw flags and historical receipts remain unchanged.

## Audit in two passages

**Passage 1 — independent review, before D0.** Reuse the completed R3 and
implementation reviews for software structure, the accepted formulation,
B/R/G interfaces, model/checkpoint provenance, bibliography, article structure,
historical figures and supplements. The
[coauthor brief](coauthor-review-brief.md) contains a compact
evidence/disposition register. Its coverage and remaining limitations are
stated; this is not blanket software or scientific certification.

Continue any unfinished independent review in PR93. No generator
certification or repeated experiment is reopened. Existing source reviews,
manifests, numerical checks and previously inspected renders can be reused
when their inputs are unchanged.

**Passage 2 — integral final audit, after D0 and qualification.** Reconcile the
integrated results, every table/figure and repeated number, scientific claims,
repository documentation and editorial package. Check that the methods,
artifacts and published version refer to the actual experiment, and that
censoring, numerical restrictions and adverse findings remain visible.
Inspect the final rendered article and supplied supplement.

Passage 1 reduces late surprises; it **never replaces the final gate**.
Use proportional source/link checks, affected numerical/manuscript/archive
tests and final-head rendering/visual review. Passing CI confirms its checked
properties, not scientific sufficiency.

## Early coauthor review and milestones

The preliminary set is now prepared in the
[scientific brief](coauthor-review-brief.md): working title,
research question, empirical gap, candidate C1–C3, methods, existing limitations
and focused review questions. It is informed by chat 01.04's completed review
and the implementation reconciliation. It does not reopen that investigation
or claim originality from citation counts.

| Milestone | Target and condition |
| --- | --- |
| Preliminary coauthor feedback | Seek a preliminary manifestation by 15 November 2026, through circulation authorized by the authors |
| Complete manuscript to coauthors | 15 December 2026, conditional on receipt, qualification and audit capacity |
| Scientific/editorial revisions | December 2026, continuing as needed toward final approval |
| Final approval | Intended by 7 January 2027 |
| Editorial submission | Intended by 10 January 2027 |
| Maximum submission deadline | 14 January 2027 |

No material or communication is sent on behalf of the authors without
authorization. Preparing the brief does not establish that feedback was
requested, received or approved. Final manuscript review remains necessary
after the qualified CPU results.

If reconciliation or audit reveals material risk, state the blocked deliverable,
its effect on the dated milestones and the earliest defensible revised path.
An editorial alternative may be a narrower claim supported by the qualified
evidence, with all exclusions disclosed. It requires author scientific
judgment; it cannot conceal failed cells or manufacture a successful answer.
If a central claim remains unsupported, revise the claim or submission
strategy rather than quietly adding experiments to a Sprint.

## Scientific and editorial completion

The synthesis must keep the historical six-medium study, principal one-hour
CPU analysis, four-medium CPU12h campaign and matched GPU pair distinguishable.
Parents, not method/cap cells or binary variables, are the comparison units.
Historical seeds 43/44 do not become repetitions of the CPU12h design.
Preparation costs, solver clocks and assigned resources retain their boundaries.

The article must connect question, literature position, mechanism, evaluation
and conclusions. Interpret displays rather than merely inventorying records.
Keep label prediction distinct from solver utility; conditional observations
distinct from seed robustness; fixed architecture distinct from an optimized
one; and CI success distinct from scientific validity.

The final PR must update the claim map for qualified CPU evidence, reconcile
abstract/prose/captions/tables, and package the scientific supplement explicitly.
The present repository working documents are not automatically included in
the editable LaTeX ZIP or approved for journal submission. Verify availability,
redistribution rights and declarations without inventing a deposit or DOI.

The Human–AI register supports review. A full IIEA-S Appendix B is not a new
MVP2 requirement; inclusion needs a clear purpose, agreed definition, adequate
primary decision evidence and coauthor approval. Authorship and the agreed
AI-use declaration remain unchanged absent explicit author revision.

## Review, merge and sign-off

Close PR92's revised stage when the brief, first-pass record, documentation
and applicable final-head checks are complete. Mark it ready and request
human merge authorization; do not close it as abandoned or merge it automatically.
Its readiness does not mean the whole article is submission-ready.

PR93 is prepared as a draft. Final readiness depends on qualified
PR89 evidence, complete R2-D8, integrated article/supplement, the second-pass
audit and the relevant author decisions. Any later PR89 scientific-closeout
or release merge also needs explicit authorization. The installed execution
source is not changed by documentary integration.

MVP2 sign-off requires delivered R2-D1–D8 products, a consistent qualified
evidence account, closed final audit, explicit availability limitations and
author acceptance of the bounded interpretation. Negative/censored outcomes
can be scientifically valid; acceptance by a journal is a later outcome.
Publication and editorial submission remain specifically approved human gates.
