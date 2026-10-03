# DaSCI-DGX launchers

This directory contains current campaign launchers and preserved legacy
`submit_step*` examples. Select a launcher through its associated
[research protocol](../../../docs/research/README.md), not by filename order.

## Before submission

Use the intended DGX host, repository root, qualified environment, explicit
input directories, and readable Gurobi license. Check LF line endings and
restore variables in every new shell. A `_DIR` variable must not include the
JSON filename. Existing absolute paths in legacy launchers are site-specific.

Do not edit scheduler resources or pull another branch into a checkout serving
active jobs. Jobs with `afterany` dependencies still need an aggregate that
rejects missing or invalid results; `afterok` alone is not a scientific gate.

The `submit_step*` scripts reproduce earlier incumbent-conditioned experiments.
Their gap thresholds, graph counts, and random-split assumptions are not current
confirmation defaults. Their comments and display messages are translated
without changing commands or allocation requests.

The [toy launcher](submit_toy_gnn.sbs) runs the preserved sandbox; this checks
model compatibility, not real-instance quality. Native licensed tests and
actual campaign validation remain separate obligations.

