# Pipeline orchestration

[parent_population.py](parent_population.py) and
[parent_collection_task.py](parent_collection_task.py) coordinate parent solves.
[gurobi_incumbents.py](gurobi_incumbents.py) preserves the original Gurobi
collection backend; SCIP collection remains separately identified.

[gurobi_graph_dataset.py](gurobi_graph_dataset.py),
[gurobi_derived_training_dataset.py](gurobi_derived_training_dataset.py), and
[scalable_augmentation.py](scalable_augmentation.py) connect accepted originals
and synthetic MIPs to Gurobi-authoritative graphs.
[confirmation_campaign.py](confirmation_campaign.py) freezes and audits the
42-parent confirmation inventory; source execution is extended in
[PR #50](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/50).

Orchestration must retain input hashes, budgets, selected labels, and failed or
censored evidence. Reuse is conditional on matching contracts, not merely an
existing file. Historical `mvp_*` routes must not silently replace strict graph
or current learning semantics.

