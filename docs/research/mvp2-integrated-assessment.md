# Working integrated assessment — R2-D8

28 October 2026 · draft for the final synthesis PR.
This document begins the synthesis of existing evidence. It is **not** the
final R2-D8 report, a qualified CPU12h return or a submission-ready conclusion.
The [Sprint/PR plan](mvp2-closeout-plan.md) governs completion.

The [preliminary coauthor brief](../../manuscript/coauthor-review-brief.md)
already states the title, question, literature position and candidate C1–C3.
This assessment does not repeat that review. It asks what the available
evidence can support and what must remain unresolved until qualification.

## Present scientific assessment

The fixed prediction-to-Start pipeline is documented. It preserves the
optimization model while offering Gurobi selected binary values to complete
or repair. That mechanism is not evidence that every start helps, that
class-aware ordering has a causal advantage, or that the architecture is novel.

The existing CPU evidence is retrospective and instance-dependent. The
principal population contains ten historically exposed parents, so neither
its number of method/cap rows nor its binary targets enlarges the independent
problem count. The longer-horizon campaign adds observations on four exposed
medium parents, not independent new test instances.

The completed GPU comparison has a clear limitation for a positive narrative:
training becomes faster, but selected parent-macro F1 decreases and assigned
GPU-hours increase. Timing, quality and resource outcomes must remain distinct.
The CPU starts still use the original checkpoint; the later GPU weights have
not demonstrated downstream solver utility.

The appropriate current conclusion is therefore bounded: this implementation
permits an auditable study of when learned starting information helps or harms
under stated conditions. The final evidence-based answer about the CPU12h
campaign is still absent.

## Evidence available now

| Evidence chain | Recorded scope | Current interpretation and source |
| --- | --- | --- |
| Data and model | 54 admitted parents from 90 candidates; 34/10/10 split | Quality-selected, potentially approximate labels; no independent generalization. [Methods/data record](mvp2-r3-methods-and-models.md) |
| Principal CPU | 150 seed-42 rows: 97 reported targets, 53 censures; 30 sensitive M4/M12 rows are a subset | Coverage categories are not exact optimality certificates. [Main summary](../evidence/methodology-20261019/summary.json), [existing CPU review](pr86-final-analysis.md) |
| Historical six-medium archive | Separate optimization cohort and figures | Retain original scope and adverse outcomes; do not substitute for the principal cohort. [Imported manifest](../../manuscript/results/current/pr60_scientific_evidence_manifest.json) |
| Matched GPU pair | One seed; loop speedup 2.167, job speedup 1.831; selected F1 loss 0.032468 | Increased assigned GPU-hours and lower selected quality; no noninferiority or isolated GPU causality. [Completed review](pr87-completed-pair-review.md) |
| CPU12h | 60 cells already submitted; final return pending | No result values or inferred outcome counts are inserted here. [Frozen R3 scope](mvp2-r3-contract.md) |

The principal CPU coverage and displayed matched-GPU values are bound by
the [claim map](../../manuscript/supplement/claim-evidence.json). Data-admission
and partition counts use the R3 methods record; historical figures retain
their imported manifest. The numerical gate does not claim coverage of every
quantity in this report. This document introduces no new estimator, pooled
dataset or experiment.
The first-pass audit record remains in the coauthor brief; its reuse is
explicit, not a declaration that all software or conclusions have been verified.

## Objectives: current coverage and remaining qualification

| Objective | What existing evidence contributes | Remaining boundary |
| --- | --- | --- |
| SO1 — dataset construction | Admitted cohort, split and label-quality checks | Not full 90-parent/hard coverage; quality-selection bias remains |
| SO2 — optimization efficacy | Historical and principal B/R/G comparisons | CPU12h conclusions need qualified cell outcomes and metric eligibility |
| SO3 — computational efficiency | Eligible target/time comparisons and cost definitions | Censored or numerically restricted pairs cannot become certified speedups |
| SO4 — robustness | Recorded configuration and historical repetitions | Principal study remains seed 42; no training-seed or broad configuration robustness |
| SO5 — scalability | CPU caps and matched serial/DDP work | GPU and CPU resources scale together; one pair does not isolate GPU causality |
| SO6 — economics | Bounded preparation scenarios, solver/job clocks and assigned GPU-hours | Missing cold costs, energy or money cannot be imputed |
| SO7 — generalization | Parent roles and information boundaries are documented | Historically exposed tests do not establish independent generalization |
| SO8 — integrated assessment | Existing source-linked synthesis begins here | Final qualified CPU integration, full audit and human scientific judgment remain pending |

An unmet objective stays unmet or explicitly limited in the final report.
Project completion does not require claiming that every objective was achieved.

## What the CPU return must resolve

For every planned cell, bind the recorded outcome to its parent, method,
physical cap, original source and supplied artifacts. Preserve any absence,
failure or blocked condition. D0 is the reception/reconciliation event;
later scientific qualification must not silently redefine it.

The final assessment must then separate:

- primal feasibility under the stated checks from exact mathematical proof;
- primal improvement from dual-bound progress and relative-gap change;
- terminal target reporting from first observed threshold crossing;
- observed follow-up from an exact common-time measurement;
- numerical restriction from censoring and missingness;
- solver Runtime from job elapsed and preparation/training boundaries.

M4/M12 require metric-specific treatment. Recorded horizon brackets keep
their real timestamps and staleness; no interpolation or extension of terminated
trajectories is introduced. More runtime is not a numerical repair.

Do not treat the CPU12h campaign as a continuation prefix of earlier solves.
Cross-campaign comparison must retain the separate time-limit settings,
measurement conditions, exposures and eligibility. Historical seed 43/44
observations remain historical and are not CPU12h replications.

## Questions for the final C1–C3 assessment

| Candidate contribution | Evidence needed in the final integrated account | Claim that must not be inferred |
| --- | --- | --- |
| C1 — specified mechanism | Consistent model/variable/Start identities and a clear explanation of the dependent R comparator | First GNN warm start, architecture novelty or causal selector superiority |
| C2 — conditional effects | All planned parent/cap outcomes, eligible comparisons, regressions, censoring and influence of restricted cases | Uniform acceleration, stable seed-averaged gain or independent population inference |
| C3 — bounded economics | Explicit clocks, measured versus scenario preparation, training quality and assigned resources | Energy savings, monetary savings or complete cold cost without measurements |

The preliminary literature position is an input to coauthor judgment,
not a completed originality verdict. If the qualified evidence cannot
support a central claim, revise that claim or the editorial strategy.
The additional experiments in the sensitivity document remain future work
outside the current Sprints.

## Independent work advanced before the CPU return

The following separation is now made for the final editorial package.
It can be reviewed without running the solver or training a model.

| Material | Intended role | Current disposition |
| --- | --- | --- |
| Main article and essential method/results displays | Scientific argument for OR readers | Existing integrated draft; final CPU synthesis pending |
| Readable methods explanation and qualified result/provenance tables | Candidate scientific supplement | Select and package explicitly; current Markdown working files are not automatically in the LaTeX ZIP |
| Claim manifest, source/asset identities and reproducible generators | Verifiable supporting provenance | Reuse existing checks; extend only to the qualified CPU return |
| Coauthor brief, planning and review decisions | Internal scientific review | Prepared for author-controlled circulation; no communication sent |
| Prospective sensitivity counts/designs | Limitations and possible future work | Not current experiments or results |
| Human–AI traceability register | Support the Appendix B decision | Not an approved journal appendix; definition/evidence/relevance remain author decisions |
| Private operational captures, credentials and licensed material | Restricted operational evidence | Do not package or publish indiscriminately; availability/rights must be explicit |

This avoids presenting planning or hypothetical resource ceilings as
experimental findings. It also identifies the packaging gap without claiming
that the journal supplement is already complete.

## Finalization conditions for this PR

Complete the qualified CPU integration and source-linked interpretation;
extend the numerical claim map and reconcile every repeated number.
Perform the integral second-pass audit of repository, evidence, article,
supplement and editorial package. Independent reviews reduce that work,
but do not replace it.

Document the final SO/C assessment and scientific limitations in R2-D8.
Verify final-head tests, rendering and visual quality, then seek human
approval for the relevant merge. Coauthor scientific/editorial decisions,
publication and submission remain separate gates. No new experiment or
change to PR89 accompanies this draft.
