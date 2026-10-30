# Supplementary material guide

These materials accompany **Evaluating Graph Neural Network-Based Partial Warm Starts for Capacitated Facility Location Problems**. They explain the evaluated method, extend the reported results and identify the settings needed to interpret or reproduce the public analyses.

- [Supplementary A](gnn-methods-audit.md) develops the graph representation, predictor, selection rules and solver interface. It distinguishes the fixed implementation from other learned optimization mechanisms.
- [Supplementary B](extended-results.md) presents per-instance CPU outcomes and the separate historical optimization evidence, retaining censoring, adverse outcomes and numerical restrictions.
- [Supplementary C](configuration-reference.md) lists inputs, parameters, hyperparameters, partitions, software and artifact identities, including the limits of measurement and access.

The combined supplement is rendered from [index.qmd](index.qmd). Its configuration records distinguish specifications from outcome observations. Sensitivity studies discussed in the article's conclusion remain future research.

## Interpreting prediction and optimization evidence

A predictive score measures agreement with a reference label; a Start is a partial candidate; and an incumbent is a solver-retained feasible solution under its numerical conventions. These objects are not interchangeable. Likewise, a common-target crossing, a time-limited terminal state and an exact optimality certificate have different evidential scopes.

B/R/G are presentation names for stored methods M0/M1/M2. Original-instance identifiers occupy a separate field. Instance M0 is not method M0. Repeated method/resource conditions do not create additional independent instances.

The [numerical claim index](claim-evidence.json) records immutable source identities, selectors, units and displayed rounding. It supports traceability of the registered numerical statements, including the extended results; it does not independently rescore predictions or establish scientific validity. Historical tables and figures retain their original manifest.
