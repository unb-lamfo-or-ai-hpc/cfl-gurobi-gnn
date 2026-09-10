# Gurobi-authoritative derived-MIP augmentation

## Scope

This stage extends the reconnected Gasse training pipeline from original parent
instances to independently solved local-branching MIPs. It creates four
comparable training views:

- Gurobi labels on original instances;
- Gurobi labels on original and Gurobi-incumbent-derived instances;
- SCIP labels on original instances; and
- SCIP labels on original and SCIP-incumbent-derived instances.

The solver named by an arm is the label and incumbent source. Gurobi remains
the exclusive graph-construction authority for every original or derived MIP.

## Identity and label contract

Each derived graph represents the exact local-branching MIP identified by its
candidate SHA-256. Its label artifact must identify the same candidate SHA-256
and must have been produced by an independent optimization of that candidate.
A parent solution is never reused as a descendant label.

The Gurobi and SCIP augmentation designs must contain the same parent, radius,
and radius-fraction combinations. Every derived parent must also occur in the
corresponding original training view. Derived records are restricted to the
training partition and inherit the parent fold.

## Graph contract

The graph builder reads every derived MIP with Gurobi, forces the known CFL
objective correction from recorded `MAXIMIZE` to effective `MINIMIZE`, and
captures the first optimal root-node relaxation through `MIPNODE`. A graph is
admissible only when the root vector is encoded exactly, the solution variable
identities match, and a fresh round-trip read succeeds. Zero-valued or generic
continuous-relaxation fallbacks are prohibited.

SCIP-derived labels do not authorize SCIP graph construction. They are overlaid
by variable name on a Gurobi-authoritative graph only when the sample is loaded.

## Training package

The output is self-contained: graph, root-relaxation, and named-label artifacts
are materialized together with four hash-validated Gasse training plans. The
original-only plans preserve their parent population. Augmented plans add only
their solver-consistent descendants. Sampling remains parent-balanced so that
parents with more derived samples do not receive greater total mass.

The current partial-population run is an engineering smoke. It remains
development-only and is not eligible for scientific reporting. Validation-based
checkpoint and threshold selection, followed by held-out test evaluation, still
require complete train, validation, and test graph inventories.
