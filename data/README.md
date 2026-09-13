# Research artifacts and data lifecycle

Raw data, solver trajectories, graphs, and model outputs are separate artifact
classes. Files present locally are not necessarily tracked or distributable.

## Raw input layout

Download links are preserved in the [root README](../README.md). The canonical
raw hierarchy is:

```text
raw/MILPBench/CFL/
  CFL_easy_instance/LP/CFL_easy_instance_0.lp.gz
  CFL_medium_instance/LP/CFL_medium_instance_0.lp.gz
  CFL_hard_instance/LP/CFL_hard_instance_0.lp.gz
```

These are layout examples, not proof of local availability. Preserve original
bytes and hashes; the solver forces MINIMIZE in memory and records the original
objective declaration.

## Artifact roles

| Location | Role |
|---|---|
| `intermediate_lps/` | Historical Gurobi features, incumbents, pool solutions, and metadata |
| `intermediate/` | Versioned parent solutions, synthetic MIPs, and independent derived labels |
| `bipartite_graphs/` | Graphs and manifests; strict and historical variants must remain distinguishable |
| `models/` | Training plans, histories, checkpoints, and held-out predictions |
| `analysis/` | Coverage, graph diagnostics, solver comparisons, and publication outputs |

The plan and receipt, not a directory name, determine eligibility. Labels and
root features are different artifacts. A source incumbent's gap/time must not
be substituted for a derived label's gap/time.

Do not commit large tensors, private paths, licenses, raw credential-bearing
logs, or unreviewed reports. Do not delete or quarantine files referenced by an
active manifest. Historical failures are evidence and should remain recoverable.
External data and solver rights are separate from the repository's MIT license.
Original project-generated metadata, tables and figures use MIT within the
authors' rights; see [data licensing](LICENSE.md) and the
[repository policy](../LICENSE_POLICY.md). Neither notice relicenses MILPBench.
