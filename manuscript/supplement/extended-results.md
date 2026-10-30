# Supplementary B: Extended Experimental Results {#sec-supp-results}

The extended results retain the original instance populations, measurement boundaries and numerical qualifications. Method/resource observations from the same instance are repeated conditions, not independent samples. Public source tables provide the original precision and artifact bindings; presentation rounding does not alter them.

## Principal CPU population and dispositions {#sec-cpu-coverage}

The principal comparison contains 150 seed42 records on six easy and four medium instances. Their three methods and five thread caps account for the rows below. The thirty sensitive observations are part of the same sample, not an additional population.

| Principal comparison | Records | Interpretation |
|:--|--:|:--|
| Easy instances | 90 | Six instances, three methods, five caps |
| Medium instances | 60 | Four instances, three methods, five caps |
| Solver-reported terminal target attained | 97 | Reported under tolerances, not exact optimality certificates |
| Terminal target right-censored | 53 | Not observed solution times at the limit |
| Numerically sensitive M4/M12 rows | 30 | Subset subject to metric-specific numerical restrictions |

: Scope and recorded dispositions of the principal CPU comparison. {#tbl-cpu-coverage}

Every easy instance attains the reported terminal target in each configuration. @tbl-easy-times lists their solver runtimes so that aggregate ratios can be read alongside individual effects. F denotes an easy instance; M denotes a medium instance.

{{< include ../tables/principal_easy_times.qmd >}}

## Medium instances: primal, dual and gap

The terminal records in @tbl-medium-quality distinguish feasible objective, solver bound, relative gap and terminal-target disposition. A smaller primal is better for minimization; a larger valid lower bound indicates stronger dual progress. These can change in opposite directions, so the gap must be interpreted with both components.

{{< include ../tables/principal_medium_quality.qmd >}}

Censoring here concerns the terminal target, not every earlier descriptive threshold. Terminal observations have their actual recorded runtimes rather than an imposed common endpoint. M4 and M12 remain visible with numerical restrictions; solver acceptance of original floating-point vectors does not certify rounded copies or exact feasibility. Their rows are not used to establish certified solution speedups.

The [principal rows](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/methodology-20261019/seed42_main.csv) retain method identifiers, exact values, censoring flags and receipt/child hashes. The [existing paired summaries](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/pr86/final-210/paired_uncertainty.csv) distinguish the seed42 view from historical repeats. Their intervals are exploratory under an exchangeable-instance model, not a guarantee of population coverage.

## Preparation and cost interpretation

The article's cost table uses the six easy instances at sixteen threads and seed42. Solver Runtime, supervised attempt time and preparation are separate quantities. The delimited cold scenario adds recorded preparation to the attempt, while the broader allocation also apportions documented preparation overhead. The seven-use scenario spreads that preparation across seven assumed uses; it does not remove expenditure from campaign accounting.

A five-use allocation appears in a different derived table and must retain that assumption. Neither scenario is a newly measured complete application. Components included within larger intervals, such as a forward pass within inference, are not added twice. R retains the cost of G-dependent matching.

The [cost scenarios](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3f5789fe34fe1dc9f80f84e3e2c46d3bdea3f30f/docs/evidence/pr86/final-210/cost_scenarios.csv) identify these scopes by instance and configuration. Missing cold-use components remain unavailable rather than zero. CPU accounting, physical reservation and allocated GPU-hours are different resource measures.

## Historical predictor and learning dynamics {#sec-historical-predictive}

The archived predictive assessment uses ten test graphs and is distinct from the six-medium optimization population below. @fig-loss shows the complete original 100-epoch history; @tbl-predictive reports the validation-selected checkpoint rather than the terminal model.

![Historical training and validation weighted BCE over 100 epochs.](../figures/figure_training_validation_loss.pdf){#fig-loss width=100%}

Training BCE decreases from 1.5877 to 0.0275. Validation BCE reaches its minimum 0.0510 at epoch 34 and is 0.1124 at epoch 100. The selected predictive result is therefore not replaced by the terminal state.

{{< include ../tables/current_predictive.qmd >}}

Precision and recall are 0.6923 and 0.7064; pooled F1 is 0.6993 and parent-macro F1 is 0.7027. AP 0.7745 and trapezoidal PR-AUC 0.7747 are distinct ranking summaries. The test contains 5,536,400 binary targets and 5,265 positives, approximately 0.0951%. Those targets are not independent problem instances.

## Preliminary six-medium optimization study {#sec-historical-six-medium}

This study uses medium instances 0, 4, 7, 9, 12 and 20 for optimization testing, separately from its six-medium guidance-validation cohort. Its single-thread, seed42, 3,600-second runs retain their original policy and method-order protocol. It is supporting historical evidence, not the ten-instance principal CPU matrix.

### Guidance qualification and frozen testing

All six validation Starts are reported as loaded without abstention. Four reduce terminal gap, the median guided-minus-control difference is -1.224 percentage points, and only one increase exceeds one point, satisfying the original qualification rule. Medium instance 19 reports zero gap near 671 seconds while its unguided comparator exhausts the time limit. These validation observations are not test results.

After qualification, checkpoint, threshold, support and ordering remain fixed. @tbl-heldout reports all six test pairs rather than selecting the favourable cases.

{{< include ../tables/current_heldout.qmd >}}

The GNN start reduces terminal gap on five of six instances, with median difference -1.164 percentage points. Medium instances 12 and 20 account for much of the magnitude. Medium 0 reaches the observed 10% target earlier despite a worse terminal gap; medium 4 exhibits the converse. @fig-effects separates validation and test observations.

![Paired terminal-gap differences in the separate historical study.](../figures/figure_validation_test_gap_effects.pdf){#fig-effects width=100%}

Negative differences favour G. Panel scales differ and values are percentage points, rather than relative percent improvements.

### Quality targets, censoring and influence

A first observed crossing is a different endpoint from terminal gap. @fig-target-time shows the 10% crossing and retains unobserved targets as censored.

![First observed 10% relative-gap crossings in the historical study.](../figures/figure_time_to_ten_percent_gap.pdf){#fig-target-time width=100%}

Hatching indicates a target unobserved within the recorded budget, not attainment at 3,600 seconds. G crosses on four instances, versus three per comparator. The medium 12 and 20 G crossings are approximately 672 and 1,168 seconds. Preparation and inference are outside these solver observations.

@tbl-influence reports the full population and post-analysis leave-out diagnostics without redefining the original test set.

{{< include ../tables/current_influence.qmd >}}

The mean paired gap difference is -7.200 percentage points. It is -1.659 without medium 20 and -0.556 without medium 12 and 20; medians are -1.164, -0.213 and -0.140 points. The magnitude is therefore influence-sensitive even where the direction remains favourable. The root-LP comparator improves terminal gap on one of six instances; its median difference from control is approximately +1.124 points.

### Optimization and worker time

@tbl-times distinguishes optimization from the historical worker interval. This distinction prevents attributing the omitted neural preparation to a zero-cost application.

{{< include ../tables/current_timing.qmd >}}

The GNN runs on medium instances 12 and 20 use approximately 702 and 1,585 solver seconds. Four GNN runs and all comparator runs exhaust the time budget; medium 0 and 4 nevertheless reach 10% with G. These are compatible endpoint-specific observations. Worker time includes verification, model construction, optimization and auditing but excludes feature preparation, inference and orchestration.

The [historical manifest](../results/current/pr60_scientific_evidence_manifest.json) binds the original tables and figures. The later principal CPU matrix and GPU pair have their own sources. None of these records turns historical exposure into an independent generalization test.
