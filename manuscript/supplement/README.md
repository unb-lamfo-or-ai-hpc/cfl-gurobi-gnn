# Supplementary explanations and evidence guide

These materials explain how neural predictions enter the facility-location
solver and how the evidence should be interpreted. They accompany the article,
with background for a reader who knows optimization or machine learning without
necessarily specializing in both.

## A route through the material

Begin with [why this GNN and what it can establish](gnn-methods-audit.md).
It introduces the problem, explains graph messages before their equations,
distinguishes training from inference, and follows a prediction into a
partial solver Start. A schematic example explains why R matches G's
assignment counts without copying its variable choices.

Then use the evidence and metric sections below to interpret an outcome.
Prediction agreement, a loaded Start, a gap crossing, terminal solver status
and a timing ratio are different observations. None should stand in for another.

Finally, the [sensitivity discussion](sensitivity-review-plan.md) explains
what is still unknown and which future designs could address it. Additional
solver seeds, root methods, neural settings and the shorter diagnostic design
remain future work outside S1–S6. Prospective counts are not results or
authority to execute.

The [Human–AI register](human-ai-traceability.md) has a different purpose:
it supports the authors' decision about a possible Appendix B. It is an
internal accountability record, not an approved scientific appendix or evidence
that AI improved research quality.

## Claims reconciled before the longer-horizon CPU return

| Question | Interpretation retained | Supporting explanation |
| --- | --- | --- |
| Was the neural configuration shown to be best? | Fixed choices differ from checkpoint/threshold selection on validation data; comparative optimality is not established | [Model and hyperparameters](gnn-methods-audit.md#2-why-these-hyperparameters) |
| Is R an independent LP-only heuristic? | R's support and positive count come from G, so its preparation is neural-dependent | [Relaxation-to-Start path](gnn-methods-audit.md#3-from-a-relaxation-to-scores-and-a-partial-start) |
| Does automatic Method imply non-determinism? | It is not sufficient evidence of the algorithm used; the single-seed study remains conditional on its settings and time limit | [Repeatability](gnn-methods-audit.md#4-what-repeatability-means-for-the-solver-comparison) |
| Does the terminal censoring flag describe every threshold? | A run can cross 10% and later time out; endpoints need separate interpretation | [Endpoint reconciliation](../../docs/research/mvp2-r3-metrics-and-reproducibility.md#historical-endpoint-reconciliation--28-october) |
| Does faster GPU training establish better downstream optimization? | The matched pair has lower selected F1 and greater assigned GPU-hours; the original CPU checkpoint remains separate | [GPU review](../../docs/research/pr87-completed-pair-review.md) |
| Does documenting AI assistance validate a collaboration method? | Traceability and human review differ from a causal evaluation of productivity or validity | [Appendix B decision](human-ai-traceability.md) |

This reconciliation concerns definitions, source-linked interpretation and
completed evidence chains. It supplies neither the pending CPU results nor
the final scientific audit. The
[working R2-D8 assessment](../../docs/research/mvp2-integrated-assessment.md)
sets out the remaining objective- and contribution-specific questions.

## Populations and evidence chains

| Evidence chain | Unit and scope | Reusable source | Interpretation boundary |
| --- | --- | --- | --- |
| Historical publication archive | Six medium optimization-test parents; separate predictive cohort | [Imported manifest](../results/current/pr60_scientific_evidence_manifest.json) and [validation receipts](../validation.md) | Its original figures/tables are historical and retain their own provenance |
| Principal CPU analysis | Ten exposed parents, seed42, 150 method/cap rows | [Main summary](../../docs/evidence/methodology-20261019/summary.json), [rows](../../docs/evidence/methodology-20261019/seed42_main.csv) and [review](../../docs/research/pr86-final-analysis.md) | 97 reported terminal targets, 53 censures; 30 sensitive M4/M12 rows are a subset, not extra observations |
| Matched GPU training | One seed42 serial1/DDP4 pair, ten exposed predictive-test parents | [Scoped review](../../docs/evidence/pr87/jobs3673-3674/review.json), [timings](../../docs/evidence/pr87/jobs3673-3674/timings.csv) and [metrics](../../docs/evidence/pr87/jobs3673-3674/aggregates.csv) | Timing scopes differ; selected F1 decreases; no isolated GPU causality, statistical noninferiority or downstream solver benefit |
| Longer-horizon CPU campaign | Four exposed medium parents × three methods × five caps; 60 existing jobs | [Frozen contract and transfer](../../docs/research/mvp2-r3-contract.md) | In progress; no final return or result table in this supplement |

B/R/G denote historical methods M0/M1/M2. Parent identifiers remain a separate
field. Method/cap rows, binary variables and repeated seeds do not enlarge
the independent parent count. The [methods/model audit](../../docs/research/mvp2-r3-methods-and-models.md)
records the 54-parent admission, 34/10/10 partitions, original CPU checkpoint,
selection rules and historical test exposure.

## Tracing numerical claims to their sources

A displayed value needs a defined population, metric and measurement boundary.
A training-loop speedup cannot replace whole-job speedup, and a selected-model
F1 cannot be replaced by a terminal-epoch F1.
[claim-evidence.json](claim-evidence.json) records these bindings for 17
principal CPU/GPU claim groups using four existing public files.

For reproducibility, sources carry their revision and file-content identifiers
(Git blob and SHA256). Named JSON fields or uniquely selected CSV rows identify
the values, including clock, checkpoint, scope and averaging. Sign conventions,
percent conversion and rounding are explicit; text templates connect the
values to the article's statements and table.

The existing manuscript source gate now verifies source bytes, required claim
coverage, unique selectors and displayed values. A missing claim, changed
source, swapped clock, pooled/terminal substitution or reversed loss direction
fails validation. This is traceability of recorded evidence, not independent
rescoring, model loading or scientific certification.

Coverage is deliberately stated: these checks cover the current principal
CPU scope and selected matched-GPU numbers. Historical tables/figures retain
their imported manifests. Other article numbers, abstract repetition, methods,
rights, declarations and interpretation still require the existing checks
and human review; this manifest does not claim exhaustive automated verification.

The source gate runs through `scripts/manuscript/check_manuscript.py` in the
existing Manuscript CI. The checks do not automatically package these working Markdown files in
the editable LaTeX ZIP or publish them to Pages. Final journal supplement
selection and packaging remain pending.

## Clocks, costs and numerical interpretation

[Metric definitions](../../docs/research/mvp2-r3-metrics-and-reproducibility.md)
separate solver Runtime, monotonic dispatch follow-up, Slurm job elapsed,
queue, shared preparation and training. A serial/DDP4 loop ratio cannot
replace the job ratio. Assigned GPU-hours are allocation × job elapsed;
they are neither active GPU time nor measured energy. R shares G-dependent
preparation, and reused/amortized cost scenarios are not cold measurements.

Threshold fractions 0.10/0.05/0.01/0.0001 correspond to 10/5/1/0.01%.
A first recorded crossing is an observed time; unavailable data, right
censoring and numerical restrictions remain distinct. Horizon brackets
preserve actual timestamps and staleness. No interpolation, extension of
terminated trajectories or replacement of missing values with zero is allowed.
M4/M12 remain visible, with eligibility reviewed separately for named metrics.

## Pending integration of the existing CPU campaign

The pending section of the manifest contains an empty result-claim list,
not zero-filled or synthetic observations. When the authorized final return
exists, reconciliation must bind all 60 planned cells to submitted jobs,
source/plan/start hashes, dependencies, attempt/optimize counts, accounting,
temporal coverage and numerical scope. Partial or failed cells stay visible.
The current metadata and checker must then be updated with that qualified
return and its review; changing only a pending flag is insufficient.

This document introduces no collector, launcher, remote command or alternate
campaign operator. The installed campaign source and sequence remain frozen.
The researcher performs any needed HPC/PowerShell intervention; existing
collection authority does not authorize a new run.

## Editorial status and remaining decisions

28 October 2026 · governed by the [R3 contract](../../docs/research/mvp2-r3-contract.md).
PR92 delivered the independent methods and preliminary-review stage and was
merged with author approval. PR93 now targets develop and remains a draft.
The [coauthor brief](../coauthor-review-brief.md) is prepared for author-controlled
circulation; Codex has not sent it. The [Sprint/PR plan](../../docs/research/mvp2-closeout-plan.md)
retains 15 December for a complete coauthor version and 14 January as the
maximum submission deadline.

These files are working repository materials. A journal supplement needs an
explicit selection of scientific content, qualified results, resolved
availability/rights, final rendering and author review. Planning documents
and internal decision registers are not included merely because they reside
here. R2-D8 and the integral post-qualification audit remain unfinished.

The remaining tasks are to:

- Integrate the CPU closeout, eligible parent pairs, cost boundaries and all
  adverse/censored outcomes before final CPU/GPU synthesis.
- Complete the C1/C2/C3 and SO1–SO8 assessment and specialist R2-D8 report.
- Confirm redistribution rights, data-availability wording, declarations
  and final supplement/package contents with the authors.
- Complete final rendering, coauthor review and separately approved release
  and submission. A green CI run does not close these dependencies.
