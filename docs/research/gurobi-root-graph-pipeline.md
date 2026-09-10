# Gurobi-authoritative graph pipeline

## Methodological role

The recovered graph stage creates exactly one bipartite graph for each
mathematical MIP. Original parents and genuinely modified synthetic MIPs are
graph identities. Incumbent observations are labels and provenance only; they
do not create additional graph copies.

Gurobi is the sole authority for reading the MIP, extracting its objective,
domains, constraint matrix, and first optimal root-node relaxation. PySCIPOpt
does not participate in graph construction. Its results remain available only
for matched solver comparisons.

The root feature is captured by a passive `MIPNODE` callback at explored-node
count zero with optimal node status. The model records its erroneous source
`MAXIMIZE` declaration and forces the effective sense to `MINIMIZE`. Presolve
is disabled for the PR #43 parity gate because that is the preserved Phase 1
configuration for the selected positive-control instance.

There is no zero-vector fallback and no substitution with a separately solved
continuous relaxation. If the documented root callback is not observed, the
variable order changes, or the vector contains non-finite values, graph
construction fails.

## Legacy parity gate

The preserved `node_relaxations.parquet` is not a graph source. For
`CFL_easy_instance_2`, its first node-zero record is an independent historical
positive control. The newly captured Gurobi vector must have the same length
and agree within the precommitted absolute tolerance of `1e-8`. New parents
without a historical observation remain buildable after this implementation
gate, but never receive fabricated parity evidence.

## Descriptive analysis

Every successful run invokes the manifest-bound `graph_statistics` and
`graph_clustering` stages. Statistics report variables, constraints, nonzeros,
density, discrete and positive-label fractions, root-feature range and
nonzero fraction, MIP gap, and label-solve time. Clustering uses relative
macro-topological features, population z-scores, deterministic SVD PCA, and a
maximum of three deterministic k-means clusters. Clusters are descriptive;
inferential claims and arm selection remain prohibited for the partial MVP.

## DaSCI-DGX validation

Use the exact PR #42 plan and run root that produced the accepted paired
parent report. Do not rerun either parent solver.

```bash
conda activate tfm_env
python3 -m pip install -e . --no-deps

export REPO_ROOT="$(pwd -P)"
export DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
export BASE_SOURCE_DIR="${DATA_ROOT}/raw/MILPBench/CFL"
export LEGACY_INTERMEDIATE_DIR="${DATA_ROOT}/intermediate_lps"
export GUROBI_LICENSE_FILE="${REPO_ROOT}/secrets/gurobi.lic"
export GRAPH_INSTANCES="CFL_easy_instance_2"
export REQUIRE_LEGACY_PARITY=1
export ROOT_TIME_LIMIT_SECONDS=600

# Restore these two paths from the accepted PR #42 execution.
export PARENT_COLLECTION_PLAN_DIR=/path/to/pr42_plan
export PARENT_COLLECTION_RUN_ROOT=/path/to/pr42_run_root

export GRAPH_RUN_TAG="pr43_$(date -u +%Y%m%dT%H%M%SZ)"
export GUROBI_GRAPH_OUTPUT_DIR="${DATA_ROOT}/bipartite_graphs/\
gurobi_authoritative/${GRAPH_RUN_TAG}"

python3 -m cfl_gnn.cli.build_gurobi_graph_dataset \
  --parent_collection_plan_dir "${PARENT_COLLECTION_PLAN_DIR}" \
  --parent_collection_run_root "${PARENT_COLLECTION_RUN_ROOT}" \
  --base_source_dir "${BASE_SOURCE_DIR}" \
  --legacy_intermediate_dir "${LEGACY_INTERMEDIATE_DIR}" \
  --output_dir "${GUROBI_GRAPH_OUTPUT_DIR}" \
  --instances CFL_easy_instance_2 \
  --require_legacy_parity \
  --root_time_limit 600 \
  --dry_run \
  --overwrite

GRAPH_JOB_ID=$(sbatch --parsable \
  --export=ALL \
  scripts/slurm/dasci/submit_gurobi_graph_dataset.sbs)
GRAPH_JOB_ID=${GRAPH_JOB_ID%%;*}
echo "GRAPH_JOB_ID=${GRAPH_JOB_ID}"
```

The accepted report must contain one planned and written graph, one unique MIP
hash, exact encoding of the root feature, passed legacy parity, passed graph
statistics and clustering, `dataset_eligible=true`,
`scientific_reporting_eligible=false`, and the next gate
`gasse_training_pipeline_reconnection`.

## Boundary of PR #43

This PR does not train the GNN, select an experimental arm, alter the preserved
Gasse architecture, or reinterpret the old zero-ablation artifacts. Those
artifacts remain historical engineering evidence. PR #44 will consume only
the new Gurobi-authoritative graph manifest.
