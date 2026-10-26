# MVP2 R3 — governing contract and completion plan

26 October 2026 · CFL-GNN-SCI-2026-10-22-R3 · deadline: **14 January 2027**.
Products R2-D1 and R2-D7; the evidence map below also tracks R2-D2–R2-D8.
This is a documentary consolidation of existing decisions, not an experimental
authorization, a new preregistration, or a scientific closeout of PR89.

## Authority, supersessions and receipt

The author approved transferring the still-running PR89 campaign on 26 October.
The receiving Codex accepted exclusive operational responsibility after checking
the transfer package, Git identities and a human-assisted HPC status capture.
The former requirement to finish PR89 on the old machine before transfer is
superseded. The previous chat is instructed to remain inactive until at least
16 November unless the author directs otherwise; its inactivity was not
independently inspected. See the [public transfer checkpoint](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/89#issuecomment-6420991852)
and the [author transfer decision checkpoint](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/89#issuecomment-6417273624).

| Earlier condition | Governing decision |
| --- | --- |
| Finish/analyze PR89 on the original machine | Receiver owns collection, reconciliation and closeout while the existing campaign runs |
| December submission target | MVP2 and article submission deadline 2027-01-14 |
| CPU budget still proposed | Separate full CPU approval received 2026-10-20; 60 jobs already submitted once |
| Synchronize main only after final article review | PR90 was specifically merged for review publication; subsequent merges/publication need their own approval |
| Develop from the local clone | Work on GitHub/Codex; local files are temporary transfer/inspection artifacts |
| New remote captures in the home directory | Use the existing data storage, preferably existing directories; no further home writes |
| Main/develop must have identical commit IDs | Preserve their different merge history; do not reset branches to equate IDs |

A statement preserved in a historical proposal does not revoke a later explicit
decision. Original receipts and dated audit documents remain unchanged.

## Frozen scientific and operational scope

Accept the MILPBench CFL formulation except for the author-identified erroneous
MAXIMIZE declaration: always use **MINIMIZE** and preserve files, coefficients,
constants, rows, bounds, domains and feasible region. Do not reopen generator or
economic-mapping certification as a gate. This author decision is not a proof
derived from reported easy maximization of hard instances.

Use B/R/G only as presentation aliases of historical methods M0/M1/M2; never
rename stored IDs. Parent M0 and method M0 are different fields.
See [methods and models](mvp2-r3-methods-and-models.md) and
[metrics and reproducibility](mvp2-r3-metrics-and-reproducibility.md).

PR89 is the already-approved fresh CPU12h campaign: four exposed medium parents
M0/M4/M7/M12 × three methods × physical caps 1/2/4/8/16, seed42, 60 single-solve
jobs, strictly serial. Limits: 43,200 solver seconds, 46,800 job-wall seconds,
65,536 MiB RAM, no GPU; ceilings 720 solver-h, 780 serial reserved-h and
4,836 physical reserved core-h. These are ceilings, not measured use or an ETA.
Reuse the original PR86 roots, graph, predictions, starts and mixed checkpoint.
The newer GPU checkpoints do not replace the CPU checkpoint.

Do not repeat prepare/authorize/submit, installed preflight, roots, inference,
training or solves; change source, matrix, order, parameters, tolerances,
resources or environment; cancel, retry, requeue or extend automatically.
A failed predecessor can block afterok descendants. Diagnose in read-only mode
and request the author's specific decision, preserving all evidence.
Consultation/collection/analysis of this campaign do not require approval of
the same budget again. New experiments or scientific changes need separate
protocol, resource and human decisions.

## Verified identities and status, not future results

| Object | Reference at transfer |
| --- | --- |
| Integration base develop | `e5804a8c6762c2e5f13447e5a16784e5824de801` |
| Main, PR90 review publication | `4e1ac7b691bd90043060b8d96ead2a3ed4f429b9` |
| Installed PR89/public source | `9ab7823c6886d19e9ec865141a1cd35b3c3c16e5` |
| Installed PR89 tree | `69ed16b9635c493161bf620727c9e0a0aee7a7dc` |
| Old-machine local source candidate | `489f8f9ed71237f5cb96e7abab26ee8b6bd7e0dc`; same tree, different commit |
| Plan SHA256 | `48fca37e2cc698f4d35e4850fdd48d8115b36d7f64b97438ded3b9e17dea3dd1` |
| Preflight SHA256 | `b31d5ac2e80a3ae76c3904e197851ce8b42c1bbc92a955212dc277c4cbb252c0` |
| Original PR86 CPU checkpoint SHA256 | `a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028` |

The 26 October full status capture has SHA256
`4a8ab4ec1f3c1c20fdea5cb4cac8a02b07fc12b94f01b664f88cd8dbbaff7797`
and 40,255 bytes. The author ran the identity-gated read-only command and
transferred its output with SCP. Receiver verified bytes, the identity marker,
complete JSON and exactly 60 unique expected IDs. Snapshot: 35 COMPLETED/0:0
(3675–3709), 3710 RUNNING at 11:27:18, 24 PENDING (3711–3734);
submitted=60, unsubmitted=0, terminal=false. This is human-assisted evidence,
not independent receiver SSH access. It is not a live status assertion.
Scheduler completion does not establish a gap, exact optimum, Start acceptance,
job-to-cell binding, or the exact number of optimize calls.
No final return or PR89 scientific result is received by this contract.

Transport verification covered 178 manifest members plus two controls and
1,235 reference-snapshot files against Git blobs. The transfer ZIP SHA256 is
`d437816388d0e5b4cf57a8269db12a5ca8258dca574504024929c348596bdaec`.
The private operational artifacts remain remote. Transport checks and green
software CI do not certify scientific conclusions.
PR90/Pages is an existing review version, not a final release containing PR89.

## Ownership, storage and next intervention

Codex implements authorized analysis/documentation and prepares coherent PRs
against develop. The researcher intervenes on every HPC access and SCP
authentication, decides impediments/scientific changes and approves merges.
Coauthors review interpretation, authorship, declarations and submission.

Work directly on GitHub or Codex. Local files are temporary only. HPC output
uses discodatos (the existing data storage), preferably inside existing
directories. Never edit the installed stage/source, plan, authorizations,
claims or results to adapt this documentation. Do not write further home
captures; do not move/delete the already-created capture automatically.
Use verified absolute remote paths for one-file SCP via local PowerShell;
passwords are entered by the author in the terminal, never stored or posted.
No unattended monitor or parallel campaign operator is established.

While terminal=false, preserve execution and advance independent documentation.
After all known jobs are terminal, including any failures, use the frozen
collector/receiver; verify and reuse an existing return instead of overwriting.
Reconcile all 60 cells, authorization/source hashes, dependencies, claims,
accounting, supervision and documented calls before metric-specific review.
Do not alter raw scientific eligibility flags. No new CLI is needed for this
documentation PR. Never ask for the same CPU budget a second time.

## Sprints and PR boundaries

Windows below are targets; overlap work and advance analysis as soon as its
evidence exists. Do not wait for an artificial date.

| Sprint | Window | Coherent delivery | Acceptance |
| --- | --- | --- | --- |
| S1 | 2026-10-26–31 | Transfer, contract and plan; R2-D1/D7 | One owner, verified references, supersessions and pending work explicit |
| S2 | 2026-11-01–15, may start now | Methods/data/model/reproducibility consolidation; R2-D2/D3/D4 | Implementation-linked methods; provenance and missing fields stated; no repeated experiment |
| S3 | 2026-11-16–30, anticipatable | Existing PR89 CPU analysis; R2-D5/D6 | 60 cells reconciled, metric eligibility, clocks/censoring/M4/M12 visible; applicable tests and final-head CI before Ready |
| S4 | 2026-12-01–15 | CPU/GPU synthesis and specialist report; R2-D8 | SO/C evidence mapping, costs and limitations proportionate |
| S5 | 2026-12-16–31, writing now | Integrated manuscript and supplements | Every numerical claim traceable; complete version for coauthor review |
| S6 | 2027-01-01–14 | Final revisions, approved release and submission | Human text/declaration/merge/publication/submission approvals |

Next PR: this contract and methods consolidation. Complete PR89 separately.
Then prepare one integrated manuscript/supplement PR using existing PR88/90
assets; finish scientific corrections on develop before a separately approved
develop-to-main release PR. Do not reserve PR numbers or create a PR per helper.
Internal planning targets are complete text by 31 December, final approval by
7 January and submission by 10 January, leaving 11–14 January contingency.
Coauthor turnaround and HPC completion remain dependencies, not commitments.

| Product | Location / dependency | State in this consolidation |
| --- | --- | --- |
| R2-D1 revised contract | This document | Documented, subject to PR review |
| R2-D2 methods audit | [Methods](mvp2-r3-methods-and-models.md) | Source-linked formalization reusing prior audits |
| R2-D3 data/model audit | Same methods document and evidence index | Documentary provenance with historical-fit limitations |
| R2-D4 determinism assessment | [Reproducibility](mvp2-r3-metrics-and-reproducibility.md) | Source/documentation assessment, no new repetition |
| R2-D5 optimization efficacy | Existing PR86; PR89 closeout pending | Partial |
| R2-D6 performance/economics | Existing PR86/87; PR89 pending | Partial, bounded costs |
| R2-D7 completion plan | Sprint table above | Documented, dates are targets |
| R2-D8 specialist report | Subsequent synthesis | Pending; this index is not that final report |

These products are distinct from PR88's D1–D6; eight new standalone reports
are unnecessary. [Evidence index](mvp2-r3-evidence-index.json) binds sources and
coverage. Methods/sample definitions and existing GPU negative results can be
written now. The manuscript must not fill pending CPU results.

## Scientific coverage and risks

| Objective | Initial state | Contribution / limit |
| --- | --- | --- |
| SO1 Dataset Construction | Partially covered | C1; admitted 54 of 90, label-quality selection, no hard |
| SO2 Optimization Efficacy | Partially covered | C1/C2; PR86 plus pending PR89, metric-specific numerical limits |
| SO3 Computational Efficiency | Partially covered | C2; comparable eligible pairs only |
| SO4 Robustness | Partially covered; broader robustness deferred | C1/C2; historical repeats do not establish main multiseed robustness |
| SO5 Computational Scalability | Partially covered | C2; CPU caps and one GPU pair, no isolated GPU causality |
| SO6 Computational Economics | Partially covered | C3; bounded measured/reused/amortized costs, missing timers remain missing |
| SO7 Generalization | Independent generalization not demonstrated | C1/C2; historically exposed test parents |
| SO8 Integrated Experimental Assessment | Partially covered | C1/C2/C3; awaits consolidated analysis and human review |

C1 describes the partial-start mechanism; C2 identifies beneficial/adverse
regimes; C3 assesses economics. They remain potential contributions requiring
verified literature positioning. Class-aware causal benefit is not isolated.

Principal risks: queue/duration heterogeneity, blocked afterok descendants,
M4/M12 numerical sensitivity, small exposed samples, incomplete cost coverage
and coauthor turnaround. The obsolete 78h23m extrapolation is discarded.
MVP2 can close with negative/censored results and explicitly accepted limits.
Generalization, multiseed robustness, hard instances, new checkpoints and
class-aware ablations are not mandatory success conditions.
P1–P5 after 14 January remain planned, not execution-authorized.
IA assistance transparency is required as applicable; a separate Human–AI
study is optional and outside the critical path.

## Validation and limits of this PR

Read existing source/receipts; reconcile aliases, counts, checkpoint identifiers,
metric encodings and relative links; compare the final Git tree to the base.
The permitted diff is documentation and its evidence index. Executors, training,
configs, raw evidence, checkpoints, figures, manuscript and workflows stay intact.
No independent historical fit replay, checkpoint deserialization, private-vector
audit or new experiment is performed.

Existing evidence/manuscript workflow path filters do not select this
documentation-only diff. Do not claim a new green CI run when none is triggered,
or add unrelated work just to trigger it. Record final-head documentation checks
and the applicable/skipped checks explicitly in the PR. T1 is targeted source
and link review; T2 checks reference identity and preservation against the base;
T3 verifies the published final head and actual check coverage. A new scientific
claim or executable change would require its affected regressions before Ready.
