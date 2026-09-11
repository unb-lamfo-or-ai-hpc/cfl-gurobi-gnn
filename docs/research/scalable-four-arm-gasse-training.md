# Scalable four-arm Gasse training and held-out evaluation

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

The accelerated baseline uses only the parent-instance graphs that were
already materialized in earlier rounds: 30 easy, 15 medium, and zero hard
instances. The launcher fails closed unless this exact 45-graph inventory is
observed. The `all_available` label policy is permitted only together with the
explicit development-only flag.

This 45-graph cohort is suitable for diagnosing optimization behavior over 100
epochs and for confirming that training and validation curves are generated.
It is not a four-arm cohort: it must not be interpreted as having paired SCIP
labels or incumbent-derived variants when those artifacts do not exist.

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

Outputs from both the partial four-arm intersection and the 45-graph baseline
are development-only integration evidence. The curves confirm pipeline and
optimization behavior, but they do not support population-level inference
because hard instances are absent and the planned population is incomplete.
Scientific reporting remains disabled until the planned complete campaign is
executed.
