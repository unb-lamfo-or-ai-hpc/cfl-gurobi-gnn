# Legacy-to-current pipeline recovery audit

## Scope and evidence boundary

This audit compares the tested legacy pipeline at commit
`9903c1dc66f65e9497d7faa2d8d4f3ee414a0f42` with `develop` immediately after
PR #40 at commit `9f7da7d206129fcd72c72d1a8d682bf3cf413fde`.

The comparison establishes source-code continuity and identifies integration
gaps.  It does not validate a new dataset, select a solver intervention, or
make the partial MVP scientifically reportable.

Pyomo remains excluded.  The priority implementation uses Gurobi directly,
and the comparison implementation uses PySCIPOpt directly.

## Executive finding

The baseline was reorganized, not removed.  Git rename detection identifies
the original collector, phase-1 audit, graph builder, graph audit, Gasse model,
serial and distributed trainers, evaluator, hint generator, and Gurobi runner
inside the current package.  Several files are byte-identical; the others have
only small packaging or compatibility changes.

The substantive regression is orchestration.  MVP-specific paths created
parallel implementations that do not consistently call the preserved stages.
Consequently the PR #40 output layer summarized an engineering smoke with
zero-valued root-LP features and hard domain fixings instead of the established
baseline.

## Component inventory

| Stage | Legacy path | Current path | Recovery action |
|---|---|---|---|
| Gurobi collection | `src/data_transformation/cfl_gnn_data_generator_v7.py` | `src/cfl_gnn/pipelines/gurobi_incumbents.py` | Canonical Gurobi backend |
| Phase-1 EDA | `src/data_transformation/audit_phase1_eda_v3.py` | `src/cfl_gnn/analysis/collection_audit.py` | Generalize to paired solver EDA |
| Graph builder | `src/graph_transform/build_pyg_dataset_v7.py` | `src/cfl_gnn/graph/build_dataset.py` | Restore Gurobi root-LP authority |
| Dataset audit | `src/graph_transform/test_pyg_dataset_v5.py` | `src/cfl_gnn/analysis/dataset_audit.py` | Reconnect to canonical manifest |
| Graph statistics | `src/graph_transform/pyg_dataset_statistics.py` | `src/cfl_gnn/analysis/graph_statistics.py` | Restore executable stage |
| Graph clustering | `src/graph_transform/pyg_clustering_pca_umap.py` | `src/cfl_gnn/analysis/graph_clustering.py` | Descriptive-only analysis |
| Gasse model | `src/gnn/models/gasse.py` | `src/cfl_gnn/models/gasse.py` | Retain baseline architecture |
| Serial trainer | `src/gnn/train_neural_diving_serial_v5.py` | `src/cfl_gnn/training/serial.py` | Parent-aware manifest input |
| DDP trainer | `src/gnn/train_neural_diving_parallel_v5.py` | `src/cfl_gnn/training/distributed.py` | Reconnect after serial parity |
| Evaluator | `src/gnn/evaluate_model_v3.py` | `src/cfl_gnn/evaluation/model.py` | Restore complete diagnostics |
| Gurobi hints | `src/gurobi_solver/generate_mip_hints.py` | `src/cfl_gnn/solvers/gurobi/hints.py` | Primary guidance path |
| Gurobi runner | `src/gurobi_solver/gurobi_hpc_runner_v2.py` | `src/cfl_gnn/solvers/gurobi/benchmark.py` | Equal-budget benchmark |

The machine-readable version of this inventory is
`configs/audits/legacy_pipeline_recovery_v1.json`.

## Stage 1: data transformation

### What remains valid

The original Gurobi callback collector remains available under the package
namespace.  It still provides the broad evidence needed by the research:
original features, root-node observations, incumbents, solution-pool results,
model status, runtime, objective, MIP gap, and node counts.  The explicit CFL
override to minimization is also preserved.

The newer Gurobi and SCIP parent collectors add valuable provenance:
fresh-process execution, incumbent streams, variable-order hashes, four timing
regions, and gap semantics.

### Current integration problem

The three entry paths overlap but do not share one backend and one population
contract.  They can therefore diverge in naming, time normalization, status
classification, retained vectors, and reuse logic.  The SCIP path is currently
an experiment-specific collector rather than a population counterpart to the
legacy generator.

### Recovery requirement

PR #42 will separate solver-independent orchestration from solver-specific
backends:

1. `gurobi_incumbents` remains the canonical Gurobi implementation;
2. `collect_gurobi_parent_solution` becomes a compatibility CLI over it;
3. the SCIP backend implements the same versioned artifact schema;
4. `collect_scip_parent_solution` becomes a compatibility CLI over that
   backend;
5. a population planner executes Gurobi first, then the matched SCIP arm;
6. valid hash-bound outputs are resumed, while partial or mismatched outputs
   fail closed.

The phase-1 EDA must consume the common index rather than scan ad hoc folders.
Its tables and figures cover coverage, status, censoring, MIP gap, the four
timing regions, incumbent trajectories, objective/bound/nodes, difficulty, and
equal-control paired solver summaries.

## Stage 2: graph transformation

### What remains valid

The bipartite graph builder, dataset class, structural audit, graph statistics,
clustering, and graph X-ray tools are preserved.  The topology remains the
constraint-variable representation used by the established Gasse baseline.

### Current integration problem

The MVP builders treated solver arms as independent graph sources and applied
a zero ablation to `root_lp_relaxation`.  This creates artificial graph copies
and discards a feature used by the original representation.  An incumbent
vector is not a new MIP and must not create a graph by itself.

### Recovery requirement

Gurobi reads every original or synthetic MIP and is the only source of graph
features.  Graphs and labels are separated:

- one original graph can have a Gurobi label view and a SCIP label view;
- each accepted local-branching MIP receives one new Gurobi-built graph;
- each synthetic graph retains its parent, incumbent, operator, and radius
  provenance;
- no graph is emitted for an incumbent until an explicit mathematical MIP is
  materialized from it.

The root-LP feature is mandatory.  PR #43 first audits parity between the
legacy root `MIPNODE` observation and a controlled Gurobi relaxation copy.  It
then adopts one versioned protocol for parents and synthetic MIPs.  Missing or
non-optimal relaxation evidence fails closed; zero is not a fallback.

After construction, `dataset_audit`, `graph_statistics`, and
`graph_clustering` run from the same graph manifest.  Their outputs must expose
parents versus synthetic descendants, difficulty, structure, sparsity,
domains, feature distributions, and provenance.  Clustering is descriptive
and cannot influence parent folds or held-out decisions.

## Stage 3: GNN training and evaluation

### What remains valid

`GasseGNN` is preserved exactly.  The established serial and distributed
training loops and the full evaluator also remain close to their legacy
versions.  The newer parent-level split, descendant inheritance, equal-parent
mass, contract hashing, and held-out protections are methodological
improvements that should be retained.

### Current integration problem

The four-arm smoke trainer is a separate minimal path.  Its two-epoch,
single-training-parent result validates wiring but cannot replace the baseline
training loop or support scientific conclusions.  Its evaluator exposes only
a subset of the original diagnostics.  The subsequent solver benchmark also
changed the intervention from native Gurobi hints to hard domain fixing.

### Recovery requirement

PR #44 reconnects the preserved serial trainer first and requires numerical
parity on a fixed toy/smoke fixture.  The DDP trainer follows only after serial
parity.  Both consume parent-aware manifests and the same Gurobi-built graphs,
while labels remain solver-specific views.  Validation selects checkpoints and
thresholds; test is deserialized once for final held-out evaluation.

The full evaluator must restore epoch histories, BCE, confusion counts,
precision, recall, F1, calibration, ROC/PR diagnostics, per-difficulty results,
and per-parent records.  These neural metrics remain secondary to solver MIP
gap and execution time.

PR #45 restores Gurobi variable hints as the primary intervention and compares
a partial MIP start as a separately named candidate.  PySCIPOpt remains a
comparison solver.  Hard fixing is not part of the recovered primary path.

## Risks and controls

| Risk | Control |
|---|---|
| Duplicate solving logic | Thin CLIs over shared solver backends |
| Graph duplicated by solver label | One graph identity per mathematical MIP |
| Root-LP semantic drift | Gurobi-only parity gate and fail-closed feature |
| Parent leakage | Parent-level folds and train-only descendants |
| Synthetic-parent over-weighting | Equal parent mass |
| Solver comparison confounding | Common parent, budget, seed, threads, and hardware |
| Post-hoc method selection | Precommit on validation; never select on test |
| Smoke results presented as evidence | `development_only=true` until population gate |

## Acceptance boundary

PR #41 passes when its static diagnostic confirms the pinned commits, all
twelve preserved current paths, the Gurobi graph authority, the one-graph-per-
MIP rule, rejection of zero root-LP ablation, exclusion of hard fixing from the
primary path, and the implementation sequence.  It must not modify production
pipeline behavior.

