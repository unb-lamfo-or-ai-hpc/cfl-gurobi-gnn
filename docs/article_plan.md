# Article plan

Approved planning revision: 2026-10-10. Target: submission by December 2026,
preferably by 11 December with the remainder of December as contingency.
Implementation/resource authorizations remain separate.

## Proposed narrative

1. Introduce CFL, the computational bottleneck, and the gap between generic
   MILP solving and learned graph guidance.
2. Define the parent-level dataset, graph construction, labels, split, and
   leakage controls before presenting results.
3. Describe the GNN architecture and training protocol, including the two
   hidden layers of 32 units only as a documented hyperparameter, not as an
   unexplained result.
4. Define the three solver arms and distinguish root-relaxation preparation
   from GNN inference and from Gurobi optimization.
5. Report quality, time, preparation cost, CPU thread scaling, GPU allocation,
   memory, and exclusions with tables and figures generated from public
   manifests.
6. Discuss limitations, reproducibility, HPC implementation, and the exact
   claims supported by qualified pairs.

## Required outputs

- cohort/partition table with F/M identifiers and train/validation/test counts;
- descriptive sample table: parents, artifacts, bytes, labels, instances,
  attempts, qualified results, and exclusions;
- three-arm paired solver table by parent and thread cap;
- CPU scaling figure for 1/2/4/8/16 threads;
- mandatory 1-GPU serial versus 4-GPU DDP training-time, speedup, efficiency,
  utilization and final-predictive-quality figures, once qualified;
- preparation-versus-solver-cost figure;
- gap, incumbent quality, runtime, and memory summaries;
- a manifest linking every public row and figure to source commit and receipt.

## Prioritized roadmap

| Sprint / target window | Deliverable | Dependency and acceptance |
| --- | --- | --- |
| C / 10-23 October | Close PR83 limitation; relocate/consolidate PR84; PR85 scientific audit | PR85 scope approved before code; partitions/provenance and mathematical sense established or specific claims blocked |
| D / 26 October-13 November | PR86 three-method CPU comparison; PR87 mandatory 1/4-GPU full training; start PR88 manuscript in parallel | Separate budgets approved; PR85 gates satisfied; matched execution and complete accounting, no presumed speedup |
| E / 9-20 November | Repeatability, uncertainty, end-to-end costs; final tables and figures in PR86/87/88 | Parent-paired analysis, missing/censored data visible, row-to-receipt traceability |
| F / 16 November-11 December | PR88 integrated manuscript, coauthor review, journal formatting and release review | Every scientific claim linked to qualified evidence; numerical and bibliographic consistency; explicit release/merge approvals |

Overlapping windows allow analysis and writing alongside execution; they are
targets, not claims that budgets or results already exist. PR identifiers 85-88
are planned deliverables, not PRs created by this document. Approximate hands-on
effort: PR83 closure 0.5-1 day; PR84 1-2 days; PR85 2-3 days; PR86 3-5 days;
PR87 2-3 days excluding substantive unexpected compatibility work; PR88 5-8 days,
plus coauthor turnaround and HPC queues. The [detailed protocol](research/submission-protocol-20261010.md)
specifies the resource estimates and stopping conditions.

No augmentation, new architecture, broad refactor or hyperparameter search is
required for this minimum article. Four-GPU training is mandatory; eight-GPU
scaling and enlarged cohorts are deferred. Negative/heterogeneous outcomes
remain valid. Poor comparability is not repaired by adding more runs.

## Manuscript evidence inventory

PR88 should begin its introduction, formulation, sample and methods alongside
Sprint D, without filling missing results with anticipated benefits. Required
publication assets are:

1. Population/admission/split table (90 -> 54, 34/10/10) and per-parent descriptive
   statistics: variables by domain, constraints, nonzeros, density, coefficient
   scales, root gap and label quality where qualified; unavailable entries explicit.
2. Checkpoint/normalization/threshold provenance table and predictive metrics
   by parent and difficulty, including the limitation of historically exposed tests.
3. M0/M1/M2 result table; CPU curves for 1/2/4/8/16 threads; quality, certified
   termination or censoring, memory and parent-paired time ratios/uncertainty.
4. Serial/4-GPU DDP table and figures: matched work, full training wall time,
   speedup, efficiency, GPU-hours, resource utilization and final F1/PR-AUC.
5. Preparation/inference/solver/export cost decomposition, cold and cache-amortized
   scenarios, repetition summaries, exclusions/failures and limitations.
6. Machine-readable source tables, vector figures and a claim/evidence index
   binding each row/figure to protocol, commit, source hashes and review status.

## Submission discipline

The manuscript must not call an observation a result when its receipt is
unqualified. Failed or unavailable historical runs are described as limitations.
The article should state the installed environment (including PyTorch and
CUDA versions) exactly as used; package upgrades are not required for the MVP.
The final release should be synchronized to protected `main` only after the
authors review the complete evidence and approve that release PR.
