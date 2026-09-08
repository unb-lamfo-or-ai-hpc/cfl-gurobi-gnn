# Easy-only four-arm MVP dataset

This gate materializes the PR #33 development slice as the smallest dataset
that exercises all four experimental arms and all three partition roles. It
does not run a solver or train a model.

## Composition

The original MILP for each selected parent is encoded once per solver arm:

| Parent | Role | Label policy | Augmentation |
|---|---|---|---|
| `CFL_easy_instance_2` | train | solver-specific Gurobi/SCIP label | three descendants per solver |
| `CFL_easy_instance_1` | validation | common PR #33 reference | prohibited |
| `CFL_easy_instance_0` | test | common PR #33 reference | prohibited |

The validation and test graphs in both solver arms use the same solution
artifact and label metrics. The graph still records its experimental arm and
the solver that produced the shared reference separately.

The six derived graphs are the independently labelled PR #28 artifacts. Their
local-branching center need not be the file selected as the original-parent
label: it must be an independently admissible incumbent from the same parent
and solver. Candidate, operator, source-incumbent, label, graph, and provenance
contracts remain unchanged and are verified before reuse.

## Statistical and held-out boundaries

Each original-only training arm contains one easy-2 sample. Each augmented arm
contains that original plus its three solver-specific descendants. Stored
weights are therefore one for the original-only arm and one quarter for each
sample in the augmented arm, retaining total parent mass one.

Validation and test contain exactly one original sample per arm and no derived
sample. The test graph is materialized for the later evaluator but remains
held out from training and validation. The PR #30 loader is the next gate and
must prove that it does not deserialize test graphs during training.

All contracts use SHA-256 fingerprints and relative artifact paths. The output
is eligible only as a development dataset; scientific reporting remains
disabled until the planned parent population and final experimental protocol
are complete.

