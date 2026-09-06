# MVP original graphs and four-arm composition

PR #29 closes the dataset boundary of the partial-population MVP. It consumes
independently solved original parents from Gurobi and SCIP plus the passing
derived-graph directory from PR #28. It does not solve a MIP or train a model.

## Symmetric original graphs

Each solver must contribute exactly the same set of original parent IDs. The
parent model bytes, fold, role, solution hash, objective, terminal MIP gap and
execution time are verified against the parent-solve plan and report. Labels
above the precommitted 10% relative-gap ceiling fail closed.

Original and derived samples use the same PySCIPOpt reader and production
`build_heterodata` encoder. The seventh variable feature is zero for every MVP
graph. For each parent, the original structural graph fingerprint must be
identical between Gurobi and SCIP; only the independently obtained label may
differ.

## Four composed arms

The output contains one manifest per experimental arm:

| Arm | Membership |
|---|---|
| `gurobi_original` | Gurobi original parents |
| `gurobi_incumbent_augmented` | the same parents plus Gurobi descendants |
| `scip_original` | SCIP original parents |
| `scip_incumbent_augmented` | the same parents plus SCIP descendants |

Derived samples are admitted only for training parents. Validation and test
remain original-only. Inside each training arm, every parent has total mass
one: if a parent has one original and three descendants, each receives weight
`1/4`. This prevents the number of accepted descendants from changing the
statistical unit.

The derived `.pt` files are hard-linked into the composed dataset when source
and destination share a filesystem. A byte-for-byte copy is only a fallback,
and its mode is reported. This preserves the artifact after an earlier run is
quarantined without normally consuming duplicate disk blocks.

## Common held-out reference

`evaluation_reference_manifest.jsonl` selects the best valid original label
across the two solvers using, in order: minimum objective, minimum MIP gap,
minimum execution time, and solver name as a deterministic tie-break. This
reference is independent of GNN predictions.

## Input inventory

Create a tab-separated file with one row per eligible parent solve. The same
parent set must appear for both solvers:

```text
gurobi<TAB>/raid/.../gurobi_parent_CFL_easy_instance_2_3171
scip<TAB>/raid/.../scip_parent_CFL_easy_instance_2_3167
```

Then submit:

```bash
export PARENT_RUNS_FILE=/raid/.../mvp_parent_runs.tsv
export DERIVED_GRAPH_DIR=/raid/.../mvp_derived_graphs_pr28_20260906T225348Z
export EXPERIMENT_NAME=mvp_four_arm_pr29_smoke

sbatch --export=ALL \
  scripts/slurm/dasci/submit_mvp_dataset_composition.sbs
```

Outputs include the unified `mvp_sample_manifest.jsonl`, four files under
`arms/`, `per_original_graph_audit.jsonl`, the common evaluation-reference
manifest, provenance sidecars, and `mvp_dataset_composition_report.json`.
All partial-population outputs remain `development_only=true` and
`scientific_reporting_eligible=false`.

