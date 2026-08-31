# Neural Diving GNN Pipeline — Technical Reference
## Data Transformation, Graph Construction, and GNN Training on MILPBench CFL Instances

This document is the complete technical specification for the `cfl-gurobi-gnn`
pipeline.  It is intended for developers, PhD supervisors, and reproducibility
reviewers who need full details on every CLI argument, generated artifact, feature
layout, and deployment configuration.

For a project overview and quick-start guide, see the root
[`README.md`](../README.md).

> All code targets **Gurobi 13.0** and **PyTorch Geometric**.
> All scripts are production-ready and have been validated on a DGX cluster
> with 8 x A100 GPUs.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Structure](#2-repository-structure)
3. [Prerequisites](#3-prerequisites)
4. [Generated Artifacts per Instance](#4-generated-artifacts-per-instance)
5. [Execution Sequence and Dependency Table](#5-execution-sequence-and-dependency-table)
6. [Step-by-Step Instructions](#6-step-by-step-instructions)
7. [Adaptive Presolve Strategy](#7-adaptive-presolve-strategy)
8. [Variable Feature Layout](#8-variable-feature-layout)
9. [Variable Hints vs. MIP Start](#9-variable-hints-vs-mip-start)
10. [Solution Pool Collection Strategy](#10-solution-pool-collection-strategy)
11. [HPC and Slurm Deployment](#11-hpc-and-slurm-deployment)
12. [Dataset Stratification and Curriculum Learning](#12-dataset-stratification-and-curriculum-learning)
13. [Repository Policy: Code vs. Data](#13-repository-policy-code-vs-data)
14. [References](#14-references)

---

## 1. Architecture Overview

```
Raw MILPBench LP files
        |
        | Step 1: collect_incumbents
        |         benchmark_gurobi
        v
per-instance directories
  original_features.pickle.gz
  incumbents.parquet
  node_relaxations.parquet
  metadata.json
        |
        | Step 2: audit_collection  (Phase 1 EDA & Data Validation)
        |
        | Step 3: build_dataset
        v
  data_0.pt ... data_N.pt   (PyG HeteroData bipartite graphs)
        |
        | Step 4: audit_dataset / graph diagnostics
        |
        | Step 5: train_serial  (smoke test)
        | Step 6: train_distributed  (full DGX run)
        v
  best_model.pt
        |
        | Step 7: generate_hints
        v
  <instance>_gnn_hint.hnt
        |
        | Step 8: benchmark_gurobi  (baseline + GNN-guided benchmark)
        | Step 9: evaluate
        v
  Thesis evaluation artefacts
```

The bipartite graph encodes the MILP following Gasse et al. (2019):

$$G = (V_{\text{var}} \cup V_{\text{con}},\; E)$$

where each variable node $v_i \in V_{\text{var}}$ carries a 7-dimensional feature
vector, each constraint node $c_j \in V_{\text{con}}$ carries a 5-dimensional feature
vector, and edges are weighted by log-scaled constraint matrix coefficients $A_{ji}$.

---

## 2. Repository Structure

```
.
├── docs/                       # Architecture, decisions, and this reference
├── src/cfl_gnn/
│   ├── cli/                    # Stable command-line entrypoints
│   ├── artifacts/              # Dependency-free persisted-data schemas
│   ├── pipelines/              # Solver + sampling-strategy composition
│   ├── solvers/gurobi/         # Gurobi collection, hints, and benchmarks
│   ├── graph/                  # MILP-to-PyG transformation and datasets
│   ├── models/                 # Gasse and Liang architectures
│   ├── training/               # Serial and distributed training
│   ├── evaluation/             # Academic model evaluation
│   └── analysis/               # Collection and graph diagnostics
├── scripts/slurm/dasci/        # HPC launchers
├── tests/                      # Structural smoke tests
├── notebooks/                  # Research notebooks
├── data/                       # Existing experimental artifacts
└── pyproject.toml              # Package metadata
```

---

## 3. Prerequisites

### Python Environment

```bash
conda create -n neural_diving python=3.10
conda activate neural_diving

pip install gurobipy pandas pyarrow numpy scipy
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install torch-geometric
pip install umap-learn seaborn scikit-learn matplotlib tqdm
pip install -e . --no-deps
```

### Gurobi License

A valid Gurobi 13.0 license is required.  For WLS (Web License Service):

```bash
export WLSACCESSID="your-access-id"
export WLSSECRET="your-secret"
export LICENSEID="your-license-id"
```

All scripts read these variables through `gp.Env(empty=True)`.

### Gurobi 13.0 API Notes

This pipeline uses the following Gurobi 13.0 canonical patterns exclusively:

| Pattern | v4 / v2 (correct) | Deprecated (do not use) |
| :--- | :--- | :--- |
| Read pool solution value | `v.PoolNX` | `v.Xn` (deprecated since 13.0) |
| Set solution number | `model.Params.SolutionNumber = n` | `model.setParam("SolutionNumber", n)` |
| Pool solution count | `model.SolCount` | — |

---

## 4. Generated Artifacts per Instance

Step 1 creates one subdirectory per instance:

| File | Format | Contents |
| :--- | :--- | :--- |
| `original_features.pickle.gz` | Pickle (Gzip) | Variable types, bounds, objective coefficients, sparse constraint matrix (COO). Extracted from the **original model before any solve**. |
| `incumbents.parquet` | Apache Parquet | Timeline of integer-feasible B&B incumbents: node, time, objective, bound, MIP gap, phase, solution vector. **Only Phase 1 (true B&B tree) solutions stored.** |
| `node_relaxations.parquet` | Apache Parquet | Timeline of LP relaxations: node, bound, fractional variable count, relaxation vector. |
| `metadata.json` | JSON | Solve summary including `complexity_class`, `probe_node_count`, `presolve_setting`. |

Step 3 produces one `.pt` file per qualifying incumbent:

| File | Format | Contents |
| :--- | :--- | :--- |
| `processed/data_{idx}.pt` | PyTorch HeteroData | Bipartite graph with `variable.x [N_v, 7]`, `constraint.x [N_c, 5]`, edge indices, log-scaled weights, solution vector `y`, pre-stored `is_discrete` mask, and graph-level labels (`mip_gap`, `exec_time`, `complexity_class`, `presolve_used`). |

---

## 5. Execution Sequence and Dependency Table

```
Step 1  ──────────────────────────────────────────────────────────────────┐
Step 1  →  Step 2  (Data validation)                           │
Step 1  →  Step 3  →  Step 4  →  Step 5  →  Step 6  →  Step 7           │
                                              Step 6  →  Step 9           │
                       Step 8 (needs Step 1 output + Step 7 output) ◄─────┘
```

| Step | Script | Depends on |
| :---: | :--- | :--- |
| 1 | `cfl_gnn.cli.collect_incumbents` | Raw MILPBench `.lp.gz` files |
| 2 | `cfl_gnn.cli.audit_collection` | Step 1 complete |
| 3 | `cfl_gnn.cli.build_dataset` | Step 1 complete |
| 4a | `cfl_gnn.cli.audit_dataset` | Step 3 complete — **cannot run before Step 3** |
| 4b | `cfl_gnn.cli.graph_statistics` | Step 3 complete |
| 4c | `cfl_gnn.cli.graph_clustering` | Step 3 complete |
| 5 | `cfl_gnn.cli.train_serial` | Step 4 validated |
| 6 | `cfl_gnn.cli.train_distributed` | Step 5 smoke test passed |
| 7 | `cfl_gnn.cli.generate_hints` | Step 6 complete (`best_model.pt`) |
| 8a | `cfl_gnn.cli.benchmark_gurobi` (baseline) | Step 1 complete |
| 8b | `cfl_gnn.cli.benchmark_gurobi` (GNN-guided) | Step 7 complete |
| 9 | `cfl_gnn.cli.evaluate` | Steps 3 and 6 complete |

> **Critical:** `cfl_gnn.cli.audit_dataset` loads `.pt` files via `NeuralDivingDataset`
> and **requires Step 3 to have completed**.  It cannot be used as a pre-ETL
> schema validator.

---

## 6. Step-by-Step Instructions

### Step 1 — Data Generation

```bash
python -m cfl_gnn.cli.collect_incumbents \
    --categories           CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --start_idx            0 \
    --end_idx              500 \
    --time_limit           3600 \
    --probe_time           30 \
    --complexity_threshold 500 \
    --input_dir            /path/to/MILPBench/CFL \
    --output_dir           /path/to/intermediate_lps
```

| Parameter | Default | Description |
| :--- | :---: | :--- |
| `--time_limit` | `3600` | Main solve time budget per instance (seconds). |
| `--probe_time` | `30` | Probe solve budget for complexity classification (seconds). |
| `--complexity_threshold` | `500` | B&B node count boundary: easy vs. hard. |
| `--pool_size` | `20` | Maximum number of incumbents to retain per instance. |
| `--pool_gap` | `0.10` | Maximum allowed MIP gap for pool solutions (10%). |

### Step 2 — Phase 1 EDA & Data Validation

```bash
python -m cfl_gnn.cli.audit_collection
```

Verify:
* Generates phase1_audit_report_<category>.csv and corresponding _plots.png.
* Check console output for zero [WARN] or [RED ALERT] messages regarding bounding or dimensionality.
* Confirm pct_ones is stable and the number of incumbents matches expectations.

### Step 3 — PyG ETL

```bash
python -m cfl_gnn.cli.build_dataset \
    --categories    CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --gaps          0.10 0.85 0.90 \
    --base_raw_dir    /raid/.../raw_instances \
    --base_pyg_dir    /raid/.../pyg_dataset \
    --clear_processed       # Include only when rebuilding from scratch
```

### Step 4 — Dataset Validation

```bash
# 4a: Schema and topology audit
python -m cfl_gnn.cli.audit_dataset \
    --categories CFL_easy_instance CFL_medium_instance CFL_hard_instance

# 4b: Statistical summary
python -m cfl_gnn.cli.graph_statistics

# 4c: PCA / UMAP cluster visualisation
python -m cfl_gnn.cli.graph_clustering
```

**Stop and review before Step 5:**
- All categories have at least 3 graphs.
- No `[RED ALERT]` LP bound violations printed by Step 4a.
- `complexity_class` is not `'unknown'` for all instances.
- Computed `pos_weight` preview: `N_neg / N_pos` should be in `[5, 500]`.

### Step 5a — Parent-instance Serial Smoke Test

The parent-instance baseline uses the canonical fold manifest and never accepts
graph-count splits. Audit the run contract first without importing PyTorch:

```bash
python -m cfl_gnn.cli.train_instance_serial \
    --base_pyg_dir /raid/.../bipartite_graphs/instance_baseline_smoke \
    --rotation 0 \
    --label_policy optimal_only \
    --development_only \
    --dry_run
```

For the current partial inventory, remove `--dry_run` and use a unique
`--experiment_name` for a one-epoch GPU smoke. The test parents are held out
and are not loaded by this trainer. A run bearing `development_only=true`
cannot be used as a final experimental result.

### Step 5b — Incumbent-conditioned Serial Smoke Test (legacy)

```bash
python -m cfl_gnn.cli.train_serial \
    --easy_split    10 2 2 \
    --medium_split   5 1 1 \
    --hard_split     5 1 1 \
    --epochs        10 \
    --hidden_dim    32
```

**Verify in console output:**
- `pos_weight` is printed as a finite number.
- Training loss decreases for at least 3 consecutive epochs.
- No CUDA out-of-memory error.
- `neural_diving_best_serial.pt` written to disk.

### Step 6 — Full Parallel Training

```bash
torchrun --nproc_per_node=8 -m cfl_gnn.cli.train_distributed \
    --easy_split    300 50 50 \
    --medium_split  200 30 30 \
    --hard_split    100 15 15 \
    --epochs        200 \
    --hidden_dim    64 \
    --patience      20
```

Output (written by rank 0 only):

| File | Description |
| :--- | :--- |
| `neural_diving_best_parallel.pt` | Best checkpoint by validation loss |
| `neural_diving_final_parallel.pt` | Final epoch checkpoint |
| `training_log_parallel.csv` | Per-epoch metrics (loss, accuracy, F1) |
| `loss_curve_parallel.png` | Learning curve with best-epoch marker |

### Step 7 — Variable Hints Generation

```bash
python -m cfl_gnn.cli.generate_hints \
    --model_path  /raid/.../neural_diving_best_parallel.pt \
    --lp_file     /raid/.../CFL_easy_instance_0.lp.gz \
    --output_dir  /raid/.../hints \
    --hidden_dim  64
```

Produces `<instance_name>_gnn_hint.hnt` in the format:

```
# MIP hints generated by GNN inference
# Format: variable_name  hint_value  hint_priority
x_0_0  1  92
x_0_1  0  65
```

### Step 8 — Gurobi Warm-Start Benchmark

```bash
# 8a. Baseline — control group (no hints)
python -m cfl_gnn.cli.benchmark_gurobi \
    --categories  CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --time_limit  300 \
    --output_dir  /raid/.../benchmark_baseline

# 8b. GNN-guided run
python -m cfl_gnn.cli.benchmark_gurobi \
    --categories  CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --time_limit  300 \
    --hint_dir    /raid/.../hints \
    --output_dir  /raid/.../benchmark_with_hints
```

Thesis comparison metrics: solve time and MIP gap with vs. without hints,
stratified by `complexity_class`.

### Step 9 — Academic Evaluation

```bash
python -m cfl_gnn.cli.evaluate \
    --model_path      /raid/.../neural_diving_best_parallel.pt \
    --base_root       /raid/.../pyg_dataset \
    --experiment_name parallel_v4 \
    --hidden_dim      64 \
    --easy_split      300 50 50 \
    --medium_split    200 30 30 \
    --hard_split      100 15 15
```

Output artefacts under `data/analysis/parallel_v4/`:

| File | Description |
| :--- | :--- |
| `classification_report.csv` | Per-class Precision / Recall / F1 (LaTeX-ready) |
| `confusion_matrix.png` | Heatmap at optimal threshold $\tau^*$ |
| `roc_auc_curve.png` | ROC curve with shaded AUC |
| `pr_curve.png` | Precision-Recall curve (recommended for imbalanced data) |
| `threshold_sweep.png` | P / R / F1 vs. $\tau$ with optimal marker |
| `per_complexity_metrics.csv` | Easy vs. hard instance breakdown (thesis ablation) |
| `evaluation_summary.json` | Machine-readable summary |

The optimal decision threshold is:

$$\tau^* = \arg\max_\tau \, F_1(\tau) = \arg\max_\tau \frac{2 \cdot P(\tau) \cdot R(\tau)}{P(\tau) + R(\tau)}$$

---

## 7. Adaptive Presolve Strategy

For well-structured CFL instances, Gurobi with presolve enabled resolves the problem
so quickly that the B&B callback fires very few times, yielding almost no intermediate
incumbent solutions for GNN training.  Disabling presolve intentionally slows the
solver, generating a richer label set.  For genuinely hard instances, however,
disabling presolve makes the search intractable within the time budget.

The solution is a two-phase classification:

**Phase A — Probe solve** (configurable seconds, `Presolve=-1`):

$$\text{Presolve}_{\text{main}} = \begin{cases} 0 & \text{if probe\_node\_count} \leq \text{threshold} \quad \text{(easy — slow Gurobi down)} \\ -1 & \text{if probe\_node\_count} > \text{threshold} \quad \text{(hard — use reductions)} \end{cases}$$

**Phase B — Main solve** uses the presolve setting from Phase A.

The complexity class is recorded in `metadata.json` and propagated into every `.pt`
graph object.  Both thresholds are tunable:

```bash
--probe_time           30     # seconds
--complexity_threshold 500    # B&B nodes
```

Calibrate on 5–10 representative instances before the full run.

---

## 8. Variable Feature Layout

All scripts that access `batch['variable'].x` use the following 7-column layout,
defined as the single source of truth in `-m cfl_gnn.cli.build_dataset`:

| Column | Feature | Transform |
| :---: | :--- | :--- |
| 0 | Objective coefficient | Log-scaled: $\text{sgn}(x) \cdot \ln(1 + \|x\|)$ |
| 1 | Lower bound | Log-scaled |
| 2 | Upper bound | Log-scaled |
| 3 | `is_continuous` | One-hot (0 or 1) |
| 4 | `is_binary` | One-hot (0 or 1) |
| 5 | `is_integer` | One-hot (0 or 1) |
| 6 | LP relaxation value | Raw (no log-scale) |

> **Important:** Columns 3, 4, and 5 are a historically common source of
> off-by-one errors across this codebase.  All v4 / v2 files use the
> pre-stored `batch['variable'].is_discrete` Boolean mask (set at ETL time
> by `-m cfl_gnn.cli.build_dataset`) instead of recomputing the mask from raw
> columns at training or inference time.

Constraint node feature layout (5 columns):

| Column | Feature | Transform |
| :---: | :--- | :--- |
| 0 | RHS ($b_j$) | Log-scaled |
| 1 | `sense_less_equal` (`<`) | One-hot |
| 2 | `sense_equal` (`=`) | One-hot |
| 3 | `sense_greater_equal` (`>`) | One-hot |
| 4 | Dummy constant (1.0) | None (Gasse et al. convention) |

---

## 9. Variable Hints vs. MIP Start

The pipeline uses **Variable Hints** (`VarHintVal` + `VarHintPri`) rather than
MIP Starts for warm-starting Gurobi:

| Property | MIP Start (`.mst`) | Variable Hints (`.hnt`) |
| :--- | :--- | :--- |
| Feasibility required | Yes (or near-feasible) | No |
| Effect on solver | Sets initial incumbent | Guides entire B&B process |
| When GNN is partially wrong | Solution may be discarded | Gurobi backtracks naturally |
| Priority support | No | Yes (`VarHintPri`) |

The hint priority is derived from the GNN output probability $\hat{p}_i$:

$$\text{HintPri}_i = \left\lfloor \left| \hat{p}_i - 0.5 \right| \times 200 \right\rfloor$$

This maps $\hat{p}_i \in \{0, 1\}$ to priority 100 (maximum confidence) and
$\hat{p}_i = 0.5$ to priority 0 (complete uncertainty).  All discrete variables
always receive a hint regardless of confidence level.

---

## 10. Solution Pool Collection Strategy

The pipeline uses `PoolSearchMode=1` (collect incumbents as a B&B by-product):

| Mode | Effect | When appropriate |
| :---: | :--- | :--- |
| 0 | Keep only best solution | Default — not useful for GNN training |
| 1 | Collect solutions found during B&B | **This pipeline** |
| 2 | Actively enumerate $N$-best globally | Solution enumeration problems |

`PoolSearchMode=2` with `Presolve=0` forces exhaustive search on an unreduced model
and is incompatible with the time budgets used here.

Additional parameters set for pool diversity:
- `Symmetry=0`: prevents pruning of symmetric feasible solutions.
- `DualReductions=0`: prevents dual-based elimination of feasible assignments.
- `PoolGap=0.10`: discards solutions more than 10% worse than the best bound.

Only **Phase 1** incumbents (`MIPSOL_PHASE == 1`, true B&B tree solutions) are
stored as training labels.  Phase 0 (NoRel heuristic) and Phase 2
(post-optimality improvement) solutions are filtered in the callback.

---

## 11. HPC and Slurm Deployment

### Environment Variables for DGX

```bash
export WLSACCESSID="..."
export WLSSECRET="..."
export LICENSEID="..."
export SLURM_CPUS_PER_TASK=8
```

### Step 6 Slurm Script — Full DGX Training

```bash
#!/bin/bash
#SBATCH --job-name=neural_diving_parallel
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --gres=gpu:8
#SBATCH --cpus-per-task=4
#SBATCH --mem=128G
#SBATCH --time=12:00:00
#SBATCH --output=logs/train_parallel_%j.log

module load cuda/11.8
conda activate neural_diving

torchrun --nproc_per_node=8 -m cfl_gnn.cli.train_distributed \
    --easy_split    300 50 50 \
    --medium_split  200 30 30 \
    --hard_split    100 15 15 \
    --epochs        200 \
    --hidden_dim    64 \
    --patience      20
```

### Step 8 Slurm Array Script — Per-Instance Benchmark

```bash
#!/bin/bash
#SBATCH --job-name=gurobi_benchmark
#SBATCH --array=0-499
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/bench_%A_%a.log

conda activate neural_diving

python -m cfl_gnn.cli.benchmark_gurobi \
    --categories   CFL_easy_instance \
    --start_idx    ${SLURM_ARRAY_TASK_ID} \
    --end_idx      $((SLURM_ARRAY_TASK_ID + 1)) \
    --time_limit   300 \
    --hint_dir     /raid/.../hints \
    --output_dir   /raid/.../benchmark_with_hints
```

---

## 12. Dataset Stratification and Curriculum Learning

The `complexity_class` field (`'easy'` or `'hard'`) is stored in every `.pt` file
and in `metadata.json`.  This enables three downstream capabilities:

1. **Stratified splits** — ensure both easy and hard instances appear in every
   train / val / test split, preventing distribution shift.

2. **Curriculum learning** — begin training on easy instances (more incumbents
   per instance) and progressively introduce hard instances.
   `-m cfl_gnn.cli.graph_statistics` provides per-category incumbent counts for
   designing the curriculum schedule.

3. **Ablation studies** — `-m cfl_gnn.cli.evaluate` automatically generates
   `per_complexity_metrics.csv` with separate Precision, Recall, F1, and
   ROC-AUC for each complexity class, directly supporting the thesis
   ablation section.

### `pos_weight` Calibration

Training uses a data-driven positive class weight computed from the training split:

$$w_{\text{pos}} = \frac{N_{\text{neg}}}{N_{\text{pos}}}$$

This value is computed once before training, broadcast across all DDP ranks via
`dist.all_reduce`, and passed to `BCEWithLogitsLoss`.  The console prints the
computed value at the start of every training run.  For CFL instances, expect
$w_{\text{pos}} \in [5, 500]$ depending on the proportion of open facilities.

---

## 13. Repository Policy: Code vs. Data

| Artefact | Location | Synced to GitHub |
| :--- | :--- | :---: |
| All Python source files | `./` | Yes |
| Raw MILPBench `.lp.gz` files | GitHub Release (attached archive) | Via Release |
| Generated raw instance data | `/raid/.../raw_instances/` | No |
| Generated PyG `.pt` graphs | `/raid/.../pyg_dataset/` | No |
| Trained model weights | `/raid/.../best_model.pt` | No |
| Generated `.hnt` hint files | `/raid/.../hints/` | No |
| Evaluation figures and CSVs | `data/analysis/<experiment>/` | No |

The final dataset and trained model should be distributed through:
- **[Zenodo](https://zenodo.org)** — DOI-citable, recommended for thesis
  reproducibility audits.
- **[Hugging Face Datasets](https://huggingface.co/datasets)** — versioned,
  accessible via the `datasets` library.
- **Compressed archive** (`.tar.gz`) — for direct transfer between cluster nodes.

---

## 14. References

- Gasse, M., Chételat, D., Ferroni, N., Charlin, L., and Lodi, A. (2019).
  *Exact Combinatorial Optimization with Graph Convolutional Networks.*
  Advances in Neural Information Processing Systems 32 (NeurIPS 2019).
  [arXiv:1906.01629](https://arxiv.org/abs/1906.01629)

- Nair, V., Bartunov, S., Gimeno, F., von Glehn, I., Lichocki, P., Lobov, I.,
  O'Donoghue, B., Sonnerat, N., Tjandraatmadja, C., Wang, P., et al. (2020).
  *Solving Mixed Integer Programs Using Neural Networks.*
  [arXiv:2012.13349](https://arxiv.org/abs/2012.13349)

- Han, Q., et al. (2023).
  *MILPBench: A Large-Scale Benchmark for Mixed-Integer Linear Programming.*
  [GitHub](https://github.com/MILPBench/MILPBench)

- Gurobi Optimization, LLC. (2024).
  *Gurobi Optimizer Reference Manual, Version 13.0.*
  [gurobi.com/documentation/13.0](https://www.gurobi.com/documentation/13.0/)
