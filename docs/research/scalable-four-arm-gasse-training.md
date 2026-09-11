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

The training protocol uses ten epochs for the accelerated integration MVP.
This is sufficient to validate histories, checkpoints, validation-only
calibration, held-out metrics, and downstream publication figures. It is not a
substitute for the deferred 90-parent, five-rotation scientific campaign.

## Data-readiness gate

A raw LP file is not a training-ready sample. A valid execution requires at
least one immutable parent in each of the train, validation, and test roles,
with solver labels, Gurobi-authoritative graphs, provenance hashes, and the
four-arm manifests already accepted by the upstream gates. Derived Local
Branching samples are allowed only in training and inherit their parent's fold.

The bounded PR #47 evidence contains a training parent and a held-out test
parent but no validation parent. Therefore the shortest admissible continuation
is a three-parent vertical slice: preserve the accepted train and test parents,
process one manifest-assigned validation parent through the existing paired
parent and Gurobi-authoritative graph stages, and then compose the four-arm
dataset. The full 90-parent campaign remains deferred.

## Interpretation

Outputs from the three-parent slice are development-only integration evidence.
They may be used to inspect training curves and verify the publication-output
code, but not for population-level scientific inference. Scientific reporting
remains disabled until the planned complete campaign is executed.
