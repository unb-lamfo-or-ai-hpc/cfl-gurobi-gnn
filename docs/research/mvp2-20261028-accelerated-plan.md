# MVP2 — accelerated completion and coauthor-review plan

28 October 2026 · target: **complete coauthor version by 15 December 2026**;
final submission deadline **14 January 2027**.
This updates dates and documentary priorities in the [R3 completion plan](mvp2-r3-contract.md),
without changing scientific scope, author decisions of22October, installed
PR89 protocol or experimental authority. Dates are delivery targets, not an
HPC completion forecast.

## Experimental scope and post-CPU closeout

The only campaign still running is the already authorized PR89. S3 covers
its receipt, reconciliation and analysis; no additional jobs are scheduled.
S1, S2, S4, S5 and S6 use documentation and existing evidence.

The sensitivity document's options B–E, including the four-hour diagnostic
alternative, are limitations and future work outside the current Sprints.
Option A means finishing the existing study. The
[post-CPU closeout plan](mvp2-closeout-plan.md) defines the remaining five
deliveries, approximate working windows, scientific audit and coauthor package.
It preserves the 15 December target and the 14 January submission deadline.

## Scientific-writing and sensitivity update

The methods supplement has been rewritten as an academic explanation for a
reader: why the representation fits the task, why the fixed hyperparameters
are reasonable, what was actually selected by validation, and what remains
untested. Literature supports design principles, not an undocumented claim
that 2×32 or a clipping threshold of 1 is optimal.

The [sensitivity assessment](../../manuscript/supplement/sensitivity-review-plan.md)
keeps new runs outside the current execution scope. The immediate path is
to finish the existing evidence and bound the article's claims. Additional
solver seeds at one cap are the first candidate if robustness evidence is
needed; explicit root methods or network changes require a specific question.
A missing central comparison cannot be excused solely by waiting for reviewers.

S1/S2 now reconcile this interpretation with the scientific contract.
S4 assesses the claim/evidence boundary; S5 integrates readable methods,
discussion and future work. Dates and the mandatory post-CPU audit remain
as planned below. No new trial is scheduled.

## Executive decision

Maintain PR92 as the integrated editorial delivery. Its existing base is
develop after merged PR91 (6bb374aae5a5ab8a388af946bdf73a4141e32abe).
Closing and recreating it now would fragment its numerical provenance,
review history and manuscript checks without an independent implementation
reason. Keep corrections in that PR; no PR per trivial adjustment.

The [GNN methods audit](../../manuscript/supplement/gnn-methods-audit.md)
adopts CFL-GNN-LIT-ARCH-2026-02 with reservations: explain and audit the
existing model, reconcile relevant references critically, and reuse existing
records. It does not authorize architecture comparison, tuning, new seeds,
training, inference, solving or modifications to frozen evidence. The current
author instruction authorizes documentary/manuscript edits on GitHub despite
the attached historical mandate's read-only repository wording. Zotero remains
read-only; absent references are optional candidates.

The [Human–AI register](../../manuscript/supplement/human-ai-traceability.md)
supports a bounded traceability account. A full Appendix B is deferred until
its definition, primary human decisions, relevance and author approval exist.
IIEA-S is not a fourth scientific contribution or a causal productivity result.

## Sprints executed concurrently, with explicit completion gates

| Sprint | Start / delivery target | Work that advances now | Completion gate / product |
| --- | --- | --- | --- |
| S1 — contract and executive reconciliation | Now; baseline31Oct, maintained through closeout | Consolidate supersessions, single campaign owner, decisions, bibliographic priorities and current evidence boundaries | R2-D1/D7, one coherent plan and dated status; no repeated transfer audit |
| S2 — methods, data and GNN foundation | Now–13Nov | Actual message equations, Gasse adaptation, channels/clipping, hyperparameter origins/gaps, checkpoint identity, root→inference→R/G path, conditional determinism, serial/DDP work | R2-D2/D3/D4 source-linked; manuscript and supplement agree; no claimed architecture tuning or independent generalization |
| S4 — synthesis and specialist review preparation | Now–27Nov for existing evidence; final within five working days after qualified S3 analysis | Map SO1–SO8 and C1–C3 to evidence, retain PR85–88 adverse findings, costs/censoring, draft R2-D8 and author questions | Existing-evidence synthesis can circulate now; final R2-D8 waits S3 and cannot claim unanswered objectives achieved |
| S5 — article, figures, references and supplements | Now; first scientific pack13Nov, integrated draft27Nov, complete pack15Dec | Improve narrative for OR readers, claim-specific references, reconcile numbers already available, table/figure inventory, availability/rights and IIEA-S disposition | All published numbers traceable; CPU placeholders remain pending until qualified; final render and coauthor review |
| S3 — existing CPU campaign closeout | Triggered only after all known jobs terminal and final authorized return; aim analysis by30Nov | Prepare review checklist and final-table schema now; execution of collection/CPU analysis waits the event | All60 planned cells reconciled, failures/censoring/missingness visible, metric eligibility qualified, original checkpoint/parameters unchanged |
| S6 — final review and submission | Prepare checklist now; author revisions16–31Dec; editorial/submission1–14Jan | Reserve review time and assemble journal checklist without premature publication | Full cross-artifact audit, author scientific/editorial approval, separately approved merges/release/submission |

S1/S2/S4/S5 are parallel workstreams, not a requirement to wait for their old
calendar windows. Only final CPU-dependent S3 execution/analysis waits the
campaign. S4's final synthesis and S5's complete version necessarily depend
on S3 even while their existing-evidence work advances.

The15December target is conditional on a qualified CPU return early enough
for the mandatory audit and author review. If no usable return is available
by30November, raise a dated schedule/interpretation decision to the author:
continue awaiting the existing campaign or adjust the review milestone.
Do not solve this risk by retrying, cutting the audit, dropping adverse cells
or inventing results. January is reserved primarily for editorial revision
and submission, not new experimental exploration.

## R2 deliverable coverage and immediate acceptance criteria

| Product | Existing / prepared coverage | Still needed for closeout |
| --- | --- | --- |
| D1 contract | PR91 R3 and this dated scheduling update | Keep supersessions and scientific question explicit |
| D2 methods | R3 methods plus GNN equations, B/R/G path and upstream comparison | Coauthor assessment of explanatory adequacy and bounded novelty |
| D3 data/model | Admission54/90, split34/10/10, features and original checkpoint bindings | Final package rights, availability and exact published artifact inventory |
| D4 determinism | Conditional assessment, actual inherited Method=−1, seed/cap/time distinctions | Qualify any additional effective parameters available in existing final logs; no rerun |
| D5 efficacy | PR86 principal150seed42 rows and archived historical outcomes | Qualified60-cell PR89 return and eligible parent-level comparisons |
| D6 performance/economics | Existing CPU scenarios and completed GPU negative-quality result | CPU12h clocks/accounting and bounded synthesis; no imputed energy/cost |
| D7 plan | Accelerated S1/S2/S4/S5 and dated gates here | Maintain risk-based checkpoints and15Dec target |
| D8 specialist assessment | Inputs prepared from existing audits and critical literature | Final post-S3 synthesis and human scientific review; not complete today |

## State, provenance and responsibilities

Codex receiver retains exclusive responsibility for reconciliation, analysis
and documentary closure of PR89. The researcher performs every HPC access
and any PowerShell/SCP transfer with their own password. New remote files
must use existing discodatos storage/directories, not home.

The latest human-provided partial report on28October states:
job3713 COMPLETED, elapsed12:01:05, ExitCode0:0, AllocCPUS8,
batch MaxRSS16050788K;3714 RUNNING at08:03:49, AllocCPUS16;
3715–3734 pending according to the author. The exact capture clock is not
supplied. This is not a fresh agent query, a full60-job snapshot, a receipt
mapping or a solver-quality result. Earlier jobs cannot all be classified
by subtraction. No final CPU return has been collected/qualified here.
The26October full snapshot remains historical and is preserved.

The original installed source remains9ab7823c6886d19e9ec865141a1cd35b3c3c16e5.
Seed42, MINIMIZE, B/R/G↔M0/M1/M2, five thread caps, original roots/starts/
checkpoint and M4/M12 limitations remain frozen. No automatic retries,
cancellations, dependency changes, new experiments or merges.

## PR strategy and independently reviewable next deliveries

- **PR92 now:** methods foundation, critical references, descriptive provenance,
  current evidence synthesis, manuscript/supplement preparation, updated plan.
  Existing paper title/question and C1–C3 remain working text for coauthor
  judgment, not a novelty verdict derived from a literature count.
- **PR89 later:** receive through its installed collector/receiver only after
  all known jobs are terminal, reuse any existing return, reconcile every
  planned cell and document scientific closeout on its original source.
  A failure receives read-only diagnosis and a specific human decision.
- **Integration after an authorized PR89 merge:** bring its reviewed receipts/
  analysis into PR92, keeping raw evidence and scientific qualification distinct.
  If merge order causes conflicts, resolve documentary integration without
  editing installed campaign code.
- **Separate later PR only for an independently justified scope:** for example,
  a final audited release/package after the integrated article is approved.
  Decide its branch/number from the then-current repository; no invented PR93
  or additional maintenance PR is required today.

PR92 remains draft until the stated completion criteria are satisfied.
No merge is performed or auto-enabled. Publishing Pages, final release and
editorial submission each retain explicit human approval.

## Review pack for early circulation

Prepare a single reading order, without sending messages to coauthors:
(1) current CI manuscript preview; (2) concise scientific question and
contribution/limitation map; (3) GNN/solver-method audit; (4) existing numerical
claim manifest and figures; (5) author decision list and IIEA-S register.
The working repository supplement is not silently represented as already
included in the editable LaTeX ZIP.

Ask coauthors to assess the relation between label prediction and solver
utility, adequacy of the dependent RELAX comparator, fixed2×32 model limits,
historical test exposure, negative GPU quality finding, and defensibility
of C1–C3. CPU12h numbers remain absent until qualified. The author controls
actual circulation; preparing material does not authorize messaging others.

Editorial checks retain the pinned Elsevier template, author identities,
AI declaration, required highlights, exact citation resolution and20-page
body budget. The official current COR guide must be rechecked before final
submission. A403 from the publisher is not confirmation of compliance;
the pinned template and existing checklist remain the working baseline.
The [official Elsevier journal description](https://shop.elsevier.com/journals/computers-and-operations-research/0305-0548)
was accessible and checked: contribution, meaningful numerical comparisons,
reproducibility and scientific English remain substantive author-review gates.
Template compliance alone does not establish journal suitability.

## Mandatory final audit — prepared now, executed after CPU qualification

| Area | Scope and evidence | Exit criterion |
| --- | --- | --- |
| A — repository/software | Architecture, actual B/R/G paths, frozen executors, checkpoints, configurations, environment, artifacts, tests and reproducibility links | Published methods and supplied package describe the same version; missing runtime fields declared |
| B — experiments | PR85–89 parents/cells, primal/dual/gap, sensitivity, censoring, time/target/cost scopes, GPU quality and failed/partial outcomes | Every planned cell accounted for; named metrics eligible; no pseudo-replication or unsupported exact claims |
| C — article | Question, objectives, literature gap, contributions, methods, all results, discussion and conclusions | Each scientific statement has evidence and an appropriately bounded interpretation; coauthors assess sufficiency |
| D — appendices/supplements | Every displayed number, table/figure generator and hash, references, model identities, rights, availability and declarations | Cross-artifact reconciliation complete; no pending result promoted; appendix decision documented |

Use proportional T1 source/link checks, T2 relevant manuscript/provenance/
archive tests, and T3 final-head HTML/PDF rendering with visual inspection.
These checks address their specific risks; none substitutes for scientific
review. Reuse completed audits and reopen only concrete new discrepancies.

## Risks and human decisions

The primary schedule risk is remaining serial CPU duration and afterok
blocking on failure. Principal scientific risks are exposed parents,
fixed-model/no-ablation limits, numerical M4/M12 restrictions, approximate
labels and preparation-dependent R. Editorial risks are overlong exposition,
incomplete rights/availability, and treating a draft review pack as final.

Scientific coauthor decisions: final novelty/title/C1–C3 wording, sufficient
limits for the fixed architecture, Appendix B inclusion, rights/declarations.
Operational interventions are needed only when the author must query/collect
on HPC or transfer via PowerShell. Merge and submission decisions are
requested when the concrete reviewed result is ready, not for routine edits.

**One immediate operational action:** complete and verify the source-linked
methods/manuscript update in PR92. Continue the existing CPU campaign unchanged.
