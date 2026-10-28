# MVP2 evidence supplement — working repository material

27 October 2026. Governed by the [R3 contract](../../docs/research/mvp2-r3-contract.md).
This working supplement supports review of the integrated article. It is not
a new experimental return, a final journal supplement or the R2-D8 closeout.

## How to read this material

Start with the article for the research question, methods and findings.
The [methods explanation](gnn-methods-audit.md) provides the reasoning behind
the fixed model, hyperparameters and solver interface. It also explains why
a conditional observed comparison differs from a claim of robust superiority.

Use the numerical provenance sections below to trace a displayed result to
its source. The historical publication archive, principal CPU analysis and
matched GPU pair have different populations and measurement boundaries.
The pending CPU campaign has no final results in this supplement.

The [sensitivity assessment](sensitivity-review-plan.md) concerns limitations
and future work: options B–E and its shorter diagnostic design are outside
the current Sprints. Option A is the existing study's completion. Prospective
counts and resource ceilings are not execution authority.

The [Human–AI register](human-ai-traceability.md) supports the authors'
Appendix B decision. It is an internal review aid, not an additional
experimental result or an approved journal appendix.

The [closeout plan](../../docs/research/mvp2-closeout-plan.md) identifies the
remaining qualification, synthesis, writing and audit tasks. A complete
coauthor version is targeted for 15 December; final submission remains
14 January. The current working documents must be selected and packaged
explicitly before they are described as the journal supplement.

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

## Machine-readable numerical provenance

[claim-evidence.json](claim-evidence.json) binds 17 principal CPU/GPU claim
groups to four existing public files. Each source has a commit, Git blob
identity and SHA256. JSON pointers select named fields; CSV selectors require
exactly one row with the stated clock, checkpoint, scope and averaging.
The only transformations are sign, percent conversion and displayed rounding.
The article section and text template bind the source value to its prose/table.

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
existing Manuscript CI. This repository material is linked from the editorial
plan and README. It is not included in the current editable LaTeX ZIP or
published to Pages by this PR; final journal supplement packaging remains pending.

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

## Editorial work still requiring evidence or decisions

- Integrate the CPU closeout, eligible parent pairs, cost boundaries and all
  adverse/censored outcomes before final CPU/GPU synthesis.
- Complete the C1/C2/C3 and SO1–SO8 assessment and specialist R2-D8 report.
- Confirm redistribution rights, data-availability wording, declarations
  and final supplement/package contents with the authors.
- Complete final rendering, coauthor review and separately approved release
  and submission. A green CI run does not close these dependencies.
