# MVP 3.0 scientific development handover

**Date:** 23 November 2026. **Language:** English. **Repository:** unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.

## Read first

Read the [methodological protocol](coauthor-methodological-protocol.md), [decision and budget register](decisions-and-budget.json), [evidence contract](evidence-contract.json), and [Gurobi design note](gurobi-adequacy-and-shared-architecture.md). The [annotation disposition](annotation-disposition-EN.csv) records the treatment of the researcher's 62 PDF annotation records.

Operational evidence belongs in the separate [NPAD transition dossier](../npad-runtime-transition-20261120/README.md). The accepted home-binding receipt completes bounded source, package and license-path admission. The researcher approved the methodological plan on 23 November 2026; Draft PR #99 now includes the requested final GRBLogTools/configuration addendum. Specific merge approval remains pending. PRs #101 and #102 also remain Draft; merges require specific approval.

## Scientific direction and decisions

The population is 66 original CFL instances: 30 easy, 30 medium, and H0/H5/H10/H15/H20/H25. Learning uses the 60 easy/medium parents with 42/9/9 train/validation/test totals. Evaluation uses nine easy/medium test parents and six hard parents: 15 parents and 45 fresh B/R/G cells.

Use native Gurobi 14 and canonical MINIMIZE, preserving the original mathematical data and complete variable identities. Root-relaxation features and integer labels have separate preparation runs. The primary ledger contains 66 root-relaxation, 66 incumbent and 45 evaluation calls: 177 total. Each has a maximum 28,800-second optimisation allowance and a 12-hour job envelope. A concrete release respects the two-job/two-Gurobi-session ceiling.

The primary main-solver profile is Threads=0, Method=-1, ConcurrentMIP=1, Seed=42, MIPGap=0.0001, automatic presolve and default heuristics. Root-relaxation capture uses Presolve=0 and Heuristics=0 with event/cut provenance. MIPFocus=1 is a proposed conditional hard-instance feasibility diagnostic. B supplies an empty external Start; R is proposed as independent relaxation rounding/ranking; G uses the frozen selected predictor. Method comparisons use T_B/T_G and T_R/T_G, with values above one favouring G. Apply the same orientation to target-time, end-to-end and cumulative elapsed-time reuse comparisons; signed savings are comparator time minus G time. Training-system speedup has a separately labelled resource-scaling definition.

The balanced split composition, label-admission tier, equivalent-work schedule, validation-only deployment rule, R/G support settings and conditional diagnostic budget are recorded as the researcher-approved methodological direction for the coauthor packet. Dataset acceptance reviews feature and label coverage before training. Benders is conditional and hard-only, with a per-instance mathematical design, audit, budget and specific approval. DIRECT/BENDERS label provenance remains distinct from root-feature provenance.

## Development sequence

| Sprint | Planned review units | Acceptance |
| --- | --- | --- |
| S1 | Contract, schema, split and native instrumentation | Executable definitions and tested observation/accounting semantics |
| S2 | Root-relaxation capture, incumbent audit and dataset | 66-instance preparation ledger and accepted learning coverage |
| S3 | Serial/DDP training and validation-only freeze | Matched work, predictor and independent Start policies |
| S4 | Partial-Start adapter, paired dispatcher and collection | 45 qualified planned cells on 15 parents |
| S5 | Target, trajectory, quality, resource and cost analysis | Reproducible C2/C3 results and denominators |
| S6 | Article, appendices and reproducibility integration | Coauthor-reviewed synthesis and approved dissemination |

PR codes in the protocol are planning identifiers; GitHub assigns numeric PR IDs when they are opened. Ordinary integration targets develop. Main is reserved for the separately approved release flow.

## Implementation references and preservation

Inspect the historical native adapter, paired solver, root science code, Gasse model and matched-training utilities as design references. Relevant paths include scripts/evidence/pr94_evaluation_solver.py, scripts/evidence/pr94_preparation_science.py, scripts/evidence/pr86_native_model.py, src/cfl_gnn/solvers/paired_partial_start.py and src/cfl_gnn/training/matched_gpu.py. Resolve model paths and function definitions in the selected revision before editing.

Some historical executable workers enforce Gurobi 13-specific guards. S1 establishes a new versioned contract while preserving frozen executed workers and receipts. Historical observations, checkpoints, partitions and numerical restrictions retain their original scope. The discontinued PR98 campaign remains closed.

## Author intervention and scope

The author runs every HPC/SSH/SCP command and uploads sensitive files manually. CLI releases specify exact source, CI, inputs, resources, attempt identities and collection instructions. Merges and publication require specific approval. A handover is not authority for a new experiment, retry, requeue, cancellation or resource expansion.

Existing runtime qualifications cover library operations, three synthetic training updates and a native technical license solve. Home binding covers package discovery and license-path metadata. Full CFL operation with real data, historical-checkpoint loading, real-data DDP, hard-instance memory and performance remain later scoped research work.

The private DELL5300 package contains local/NPAD paths, receipt references, repository snapshots and a starter prompt. The coauthor PDF contains the permanent scientific protocol and development plan only.

## Final logging addendum

S1 includes release-pinned, field-specific qualification of offline GRBLogTools extraction against native logs and worker records. S5 may use the reconciled summary/progress tables, preserving each section's clock origin and missing-field status. Native callback observations and audited vectors retain their measurement roles. The plan is approved by the researcher; concrete implementation/CLI releases and PR integration follow their stated review and approval flow.
