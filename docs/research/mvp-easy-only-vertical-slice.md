# Development-only easy MVP vertical slice

The six-parent easy/medium experiment remains the immutable fixed-budget
benchmark. Its medium observations and label-rescue runs are valid engineering
evidence, but they did not provide complete labels under the precommitted 10%
relative MIP-gap threshold. This gate therefore declares the previously listed
easy stratum as the smallest executable development slice. It does not change
the original experiment or claim scientific representativeness.

## Selected parents

Rotation 0 supplies one parent per role:

| Role | Parent | Downstream use |
|---|---|---|
| train | `CFL_easy_instance_2` | solver-specific Gurobi and SCIP labels; augmentation allowed |
| validation | `CFL_easy_instance_1` | one deterministic common reference; original graph only |
| test | `CFL_easy_instance_0` | one deterministic common reference; held out and original graph only |

The common validation and test references are selected among admissible
one-hour observations by relative gap, objective, execution time, and solver
name. Both solver-specific easy-2 labels must be admissible. The 10% threshold
is unchanged.

## Evidence boundary

The composer verifies the PR #31 vertical-slice contract, all twelve paired
benchmark observations, and the PR #32 rescue outcome. The fallback is allowed
only when all three rescue executions have valid integrity, exactly one rescue
label is admissible, two are inadmissible, and no execution failed. All medium
benchmark and rescue metrics are copied into a path-sanitized censored-evidence
inventory; no result is deleted or relabeled.

The output contract contains only relative artifact paths and SHA-256
fingerprints. It verifies solution artifacts without loading solution vectors
and does not deserialize any graph, especially the held-out test graph.

This slice remains `development_only=true`, `dataset_eligible=false`, and
`scientific_reporting_eligible=false`. The next gate composes the easy-only
four-arm dataset, retaining train-only local-branching descendants and common
original-only validation/test partitions.

