# CFL research package

The package uses a `src` layout. Install it before invoking
`python3 -m cfl_gnn.cli.<entrypoint>`; do not prepend `src.` to the module name.

| Layer | Responsibility |
|---|---|
| [cli](cli/README.md) | Public command adapters |
| [pipelines](pipelines/README.md) | Campaign composition and provenance |
| [solvers](solvers/README.md) | Native Gurobi and PySCIPOpt execution |
| [augmentation](augmentation/README.md) | Explicit synthetic MIP operators |
| [artifacts](artifacts/README.md) | Persisted schemas |
| [graph](graph/README.md) | Gurobi-authoritative features and dataset access |
| [splits](splits/README.md) | Canonical parent partitions |
| [models](models/README.md) | Preserved and versioned GNN architectures |
| [training](training/README.md) | Learning, sampling, and checkpoint policy |
| [evaluation](evaluation/README.md) | Held-out diagnostics and predictions |
| [analysis](analysis/README.md) | Descriptive and artifact audits |
| [experiments](experiments/README.md) | Methodological contracts |
| [validation](validation/README.md) | Independent mathematical checks |

Legacy entry points remain for reproducibility. Their presence does not make
them defaults for the current confirmation protocol.

