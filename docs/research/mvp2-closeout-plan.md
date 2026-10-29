# MVP2 completion by Sprints and pull requests

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
