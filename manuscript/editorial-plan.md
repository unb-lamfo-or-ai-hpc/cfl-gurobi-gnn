# Scientific and editorial revision

## Reader-only publication boundary — 29 October 2026

The author requires article and appendix/supplement prose to address future
journal readers only. Internal review instructions, pending integration,
campaign scheduler status, dates, approvals and resource decisions belong in
GitHub research records and PR checkpoints, never in that prose.

The registered reader texts are the article and supplement README, methods
explanation, configuration reference and sensitivity discussion. The latter
retains scientific limitations and future research questions, while its full
prospective execution/budget discussion is preserved in
[internal sensitivity planning](../docs/research/mvp2-sensitivity-planning.md).
The [coauthor brief](../docs/research/coauthor-review-brief.md) and
[Human–AI/Appendix B decision register](../docs/research/human-ai-traceability-review.md)
are moved to docs/research with their evidence and limitations intact.
No new Human–AI appendix is promoted.

The article no longer narrates PR/job progress or reserves hidden editorial
extension text. It states the scientific scope of the reported observations.
No final CPU12h quality, timing or cost result is supplied. All original
scientific data, checkpoints, configurations and the installed campaign stay
unchanged. The [29 October scheduler transcription](../docs/evidence/pr89/status-20261029-author.json)
records the human-supplied partial snapshot separately.

Temporary files are local only, in the writable conversation directory under
the user's .codex profile. The literal alternative profile-name suffix in the
new message does not exist; the established .codex directory does. The
OneDrive Temp Codex location exists but was not used for writes. A local
write/read probe passed; direct PowerShell DNS for api.github.com failed,
while the GitHub connector succeeded. This is a point-in-time observation,
not a general claim about every sandbox capability. No external desktop app,
remote HPC command, temporary cloud/blob upload or review-PDF export is used.

Source and rendering checks enforce the reader-text boundary without replacing
the integral scientific audit after campaign qualification. PR93 remains draft;
merge, publication and submission still require their own human decisions.
The full final article/annex review remains required.


## PR93 — synthesis and final integration

PR92 was merged into develop with explicit author approval on 28 October
(merge `ac2dccb8bd56af6b03b866db5199d19944b7a28b`). PR93 now targets
develop and remains a draft requiring its own merge approval. The [working assessment](../docs/research/mvp2-integrated-assessment.md)
is the first S4 deliverable, using existing evidence only.

Completion requires: the reconciled 60-cell return with explicit metric
eligibility; the integrated CPU/GPU interpretation and R2-D8 assessment;
updated numerical provenance and consistent tables/figures/prose; an
explicitly packaged scientific supplement with availability/rights resolved;
the integral second-pass audit and final-head verification; and the
relevant author scientific/editorial decisions. PR92's independent first
pass does not close these requirements.

The following sections preserve PR92's delivered scope and earlier review
history. They do not mark PR93 complete or authorize a new experiment.


## Backmatter requirements from author review — 28 October 2026

Before PR93 is ready for merge, retain this order: numbered Acknowledgements,
numbered Declaration of generative AI and AI-assisted technologies in the
manuscript preparation process, then numbered References. Preserve the
approved AI disclosure text. The acknowledgements thank the University of
Jaén (UJA) and the DaSCI Institute for access to the dgx-dasci HPC infrastructure;
they do not add an unconfirmed funding or grant statement.

The manuscript and local Elsevier adapter implement this requirement without
editing the upstream class. Source, HTML and PDF checks cover the order and
numbering; numbered References must still trigger the existing body-page
budget check. No new review PDF is requested or delivered for this change.
The final qualified CPU return and complete audit remain prerequisites for
PR93 closeout; this editorial correction does not authorize its merge.

## PR92 delivery baseline — 28 October 2026

The author requests completion of PR92 now and preparation of the next PR.
PR92 closes the independent methods, evidence provenance and preliminary
coauthor-review stage. The [completion plan](../docs/research/mvp2-closeout-plan.md)
is organized by Sprints and PRs and supersedes the earlier requirement that
this PR wait for the final CPU return.

The [coauthor brief](../docs/research/coauthor-review-brief.md) is the immediate independent
deliverable: working title, question, empirical gap, C1–C3, methods and
limitations, informed by chat 01.04. Preliminary feedback is sought by
15 November through circulation controlled by the authors. No material has
been sent. Its first-pass audit register reuses completed source reviews;
it is not the final scientific gate.

The next draft PR begins the existing-evidence synthesis and any unfinished
independent audit work. Its final CPU integration, R2-D8, article/supplement
and second-pass integral audit await the authorized return and qualification.
The complete manuscript target is 15 December; final approval is intended
by 7 January, submission by 10 January and no later than 14 January.

## Reader-oriented revision and sensitivity decisions

The methods text is now organized around the reader's questions rather than
internal deliverable identifiers. It explains why bipartite messages fit
the MILP structure, separates fixed values from validation-selected choices,
and gives the limits of literature-based hyperparameter justification.
Adam and gradient clipping are supported by their primary references without
claiming that those references validate the exact CFL settings.

The solver discussion corrects an overly broad interpretation of Method=−1:
automatic selection alone does not imply a non-deterministic MIP algorithm.
The manuscript distinguishes observed conditional comparisons from
across-seed robustness. Its conclusions now describe targeted sensitivity
work without presenting it as completed evidence or promising reviewer acceptance.

See the [prospective assessment](supplement/sensitivity-review-plan.md) for
incremental counts, cost boundaries and the conditions for deferral.
A narrow seed study would take priority over a broad architecture grid if
the final claim requires robustness evidence. No new experiment accompanies
this revision, and the CPU-dependent synthesis remains pending.


## Accelerated scientific preparation — 28 October 2026

The [updated S1–S6 plan](../docs/research/mvp2-20261028-accelerated-plan.md)
sets15December2026 as the target for a complete coauthor-review version,
retaining14January2027 for submission. S1/S2/S4/S5 advance concurrently;
S3 waits the qualified return of the existing campaign, and final S4/S5
synthesis remains dependent on it. PR92 delivered the independent stage;
PR93 now carries final integration.

The [GNN audit](supplement/gnn-methods-audit.md) supplies source-linked
architecture, hyperparameter, serial/DDP and solver-interface reconciliation.
The article now includes actual message equations and concise distinctions
between GCN, GraphSAGE and GAT/GATv2, plus the task-specific value and limits
of the coauthors' opinion-dynamics paper. Five references are added because
they support these statements, not because every Zotero item must be cited.

The [IIEA-S decision register](../docs/research/human-ai-traceability-review.md) recommends
a bounded traceability account; a full Appendix B remains conditional on
a stable definition, primary decision evidence and coauthor approval.
The agreed AI declaration and author identities remain unchanged.

An early review pack uses the current manuscript preview, existing claim map,
methods audit, figures and explicit author decisions. Preparing it does not
authorize sending it to coauthors. CPU12h numbers remain pending.
The scientific priority is explaining the fixed model and defensible claims,
not proposing an unapproved architecture search. See the plan's mandatory
A–D audit and T1/T2/T3 exit criteria.

## Current integrated manuscript — 27 October 2026

PR91 is merged in develop at `6bb374aae5a5ab8a388af946bdf73a4141e32abe`.
The [R3 contract](../docs/research/mvp2-r3-contract.md) governs completion by
14 January 2027. This editorial branch begins the integrated manuscript while
PR89 remains in progress. It is not the final specialist report or a
submission-ready article.

Current changes reconcile B/R/G presentation with historical M0/M1/M2,
first optimal root-node capture, G-dependent R support/one counts, historical
batch1 versus matched GPU globalbatch4, and the authorized pending CPU campaign.
The immutable historical publication archive, PR86/87/88 receipts and existing
figures are reused. No pending PR89 quality or time result is inserted.

### Working claim-to-evidence map

| Claim / article location | Existing evidence | Qualification and next dependency |
| --- | --- | --- |
| B/R/G partial Start; Proposed method | [R3 methods](../docs/research/mvp2-r3-methods-and-models.md), [selection source](../src/cfl_gnn/experiments/pr58_guidance.py) | Implemented mechanism; not a causal class-aware ablation |
| Root capture and original checkpoint; Offline graph learning | [Root preparation](../scripts/evidence/pr86_root_preparation.py), [checkpoint table](../docs/evidence/e0/pr85/checkpoints.csv) | First optimal root-node event; original mixed CPU weights, not later GPU weights |
| Admission and partitions; Instances / Design | [PR85 closure](../docs/research/pr85-closure.md), [R3 model/data audit](../docs/research/mvp2-r3-methods-and-models.md) | 90 candidates, 54 admitted, 34/10/10; label-quality selection and exposed tests |
| Main CPU coverage; MVP2 principal analysis | [Main summary](../docs/evidence/methodology-20261019/summary.json), [PR86 final review](../docs/research/pr86-final-analysis.md) | 150 seed42 rows, 97 reported targets/53 censures, 30 sensitive M4/M12; not exact certificates |
| CPU scaling and preparation costs; MVP2 / Discussion | [D1 metrics](../docs/research/methodology-20261019/D1-protocol.md), [PR86 final assets](../docs/evidence/pr86/final-210/README.md) | Eligible matched targets and stated cost boundaries; no complete cold job cost |
| GPU speed/quality; Matched training | [PR87 review](../docs/research/pr87-completed-pair-review.md), [PR88 figure manifest](../docs/evidence/pr88/gpu/manifest.json) | One seed; loop2.167x/job1.831x, F1 loss0.032468, increased assigned GPU-h |
| Historical six-medium figures/tables | [Imported archive manifest](results/current/pr60_scientific_evidence_manifest.json) | Preserve all original outcomes/labels and historical scope; not the ten-parent principal cohort |
| Authorized CPU12h; Pending campaign paragraph | [R3 source index](../docs/research/mvp2-r3-evidence-index.json), [operational checkpoint](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/89#issuecomment-6450594964) | In progress; final return, 60-cell reconciliation and named metric review pending |
| C1/C2/C3 and SO1–SO8; Discussion / synthesis | [R3 coverage](../docs/research/mvp2-r3-contract.md), [D5 matrix](../docs/research/methodology-20261019/D5-contributions.md) | Mechanism, conditional regimes and bounded economics; original literature positioning and final synthesis pending |

This map is an editorial work product reusing prior audits, not eight new
reports or a new scientific promotion. R2-D8 remains pending integrated
results, specialist questions and human review.

### Independent work completed while PR89 runs

The [working supplement](supplement/README.md) separates population/evidence
chains, clock/cost conventions and remaining integration decisions. Its
[machine-readable claim map](supplement/claim-evidence.json) binds 17 existing
principal CPU/GPU claim groups to four public source files with hashes and
unambiguous selectors. The source gate verifies the corresponding displayed
values and rejects missing claims, clock/averaging substitutions and invented
pending results. Coverage is stated explicitly; this is not complete scientific
review or a final journal supplement. Article prose, figures, raw evidence and
the installed PR89 source are unchanged by this additional step.

### Completion criteria for PR92's independent stage

1. Provide the readable fixed-model methods, implementation-linked caveats
   and existing-evidence claim map without promoting pending CPU results.
2. Complete the preliminary coauthor brief and record the first-pass audit
   coverage, limitations and unresolved human questions.
3. Keep one current Sprint/PR plan with D0 separate from metric qualification,
   two audit passages and all additional experiments outside current Sprints.
4. Pass applicable final-head source/manuscript/archive checks and rendering;
   reuse earlier visual review only where the render inputs remain unchanged.
5. Prepare the next draft integration PR with explicit dependency on PR92.
   Mark PR92 ready and request merge authorization; no merge or publication
   is included in this stage.

The final manuscript integration criteria move to the next PR: qualify the
60-cell return, finish the principal CPU/GPU interpretation, reconcile SO/C
coverage and all repeated numbers, package the scientific supplement, perform
the complete audit and obtain the necessary author/editorial decisions.
These are not declared complete by PR92's readiness.

## Historical editorial plan — original text preserved

The dated text below describes the earlier six-medium archive and its
selection/metrics. Its population and checkpoint are not substituted for
the later PR86/87/89 cohorts or checkpoints.


Target: **Computers & Operations Research**. The alternatives considered were
**European Journal of Operational Research** and **Expert Systems with Applications**.
Journal suitability is an editorial judgment, not an acceptance prediction.

The article addresses whether supervised bipartite GNN predictions produce
useful nonbinding partial MIP starts for medium CFL instances. It distinguishes
offline learning from online solver application, predictive evaluation from
optimization evaluation, and descriptive evidence from confirmatory inference.
It is written for external readers, without development-history narration.

## Organization

1. Problem, motivation, and a precise research question.
2. Parsimonious L2O, graph-learning, and primal-guidance positioning.
3. Mathematical model convention, graph features, supervised prediction,
   and class-aware partial-start construction; an offline/online diagram.
4. Parent-level splits, distinct populations, validation qualification,
   comparators, budget, information boundaries, and censoring.
5. Actual training/validation curves together, pooled and parent-macro
   predictive metrics, all solver-test outcomes, influence, and timing scope.
6. Regressions, negative pilot, uncertain labels, selection bias, and
   incomplete objectives; controlled follow-up experiments.
7. Reproducibility, availability, template rights, and the agreed AI declaration.

## Additional reference positioning

- Bengio, Lodi, and Prouvost (2021), DOI
  [10.1016/j.ejor.2020.07.063](https://doi.org/10.1016/j.ejor.2020.07.063):
  hybrid learning/optimization and distributional generalization.
- Qu, Dong, Wei, and Shang (2026), DOI
  [10.1016/j.cor.2025.107290](https://doi.org/10.1016/j.cor.2025.107290):
  autoencoder-derived restrictions, distinct from nonbinding starts.
- Goerigk and Kurtz (2025), DOI
  [10.1016/j.cor.2024.106886](https://doi.org/10.1016/j.cor.2024.106886):
  learned scenario initialization, not variable-value prediction.
- Zhang, Chen, Yang, and Zeng (2026), DOI
  [10.1016/j.eswa.2025.129924](https://doi.org/10.1016/j.eswa.2025.129924):
  structured cut selection, not supervised assignment prediction.

Metadata were checked against publisher/Crossref records; positioning uses
public abstracts and available author versions. No inaccessible full text
is claimed to have been reviewed. These citations are selected for relevance,
not merely journal membership. Gasse et al. (2019), arXiv version 3, remains
the required architectural reference; its branching task is not described
as our assignment-prediction experiment.

## Evidence boundary

Current sources comprise 13 immutable publication files, imported from the
author-supplied archive. The selected checkpoint is epoch 34, not epoch 100.
The 54-parent predictor has 34/10/10 graph partitions; optimization validation
and test each use six medium parents. Medium 9 and 20 lack admitted graph-test
labels, but retain their frozen optimization-test role. No descendant can
cross its parent's split. Millions of variable targets do not enlarge the
six-parent optimization sample.

The favorable median (-1.164 percentage points) is the primary descriptive
summary. Influence diagnostics accompany the mean, without replacing the
frozen cohort. Matched synthetic augmentation, hard generalization, additional
seeds, full 90-parent coverage, and network-science visualization remain
future work. Missing online-cost components remain unavailable in the
transferred publication evidence.
