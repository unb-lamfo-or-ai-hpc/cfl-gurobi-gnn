# MVP derived graphs and sample manifest

PR #28 converts only independently labelled local-branching MIPs that passed
the PR #27 gate.  It builds each graph from the derived LP itself, joins the
named independent solution by variable identity, and emits the canonical
`mvp_sample_manifest.jsonl` fragment for the two augmented arms.

## Fail-closed lineage

The builder requires one passing Gurobi run and one passing SCIP run.  Every
candidate LP, generation sidecar and solution artifact must match its recorded
SHA-256.  Solver, parent, fold, role, local-branching radius, source incumbent,
label objective, terminal MIP gap and execution time must agree through the
entire chain.  Derived samples remain train-only and inherit their parent fold.

Both solver arms are read by the same PySCIPOpt LP extractor and encoded by
`cfl_gnn.graph.build_dataset.build_heterodata`.  PySCIPOpt is preprocessing in
this stage; it does not produce or modify either independent label.  Binary
variables serialized by LP as integer variables with bounds in `[0, 1]` are
canonicalized back to binary.

## Root-relaxation policy

The seventh variable feature is retained for architectural compatibility but
set to zero for every MVP derived graph.  This is a precommitted symmetric
ablation: it avoids making the augmented SCIP arm depend on a Gurobi relaxation
or introducing solver-dependent LP optima.  The same policy must be used when
the MVP original-arm graph manifests are composed in the next dataset sprint.

## Eligibility

The output manifest is re-read by the PR #24 MVP contract.  A graph becomes
`dataset_eligible=true` only when it is readable after serialization, its
solution covers exactly the candidate variable identities, its hashes and
lineage match, and no sibling radius in the same parent/solver arm produces a
duplicate structural graph.  All artifacts remain
`scientific_reporting_eligible=false` while the parent inventory is partial.

Outputs:

- `mvp_derived_graph_plan.json`;
- `mvp_derived_graph_report.json`;
- `mvp_sample_manifest.jsonl`;
- `per_derived_graph_audit.jsonl`;
- `graphs/<solver>/<sample_id>.pt`;
- `provenance/<solver>/<sample_id>.provenance.json`.

The next gate composes original-sample manifests for Gurobi and SCIP under the
same feature policy, then assembles the four training arms with equal parent
mass.
