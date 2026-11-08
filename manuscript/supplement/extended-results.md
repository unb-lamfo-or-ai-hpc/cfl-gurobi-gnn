# Appendix B: Descriptive Analyses and Extended Experimental Results {#sec-supp-results}

```{=latex}
\AppendixDisplayNumbers{B}
```

The descriptive analyses and extended results retain their original populations, measurement boundaries and numerical qualifications. Repeated method/resource observations are not independent instances. Presentation rounding does not change the public source records.

## B.1. Populations and the role of historical material {#sec-appendix-populations}

The analyses below answer different questions and retain their original populations. In particular, the earlier development cohort is not the later predictor cohort, and a predictive test is not an optimization benchmark. This distinction prevents a descriptive figure or a large number of binary targets from being mistaken for independent experimental replication.

@tbl-study-populations identifies the populations and their roles.

| Evidence block | Population and role | Appropriate interpretation |
|:--|:--|:--|
| Earlier development study | 39 original instances; 23 training, 8 validation, 8 test | Descriptive graph analysis and the earlier predictor's diagnostics |
| Later predictor | 54 admitted instances; 34 training, 10 validation, 10 predictive test | The historical predictive results used in the article |
| Principal CPU comparison | Six easy and four medium instances, B/R/G and five caps | 150 recorded conditions on ten historically exposed instances |
| Preliminary optimization study | Separate six-medium validation and six-medium test cohorts | Supporting optimization evidence under its own protocol |
| Matched GPU training pair | Same later learning split, one versus four GPUs | Training time, selected quality and allocated resources |
| Long-horizon CPU evaluation | 60 completed configurations on the same four medium instances | Separate 12-hour evaluation, kept distinct from the retrospective comparison |

: Study populations and their roles. {#tbl-study-populations}

The following sections restore the earlier development material alongside the later results. They preserve its scientific role rather than replace the current data partition, predictor or optimization population.

## B.2. Earlier instance admission and acquisition costs {#sec-history39-cohort}

The admitted cohort contains 39 original instances: 30 easy and 9 medium. It derives from a planned set of 42, with medium instances 3, 5 and 6 excluded from that historical revision. @tbl-history39-cohort records the roles before and after those exclusions. Original identifiers are retained throughout; an identifier such as M0 denotes an instance here, not the historical method code M0.

{{< include ../tables/history39_cohort.qmd >}}

The source records contain two acquisition attempts for each excluded instance, with budgets of 3600 and 14400 seconds. @tbl-history39-rejections retains both attempts, their terminal primal/dual values and their censoring flags. Even after the longer budget, each reported gap remained above the historical 10% label-quality ceiling. Excluding them was quality-based admission, not random sampling. These are earlier label-acquisition records, not additional B/R/G experiments or evidence that the same instances must be excluded from every later cohort. The [original acquisition record](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/source_evidence.json) retains the source report hashes and full timing precision.

{{< include ../tables/history39_rejections.qmd >}}

@fig-history39-admission and @fig-history39-gap show the original admission balance and retained unsuccessful acquisition attempts.

![Original and admitted inventories in the earlier 39-instance development study.](../figures/figure_history39_admission.pdf){#fig-history39-admission width=100%}

![Recorded terminal gaps for the three excluded medium instances under the two historical acquisition budgets.](../figures/figure_history39_source_gap.pdf){#fig-history39-gap width=100%}

Acquisition cost includes more than optimizer time. @tbl-history39-times and @fig-history39-times retain the four separately recorded wall-time regions. Total includes other work and need not equal the sum of the three named components. The intervals are historical observations, not new timings or a complete deployment-cost estimate for GNN Starts.

{{< include ../tables/history39_times.qmd >}}

![Data reading, model construction, optimization and total wall time for the six historical acquisition attempts. Panels have separate scales.](../figures/figure_history39_time_regions.pdf){#fig-history39-times width=100%}

{{< pagebreak >}}

## B.3. Descriptive statistics of the earlier graphs {#sec-history39-statistics}

A bipartite graph has one node per original variable, one per linear constraint, and an edge for every nonzero matrix coefficient. For \(n\) variables, \(m\) rows and \(e\) nonzeros, density is \(e/(nm)\); it is not the fraction of nonzero entries in a neural embedding. The discrete-variable fraction and target-positive fraction describe different objects: a variable's domain and its reference label, respectively.

@tbl-history39-structure summarizes graph topology by difficulty. The accompanying distributions in @fig-history39-distributions retain individual instances rather than interpreting their numerous variable labels as independent samples. Identical sizes within a difficulty class do not imply identical coefficients, labels or optimization behaviour.

{{< include ../tables/history39_structure.qmd >}}

@tbl-history39-distributions reports the minimum, quartiles, median and maximum of the domain, label, source-quality and root-vector descriptors. Quartiles are descriptive interpolations, not confidence limits.

{{< include ../tables/history39_distributions.qmd >}}

![Instance-level distributions of structural density, encoded discrete-variable fraction, positive-label fraction and historical source execution time.](../figures/figure_history39_distributions.pdf){#fig-history39-distributions width=100%}

The complete instance inventory appears in @tbl-history39-instances. Counts refer to the original matrix; label fractions use the archived graph-statistics definition. Reported source gap, execution time and root-vector sparsity are retained separately in @tbl-history39-quality.

{{< include ../tables/history39_instances.qmd >}}

{{< include ../tables/history39_quality.qmd >}}

All 39 graph-statistics censoring fields are missing. A long source execution time therefore cannot be relabelled as a completed solve or assigned a censoring flag from a guessed time limit. The gap and time columns describe the recorded acquisition provenance; they are not a controlled speed comparison. Their medians and ranges must not be pooled with the later one-hour CPU results.

The [graph-statistics CSV](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/graph_statistics.csv) retains all original fields and precision.

## B.4. Dimensionality reduction and descriptive grouping {#sec-history39-pca}

The archived projection reduces 17 encoded macro-descriptors of each graph to two coordinates. It is a PCA of hand-defined instance descriptors, not a projection of latent representations learned by the GNN. @tbl-history39-descriptors identifies every input to the reduction. Label prevalence, source runtime and terminal gap are present in the broader archive but were excluded from the projection inputs.

{{< include ../tables/history39_descriptors.qmd >}}

Each descriptor was standardized using its population mean and standard deviation across the 39 graphs; a zero-variance column was mapped to zero. Deterministic singular-value-decomposition PCA then supplied the recorded coordinates. PC1 accounts for 85.78% and PC2 for 7.74% of standardized-descriptor variance. The two coordinates thus retain approximately 93.52% of that descriptor variance, not 93.52% of information relevant to warm-start quality.

The recorded effective rank is 10; the retained cluster labels form 3 descriptive groups. @fig-history39-structure shows the graph sizes and the archived coordinates, with markers for those fixed groups. @tbl-history39-clusters reports their composition; @tbl-history39-pca preserves every point and cluster assignment.

![Graph sizes and the archived PCA of 17 structural descriptors for the earlier 39-instance cohort. Shape denotes the retained descriptive cluster; shade denotes difficulty.](../figures/figure_history39_structure_pca.pdf){#fig-history39-structure width=100%}

{{< include ../tables/history39_clusters.qmd >}}

{{< include ../tables/history39_pca.qmd >}}

The grouping used deterministic k-means with at most three clusters. Neither a visible separation nor a retained cluster label demonstrates natural problem classes, out-of-sample generalization or a cause of solver performance. Global standardization and PCA use all 39 instances solely for this descriptive view; they did not select the learning split, checkpoint or Start policy. No new PCA fit, clustering run or embedding extraction is needed to redraw the stored coordinates.

The [full descriptor/coordinate table](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/graph_clustering.csv) and [projection report](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/graph_clustering_report.json) specify the archived transformation. The reported limitations include loss of information about infinite bounds after clipping.

### B.4.1. Earlier PCA/UMAP illustrations

An [earlier PCA/UMAP image](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/data/analysis/pyg_plot_pca_vs_umap.png) and [dataset dashboard](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/data/analysis/step2/pyg_clustering_dashboard.png) remain available as archival visualizations. Their [source implementation](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9903c1dc66f65e9497d7faa2d8d4f3ee414a0f42/src/graph_transform/pyg_clustering_pca_umap.py) uses three macro-features: density, discrete-variable fraction and constraint/variable ratio. It also applies UMAP with a fixed seed. It does not extract learned GNN embeddings.

Those illustrations belong to an earlier artifact population; their point-to-input binding and fitted projection state are not available in the returned 39-instance evidence. Their PCA percentages therefore do not describe the 17-descriptor PCA above. The [legacy dataset summary](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/data/analysis/step2/pyg_dataset_statistics_report.csv) counts graph artifacts rather than verified independent parents. Its confidence-interval columns are not adopted as instance-level inference. Preserving these links retains the earlier material without presenting its visually numerous points as additional independent evidence.

## B.5. Earlier learning history and checkpoint selection {#sec-history39-learning}

The earlier predictor uses the 23/8/8 split stated above. @fig-history39-training retains all 100 recorded training and validation epochs, and @tbl-history39-epochs makes the first, minimum-validation and final observations explicit. The minimum validation BCE is 0.0985 at epoch 91. Subsequent validation deterioration must not be hidden by showing only the training loss.

![Complete archived training and validation weighted BCE for the earlier 39-instance study. The marker identifies the minimum recorded validation loss.](../figures/figure_history39_training.pdf){#fig-history39-training width=100%}

{{< include ../tables/history39_epochs.qmd >}}

The historical report identifies this checkpoint (SHA256):

`7de62c2ccd374509179c5caf29d8ad0842c7b5e2fd74175078ef0ac685875cf3`.

Its validation-selected score threshold is 0.993316113948822. These identify the earlier result; they are not the later mixed CPU checkpoint or its threshold. The [confirmation record](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/confirmation_final.json) and [full epoch table](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/training_epoch_metrics.csv) retain the provenance.

The report verifies the consistency of supplied files, but raw graph tensors, root vectors, checkpoint weights and predictions were not independently retransferred for that delivery audit. Its diagnostics are preserved at that evidential level; a rendered learning curve is not a replayed training fit.

## B.6. Earlier prediction, imbalance and score calibration {#sec-history39-prediction}

The archived predictive test contains 3,222,800 binary targets and 3,773 positives from eight original instances. Pooled F1 is 0.5825, while the unweighted mean of per-instance F1 is 0.5849. @tbl-history39-predictive retains precision and recall for pooled, instance-macro and difficulty-specific summaries. Very high accuracy in this imbalanced population cannot substitute for recovery of the rare positive class.

{{< include ../tables/history39_predictive.qmd >}}

@tbl-history39-baselines compares archived score diagnostics with the clipped root-LP and constant-zero references. Average precision is not trapezoidal PR-AUC. The archived scalar ROC-AUC and PR-AUC are reported in the table's note; full ROC and PR coordinate files were withheld from the historical delivery, so no curve is reconstructed from those scalars.

{{< include ../tables/history39_baselines.qmd >}}

@tbl-history39-per-parent retains all eight instances and their confusion counts, and @fig-history39-prediction displays the F1 variation and ten-bin score diagnostic. The reliability diagonal is a reference, not a fitted recalibration. Threshold selection and positive-class-weighted BCE do not guarantee that sigmoid scores represent calibrated probabilities.

{{< include ../tables/history39_per_parent.qmd >}}

![Per-instance F1, binned reliability and score-bin counts for the earlier eight-instance predictive test.](../figures/figure_history39_prediction.pdf){#fig-history39-prediction width=100%}

@tbl-history39-calibration gives all ten bins, including their target counts, mean scores and observed positive fractions. Many dependent variable targets can make an aggregate look numerically stable without increasing the number of independent problem instances. These older diagnostics do not replace the later ten-instance predictive assessment. The [per-instance CSV](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/per_parent_metrics.csv), [difficulty summaries](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/per_difficulty_metrics.csv) and [calibration bins](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/bb39aafe1535bfa255e77dca1a6f203479e88586/manuscript/results/calibration_curve.csv) provide the complete archived metrics.

{{< include ../tables/history39_calibration.qmd >}}

## B.7. Principal CPU population and dispositions {#sec-cpu-coverage}

The principal comparison contains 150 seed42 records on six easy and four medium instances. Their three methods and five thread caps account for the rows below. The thirty sensitive observations are part of the same sample, not an additional population.

@tbl-cpu-coverage gives the dispositions for the historical CPU cohort.

| Principal comparison | Records | Interpretation |
|:--|--:|:--|
| Easy instances | 90 | Six instances, three methods, five caps |
| Medium instances | 60 | Four instances, three methods, five caps |
| Solver-reported terminal target attained | 97 | Reported under tolerances, not exact optimality certificates |
| Terminal target right-censored | 53 | Not observed solution times at the limit |
| Numerically sensitive M4/M12 rows | 30 | Subset subject to metric-specific numerical restrictions |

: Scope and recorded dispositions of the principal CPU comparison. {#tbl-cpu-coverage}

Every easy instance attains the reported 0.01% gap criterion in each configuration. @tbl-easy-times lists both runtime and final MIP gap for all 90 observations; gaps are percentages, not fractions. Twelve gaps are nonzero, and the largest is approximately 0.009687%, for E14 with G at eight threads. A zero under solver tolerances does not establish exact optimality. F denotes an easy instance; M denotes a medium instance.

{{< include ../tables/principal_easy_times.qmd >}}

## B.8. Medium instances: primal, dual and gap {#sec-mvp2-current}

The terminal records in @tbl-medium-quality distinguish feasible objective, solver bound, relative gap and terminal-target disposition. A smaller primal is better for minimization; a larger valid lower bound indicates stronger dual progress. These can change in opposite directions, so the gap must be interpreted with both components.

{{< include ../tables/principal_medium_quality.qmd >}}

Censoring here concerns the terminal target, not every earlier descriptive threshold. Terminal observations have their actual recorded runtimes rather than an imposed common endpoint. M4 and M12 remain visible with numerical restrictions; solver acceptance of original floating-point vectors does not certify rounded copies or exact feasibility. Their rows are not used to establish certified solution speedups.

The [principal rows](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/methodology-20261019/seed 42_main.csv) retain method identifiers, exact values, censoring flags and receipt/child hashes. The [existing paired summaries](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/pr86/final-210/paired_uncertainty.csv) distinguish the seed 42 view from historical repeats. Their intervals are exploratory under an exchangeable-instance model, not a guarantee of population coverage.

On medium instance 0 at one thread, G improves the primal (4.6556 versus B's 4.6664) but weakens the dual (4.3230 versus 4.3504), leaving a larger terminal gap. On medium instance 7 at eight threads, G's much better primal (5.4337 versus 10.7283) yields a smaller gap despite a weaker dual (4.7261 versus 4.7750). Appendix B retains all configurations and adverse outcomes. Primal and dual changes therefore require joint interpretation.

Medium instance 0 with G at sixteen threads reports zero terminal gap after approximately 3204 seconds, while both comparators are censored for the terminal target. This is a solver-reported outcome under tolerances, not an exact certificate. M4 and M12 retain metric-specific numerical limits: acceptance of original floating-point vectors does not establish feasibility of rounded diagnostic copies. Their observations cannot be promoted to certified speedups.

## B.9. Preparation and cost interpretation {#sec-cost-results}

The historical cost comparison uses the six easy instances at sixteen threads and seed 42. Solver Runtime, supervised attempt time and preparation are separate quantities. The delimited cold scenario adds recorded preparation to the attempt, while the broader allocation also apportions documented preparation overhead. The seven-use scenario spreads that preparation across seven assumed uses; it does not remove expenditure from campaign accounting.

A five-use allocation appears in a different derived table and must retain that assumption. Neither scenario is a newly measured complete application. Components included within larger intervals, such as a forward pass within inference, are not added twice. R retains the cost of G-dependent matching.

The [cost scenarios](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/pr86/final-210/cost_scenarios.csv) identify these scopes by instance and configuration. Missing cold-use components remain unavailable rather than zero. CPU accounting, physical reservation and allocated GPU-hours are different resource measures.

A solver-level advantage is not necessarily an application-level advantage. @tbl-principal-costs compares five already documented cost boundaries for the six easy instances at sixteen threads.

{{< include ../tables/principal_costs.qmd >}}

The solver-only G/B ratio of 0.8435 becomes 1.0461 with delimited cold preparation, or 1.0692 with broader allocation. The corresponding seven-use scenarios yield 0.8935 and 0.8969. Accounting scope and reuse thus reverse the direction of the estimate.

These are conditional cost scenarios, not complete deployment measurements. The exploratory intervals around the sixteen-thread solver and cold-use ratios both include one. The observation is useful for accounting decisions on this sample, without establishing a universal break-even rule. It also does not remove preparation from the measured campaign expenditure or imply that missing operational costs are zero.

## B.10. Predictor history and matched GPU training {#sec-historical-predictive}

The historical predictor and the matched GPU training runs have distinct roles. The former supplies the fixed weights used to generate solver starts. The latter compares execution modes at matched training work.

### B.10.1. Historical predictor and learning dynamics

The archived predictive assessment uses ten test graphs and is distinct from the six-medium optimization population below. @fig-loss shows the complete original 100-epoch history; @tbl-predictive reports the validation-selected checkpoint rather than the terminal model.

![Historical training and validation weighted BCE over 100 epochs.](../figures/figure_training_validation_loss.pdf){#fig-loss width=100%}

Training BCE decreases from 1.5877 to 0.0275. Validation BCE reaches its minimum 0.0510 at epoch 34 and is 0.1124 at epoch 100. The selected predictive result is therefore not replaced by the terminal state.

{{< include ../tables/current_predictive.qmd >}}

Precision and recall are 0.6923 and 0.7064; pooled F1 is 0.6993 and parent-macro F1 is 0.7027. AP 0.7745 and trapezoidal PR-AUC 0.7747 are distinct ranking summaries. The test contains 5,536,400 binary targets and 5,265 positives, approximately 0.0951%. Those targets are not independent problem instances.

### B.10.2. Matched serial and distributed GPU training {#sec-gpu-appendix}

The matched comparison asks how much elapsed time changes when the same graph-level training schedule runs on one V100 or on four V100s using distributed data parallelism (DDP). The fixed split comprises 34 training, ten validation and ten test instances. Each global update averages four per-graph weighted binary cross-entropies. The serial process accumulates four scaled gradients. In DDP, each rank processes one complete graph, then the ranks average their gradients before clipping and the optimizer step [@li2020ddp]. Both arms used seed 42, the same initial state and graph schedule, and completed 100 epochs, 13,600 graph presentations and 3,400 updates. Validation selects the checkpoint separately for each arm. Appendix C.7 records the full configuration.

@tbl-gpu-pair-appendix separates training time, scheduler elapsed time, allocated GPU-hours and the selected checkpoints' predictive quality.

| Measure | Serial 1 V100 | DDP 4 V100s |
|:--|--:|--:|
| Physical CPU cores |4|16|
| Training loop (s) |1724.128|795.637|
| Slurm job elapsed (s) |2021|1104|
| Assigned GPU-hours |0.5614|1.2267|
| Selected epoch |99|92|
| Minimum validation BCE |0.045286|0.048772|
| Selected parent-macro F1 |0.723065|0.690597|
| Selected parent-macro PR-AUC |0.783809|0.769959|

: Matched GPU training time, allocation and selected quality. {#tbl-gpu-pair-appendix}

The training loop is 2.167 times faster, corresponding to 54.17% efficiency relative to the fourfold GPU allocation. Slurm elapsed time falls from 2,021 to 1,104 seconds (1.831×, 45.77% GPU-normalized efficiency), while allocated GPU-hours rise by a factor of 2.185. Selected F1 falls 0.032468 (3.247 percentage points), exceeding the predeclared descriptive 0.02 loss margin; PR-AUC falls 0.013850. The smaller PR-AUC loss does not establish preserved predictive quality or statistical noninferiority. @fig-gpu-bce-appendix shows the unmodified loss trajectories.

![Training and validation weighted BCE for the matched serial/distributed comparison.](../figures/gpu_bce_by_epoch_article_en.pdf){#fig-gpu-bce-appendix width=90% fig-pos="htbp"}

The loss curves compare training and validation at the same epoch, with the selected checkpoint read from each run's validation curve. Communication and gradient synchronization can contribute to sublinear DDP speedup [@li2020ddp]. GNN workloads can also involve irregular data movement [@zheng2020distdgl]; here each rank processes complete instance graphs. Matched global batches do not establish identical floating-point trajectories [@pytorch21numerical]. CPU and GPU allocations change together. The single pair shows an F1 loss, but does not identify its cause. These weights do not replace the CPU predictor.

## B.11. Preliminary six-medium optimization study {#sec-historical-six-medium}

This study uses **M0, M4, M7, M9, M12 and M20** for optimization testing, separately from its six-medium guidance-validation cohort. The later principal CPU matrix and long-horizon extension use only **M0, M4, M7 and M12** as their medium instances. M9 and M20 belong to this earlier study; their presence here does not redefine the later split or add observations to the principal matrix. Its single-thread, seed 42, 3,600-second runs retain their original policy and method-order protocol. Historical exposure precludes presenting M9/M20 as entirely untouched instances in a later evaluation.

### B.11.1. Guidance qualification and frozen testing

All six validation Starts are reported as loaded without abstention. Four reduce terminal gap, the median guided-minus-control difference is -1.224 percentage points, and only one increase exceeds one point, satisfying the original qualification rule. Medium instance 19 reports zero gap near 671 seconds while its unguided comparator exhausts the time limit. These validation observations are not test results.

After qualification, checkpoint, threshold, support and ordering remain fixed. @tbl-heldout reports all six test pairs rather than selecting the favourable cases.

{{< include ../tables/current_heldout.qmd >}}

The GNN start reduces terminal gap on five of six instances, with median difference -1.164 percentage points. Medium instances 12 and 20 account for much of the magnitude. Medium 0 reaches the observed 10% target earlier despite a worse terminal gap; medium 4 exhibits the converse. @fig-effects separates validation and test observations.

![Paired terminal-gap differences in the separate historical study.](../figures/figure_validation_test_gap_effects.pdf){#fig-effects width=100%}

Negative differences favour G. Panel scales differ and values are percentage points, rather than relative percent improvements.

### B.11.2. Quality targets, censoring and influence

A first observed crossing is a different endpoint from terminal gap. @fig-target-time shows the 10% crossing and retains unobserved targets as censored.

![First observed 10% relative-gap crossings in the historical study.](../figures/figure_time_to_ten_percent_gap.pdf){#fig-target-time width=100%}

Hatching indicates a target unobserved within the recorded budget, not attainment at 3,600 seconds. G crosses on four instances, versus three per comparator. The medium 12 and 20 G crossings are approximately 672 and 1,168 seconds. Preparation and inference are outside these solver observations.

@tbl-influence reports the full population and post-analysis leave-out diagnostics without redefining the original test set.

{{< include ../tables/current_influence.qmd >}}

The mean paired gap difference is -7.200 percentage points. It is -1.659 without medium 20 and -0.556 without medium 12 and 20; medians are -1.164, -0.213 and -0.140 points. The magnitude is therefore influence-sensitive even where the direction remains favourable. The root-LP comparator improves terminal gap on one of six instances; its median difference from control is approximately +1.124 points.

### B.11.3. Optimization and worker time

@tbl-times distinguishes optimization from the historical worker interval. This distinction prevents attributing the omitted neural preparation to a zero-cost application.

{{< include ../tables/current_timing.qmd >}}

The GNN runs on medium instances 12 and 20 use approximately 702 and 1,585 solver seconds. Four GNN runs and all comparator runs exhaust the time budget; medium 0 and 4 nevertheless reach 10% with G. These are compatible endpoint-specific observations. Worker time includes verification, model construction, optimization and auditing but excludes feature preparation, inference and orchestration.

The [historical manifest](../results/current/pr60_scientific_evidence_manifest.json) binds the original tables and figures. The later principal CPU matrix and GPU pair have their own sources. None of these records turns historical exposure into an independent generalization test.


## B.12. Long-horizon CPU evaluation {#sec-partial-cpu-evidence}

All 60 configurations were completed and reconciled. Forty-seven reached the reported 0.01% criterion and 13 were time-limited, all on M7. This historical evaluation is analyzed separately from the 150-observation retrospective comparison. On M0, G reached the target before B at four of five caps. On M7, all methods ended with the same reported primal value. The reported times do not establish certified speedups.

This separate evaluation reuses the four medium instances, original prediction-to-Start bindings and seed 42, with five physical-thread limits and a 43,200-second solver budget. All 60 planned configurations were completed and received, with 15 combinations for each instance. The complete campaign is kept separate from the earlier 150 observations; it does not enlarge the number of independent instances or solver seeds.

The versioned [data and review record](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/565d9146729c7f35f280d1ae37818beab71879ff/docs/evidence/pr89/final-20261101) binds the source, three input archives, all 60 cells, threshold observations, horizon brackets and metric dispositions. The sealed 54-cell review was retained, and the six final receipts were independently checked for controls, parameter bindings, nested seals, temporal records and cost arithmetic. A joint accounting query recorded all 60 jobs and 180 job/step rows as completed. These transport and execution checks establish receipt coverage, rather than exact optimality or scientific validity. The original four-point M12 audit is complemented by a [six-point extension](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/565d9146729c7f35f280d1ae37818beab71879ff/docs/research/pr89-m12-terminal-audit-20261101.json); the other five M12 stored vectors have not undergone this independent exact-primal check.

### B.12.1. Target attainment, censoring and thread limits

Of the 60 received configurations, 47 report the terminal 0.01% criterion and 13 stop at the 12-hour limit. All time-limited cases concern M7. Technical completion of a job is therefore different from attainment of its optimization target [@gurobi2026]. A first observed threshold crossing retains its previous observation and does not identify an exact continuous hitting time.


@tbl-cpu-long-coverage retains every instance, including censored and numerically restricted cases.

| Instance | Configurations | Reported target attained | Time-limited |
|:--|--:|--:|--:|
| M0 | 15 | 15 | 0 |
| M4 | 15 | 15 | 0 |
| M7 | 15 | 2 | 13 |
| M12 | 15 | 15 | 0 |

: Complete long-horizon coverage at the reported 0.01% target. Attainment does not remove numerical qualifications. {#tbl-cpu-long-coverage}

@tbl-partial-cpu-m0 gives M0 crossing times at the same reported 0.01% threshold. Ratios describe individual fixed-seed configurations, not replicated or population-level effects.

{{< include ../tables/partial_cpu_m0.qmd >}}

G is earlier than B at four of five caps, but at two threads both B and R are earlier. R is also earlier at one thread. This is evidence of configuration-dependent behaviour, rather than uniform neural acceleration.

@fig-partial-cpu compares these M0 observations with the terminal gaps of M7.

![Long-horizon evaluation: M0 first observed terminal-target times and M7 terminal gaps.](../figures/partial_cpu_time_gap.pdf){#fig-partial-cpu width=100%}

Each point represents one configuration. In the right panel, crosses mark 12-hour terminal-target censoring and circles indicate reported attainment. Lines connect observed thread caps and do not interpolate a solution-time distribution.

All M7 runs end with primal 5.428377599678637, but their dual bounds differ. @tbl-partial-cpu-m7 separates their terminal gaps. B at one thread and R at sixteen threads attain the target; none of the G runs does so.

{{< include ../tables/partial_cpu_m7.qmd >}}

The ranking also depends on the target. With four threads, G first observes 10% gap at 2.795 hours, versus 7.881 for B and 6.365 for R, yet none reaches 0.01% in that configuration. With eight threads, R reaches 10% before G, while G reaches 5% before R. Across the received records, the observed/censored counts are 60/0 at 10%,54/6 at 5%, and 47/13 at both 1% and 0.01%. These counts preserve reported coverage, not numerical certification.

The four quality horizons retain their actual before/after timestamps and staleness. A run ending before a horizon remains labelled terminated_before_horizon; its trajectory is neither extended nor interpolated. Bounds from another execution are not substituted into a censored run.

The common terminal incumbent makes M7 particularly informative about the distinction between finding a solution and proving its quality. Its terminal gap ranking is a dual-bound ranking conditional on that incumbent. At eight threads R has a smaller terminal gap than G, whereas at four threads G has the smaller gap but all three arms remain censored for the terminal target. At sixteen threads R attains the reported target and G does not. Neither a favorable intermediate crossing nor a smaller terminal gap should be relabelled as faster completion of the MILP proof.

For a time-to-target comparison, a censored observation supplies a lower bound on the unobserved attainment time; it is not an attainment at 43,200 seconds. A ratio obtained by dividing a completed time by that limit is consequently not a measured speedup. Restricting analysis to completed runs would also remove 13 of the 15 M7 observations. We therefore retain the full instance and report target attainment, terminal quality and resource expenditure separately. The five thread configurations share an instance, seed and Start, and cannot provide five independent replications for a significance test.

### B.12.2. Numerical qualifications and the large M12 time contrast

@tbl-partial-cpu-all lists all received terminal records. Runtime is the solver clock; it excludes preparation and differs from job elapsed time. C denotes a terminal target censored at the recorded limit.

{{< include ../tables/partial_cpu_all.qmd >}}

M12 with one thread illustrates why runtime alone is insufficient. B, R and G use 20,379.962, 30,843.561 and 648.369 solver seconds, respectively. The resulting 31.43 and 47.57 runtime quotients are not certified speedups. G reports primal and dual 4.741382854739, while B/R report smaller tolerance-accepted objective values 4.740937765901 and 4.740932705477. The G value is higher and its bound lies above those primal reports; interpreting this ordering requires checking integer feasibility. The largest dual exceeds the smallest primal by 0.000450149263, approximately 0.009495%. A zero gap within one run does not resolve this cross-run disagreement.

At two threads, B/R/G use 6,479.262/5,177.102/572.465 seconds; R/G is 9.04. At four threads, B/R/G use 21,726.307/20,762.970/578.430 seconds. The latter runtime quotients, 37.56 and 35.90, are also not certified speedups: G again reports primal/dual 4.741382854739, above the B/R primal reports 4.740932705477/4.740937765901. All three runs report zero internal gap, which does not remove the cross-run discrepancy.

At four threads G explores 1,738 nodes, versus 266,765 for B and 217,149 for R. The closed logs provide a more informative account than node counts alone. G processes 72,551 simplex iterations and reports 583.73 work units, compared with 13,553,138 iterations and 29,427.31 work units for B, and 10,831,133 iterations and 27,105.65 work units for R. These are printed log observations, not recovered terminal attributes. Callback times are 0.32, 18.76 and 17.52 seconds, respectively. Together with the approximately 65--68 seconds outside solver Runtime, these measurements show that the hours chiefly accompany different amounts of solver work. They do not exclude unmeasured contention or isolate a causal neural effect.

The search differs from its early stages. G loads a completed start with printed objective 5.91168, whereas R's is 377.207. G's presolved model contains 1,729 rows and 661,125 columns, compared with 2,400 rows and 1,153,162 columns for B/R. A stronger incumbent can support objective-based reductions and change subsequent search; the observed ordering is consistent with that mechanism, without identifying the contribution of each reduction or cut. The root logs explicitly describe deterministic concurrent LP optimization. This algorithmic property should be distinguished from numerical exactness.

A [separate exact-arithmetic record](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/79983e119aefb90f6a55d4bc5e76b8006830f439/docs/research/pr89-m12-raw-audit-20261101.json) binds the original model, stored vectors and closed logs. All original rows, variable bounds and binary domains were evaluated using rational arithmetic, both for binary64 input coefficients and for the decimal coefficients in the LP file. G's four-thread stored point satisfies these checks exactly. The B points at two/four threads and R at four threads each contain one nonintegral binary value of approximately $5.21\times10^{-8}$, accepted under the original integrality tolerance of $10^{-5}$.

The affected linking row contains a coefficient of $-800$ for that binary. The small fractional value offsets approximately $4.16587\times10^{-5}$ of positive row activity. Rounding it to zero in an in-memory copy exposes a violation of 0.0000416587, or 41.66 times the original row tolerance. Exact interval arithmetic also shows that the row remains violated for every continuous completion with those rounded binaries fixed. The lower control points therefore do not constitute better feasible integer solutions. The mechanism illustrates the effect of absolute tolerances in linking constraints [@gurobi2026].

G and each control differ in only three coordinates: the fractional component and two integral binary switches; their continuous coordinates agree. The direct objective contribution removed by rounding is approximately $1.54\times10^{-7}$ for B and $1.67\times10^{-7}$ for R. The larger objective difference also reflects the distinct binary choices; it is not a display-rounding error. G's reported value is 0.009495% above B's and 0.009388% above R's, but these percentages do not measure loss relative to better feasible integer solutions. Exact primal feasibility does not certify global optimality: no exact dual or search-tree proof is supplied. The observed runtime quotients remain numerically qualified.

The six final runs extend this diagnosis to eight and sixteen threads. All six report zero internal gap. At eight threads B/R/G use 16,219.853/13,488.320/617.228 seconds, and at sixteen they use 13,071.843/16,005.814/791.673 seconds. The G points satisfy every original row, bound and binary domain under both exact arithmetic interpretations. Each of these four new control points contains one nonintegral binary; its rounded pattern has the same 0.0000416587 violation, and the row interval excludes every continuous completion with those rounded binaries fixed. Together, the two audits cover ten stored points: three G points and seven controls. This is a statement about those vectors, not an exact dual proof or a classification of the five unaudited M12 points.

With eight threads, the printed G/B/R work counts are 558.47/14139.09/12019.86 and the simplex iterations are 79943/4785572/5509499. With sixteen threads, the corresponding figures are 721.35/10209.34/12749.97 and 103045/8847763/13452114. The same G-versus-control presolved dimensions recur. All six root logs explicitly name deterministic concurrent LP optimization; the algorithm used here is therefore observed rather than inferred from Method=-1. Timing, work and presolve differences support a heterogeneous-search interpretation without proving which starting assignments caused it. A partial Start leaves all original domains free, so this behaviour should not be interpreted as trapping MILP optimization in a local optimum.

M4 also retains its numerical restriction. Its smallest reported feasible objective is 4.900767176540, while the largest reported bound is 4.907256631978: a difference of 0.006489455439, or 0.132417%. Identical input identities and a passed feasibility report do not make these bounds mutually exact. M4/M12 remain visible in descriptive quality and cost accounting but are excluded from exact-optimum and certified-speedup claims.

M0 has a smaller disagreement: the largest bound, 4.608320190371, exceeds the smallest feasible-objective report, 4.608296033273, by approximately 0.000524%. Although below the configured relative target, this still precludes an exact-certificate interpretation. Its time contrasts remain conditional on the reported tolerance-based criterion.

### B.12.3. Measurement and interpretation boundaries

The 60 completed records contain 293.919 hours of summed solver Runtime and 295.072 hours of summed job elapsed time. The latter exceeds Runtime by 64.23--82.93 seconds per job. Thus loading, checking and export do not alone explain contrasts of several hours. These complete-campaign totals exclude queueing and historical preparation expenditure. Observed allocation products are 1,750.185 physical core-hours and 3,500.369 logical AllocCPU-hours; they are neither measured utilization nor energy or financial charges.

Preparation is reused from the earlier campaign rather than measured anew. Cold and five-use allocations retain their scenario definitions, including the G-dependent preparation charged to R. They are not complete new cold-deployment measurements.

The complete evaluation supports a bounded interpretation: benefits in some M0 configurations, earlier intermediate progress without terminal attainment by G on M7, and large time contrasts on M12 that remain numerically qualified. One seed and one execution per configuration do not establish repeatability, seed-averaged superiority or independent generalization. A later prospective study could use these observations to separate numerical comparability, solver-seed stability and endpoint choice, without treating thread caps as replications.

## B.13. One-hour paired solver-seed results {#sec-pr94-appendix}

The one-hour comparison comprises 144 runs in 48 instance–seed blocks. Each run uses one physical solver thread. The design varies solver seed with fixed starts. It provides neither a thread-scaling comparison nor a comparison of concurrent MIP configurations. All blocks yielded three reconciled terminal records. All 96 supplied R and G starts were accepted by the solver. The solver ended at the time limit on 84 medium runs. The other six medium runs and all 54 easy runs attained the reported 0.01% criterion within the observation window. Each terminal incumbent passed the recorded checks at the applicable numerical tolerances.

### B.13.1. Easy instances

All 18 easy blocks attained 0.01% with all three methods. @tbl-pr94-easy reports the median observed time across the three seeds, and the median of the seed-paired ratios for each instance. The ratio columns use paired times directly, so dividing two columns of median times can give a different value.

| Instance | B (s) | R (s) | G (s) | R/B | G/B | G/R |
|:--|--:|--:|--:|--:|--:|--:|
| E0 | 104.2 | 110.0 | 235.3 | 1.070 | 2.234 | 2.266 |
| E3 | 71.0 | 71.8 | 42.8 | 1.022 | 0.603 | 0.609 |
| E6 | 67.7 | 69.7 | 52.8 | 1.031 | 0.751 | 0.734 |
| E14 | 83.9 | 80.9 | 75.7 | 1.027 | 0.833 | 0.936 |
| E27 | 65.6 | 68.5 | 54.9 | 1.044 | 0.806 | 0.764 |
| E29 | 89.6 | 91.0 | 129.3 | 0.981 | 1.482 | 1.569 |

: Easy-instance times to the 0.01% gap target. {#tbl-pr94-easy}

Across the 18 paired observations, geometric mean time ratios were 1.038 for R/B, 1.083 for G/B and 1.043 for G/R at 0.01%. At 10%, the G/B ratio was 0.752, compared with 1.083 at 0.01%. G was faster than B in ten of the 18 pairs at the tight target, but the larger slowdowns on E0 and E29 raised the geometric mean above one. Thus the balance between wins and losses and the size of those differences tell different parts of the story. All three methods have the same terminal primal values within floating-point rounding on these six instances.

### B.13.2. Medium instances

@tbl-pr94-medium reports median gaps over the three seeds and counts of observed target crossings within 3,600 seconds. At 5% and 1%, the attainment counts equal those at 0.01%. The common-horizon outcomes use the last observation at or before one hour, including the terminal result of early finishes. Late callback or terminal observations do not replace the fixed-horizon records.

| Instance | B gap (%) | R gap (%) | G gap (%) | 10% hits (B/R/G) | 0.01% hits (B/R/G) |
|:--|--:|--:|--:|:--:|:--:|
| M0 | 7.400 | 7.321 | 8.762 | 3/3/3 | 0/0/0 |
| M4 (restricted) | 8.562 | 9.029 | 8.232 | 3/3/3 | 0/0/0 |
| M5 | 15.336 | 15.985 | 13.960 | 0/0/0 | 0/0/0 |
| M6 | 18.595 | 18.973 | 16.501 | 0/0/0 | 0/0/0 |
| M7 | 16.917 | 19.868 | 14.795 | 0/0/0 | 0/0/0 |
| M9 | 19.095 | 18.270 | 18.417 | 0/0/0 | 0/0/0 |
| M12 (restricted) | 6.511 | 6.904 | 0.000 | 3/2/3 | 0/0/3 |
| M13 | 19.266 | 16.351 | 13.105 | 0/0/0 | 0/0/0 |
| M20 | 24.913 | 19.048 | 0.010 | 0/0/3 | 0/0/3 |
| M26 | 27.838 | 24.473 | 19.235 | 0/0/0 | 0/0/0 |

: Medium-instance gaps and target attainment at one hour. {#tbl-pr94-medium}

At 10%, G and B both attained in nine pairs, G alone in three, and neither in 18. For G and R, the corresponding counts were eight, four and 18. R and B both attained in eight, B alone in one, and neither in 21. After restricting the eligible time comparison to cases outside M4 and M12, only the three M0 seeds offer common 10% crossings for these contrasts. At 0.01% there are no pairs with common observed attainment. The exclusive G attainments on M20 therefore inform coverage under the fixed budget, with no observed time ratio against B or R. The nine M7 runs remained censored even at 10% in this one-hour study.

For each seed we calculate the relative primal and dual differences and the gap difference in percentage points, then take the median across seeds within each instance. Across the ten instance medians, the reported primal differences were -0.42% for G versus B and -0.92% for G versus R, the dual differences were +1.05% and +1.15%, and the gap differences were -2.11 and -2.52 percentage points. The gap medians remain -2.11 and -2.52 percentage points in the eight-instance sensitivity summary outside M4 and M12. R versus B gives +0.06 percentage points in that sensitivity summary. A smaller gap can coexist with a worse primal, as on M6 in G versus R. M20 contributes one instance-level attainment advantage, even though it recurs across three solver seeds. The results do not establish that G generally outperforms B or R.

### B.13.3. Numerical and cost scope {#sec-pr94-numerics-costs}

At M12 seed 42, G reports a bound of 4.741382855, above R's latest in-budget primal of 4.740933499. This cross-run difference of approximately 0.000449355 is retained as a numerical warning. It is consistent with the need for the separate M12 feasibility qualification in the longer experiment. The one-hour metadata document tolerance checks and solution hashes. Establishing exact feasibility for these new points would require examining the underlying vectors. Both M4 and M12 remain in the descriptive tables and outside the eligible time contrasts.

Total solver runtime was 87.61 hours and supervised attempt time was 89.60 hours, summed over runs. Slurm recorded 89.62 job-hours and 179.23 allocated logical CPU-hours, with two jobs overlapping at peak. These are separate accounting boundaries. The measured attempt includes model loading, optimization, audit and export. The return has no qualified cold or three-use amortized preparation totals for R or G. The times therefore support comparisons of the recorded attempts, while the cost of deploying and reusing the starting-information pipeline remains a separate question.
