# SCIP domain-variant graph-observability audit

## Question

Do the local bound changes that distinguish a SCIP node MIP from its parent
survive the exact feature encoding used by the current bipartite graph builder?

## Scope

The audit reloads one schema-v3 root `writeMIP()` baseline and one or more
mechanically valid node `writeMIP()` artifacts. It extracts a solver-neutral
feature snapshot, calls the production `build_heterodata()` function, and
compares raw domains with encoded graph tensors.
The run contract is also bound to the SHA-256 of the production graph-builder
source so a later feature-code change cannot be mistaken for the same audit.

It does not write PyG datasets, generate labels, change folds, train models, or
modify the production graph builder. PySCIPOpt, PyTorch, and PyG are imported
only during the runtime audit; dry-run and contract tests remain lightweight.

## Required invariants

For a `domain_distinct_same_matrix` candidate:

- variable names and normalized types match the root;
- matrix, objective, topology, and constraint features match the root;
- at least one raw lower or upper bound differs;
- every variable with a raw bound difference also differs in encoded bound
  features;
- no encoded bound difference appears without a raw domain difference;
- non-bound variable features remain unchanged;
- variable-feature and complete-graph fingerprints differ from the root.

The audit fails closed if clipping, type normalization, ordering, or any other
step removes a raw domain change.

## Outputs

- `scip_domain_graph_audit_plan.json`;
- `scip_domain_graph_observability_report.json`;
- `per_candidate_graph_audit.jsonl`.

All outputs use file names and SHA-256 values rather than absolute input paths.
Both `dataset_eligible` and `label_eligible` remain false regardless of the
gate result.

## Interpretation

A passed gate proves only representational observability: the existing graph
features distinguish the tested domain-restricted formulations. It does not
validate targets, independence, sampling, or dataset eligibility. The next
permitted experiment is independent label validation on the derived MIPs.
