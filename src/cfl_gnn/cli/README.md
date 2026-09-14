# Command-line interfaces

These modules expose package functions without duplicating solver or learning
implementations. Inspect the chosen module's `--help` and its
[protocol](../../../docs/README.md) before execution.

Current route families include `plan_parent_collection`,
`run_parent_collection_task`, `audit_parent_collection`,
`build_gurobi_graph_dataset`, `scalable_augmentation`,
`build_scalable_gurobi_dataset`, `train_gasse_reconnected`,
`evaluate_gasse_reconnected`, and `run_native_neural_guidance`.

`collect_incumbents`, `build_dataset`, `train_serial`,
`train_distributed`, and `evaluate` also preserve earlier interfaces.
Do not infer a compatible artifact schema solely from a similar command name.
Use the run's plan and hashes; no CLI may move test parents into training.

