# Four-arm MVP training loader

This stage is the dependency-free gate between the composed dataset from PR
#29 and model training. It does not optimize a model. It verifies every input
contract and graph digest before PyTorch is allowed to deserialize a graph.

## Statistical unit and threshold

The parent MILPBench instance remains the statistical unit. The versioned
loader policy selects one of the gap thresholds precommitted by ADR 0012. The
threshold applies to training labels; validation and test use the common
best-known original reference selected before model training.

A parent is retained for training only when every one of the four arms has at
least one gap-eligible sample for that parent. This intersection keeps the
factorial comparison paired. When a stricter threshold removes a descendant,
the within-parent weights are recomputed over the remaining samples.

## Deterministic parent-balanced schedule

`deterministic_parent_balanced_cycle_v1` emits exactly the configured number of
draws for every parent in every epoch. An original-only arm repeats its one
graph; an augmented arm cycles deterministically through its eligible original
and derived graphs. The final epoch order is shuffled from the policy seed and
epoch number.

Consequently:

- every parent has identical realized mass, not merely equal expected mass;
- all four arms have the same number of optimizer updates per epoch;
- rerunning the same seed and epoch reproduces the same schedule;
- changing the gap threshold cannot silently retain stale PR #29 weights.

The default four draws per parent expose one original plus three local-
branching descendants when all are eligible. The number is part of the loader
contract and is not tuned from held-out performance.

## Held-out boundary

Training records are read from one arm manifest. Validation records are read
from `evaluation_reference_manifest.jsonl` and resolve to the selected original
graph. Test records are present in the plan but the loader audit never
deserializes them. The training implementation in the next sprint must retain
that boundary.

The current one-parent PR #29 artifact is expected to pass manifest, hash,
sampler, and graph-load checks while reporting `training_ready=false`, because
it has no validation or test parents. This is an honest development gate, not
a failure of the loader.

## DaSCI-DGX audit

```bash
export DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
export MVP_DATASET_DIR="${DATA_ROOT}/bipartite_graphs/mvp/<pr29-run>"
export EXPERIMENT_NAME=mvp_loader_pr30_smoke

sbatch --export=ALL \
  scripts/slurm/dasci/submit_mvp_training_loader_audit.sbs
```

The job writes `mvp_training_data_plan.json` and
`mvp_training_data_audit.json` below
`data/models/mvp/training_plans/<experiment>`. Persisted paths are relative to
the dataset root, so the reports contain no host-specific source path.

For the six-parent vertical slice, acceptance requires at least one common
training, validation, and test parent, `mvp_execution_ready=true`, equal sampler
draw counts for every parent, zero test graphs loaded, and a passing graph-load
smoke for all four arms plus the common validation reference.

