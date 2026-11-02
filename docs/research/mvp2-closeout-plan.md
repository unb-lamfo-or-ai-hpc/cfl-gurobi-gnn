# MVP2 completion by Sprints and pull requests

Revised 1 November 2026. This is the current delivery plan, incorporating the
author's PDF instruction and the completed four-point M12 audit. It replaces
older operational schedules on this page; their rationale remains in the
[previous version](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/94d322ab25b52a61cc699d60e8a980be50d6f0ce/docs/research/mvp2-closeout-plan.md).
The approved scientific contracts, identities and archived receipts remain intact.

## Current position and governing boundaries

PR93 is a draft targeting develop. PR89 remains open at frozen source
9ab7823c6886d19e9ec865141a1cd35b3c3c16e5. There are 54 received and reconciled
CPU12h cells out of 60. The author's latest snapshot, without a query timestamp,
reports 3729–3733 COMPLETED and 3734 RUNNING at03:08:51. A completed scheduler
job is not a received result. The [terminal-tail collector](runbooks/pr89-terminal-tail-collection.md)
is ready for the author's CLI execution when the remaining jobs are terminal.

Keep MINIMIZE, seed42 and the original five caps, method order, resources,
checkpoints, starts, parameters and source throughout PR89. No retry, new solve,
training or changed tolerance is introduced by this plan. Every HPC or local
PowerShell operation requires the author; all merges, publication and editorial
submission retain specific approval.

The approved extension is a separate study: ten medium plus six easy evaluation
parents, with solver seeds42/43/44. Its planning approval is already recorded;
do not ask for that approval again. Execution remains unreleased until the
concrete manifest, resource accounting and author's CLI intervention. Training,
root-method, tolerance and hyperparameter ablations remain future work, rather
than implicit additions to the extension.

**Do not generate or open new article/appendix review PDFs in Codex until the
complete PR89 experiment has been integrated, unless the author explicitly requests an earlier review PDF.** Completion means all 60 cells
have explicit reconciled dispositions and the scientific interpretation is
updated; it does not mean every solve succeeded. If returns remain unavailable,
record the evidence and obtain the specific human disposition before closing.
Only then compile, verify and present two separate PDFs in Codex tabs: article
and appendices. Source editing and non-PDF checks can proceed now.

## What M12 changes in the interpretation

The [four-point raw audit](pr89-m12-raw-audit-20261101.md) examined B at two/four
threads and R/G at four threads. Exact rational evaluation of all original rows,
bounds and domains establishes G/4 stored-point primal feasibility. Each
control has one tolerated nonintegral binary; rounding exposes a 0.0000416587
row violation. A single-row interval obstruction excludes every continuous
completion with those rounded binaries fixed. The lower control objectives
therefore are not better exactly feasible integer points.

The 0.009495% and 0.009388% reported G excesses over B/R are not demonstrated
quality loss relative to better feasible integer solutions. A zero internal
gap is not an exact global-optimality proof. The much smaller logged work,
iteration counts and presolved model support a search-effort explanation of
the time contrast, without isolating a causal neural effect.

This result does not certify every M12 point or remove M4's distinct
restrictions. Preserve the raw records and their original flags. Qualification
must separate tolerance-accepted primal values, exact checked primal
feasibility, reported bounds/gaps, threshold attainment, numerical eligibility
and computational cost. Numerical ineligibility is not ordinary time censoring.

## PR93: work that can finish while PR89 runs

1. Reconcile every M12 statement in the article, appendices, captions, claim map
   and project summaries. Use “higher reported objective” where the compared
   point has not been shown exactly integer-feasible. Keep primal feasibility
   distinct from global optimality and from a certified speedup.
2. Complete the independent review of B/R/G implementation, accepted
   formulation, G-dependent RELAX support, frozen predictor provenance,
   parameters, bibliography and historical CPU/GPU cohorts. Reuse completed
   audits whose inputs have not changed.
3. Prepare the 60-cell disposition/metric-eligibility structure and the final
   tables/figures pipeline with the six unreceived cells explicitly pending.
   Do not fabricate observations or treat unknown values as zero.
4. Finish reader-facing prose and appendix consistency. Retain easy final gaps,
   paired-ratio interpretation, identified historical medium cohorts and the
   serial/DDP evidence boundaries. Operational instructions stay outside the
   article and appendices.
5. Prepare the final audit checklist and release description; keep PDFs deferred
   as instructed. Prepare the next protocol PR's offline inventory and exact
   manifest where independent of the final CPU results.

The article and Appendix B already incorporate the scoped M12 findings.
Their latest source validation has 100 manuscript tests plus the source gate;
the offline auditor has 12 tests. The terminal-tail collector has 18 tests.
These are checked properties, not final scientific qualification of PR89.

## PR93: completion gate after the tail receipt

### Reception and cell reconciliation

Receive the six-job private ZIP, verify its hash and member/seal identities,
and reconcile 3729–3734 with the 54 reviewed records. Reuse the sealed 50-cell
and four-cell reviews. Retain a simultaneous full accounting snapshot when
available, together with each snapshot's actual query time and scope.

Every one of the 60 planned cells must retain a disposition: source/model/Start
identity, scheduler and solver statuses, primal, dual, gap, follow-up, observed
thresholds, censoring, cost, missingness/failure and metric eligibility. Preserve
the original records rather than repairing numerical results or retrying them.

D0 remains the reception/reconciliation event for the full planned matrix,
independent of favorable results. It is not silently moved to a later date
when metrics become eligible. Any unresolved absence requires its own recorded
human decision; the schedule is not reset to conceal a block.

### Scoped numerical qualification and scientific synthesis

The tail includes the original six M12 vectors and closed logs at caps8/16.
Check them against the same original model and classify their numeric
properties. Extend exact checking only where the claim requires it and the
artifacts support it. The existing raw audit covers four points, not all 15
M12 cells; other points retain “not independently checked” where appropriate.
If a broader claim needs additional original vectors, prepare only that
targeted read-only collection for the author's CLI. Never infer an unaudited
point's feasibility from another point's equal objective or residual.

Keep M4's existing limitations separate. Distinguish numerical restrictions
from M7's time censoring and from the smaller M0 bound disagreement. Report
eligible denominators for each metric; do not omit adverse or ineligible
cells to improve a summary. Assess primal quality, dual progress, threshold
coverage and cost separately. Logged work values are printed observations,
not recovered terminal attributes or independently repeated measurements.

Complete the final synthesis across the historical six-medium study,
principal one-hour CPU matrix, four-medium CPU12h matrix and matched GPU
training pair. Keep populations, clocks and stopping rules distinct. C2 concerns
conditional optimization effects; C3 concerns computational economics.
C1 remains a methodological obligation. No isolated architectural, class-aware
or causal neural claim follows from these runs.

### Final audit, PDFs and review

After integration, perform the full second audit passage:
- repository/software: B/R/G, runners, dependencies, configurations, checkpoints,
  provenance, relevant tests and reproducibility boundaries;
- experiments: all attempts, identities, primal/dual values, gaps, censoring,
  numerical dispositions, cost and GPU outcomes;
- article: question, literature position, methods, results, discussion and
  conclusions, with every numerical claim traceable;
- appendices/editorial package: repeated numbers, figures/tables, links, hashes,
  declarations, references and separate-document packaging.

Then generate the article and appendices PDFs from the same reviewed source
commit, verify cross-references, numbering, equations, layout and hashes, and
open the two documents in Codex tabs. The earlier independent audit never
substitutes for this final check. PR93 is ready only when the scoped scientific
limitations, final audit, documents and applicable checks are complete.

## Subsequent PRs and merge order

Future PR numbers are assigned when the PRs are opened. Do not reserve numbers
or create separate PRs for trivial corrections.

| Delivery | Scope and exit criterion | Dependency |
| --- | --- | --- |
| PR89 closeout | Record all 60 dispositions and the scientific closeout in the existing evidence/documentary record; retain installed source9ab unchanged | Tail return and qualification |
| PR93 final synthesis | Complete current-study article, separate appendices, R2-D8, full audit and verified PDFs, including the M12 interpretation | Complete PR89 integration |
| Current-study release PR | Synchronize reviewed develop into main, verify the published Pages version and document/PDF identities | Explicitly approved scientific merges and publication |
| [Draft PR94](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/94): experimental protocol/tooling | Freeze the six candidate identities, reuse decision, predictor/preparation bindings, numerical checks, exact job manifest and complete resource accounting | Can be prepared now; execution release requires the finished manifest and author CLI |
| Extension results and manuscript PR | Receive and qualify the approved seed-extension campaign; add difficulty profiles, paired seed analysis and the revised article/appendices | Qualified new receipts, without reopening PR89 |
| Final editorial/release PR, if needed | Incorporate coauthor decisions, close final audit and deliver the exact publication/submission package | Scientific/editorial review and specific release/submission approval |

Git inspection on 1 November shows that PR89's two commits are not ancestors
of PR93 or develop; these branches have diverged. Prepare reconciliation
without changing installed HPC source. The planned approval sequence is
PR89 into develop, then PR93 into develop, then the current-study release to
main. Resolve any source/document conflicts and check the combined result;
do not assume merging PR93 alone integrates PR89's execution implementation.
Every merge requires explicit approval. Preparation of later PRs can overlap;
their experimental results must not be represented as part of PR93's baseline.

The first release may publish the qualified current study before the extension
is complete. It must state the actual four-medium evidence base. A later
reviewed release can incorporate the expanded cohort; neither publication is
automatic.

## Experimental extension: bounded design and resource gate

Freeze the admitted 54-parent learning corpus, 34/10/10 split, CPU checkpoint
a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028 and validation
threshold0.9991843104362488. The extension varies optimizer seeds, not neural
weights. Preserve all parent IDs and original canonical folds.

The existing medium group is M0/M4/M7/M12. The proposed six additions remain
M5/M6/M9/M13/M20/M26, subject to identified-input/preparation review. M5/M6 have
validation/guidance exposure, M9/M20 historical optimization-test exposure,
and M13/M26 earlier audit exposure despite exclusion from admitted training.
Do not call this an untouched external generalization sample or change the
old folds. Do not substitute instances according to favorable outcomes.

| Matched extension at one physical thread and one-hour solver limit | Count |
| --- | ---: |
| Parents: ten medium plus six easy | 16 |
| B/R/G × solver seeds42/43/44 per parent | 9 |
| Total evaluation cells | 144 |
| Historical cells potentially reusable | 90 |
| New solve cells if reuse is compatible | 54 |
| New root preparations if none is reusable, at most600s each | 6 |
| Conditional optimizer-time ceiling:54h solves plus1h roots | 55h |

The [approved planning matrix](mvp2-proposed-job-matrix-20261031.csv) remains
planning-approved with execution_authorized=false and no job IDs. Reuse of
90 historical cells requires model/Start/checkpoint, settings, cap, stopping
rule and clock compatibility. Historical seeds43/44 remain retrospective
secondary evidence, not a rewrite of the original R3 principal analysis.

**Identity-compatible reuse and metric eligibility are different checks.**
The M12 finding does not make a lower tolerance-accepted point an exact
feasible control. Retain those records as numerical diagnostics where
necessary; do not count them in an ineligible paired quality/time estimand.
Publish coverage and exclusions by reason without dropping entire instances.
A three-seed comparison does not itself repair a numerical feasibility issue.

The [PR94 preparation/resource proposal](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/edc8e1914556a81ffaf8b50bbd0d858f17475c9e/docs/research/solver-seed-extension-v1/preparation-and-resources.md) now completes the conditional reservation account:20 jobs,75 serial reserved job-hours,78 physical-core-hours,one V100 GPU-hour and64GiB host RAM per job, with64GiB private working storage proposed. The unchanged55h ceiling is optimizer time, not job duration or utilization. Queue and human-review time are outside the reservation ceiling; financial/energy costs remain unmeasured. These ceilings assume90 legacy observations are retained for their admitted metrics and do not release execution.

The package pins15 reference sources and ten historical artifact chains. Six original-file hashes and the installed source/private input bindings are now checked by the [zero-call installation return](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/264b29246b785bbfa7e1038c12aedde7c64f1599/docs/research/pr94-installation-return-20261101.json). Installed source c623fe8 and plan b41953a8 remain frozen even as documentation advances. All four final-head T3 matrices and the synthetic CPU tensor job passed. New root/graph/score/Start hashes remain null until actual preparation. Real HPC feature/round-trip parity, affinity/cgroup/device/storage admission and the six-root return review remain future gates. The isolated adapter includes bounded collectors, but does not dispatch the54 evaluations. Historical PR86 wrappers/stages are not repurposed; PR89 is untouched.
If reuse changes the actual number of solves, report the revised manifest
and resource impact. Do not automatically rerun the 90 old cells or combine
12h seed42 PR89 endpoints with one-hour seeds43/44 as matched repetitions.

All new result vectors must have a documented model-bound feasibility screen,
with exact/rounded diagnostics where needed and closed logs retained for
numerical attribution. These are checks of existing outputs, not silent
changes to IntFeasTol, Method or other experimental factors. Solver-tolerance,
root-method, hyperparameter and neural-retraining experiments remain separate
future work. A material new numerical block requires a specific decision,
not an unapproved diagnostic solve.

## Difficulty and statistical analysis

Describe empirical computational difficulty, not a theoretical complexity
classification of the ten medium parents. Before new outcomes, inventory
variables/binaries, rows, nonzeros, sparsity and coefficient ranges from
identified files. No new difficulty predictor, pilot solve or forced
small-sample clustering is needed.

After qualification, describe B's target attainment and progress under the
fixed protocol:0.01% attained;10% but not0.01%;10% not attained; unavailable.
Report counts across seeds rather than inventing an intrinsic difficulty
label. Numerical eligibility is a separate axis. A B-outcome-based group is
exploratory and coupled to G/B ratios, not independent proof of a difficulty
interaction.

Pair B/R/G within parent/seed/resource condition. Seeds are nested within the
parent;30 medium parent-seed records are not30 independent instances. Lead
with per-parent primal/dual outcomes, gaps, coverage, censoring and seed
variation. Geometric means of eligible positive paired time ratios may be
secondary summaries; retain unsolved/censored mass and explain exclusions.
Do not use a time limit as a completed time-to-target or run automatic
cell-level significance tests.

## Sprint map and milestones

| Sprint | Work now / remaining delivery | PRs and exit criterion |
| --- | --- | --- |
| S1 — governance | Maintain one plan, received-versus-reported inventory, supersessions and the PDF/merge gates | PR93, then each substantive protocol/release record |
| S2 — methods and experimental readiness | Finish independent methods/appendix review; maintain the verified six-input inventory, prepare frozen-predictor/artifact interfaces, reuse/numerical screens and complete resource manifest | PR93 and next protocol PR; no new training or unreleased HPC preparation |
| S3 — campaigns and qualification | Finish PR89 reception and all60 dispositions; later execute/collect only the separately released seed extension | PR89/PR93 baseline; next experiment/results PRs with qualified receipts |
| S4 — scientific analysis | Finalize M12-aware baseline synthesis, then separate paired seed/difficulty analysis with per-metric eligibility | PR93 and extension results PR; no global-optimum or causal claims beyond evidence |
| S5 — article and appendices | Complete current-study integration, then review PDFs in Codex; incorporate qualified extension and coauthor decisions | PR93 and later manuscript/results PR; reader-oriented argument and auditable numbers |
| S6 — audit, release and submission | Full audit after PR89, renewed checks after any new evidence, coauthor/editorial approval and controlled releases | Release/editorial PRs; explicit merge, publication and submission approvals |

S1/S2/S4/S5 overlap while PR89 runs. New experimental execution belongs to
the later released protocol, not an incidental documentary task. Proportional
T1/T2/T3 checks and CI support review; they are not scientific certification.

| Milestone | Planning target and condition |
| --- | --- |
| Preliminary coauthor feedback | Seek by15November through authorized circulation; do not imply material has been sent |
| Qualified extension receipts | Aim for30November, conditional on exact manifest, resources, queueing and numerical eligibility |
| Extension synthesis and integrated review | Early December, with scope/risk surfaced promptly |
| Complete manuscript and separate appendices to coauthors | By15December2026 |
| Scientific/editorial revisions | December; January principally reserved for approval and submission |
| Final author approval | Intended by7January2027 |
| Submission | Intended by10January2027 |
| Absolute submission deadline | 14January2027 |

These dates are targets, not guaranteed job completion. If qualification or
the extension threatens15December, present the impact and a bounded
current-study alternative to the authors. Do not silently omit adverse
results, add resources, alter the protocol or claim the expanded cohort
before qualified evidence exists. Editorial acceptance is a later outcome,
not an MVP2 sign-off condition.

The immediate operational priority remains receiving the prepared six-job tail when terminal. PR94 installation receipt review and complete source-commit CI are now closed for their stated scope. The next preparation stage uses the existing isolated source and reviewed plan through a separate author CLI after PR89 finishes; it does not reinstall or alter that campaign. New graph/Start identities, live allocation admission and evaluation release remain pending. No new review PDF is generated at this stage.
