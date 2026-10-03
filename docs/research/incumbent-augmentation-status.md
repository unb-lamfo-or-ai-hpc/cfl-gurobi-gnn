# Incumbent and augmentation evidence status at MVP 1.0

## What the completed experiment establishes

The 54-parent predictor uses one independently screened Gurobi label per original model. The final training study is original-instance-only. Neither a matched four-arm augmentation benefit nor a complete matched SCIP collection on those same 54 parents is demonstrated by the frozen publication inputs.

The repository implements Gurobi incumbent capture, SCIP original-parent collection, local-branching derived-model generation, independent derived-model labelling and four-arm training plans. Implementation and bounded engineering tests establish available mechanisms, not complete population-scale execution.

## What must not be inferred

It is not currently possible to state how many unique feasible incumbents each solver supplied across all 54 parents from the thirteen publication inputs. Missing population counters are unavailable, not zero. Historical pilot counts, solver solution counts and Parquet row counts must not be silently substituted for a reconciled 54-parent result. The aggregate legacy archive also contains different experiments and model conventions; it is not a compatible current-cohort total.

An incumbent event, a distinct solution vector, a solution-pool entry, an independently certified label and a derived synthetic MILP are different objects. Multiple incumbent vectors for an unchanged model do not increase the number of independent problem instances. Repeated vectors across budgets, solvers or source runs can inflate event totals. Approximate incumbents may be useful generation inputs without satisfying the final label gap threshold.

## Required reconstruction

For each admitted parent, inventory existing solver-specific Parquet tables and solve reports, including failed/censored attempts and their resource budgets. Read Parquet metadata without loading pickle/PyTorch objects. Initially report rows and available scalar counters as observations. Then qualify table semantics, reconstruct variable order, deduplicate solution vectors and independently check feasibility/objective/gap. Join source-parent roles and derivative reports to identify which synthetic MILPs were generated, independently labelled, encoded and actually used for fitting.

The diagnostic inventory supplied with the corrected archival tools reads only generated outputs and records JSON parse failures. It does not run a solver, deserialize training binaries, create derivatives or equate unqualified rows with unique valid incumbents. Population totals require the resulting HPC evidence. Data and manuscript updates should follow that reconstruction, rather than an assumed oversampling narrative.

## Next experimental steps

Use only fitting-parent incumbents for augmentation. Qualify independent derived labels and Gurobi-authority root features before encoding. Compare original-only and available matched Gurobi/SCIP arms with controlled parent mass and duplicate/lineage checks. Keep validation and test descendants out of fitting. Report generation yield, rejection reasons, diversity and predictive/optimization effects separately. A successful collection mechanism alone is not evidence that oversampling improves warm starts.
