# MVP2: accepted results-first delivery plan (9 October 2026)

Approved by the operator in chat. This updates scheduling and presentation
requirements, not historical evidence or execution authority. No new HPC budget,
training run, solver call or merge is authorized by this document.

## Sequence and output requirements

| Delivery | Work and exit condition | Figures and tables |
| --- | --- | --- |
| PR80 / C1 | All 54 parents reviewed, four initial forwards, fixed representation and E0 handoff | Parent/role and descriptive tables; sample, CPU pilot, predictive and inference-cost figures |
| E0 advanced | Evaluate existing frozen models before new training; reconcile historical coverage first | Per-parent three-method table, paired quality/time, start acceptance and preparation/inference/solve cost |
| C2 | Easy-only versus mixed learning under matched rules; reuse compatible runs, train only what is missing | Full hyperparameter/sampling/compute tables; learning curves and predictive metrics by parent/class |
| C3 | 1-GPU versus 2-GPU DDP; 4/8 only with feasibility and bounded budget | Time, speedup, efficiency, GPU-hours, utilization/communication and peak memory; predictive quality alongside cost |
| D | Truly different train-parent-only MILPs, independent labels, equal sampling influence | Proposed/valid/rejected derivatives and labeling cost; structural diversity and learning quality/cost |
| E1/E2 | Unguided, matched root-LP and GNN starts at 1/2/4/8/16 CPU thread caps; qualified hard expansion | Paired per-run table; quality/time/resource curves, censoring, failures and whole-pipeline cost |
| F (parallel, then final) | Scientific synthesis, numerical/editorial/coauthor review, reproducible release | Main-paper figure selection, complete supplement, claim-to-source mapping and presentation |

Planning target: finish PR80 plus six integrated PRs (E0,C2,C3,D,E1/E2,F),
not one PR per helper. Numbers after PR80 are not reserved. Split a delivery
only if genuinely needed; do not expand experiments just to fill a PR quota.

## Comparison rules

CPU methods share parent/seed/thread cap/budget. Distinguish configured Gurobi
threads, physical affinity, logical Slurm allocation and measured process CPU.
GPU comparisons preserve global batch, actual parent sampling mass and optimizer
updates; equal epoch counts alone are insufficient. Do not report Gurobi GPU
acceleration. Record exact effective optimizer parameters, precision, device,
software, checkpoint, threshold and preprocessing provenance.

Separate preparation, inference, start construction, main solve and verification.
Include failed allocations in campaign cost, deduplicated by job. Do not equate
allocated hours with measured active CPU/GPU time. Preserve memory scopes.
For censored targets, show non-attainment and observation horizon, not fabricated
target time or ordinary speedup. One seed/two parents cannot support population
significance. Negative findings remain results, not automatic retry triggers.

Sample roles never change retrospectively. Known validation/test outcomes must
be disclosed when revising a policy. Dimensionality reduction is an explicit
training-only-fit ablation with an out-of-sample rule; no baseline replacement
or claim of implemented Vargas-Perez work without verifying its applicability.

## Reproducible publication outputs

Each delivery includes machine-readable CSV/JSON, source hashes, executable
generation code, figures in SVG/PDF plus presentation PNG, and readable captions.
Captions state population, units, conditions, exclusions and limitations. Keep
old MVP1 outputs separate from new MVP2 evidence. Regeneration should not need
an HPC solve or undocumented manual spreadsheet manipulation.

F proceeds in three review passes: scientific coherence; numerical agreement
between text/tables/figures; reproducibility/editorial/coauthor checks. Make a
claim-to-evidence index before final submission. Select a compact main-paper set,
retain full data tables and additional figures in supplementary material. A new
Spanish coauthor presentation should explain the question, sample, methods,
results and remaining decisions, not enumerate every engineering PR.

## Current next step

Job3503 completed the installed C1 audit and initial forwards. See the
[closure review](pr80-closure-job3503.md). No repeat of jobs3501–3503 is needed.
E0 remains a separate delivery: reconcile the eight parents missing from the
published solver table, bind exact models/parameters and freeze admitted costs
before any new solver submission. No 30-hard campaign or 8-GPU training is implied.
