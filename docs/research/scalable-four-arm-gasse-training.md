# Scalable four-arm Gasse training and held-out evaluation

> Historical cohort note: the 30-easy diagnostic and proposed 45-graph route
> below record earlier development decisions. The current frozen confirmation
> is 42 original parents (30 easy, 12 medium), with no hard parents; missing or
> inadmissible medium labels may not be silently excluded. Use the
> [PR49 confirmation protocol](pr49-confirmation-validation.md) and the
> [PR50 execution work](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/50).
> A paired four-arm intersection remains a separately reported population.

## Scope

This development gate reconnects the four solver/data arms to the preserved
`GasseGNN` training and held-out evaluation code. The arms are Gurobi original,
Gurobi incumbent-augmented, SCIP original, and SCIP incumbent-augmented. Gurobi
remains the graph-construction authority; SCIP is a matched comparison arm.

The implementation consumes the Gurobi-authoritative dataset produced by the
scalable augmentation pipeline. It does not solve parent or derived MIPs and it
does not move parents between folds.

## Experimental controls

- The random seed is fixed at 42.
- Each arm starts from an independently instantiated model with the same seeded
  initial state.
- Parent-balanced sampling gives each training parent equal mass in every arm.
- The two arms associated with one solver reuse the same original-parent
  pre-normalization reference and positive-class weight.
- Every arm receives the same optimizer-step budget per epoch.
- The checkpoint is selected by minimum weighted BCE on the common validation
  partition.
- Each arm's probability threshold is selected by maximum F1 on that same
  validation partition. The deterministic tie break prefers the threshold
  nearest 0.5 and then the lower threshold.
- Test graphs are not deserialized during training or threshold selection. They
  are loaded only by the final held-out evaluator.
- All four arms are forwarded to the solver benchmark. Test outcomes never
  select an arm.

The training protocol uses 100 epochs with seed 42. Early stopping cannot
shorten this confirmation budget. Every training run emits one SVG in which
training loss and validation loss share the same axis; the figure and history
are hash-bound to the run summary.

## Existing-graph confirmation cohort

The audited storage root contains 42 parent-instance graphs materialized in
earlier rounds: 30 easy, 12 medium, and zero hard. All 12 medium labels have
relative MIP gaps above 40%, ranging from approximately 43.29% to 84.73%.
Consequently they are not admissible under the precommitted 10% ceiling.

The immediate quality-controlled baseline therefore trains on the 30 eligible
easy graphs while recording that 42 graphs were discovered. The dedicated
`gap_le_10pct` label policy makes this exclusion part of the dataset contract,
rather than an informal post-hoc filter. The launcher fails closed unless it
observes 42 discovered graphs and exactly 30 eligible easy graphs.

This 30-graph cohort is suitable for diagnosing optimization behavior over 100
epochs and for confirming that training and validation curves are generated.
It is not a four-arm cohort: it must not be interpreted as having paired SCIP
labels or incumbent-derived variants when those artifacts do not exist.

The intended 45-graph easy-plus-medium confirmation requires a separate
Gurobi-first rescue: independently solve and label 15 medium parents to a
relative MIP gap no greater than 10%, materialize the three missing graphs, and
rebuild the affected graph labels under the accepted Gurobi-authoritative
contract. That campaign can run independently of the 30-easy confirmation.

The preserved `sandbox/toy_bipartite.py` path remains a required compatibility
gate for `GasseGNN`. The smoke suite exercises a deterministic toy graph through
pre-normalization, forward propagation, weighted binary cross-entropy, and one
optimizer step without changing the original toy entry point.

## Data-readiness gate

A raw LP file is not a training-ready sample. A valid execution requires at
least one immutable parent in each of the train, validation, and test roles,
with solver labels, Gurobi-authoritative graphs, provenance hashes, and the
four-arm manifests already accepted by the upstream gates. Derived Local
Branching samples are allowed only in training and inherit their parent's fold.

The four-arm run remains restricted to the common paired intersection that has
all required Gurobi and SCIP labels and derived graphs. If that intersection
lacks a validation or held-out test parent, the four-arm run remains blocked
without affecting the separate 45-graph baseline confirmation. The full
90-parent campaign remains deferred.

## Interpretation

Outputs from both the partial four-arm intersection and the 30-graph baseline
are development-only integration evidence. The curves confirm pipeline and
optimization behavior, but they do not support population-level inference
because hard instances are absent and the planned population is incomplete.
Scientific reporting remains disabled until the planned complete campaign is
executed.
