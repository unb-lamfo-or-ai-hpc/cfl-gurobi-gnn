# MVP2 closeout after the CPU campaign

28 October 2026. The target is a complete version for coauthors by
**15 December 2026**, with final editorial revision and submission by
**14 January 2027**. This plan implements the existing R3 scope. It does
not add an experimental campaign.

MVP2 is complete when the software, experimental evidence and article support
the same bounded scientific account. Completion does not require a favourable
GNN effect. Negative, censored or unavailable outcomes must be accounted for;
they cannot be removed to make the project appear successful.

## What belongs to the current work?

The only experimental campaign still in progress is PR89, whose 60 jobs were
already authorized and submitted. S3 covers its receipt, reconciliation and
scientific analysis. The matched GPU experiment is complete and supplies
existing evidence.

| Sprint | Remaining role in completion | New experimental execution |
| --- | --- | --- |
| S1 | Maintain the contract, decisions, responsibility and completion record | None |
| S2 | Finish source-linked methods, model/data provenance and reproducibility explanations | None |
| S3 | Reconcile and analyze the existing PR89 campaign | No additional jobs, preparation, inference or training |
| S4 | Synthesize the qualified CPU and GPU findings; complete the specialist assessment | None |
| S5 | Complete the article, figures, tables and scientific supplements | None |
| S6 | Address author review, verify editorial requirements and prepare the approved release/submission | None |

In the [sensitivity assessment](../../manuscript/supplement/sensitivity-review-plan.md),
option A means completing the existing study. Options B–E and the separate
four-hour diagnostic design are **future work outside S1–S6**: additional
solver seeds, an explicit root method, depth/width changes and training-seed
checks. Their execution counts are planning information, not a schedule,
budget approval or commitment to perform them before submission.

A reviewer request would not automatically authorize those studies. If a
missing comparison is essential to a central claim, the immediate editorial
response is to narrow that claim; any change to the experimental scope
requires a separate human decision.

## Starting point and working calendar

Let D0 be the date on which the final authorized return has been received
and the 60 planned cells have been reconciled against their submitted jobs.
This must satisfy the original collection gate; it does not mean that all
cells succeeded or that every metric is scientifically eligible.

The following is a planning allowance of about ten working days after D0,
with writing and synthesis overlapping. It is not a guarantee or permission
to skip a failed check. Work on methods, existing evidence and prose should
continue before D0 so that only the CPU-dependent additions remain.

| Delivery | Indicative window | What must be available at its completion |
| --- | --- | --- |
| 1. Scientific closeout of PR89 | D0 to D+2 | Qualified outcomes, metric eligibility and an explicit disposition for every planned cell |
| 2. Integrated CPU/GPU assessment | D+2 to D+5 | Answers to the research question and objectives, with supporting and adverse evidence |
| 3. Complete article and supplements | D+3 to D+7 | A coherent manuscript and all corresponding tables, figures and provenance |
| 4. Mandatory integral audit | D+7 to D+9 | Repository, evidence, article and supplements reconciled; material findings resolved or explicitly limiting claims |
| 5. Coauthor-ready version | Target D+10 | Verified reading package, specialist report and concise remaining author decisions |

A reconciled return by the end of November is the working dependency for the
15 December target. If receipt, qualification or a material audit issue slips,
revise the milestone explicitly. Do not compensate by omitting adverse cells,
creating results, repeating experiments or removing the audit. Coauthors can
review the methods and existing-evidence material before the CPU closeout.

## 1. Close PR89 scientifically

Reconciliation establishes which record belongs to which execution.
Scientific qualification then establishes which comparisons the record
supports. Preserve the installed source, model/checkpoint and start identities,
seed 42, MINIMIZE, original parameters and historical identifiers.

For each cell, keep scheduler state, solver status, primal value, dual bound,
gap, observed follow-up, threshold observations, resource accounting and
numerical qualification distinct. A scheduler COMPLETED state is not a
certificate of optimality. A missing observation is not zero; numerical
ineligibility is not ordinary administrative censoring.

Report B/R/G comparisons within the same parent and physical cap. Use
recorded observations at the defined thresholds and horizons, retaining
timestamps and brackets. Do not interpolate an exact crossing, extend a
terminated trajectory or divide timeout runtimes to claim a solution speedup.
M4/M12 remain visible with their existing metric-specific restrictions.

The deliverable is a sanitized evidence package, readable result tables,
a separate eligibility review and an analysis that includes failures,
censoring and regressions. Raw flags and historical receipts remain unchanged.
A blocked dependency or failed job receives read-only diagnosis and a specific
human decision; no retry or cancellation is implicit in project closeout.

## 2. Explain the combined findings

The synthesis must answer three connected questions:

- **Prediction:** What information does the fixed model recover from checked
  incumbent labels, and how do imbalance, approximate labels and historical
  test exposure limit that evidence?
- **Optimization:** When do the supplied partial starts help or harm primal
  quality, dual progress, terminal gap or observed time to a common target?
- **Cost:** Does an observed solver benefit remain after the stated preparation
  boundary, and what does the completed GPU pair show about speed, quality
  and assigned resources?

Keep the historical six-medium study, principal one-hour CPU analysis,
longer-horizon four-medium campaign and matched GPU pair distinguishable.
They do not form one enlarged independent sample. In particular, more time
is not a repair for numerical sensitivity, and historical seeds 43/44 do not
become repetitions of the CPU12h design.

Complete the R2-D8 specialist assessment by mapping SO1–SO8 and C1–C3 to
specific findings and limitations. An objective that was not demonstrated
must remain unachieved or bounded. Do not turn the absence of independent
generalization or architecture ablation into an implied positive result.

## 3. Make the article and supplements tell the same story

The article should move from the optimization question to the proposed
information, the comparison design and the findings. Methods explain the
actual fixed predictor; results explain what was observed; discussion
explains what follows and what does not. Operational history belongs in
the evidence record rather than interrupting the scientific argument.

The main remaining editorial tasks are:

1. State the contribution precisely and check that the title, abstract and
   conclusions make the same claim.
2. Distinguish label agreement, solution quality, proof progress and speedup;
   define each endpoint before using it.
3. Replace coverage inventories with interpreted results once qualified:
   introduce every display, identify its denominator and explain its meaning.
4. Keep the CPU/GPU contrast balanced, including slower, censored, numerically
   restricted and lower-quality outcomes.
5. Use one consistent account of fixed hyperparameters, validation selection,
   automatic root methods and the limits of repeatability.
6. State the sensitivity studies as future work, without adding them to the
   current methods or completion requirements.
7. Separate the scientific supplement from internal review registers and
   machine-readable provenance; give the reader a clear reading order.

Update the claim-to-evidence map for the qualified CPU return and reconcile
all repeated numbers in abstract, prose, tables, captions and conclusions.
Preserve the historical figures and their original scopes. Derived tables
and figures may be regenerated from qualified existing evidence; this does
not authorize a new solver or training run.

Package the final scientific supplement explicitly. The current repository
working material is not already part of the editable LaTeX ZIP. Verify
contents, citations, source identities and data/software availability, with
redistribution rights stated. Do not claim an unpublished deposit or DOI.

The Human–AI register remains supporting review material. A full IIEA-S
Appendix B is not a new MVP2 requirement; inclusion depends on a clear
scientific purpose, an agreed definition, sufficient primary decision evidence
and coauthor review.

## 4. Perform the mandatory final audit

| Area | Question that must be answered |
| --- | --- |
| Repository and scientific software | Do the described architecture, B/R/G paths, configurations, checkpoints and supplied artifacts correspond to the recorded experiment? |
| Experimental evidence | Are all planned cells accounted for, denominators correct, metrics eligible, clocks comparable and adverse outcomes retained? |
| Article | Do the question, literature position, contribution, methods, findings and conclusions form one defensible argument? |
| Supplements and editorial package | Does every displayed number and figure agree with its source, and are references, availability, rights and declarations consistent? |

Use source/link review, affected numerical/manuscript/archive tests and
final-head HTML/PDF rendering. Inspect the rendered pages visually.
Reuse completed audits and reopen them only for a concrete new discrepancy.
Passing CI establishes its checked properties, not scientific sufficiency.

Material findings must be resolved or used to narrow a claim before the
version is described as complete. Missing numerical qualification or a
central unsupported claim cannot be relegated to a cosmetic checklist item.

## 5. Deliver to coauthors, then complete the editorial release

The coauthor package consists of the complete article preview and editable
sources, scientific supplement, evidence/provenance index, R2-D8 assessment
and a short decision list. Preparing it does not itself authorize sending
messages to coauthors.

Human scientific review must settle contribution/title wording, the adequacy
of the bounded claims, final availability/rights and declarations, and any
Appendix B inclusion. The existing authorship and AI-use declaration remain
unchanged unless the authors explicitly revise them.

PR89 can be marked ready once its scientific closeout and applicable checks
are complete. Request its merge only then. Integrate the approved evidence
into PR92 against develop, resolve any documentary conflicts, and validate
the resulting final head. Request the PR92 merge when its own completion
criteria are satisfied. Do not merge either automatically or reset histories
to make branch identities match.

Use 16–31 December primarily for coauthor revisions and 1–14 January for
final editorial checks and submission preparation. A release/main merge
that publishes Pages must be identified as such for approval. Editorial
submission remains a human decision; it is not implied by a GitHub merge.

## Definition of completion

MVP2 is ready for scientific sign-off when the R2-D1–D8 products are delivered,
the qualified existing evidence is reflected in the article and supplement,
the integral audit is closed, reproducibility/availability limitations are
explicit, and the authors have accepted the bounded interpretation.
Paper acceptance is a later outcome, not an MVP2 completion condition.

Until D0, the next executable action is to finish the independent editorial
work in PR92. After D0, the first priority is the metric-specific scientific
closeout of PR89, not another experiment.
