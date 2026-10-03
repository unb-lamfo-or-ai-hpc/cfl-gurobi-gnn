# Pipeline output inventory

This inventory describes the artifact names emitted by the current route. An
artifact is scientifically usable only when its enclosing report passes and its
declared hash matches. Paths vary by experiment name and timestamp; file names
and responsibilities are stable within a schema version.

## Parent collection and label admission

| Artifact | Format | Purpose |
|---|---|---|
| `parent_collection_plan.json` | JSON | frozen parents, budgets, solver order, source hashes |
| `parent_collection_tasks.jsonl` | JSONL | combined per-solver task ledger |
| `gurobi_parent_collection_tasks.jsonl` | JSONL | Gurobi task array |
| `scip_parent_collection_tasks.jsonl` | JSONL | matched SCIP task array |
| `gurobi_parent_solve_plan.json` | JSON | immutable per-parent Gurobi plan |
| `gurobi_parent_solve_report.json` | JSON | status, gaps, four time regions, hashes |
| `scip_parent_solve_plan.json` | JSON | immutable per-parent SCIP plan |
| `scip_parent_solve_report.json` | JSON | matched SCIP status and measurements |
| `parent_solution.json.gz` | gzip JSON | named variable assignments |
| `incumbent_trajectory.jsonl` | JSONL | time-indexed incumbent observations |
| `parent_collection_audit_report.json` | JSON | paired population gate and eligibility |
| `parent_solve_metrics.csv` | CSV | per-parent solver outcomes |
| `paired_parent_metrics.csv` | CSV | paired descriptive effects |
| `parent_gap_sensitivity.csv` | CSV | admissibility under registered gap ceilings |
| `incumbent_trajectory.csv` | CSV | normalized trajectories for analysis |
| `figure_parent_incumbent_trajectories.svg` | SVG | incumbent evolution |
| `figure_parent_terminal_mip_gap.svg` | SVG | terminal gaps by solver |
| `figure_parent_time_regions.svg` | SVG | total/read/build/optimize times |

## Synthetic MIPs and independently solved labels

| Artifact | Format | Purpose |
|---|---|---|
| `local_branching_generation_plan.json` | JSON | parent, incumbent center, radii, operator hash |
| `local_branching_generation_report.json` | JSON | generated MIP identities and checks |
| `derived_mip_solution_plan.json` | JSON | fresh independent solve tasks |
| `derived_mip_solution_report.json` | JSON | feasibility, gap, time, and label eligibility |
| `scalable_augmentation_plan.json` | JSON | paired train-parent augmentation campaign |
| `scalable_augmentation_report.json` | JSON | campaign-level gate |
| `scalable_augmentation_task_status.jsonl` | JSONL | per-parent/per-solver status |
| `derived_source_index.jsonl` | JSONL | accepted synthetic source identities |
| `*.lp` or `*.lp.gz` | LP | independently identified synthetic MIP |

An incumbent is only the center of a transformation. The resulting LP and its
independent solution define the synthetic sample.

## Gurobi-authoritative graph construction

| Artifact | Format | Purpose |
|---|---|---|
| `gurobi_graph_dataset_plan.json` | JSON | graph population and strict feature contract |
| `gurobi_graph_dataset_report.json` | JSON | dataset gate and source contracts |
| `gurobi_derived_training_dataset_plan.json` | JSON | parent/descendant graph build plan |
| `gurobi_derived_training_dataset_report.json` | JSON | derived graph gate |
| `per_original_graph_audit.jsonl` | JSONL | original graph dimensions and identity checks |
| `per_gurobi_derived_graph_audit.jsonl` | JSONL | synthetic graph checks |
| `confirmation_graph_manifest.jsonl` | JSONL | graph paths, parent roles, hashes, labels |
| `graph_receipt.json` | JSON | source MIP, root observation, graph identity |
| `node_relaxations.parquet` | Parquet | root relaxation observation where retained |
| `*.pt` | PyTorch | heterogeneous bipartite graph tensor |
| `graph_statistics.csv` | CSV | outcome-free structural descriptors |
| `graph_clustering.csv` | CSV | descriptive PCA/UMAP coordinates and clusters |
| `*.png`, `*.svg` | image | structural summaries and projections |

PCA and UMAP are descriptive projections. They do not select partitions,
checkpoints, or solver policies.

## PR #57 training and held-out prediction

| Artifact | Format | Purpose |
|---|---|---|
| `pr57_54_cohort_contract.json` | JSON | 54-parent, 34/10/10 partition contract |
| `pr57_54_graph_manifest.jsonl` | JSONL | hash-bound graphs and roles |
| `pr57_54_graph_report.json` | JSON | graph inventory gate |
| `gasse_training_plan.json` | JSON | model, seed, epochs, normalization policy |
| `gasse_training_report.json` | JSON | selected checkpoint and training summary |
| `training_epoch_metrics.csv` | CSV | 100 rows of train/validation metrics |
| `best_model.pt` | PyTorch | validation-selected checkpoint |
| `gasse_evaluation_plan.json` | JSON | frozen held-out predictive evaluation |
| `gasse_evaluation_report.json` | JSON | aggregate predictive metrics and eligibility |
| `per_instance_metrics.csv` | CSV | parent-level predictive metrics |
| `predictions.json.gz` | gzip JSON | named model outputs, protected large artifact |
| `pr57_54_training_audit.json` | JSON | hashes, cohort, training, evaluation gate |

## PR #58 validation guidance

For each validation parent, the run directory may contain
`label_free_graph.pt`, `root_features.json.gz`, `predictions.json.gz`,
`preparation.json`, `parent_receipt.json`, and one receipt for each method.
`preparation_failure.json` is retained on failure.

| Artifact | Format | Purpose |
|---|---|---|
| `pr58_validation_guidance_plan.json` | JSON | six validation parents and three frozen methods |
| `per_method_status.json` | JSON | artifact validity per parent/method |
| `per_method_outcomes.json` | JSON | complete machine-readable solver outcomes |
| `per_method_outcomes.csv` | CSV | tabular outcomes |
| `paired_effects.json` | JSON | paired validation effects |
| `paired_effects.csv` | CSV | tabular effects |
| `pr58_validation_guidance_report.json` | JSON | qualification checks and frozen test decision |

## PR #59 frozen held-out benchmark

The per-parent artifact names mirror PR #58. The campaign adds:

| Artifact | Format | Purpose |
|---|---|---|
| `pr59_heldout_guidance_plan.json` | JSON | PR #58-frozen test identities, methods, and budgets |
| `per_method_status.json` | JSON | artifact validity per parent/method |
| `per_method_outcomes.json` | JSON | complete held-out solver outcomes |
| `per_method_outcomes.csv` | CSV | tabular held-out outcomes |
| `paired_effects.json` | JSON | paired held-out effects |
| `paired_effects.csv` | CSV | tabular held-out effects |
| `pr59_heldout_guidance_report.json` | JSON | held-out gate, censoring, and scope |

## PR #60 scientific evidence synthesis

PR #60 executes no solver and emits exactly six tables and five figures, plus
its plan, report, and manifest:

| Artifact | Format | Purpose |
|---|---|---|
| `table_training_epoch_metrics.csv` | CSV | copied, verified epoch evidence |
| `table_predictive_metrics.csv` | CSV | aggregate predictive quality |
| `table_solver_outcomes.csv` | CSV | validation and test method outcomes |
| `table_paired_gap_effects.csv` | CSV | parent-level guided-minus-control gaps |
| `table_censoring_summary.csv` | CSV | censoring by partition and method |
| `table_heldout_influence_analysis.csv` | CSV | predeclared leave-out sensitivity |
| `figure_training_validation_loss.svg` | SVG | joint learning curves |
| `figure_predictive_quality.svg` | SVG | predictive metrics |
| `figure_validation_test_gap_effects.svg` | SVG | paired validation/test effects |
| `figure_time_to_ten_percent_gap.svg` | SVG | observed threshold times with censoring |
| `figure_offline_online_pipeline.svg` | SVG | training/application pipeline |
| `pr60_scientific_evidence_plan.json` | JSON | source contracts and planned outputs |
| `pr60_scientific_evidence_report.json` | JSON | results, limitations, and eligibility |
| `pr60_scientific_evidence_manifest.json` | JSON | size and SHA-256 of every table/figure |

## Formats and publication policy

PNG outputs belong primarily to legacy and descriptive graph-analysis routes;
the current PR #60 publication layer uses SVG for scalable vector output. CSV is
the reviewable table format, JSON/JSONL is the contract format, and `.pt`, `.gz`,
Parquet, and LP artifacts remain external to routine Git history. See
[reproducibility](reproducibility.md) for sanitization and archival rules.
