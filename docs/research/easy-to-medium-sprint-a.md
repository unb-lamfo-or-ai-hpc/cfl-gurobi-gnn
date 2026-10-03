# Sprint A: easy-only training for medium transfer

## Scientific question and scope

Can a GNN fitted exclusively to easy CFL parents provide useful partial MIP
starts for Gurobi on medium parents? This sprint produces a fresh model and a
verifiable training contract, not a claim of solver acceleration. Sprint B will
test the intervention; Sprint C will consolidate the evidence. Manuscript
rewriting follows all three sprints.

Reuse the thirty easy originals in the audited PR50 graph inventory. Do not
regenerate graphs or require the new PR54 medium labels. Preserve rotation0:
18 training, six validation and six held-out easy test parents. The source
39-parent model and its weights are not reused. Medium data must not fit
normalization, class weights, model parameters, the checkpoint or the threshold.

The adapter verifies the historical plan contract, canonical identities/folds,
label admission, graph/root/label/receipt hashes, original-only provenance and
the existing mathematical/root-feature audit. It produces a new plan containing
only easy rows. Hashing a held-out file is not loading its graph into training.
No medium graph file is opened by the adapter. Existing source artifacts remain
immutable. Use only trusted, audited PyTorch artifacts, not arbitrary downloads.

Training reuses Gasse v2 alternating prenorm, two layers, hidden dimension32,
Adam learning rate0.001, seed42,100epochs and patience100. Prenorm and positive
weights are fitted on easy training data. Minimum validation weighted BCE selects
the checkpoint; easy validation F1 selects the probability threshold. These
scores are not assumed calibrated. Training and validation loss share one SVG.

## DGX-DaSCI preflight

Run from the repository root in the qualified environment. The three source
locations must refer to the SAME PR50 campaign, graph dataset and training plan.
Use directories for roots, but a JSON file for SOURCE_TRAINING_PLAN. Do not select
the most recent folder blindly or reuse a newly generated timestamp for a source.

```bash
git fetch origin
git switch feature/easy-only-transfer-training
git pull --ff-only origin feature/easy-only-transfer-training
conda activate tfm_env
export EXEC_DIR="$(pwd -P)"
export DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
export PYTHONPATH="${EXEC_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

PYTHONPATH=src python3 -m pytest tests/smoke -q
PYTHONPATH=src python3 -m pytest tests/smoke/test_easy_transfer_training.py \
  tests/smoke/test_gasse_numerical.py -q -rs

# Read-only inventory: recover the exact PR50 paths before dry-run.
find "${DATA_ROOT}/models" -type f -name gasse_training_plan.json -print
find "${DATA_ROOT}/bipartite_graphs" -type f -name confirmation_graph_report.json -print
```

The known label root is
`data/analysis/confirmation_execution/pr50_20260912T121753Z` under DATA_ROOT.
The previous evidence bundle contains the approved39 training plan, but its
current HPC location and the corresponding graph root must be recovered above.
Do not launch a job with placeholder or empty paths.

Once those three variables are set to verified paths:

```bash
easy_preflight() {
  test -s "${SOURCE_TRAINING_PLAN:-}" || { echo SOURCE_PLAN_MISSING; return 1; }
  test -d "${SOURCE_GRAPH_ROOT:-}" || { echo GRAPH_ROOT_MISSING; return 1; }
  test -d "${SOURCE_LABEL_ROOT:-}" || { echo LABEL_ROOT_MISSING; return 1; }
  export EASY_NAME="easy_transfer_seed42_$(date -u +%Y%m%dT%H%M%SZ)"
  export EASY_PLAN_DIR="${DATA_ROOT}/analysis/easy_transfer/${EASY_NAME}_plan"
  export EASY_TRAINING_DIR="${DATA_ROOT}/models/easy_transfer/${EASY_NAME}"
  python3 -m cfl_gnn.cli.run_easy_transfer_training dry-run \
    --source_training_plan "$SOURCE_TRAINING_PLAN" \
    --graph_root "$SOURCE_GRAPH_ROOT" --label_root "$SOURCE_LABEL_ROOT" \
    --output_dir "$EASY_PLAN_DIR" || return 1
  export EASY_EXPECTED_CONTRACT
  EASY_EXPECTED_CONTRACT=$(jq -er '.contract_sha256' \
    "$EASY_PLAN_DIR/gasse_training_plan.json") || return 1
  jq -e '.partition_counts == {train:18,validation:6,test:6}
    and .medium_records_in_training_plan == 0
    and .protocol.optimization.epochs == 100
    and .protocol.optimization.seed == 42
    and .scientific_reporting_eligible == false' \
    "$EASY_PLAN_DIR/gasse_training_plan.json" || return 1
  echo EASY_TRANSFER_PREFLIGHT_OK
}
if easy_preflight; then
  echo 'Preflight complete; preserve the printed contract and directories.'
else
  echo 'Do not submit training; this interactive shell remains open.'
fi
```

After the licensed-environment preflight is reviewed, submit the existing
`scripts/slurm/dasci/submit_easy_transfer_training.sbs` with the exported
variables. It reserves one GPU,8CPUs,64GiB and24h. It neither submits child jobs
nor runs optimization. The worker recomputes the plan and checks the expected
contract before training; existing output directories are rejected.

## Completion criteria

- All qualified DGX smoke tests, including the original toy/Gasse numerical tests.
- 100 finite epochs; combined training/validation plot and checkpoint hashes.
- Zero test or medium graphs loaded during training.
- Easy-only validation selection, no pretrained checkpoint, immutable sources.
- `easy_transfer_training_report.json` passes; no medium benchmark or scientific
  effectiveness certification is inferred from it.

Preserve the raw training history, Gasse report, wrapper report, plan, curve and
checkpoint. Publish only sanitized evidence, not credentials or machine paths.
