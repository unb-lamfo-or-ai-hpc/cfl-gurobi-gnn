# Gurobi-first original-parent collection

## Scope

This stage reconnects the preserved Phase 1 collector to the revised research
pipeline. It solves each available original CFL parent, streams every observed
incumbent vector, and emits a common artifact contract for both solvers.
Gurobi is the priority solver and graph authority. PySCIPOpt is executed only
as a matched comparison after the complete Gurobi array succeeds.

The historical `collect_incumbents` batch entry point remains available. The
specialized `collect_gurobi_parent_solution` path now reaches the canonical
`gurobi_incumbents.solve_parent_mip` backend through the shared parent
contract; the SCIP entry point reaches the corresponding PySCIPOpt kernel.
This preserves the legacy implementation surface while removing duplicated
population orchestration.

The campaign targets the fixed 90-parent manifest. During development, the
planner records unavailable parents instead of fabricating data or changing the
population. A partial campaign is always marked `development_only` and cannot
support scientific reporting.

## Contracts

- The source MIP SHA-256 is fixed before execution and checked again by the
  worker.
- The erroneous `MAXIMIZE` declaration in the MILPBench CFL files is recorded
  as the original sense and the effective solve sense is forced to `MINIMIZE`.
- Gurobi uses a passive `MIPSOL` callback. PySCIPOpt uses a passive
  `BESTSOLFOUND` event handler. Neither callback changes the search.
- Each run starts in a fresh process, receives no warm start, and streams full
  incumbent vectors to Parquet.
- `terminal_mip_gap_relative` and `model_optimize_wall_time_seconds` are the
  primary outcomes. The external wall clock is also partitioned into total,
  data-read, model-build, and optimize regions. The solver's internal runtime
  remains available separately as `solver_execution_time_seconds`.
- Right-censored runs remain in the descriptive tables and are explicitly
  flagged. They are not discarded or treated as optimal observations.
- Resume is conservative: an existing run is reused only when its parent hash,
  solve contract, validation checks, and all artifact hashes still match.

## DaSCI-DGX execution

Run from the repository root after installing the editable package. The
example plans only the instances currently present under the raw CFL root; the
same commands automatically expand to 90 parents when all files exist.

```bash
conda activate tfm_env
python3 -m pip install -e . --no-deps

export REPO_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn
export DATA_ROOT="${REPO_ROOT}/data"
export BASE_SOURCE_DIR="${DATA_ROOT}/raw/MILPBench/CFL"
export PARENT_COLLECTION_PLAN_DIR="${DATA_ROOT}/analysis/parent_collection/parent_collection_pr42"
export PARENT_COLLECTION_RUN_ROOT="${DATA_ROOT}/intermediate/parent_solutions/parent_collection_pr42"
export PARENT_COLLECTION_AUDIT_DIR="${DATA_ROOT}/analysis/parent_collection/parent_collection_pr42_audit"

python3 -m cfl_gnn.cli.plan_parent_collection \
  --base_source_dir "${BASE_SOURCE_DIR}" \
  --output_dir "${PARENT_COLLECTION_PLAN_DIR}" \
  --parent_manifest configs/splits/cfl_90_seed42_folds.csv \
  --instances CFL_easy_instance_2 \
  --time_limit 3600 \
  --overwrite
```

The PR #42 gate is deliberately restricted to the known parent
`CFL_easy_instance_2`: one fresh Gurobi run and one matched PySCIPOpt run are
enough to validate collection, timing, provenance, and Phase 1 analysis. Remove
`--instances CFL_easy_instance_2` only when starting the later approved
population campaign; doing so during this PR would prematurely spend the
computational budget reserved for pipeline execution.

The accepted per-parent time budgets are 3,600 or 14,400 seconds. Determine the
actual array length from the generated solver manifest, then submit Gurobi
first and bind SCIP to its successful completion:

```bash
GUROBI_TASKS=$(wc -l < "${PARENT_COLLECTION_PLAN_DIR}/gurobi_parent_collection_tasks.jsonl")
SCIP_TASKS=$(wc -l < "${PARENT_COLLECTION_PLAN_DIR}/scip_parent_collection_tasks.jsonl")

GUROBI_JOB_ID=$(sbatch --parsable \
  --array="0-$((GUROBI_TASKS - 1))%4" \
  --export=ALL,SOLVER=gurobi \
  scripts/slurm/dasci/submit_parent_collection_array.sbs)
GUROBI_JOB_ID=${GUROBI_JOB_ID%%;*}

SCIP_JOB_ID=$(sbatch --parsable \
  --dependency="afterok:${GUROBI_JOB_ID}" \
  --array="0-$((SCIP_TASKS - 1))%4" \
  --export=ALL,SOLVER=scip \
  scripts/slurm/dasci/submit_parent_collection_array.sbs)
SCIP_JOB_ID=${SCIP_JOB_ID%%;*}

AUDIT_JOB_ID=$(sbatch --parsable \
  --dependency="afterok:${SCIP_JOB_ID}" \
  --export=ALL \
  scripts/slurm/dasci/submit_parent_collection_audit.sbs)
AUDIT_JOB_ID=${AUDIT_JOB_ID%%;*}
```

Use `--time_limit 14400` only as a precommitted campaign-wide sensitivity, not
as a per-instance rescue chosen after seeing outcomes. Arrays may be repeated
without `OVERWRITE=1`; valid completed runs are hash-checked and reused.

## Phase 1 outputs

`audit_parent_collection` produces the following path-neutral artifacts:

- `parent_solve_metrics.csv`: coverage, status, objective, bound, terminal MIP
  gap, four time regions, node counts, censoring, and label eligibility;
- `incumbent_trajectory.csv`: objective, bound, MIP gap, time, and node at each
  observed incumbent;
- `paired_parent_metrics.csv`: paired SCIP-minus-Gurobi descriptive effects on
  common parents;
- `parent_gap_sensitivity.csv`: counts at 1%, 5%, 6%, and 10% terminal gaps;
- three SVG figures for terminal gaps, time regions, and incumbent trajectories;
- `parent_collection_audit_report.json`: hashes, gate status, failure inventory,
  and the next-gate decision.

These outputs restore and generalize the descriptive intent of
`audit_phase1_eda.py`. The legacy entry point remains available for historical
artifacts, while the common audit is authoritative for newly collected paired
parent runs.

## Boundary of PR #42

This stage does not build graphs. Its successful next gate is the audited
Gurobi root-relaxation feature contract. Only after that gate may one Gurobi-
constructed graph be created per original parent MIP; SCIP never becomes the
graph-construction authority.
