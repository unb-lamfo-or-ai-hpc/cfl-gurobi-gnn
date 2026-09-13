# Interim evidence and reserved publication outputs

SPDX-License-Identifier: MIT

The current extract transcribes the diagnostic supplied by the project owner on
13 September 2026. It contains no private paths, vectors or credentials. Source
report hashes are references, not a claim that the manuscript build revalidated
remote HPC bytes. The original diagnostic and immutable run reports remain in
the research evidence store; this is a new, explicitly scoped publication file.

The ledger hashes `source_evidence.json`. The deterministic plotting script
`scripts/manuscript/build_results_assets.py` renders three PNG/SVG figures and
one CSV from that file. It runs no solver, training or inference process.

## Output register

| Table | Associated figure(s) | Population / current status |
| --- | --- | --- |
| Cohort revision in article | `figure_cohort_admission` | 42 original / 39 admitted parents; supplied diagnostic |
| `table_source_rejection_outcomes.csv` | `figure_source_gap`, `figure_source_time_regions` | Three excluded parents, six repair runs; supplied diagnostic |
| `parent_solve_metrics.csv`, `paired_parent_metrics.csv` | `figure_parent_terminal_mip_gap`, `figure_parent_time_regions` | Final current-cohort source bundle pending |
| `incumbent_trajectory.csv` | `figure_parent_incumbent_trajectories` | Current-cohort trajectory bundle pending |
| `table_instance_descriptive_statistics.csv` | `figure_instance_descriptors` | Current-cohort descriptor audit pending |
| `table_graph_statistics.csv` | `figure_graph_statistics`, `figure_graph_projection`, `figure_graph_clustering` | Current-cohort graph audit pending; projection is not a learned embedding |
| `table_training_epoch_metrics.csv` | `figure_training_curves` | Job3307 running; training/validation loss must share axes |
| `table_gnn_test_metrics.csv`, `table_gnn_per_instance_metrics.csv` | `figure_gnn_quality`, `figure_precision_recall`, `figure_calibration`, optional `figure_roc` | Eight held-out parents; evaluation pending |
| `table_solver_run_outcomes.csv` | `figure_solver_mip_gap` | Native current-cohort guidance not available |
| `table_solver_time_regions.csv` | `figure_solver_time_regions` | Native current-cohort guidance not available |
| `table_paired_descriptive_effects.csv` | `figure_paired_effects` | Matched current-cohort effects not available |
| `table_gap_sensitivity.csv`, `parent_gap_sensitivity.csv` | `figure_gap_sensitivity` | Full sensitivity output pending; disclose each population and denominator |

Names in pending rows are planned publication names, not claims that the files
currently exist. Do not fill unavailable rows with zeros, interpolate missing
epochs, draw illustrative scientific curves, or reuse rejected historical
outputs. Use supplementary assets for detailed diagnostics so the article body
including figures and declarations stays within 20 pages.

## Integration after the running job

Review the cohort revision and rejection evidence, graph receipts, epoch
history, checkpoint selection, final training report and held-out evaluation.
Record success, partial completion or failure exactly as observed. Update the
article, captions, ledger, tests and register together. Missing outputs can
remain documented limitations when closing the research MVP. Such closure does
not certify predictive usefulness, solver improvement, statistical
generalization or TRL6. The full90 experiment remains deferred.

Original project-generated tables and figures use MIT within the authors'
rights. This does not relicense MILPBench or third-party assets; see
`LICENSE_POLICY.md` at the repository root and the manuscript template notices.
