# Sprint C: scientific evidence consolidation

## Initial scope

This PR starts the result schema and acceptance criteria. No benchmark values,
figures or claims are fabricated while Sprints A/B are unfinished. Manuscript
rewriting is deferred until all three sprints have evidence. See the separate
manuscript revision requirements for that later task.

## Planned outputs

| Table | Unit and required contents |
| --- | --- |
| `training_epoch_metrics.csv` | epoch1-100; training/validation weighted BCE; checkpoint selection |
| `easy_test_prediction_metrics.csv` | held-out easy parent; prevalence, PR metrics, calibration diagnostics |
| `medium_solver_outcomes.csv` | planned parent and method; status, primal, dual, gap, feasibility, censoring, missingness |
| `medium_time_regions.csv` | parent and method; read/build/optimize/total, preprocessing, inference and residual overhead |
| `medium_paired_effects.csv` | parent pair; gap difference, cost difference, denominator and validity of comparisons |
| `medium_target_gap_times.csv` | parent and method; time to10% gap, observation/censoring and reason |
| `experiment_coverage.csv` | planned/attempted/completed/missing/invalid counts, without survivorship filtering |

Figures: combined training and validation loss; descriptive easy test quality;
paired medium terminal gaps; optimize and end-to-end cost; target-gap attainment
with explicit censoring; coverage/missingness. Each figure must be generated from
a versioned table and labelled with cohort, seed, budget and experiment status.
Preserve source hashes, units and an output ledger. Do not use a publication-like
figure title to imply scientific certification.

## Analysis rules

- The independent experimental unit is the parent instance, not millions of
  binary targets, epochs, or repeated radii. Keep pooled prediction metrics
  separate from parent-level macro summaries.
- Report negative and null solver effects, start rejections, unavailable bounds,
  preparation failures and excluded source labels. Every exclusion has a reason.
- Do not divide censored optimization times and call the ratio a speedup to
  optimality. Use paired final gaps under equal optimize budgets and clearly
  stated time-to-target outcomes. When both reach a target, descriptive timing
  ratios may be reported with their restricted denominator.
- Report cold end-to-end costs as well as optimize-only costs. Improvements in
  one metric with regressions in another are trade-offs, not unconditional wins.
- Retain the existing unfavourable calibration evidence. Class-weighted BCE
  outputs are not automatically calibrated probabilities.
- One seed and a development-selected problem family do not establish broad
  generalisation. Replication and independent future cohorts remain explicit
  limitations; no variable-level significance test substitutes for parents.

## Completion criteria

1. Source training and paired benchmark integrity gates pass, or missing/failed
   components are explicitly classified rather than certified.
2. Table counts reconcile against the frozen manifests, with unique parent/method
   keys and no leakage of evaluation outcomes into selection.
3. Figure values reconcile with tables; training/validation curves share axes;
   source hashes, units, censoring and legends are visually reviewed.
4. A concise findings document distinguishes demonstrated results, inconclusive
   outcomes, engineering achievements and untested objectives.
5. Only then start the manuscript revision using the retained requirements.
