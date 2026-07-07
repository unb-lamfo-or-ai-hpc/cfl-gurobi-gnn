# Neural Diving GNN Pipeline for MIP Warm-Start
## Data Transformation, Graph Construction, and GNN Training on MILPBench CFL Instances

This repository implements a complete research pipeline for training a Graph Neural
Network (GNN) to predict near-optimal variable assignments for Mixed-Integer Linear
Programs (MILPs), using instances from the
[MILPBench](https://github.com/MILPBench/MILPBench) benchmark (Capacitated Facility
Location category).  The GNN predictions are injected into Gurobi as Variable Hints
(`VarHintVal` / `VarHintPri`), guiding Branch-and-Bound search toward high-quality
solutions faster than an unguided solve.

> This module covers the **full pipeline**: raw LP extraction, bipartite graph
> construction, GNN training (serial and distributed), hint generation, and
> academic evaluation.  All code targets Gurobi 13.0 and PyTorch Geometric.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Structure](#2-repository-structure)
3. [Prerequisites](#3-prerequisites)
4. [Generated Artifacts per Instance](#4-generated-artifacts-per-instance)
5. [Execution Sequence](#5-execution-sequence)
6. [Step-by-Step Instructions](#6-step-by-step-instructions)
7. [Adaptive Presolve Strategy](#7-adaptive-presolve-strategy)
8. [Variable Feature Layout](#8-variable-feature-layout)
9. [Variable Hints vs. MIP Start](#9-variable-hints-vs-mip-start)
10. [Solution Pool Collection Strategy](#10-solution-pool-collection-strategy)
11. [HPC / Slurm Deployment](#11-hpc--slurm-deployment)
12. [Dataset Stratification and Curriculum Learning](#12-dataset-stratification-and-curriculum-learning)
13. [Repository Policy: Code vs. Data](#13-repository-policy-code-vs-data)

---

## 1. Architecture Overview

```
Raw MILPBench LP files
        |
        | Step 1: cfl_gnn_data_generator_v4.py
        |         gurobi_hpc_runner_v2.py
        v
per-instance directories
  original_features.pickle.gz
  incumbents.parquet
  node_relaxations.parquet
  metadata.json
        |
        | Step 2: transformer_v2.py  (independent — raw LP audit)
        |
        | Step 3: build_pyg_dataset_v4.py
        v
  data_0.pt ... data_N.pt   (PyG HeteroData bipartite graphs)
        |
        | Step 4: test_pyg_dataset_v4.py
        |         dataset_statistics_v2.py
        |         graph_clustering_v2.py
        |
        | Step 5: train_neural_diving_serial_v4.py  (smoke test)
        | Step 6: train_neural_diving_parallel_v4.py  (full DGX run)
        v
  best_model.pt
        |
        | Step 7: generate_mip_hints.py
        v
  <instance>_gnn_hint.hnt
        |
        | Step 8: gurobi_hpc_runner_v2.py  (baseline + GNN-guided benchmark)
        | Step 9: evaluate_model_v2.py
        v
  Thesis evaluation artefacts
```

The bipartite graph encodes the MILP as a variable-constraint heterogeneous graph,
following the formulation in Gasse et al. (2019) *"Exact Combinatorial Optimization
with Graph Convolutional Networks"*:

$$G = (V_{\text{var}} \cup V_{\text{con}},\; E)$$

where each variable node $v_i \in V_{\text{var}}$ carries a 7-dimensional feature
vector, each constraint node $c_j \in V_{\text{con}}$ carries a 5-dimensional feature
vector, and edges are weighted by the (log-scaled) constraint matrix coefficients
$A_{ji}$.

---

## 2. Repository Structure

```
.
├── src/
│   ├── gnn/
│   │   └── models/
│   │       └── gasse.py                 # GNN architecture (GasseGNN)
│   └── graph_transform/
│       └── milp_dataset.py              # NeuralDivingDataset (PyG, cached I/O)
│
├── cfl_gnn_data_generator_v4.py         # Step 1: Gurobi data extraction
├── gurobi_hpc_runner_v2.py              # Step 1 / Step 8: HPC parametric runner
├── transformer_v2.py                    # Step 2: Raw LP metadata audit
├── build_pyg_dataset_v4.py              # Step 3: PyG ETL pipeline
├── test_pyg_dataset_v4.py               # Step 4: Dataset schema audit
├── dataset_statistics_v2.py            # Step 4: Statistical summary
├── graph_clustering_v2.py              # Step 4: PCA / UMAP visualisation
├── train_neural_diving_serial_v4.py    # Step 5: Single-GPU training
├── train_neural_diving_parallel_v4.py  # Step 6: DDP multi-GPU training
├── generate_mip_hints.py               # Step 7: GNN inference → .hnt files
├── evaluate_model_v2.py                # Step 9: Academic evaluation
├── ml_scheme_v2.py                     # Shared training utilities
└── README.md                           # This file
```

---

## 3. Prerequisites

### Python Environment

```bash
conda create -n neural_diving python=3.10
conda activate neural_diving

pip install gurobipy pandas pyarrow numpy
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install torch-geometric
pip install umap-learn seaborn scikit-learn matplotlib tqdm
```

### Gurobi License

A valid Gurobi 13.0 license is required.  For WLS (Web License Service), set the
following environment variables before running any script:

```bash
export WLSACCESSID="your-access-id"
export WLSSECRET="your-secret"
export LICENSEID="your-license-id"
```

All scripts read these variables automatically through `gp.Env(empty=True)`.

### Gurobi Version Note

This pipeline uses `v.PoolNX` (not the deprecated `v.Xn`) and
`model.Params.SolutionNumber` (not `setParam("SolutionNumber", i)`) as the
canonical solution pool access pattern introduced in Gurobi 13.0.  Running on
earlier versions requires migrating back to `v.Xn`.

---

## 4. Generated Artifacts per Instance

Step 1 creates one subdirectory per instance containing the following files:

| File | Format | Contents |
| :--- | :--- | :--- |
| `original_features.pickle.gz` | Pickle (Gzip) | Variable types, bounds, objective coefficients, sparse constraint matrix (COO format). Always extracted from the **original** model before any solve. |
| `incumbents.parquet` | Apache Parquet | Timeline of integer-feasible solutions found during B&B: node, time, objective, bound, MIP gap, phase, solution vector. Only Phase 1 (true B&B tree) solutions are stored. |
| `node_relaxations.parquet` | Apache Parquet | Timeline of LP relaxations at B&B nodes: node, bound, fractional variable count, relaxation vector. |
| `metadata.json` | JSON | High-level solve summary: status, runtime, MIP gap, node count, solution counts, **and adaptive presolve metadata** (`complexity_class`, `probe_node_count`, `presolve_setting`). |

Step 3 adds one `.pt` file per qualifying incumbent:

| File | Format | Contents |
| :--- | :--- | :--- |
| `processed/data_{idx}.pt` | PyTorch HeteroData | Complete bipartite graph: variable features `[N_v, 7]`, constraint features `[N_c, 5]`, edge indices and log-scaled weights, solution vector `y`, `is_discrete` mask, graph-level labels (`mip_gap`, `exec_time`, `complexity_class`). |

---

## 5. Execution Sequence

The pipeline has strict dependencies between steps.  **Do not skip the validation
steps** (4 and 5) before committing compute resources to the full DGX run.

```
Step 1  →  Step 2 (independent, can run anytime after Step 1)
Step 1  →  Step 3  →  Step 4  →  Step 5  →  Step 6  →  Step 7
                                                       →  Step 8 (needs Step 1 + Step 7)
                                  Step 6  →  Step 9
```

| Step | Script | Depends on |
| :---: | :--- | :--- |
| 1 | `cfl_gnn_data_generator_v4.py` | Raw MILPBench `.lp.gz` files |
| 2 | `transformer_v2.py` | Raw `.lp.gz` files (independent of Step 3) |
| 3 | `build_pyg_dataset_v4.py` | Step 1 complete |
| 4a | `test_pyg_dataset_v4.py` | Step 3 complete |
| 4b | `dataset_statistics_v2.py` | Step 3 complete |
| 4c | `graph_clustering_v2.py` | Step 3 complete |
| 5 | `train_neural_diving_serial_v4.py` | Step 4 validated |
| 6 | `train_neural_diving_parallel_v4.py` | Step 5 smoke test passed |
| 7 | `generate_mip_hints.py` | Step 6 complete (`best_model.pt`) |
| 8a | `gurobi_hpc_runner_v2.py` (baseline) | Step 1 complete |
| 8b | `gurobi_hpc_runner_v2.py` (GNN-guided) | Step 7 complete |
| 9 | `evaluate_model_v2.py` | Steps 3 and 6 complete |

> **Critical:** `test_pyg_dataset_v4.py` reads `.pt` files via `NeuralDivingDataset`
> and therefore **requires Step 3 to have completed successfully** before it can run.
> It cannot be used as a pre-ETL schema validator.

---

## 6. Step-by-Step Instructions

### Step 1 — Data Generation

```bash
python cfl_gnn_data_generator_v4.py \
    --categories      CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --start_idx       0 \
    --end_idx         500 \
    --time_limit      300 \
    --probe_time      30 \
    --complexity_threshold 500 \
    --input_dir       /path/to/MILPBench/CFL \
    --output_dir      /raid/.../raw_instances
```

Key parameters:

| Parameter | Default | Description |
| :--- | :---: | :--- |
| `--time_limit` | `60` | Main solve time budget per instance (seconds). |
| `--probe_time` | `30` | Probe solve budget for complexity classification (seconds). |
| `--complexity_threshold` | `500` | B&B node count boundary between easy and hard instances. |

### Step 2 — Raw LP Metadata Audit

```bash
python transformer_v2.py \
    --input_dir   /path/to/MILPBench/CFL/CFL_easy_instance/LP \
    --output_file /raid/.../metadata/cfl_easy_metadata.parquet
```

Verify: all instances are flagged as `IsMIP=True`, variable and constraint counts
are consistent across categories.

### Step 3 — PyG ETL

```bash
python build_pyg_dataset_v4.py \
    --categories      CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --base_raw_dir    /raid/.../raw_instances \
    --base_pyg_dir    /raid/.../pyg_dataset \
    --clear_processed          # Add only when rebuilding from scratch
```

### Step 4 — Dataset Validation (all three scripts)

```bash
# 4a: Schema audit — run on all categories
python test_pyg_dataset_v4.py \
    --categories CFL_easy_instance CFL_medium_instance CFL_hard_instance

# 4b: Statistical summary
python dataset_statistics_v2.py

# 4c: PCA / UMAP cluster visualisation
python graph_clustering_v2.py
```

**Stop and review before Step 5:**
- All categories have at least 3 graphs.
- No `[RED ALERT]` LP bound violations.
- `complexity_class` is not `'unknown'` for all instances (check `metadata.json`).
- Computed `pos_weight` preview: `N_neg / N_pos` should be in `[5, 500]`.

### Step 5 — Smoke Test (Serial, Small Subset)

```bash
python train_neural_diving_serial_v4.py \
    --easy_split   10 2 2 \
    --medium_split  5 1 1 \
    --hard_split    5 1 1 \
    --epochs       10 \
    --hidden_dim   32
```

**Verify in console output:**
- `pos_weight` is printed and is a finite number in a reasonable range.
- Training loss decreases for at least 3 consecutive epochs.
- No CUDA out-of-memory error.
- `neural_diving_best_serial.pt` is written to disk.

### Step 6 — Full Parallel Training (DGX)

```bash
torchrun --nproc_per_node=8 train_neural_diving_parallel_v4.py \
    --easy_split    300 50 50 \
    --medium_split  200 30 30 \
    --hard_split    100 15 15 \
    --epochs        200 \
    --hidden_dim    64 \
    --patience      20
```

Output files (written by rank 0 only):
- `neural_diving_best_parallel.pt` — best checkpoint by validation loss.
- `neural_diving_final_parallel.pt` — final epoch checkpoint.
- `training_log_parallel.csv` — per-epoch metrics.
- `loss_curve_parallel.png` — learning curve figure.

### Step 7 — Variable Hints Generation

```bash
python generate_mip_hints.py \
    --lp_file     /path/to/instance.lp.gz \
    --model_path  /raid/.../neural_diving_best_parallel.pt \
    --output_dir  /raid/.../hints \
    --hidden_dim  64
```

Produces `<instance_name>_gnn_hint.hnt` in the format:

```
# MIP hints generated by GNN inference
# Format: variable_name  hint_value  hint_priority
x_0_0  1  92
x_0_1  0  65
...
```

### Step 8 — Gurobi Warm-Start Benchmark

```bash
# 8a. Baseline (control group)
python gurobi_hpc_runner_v2.py \
    --categories  CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --time_limit  300 \
    --output_dir  /raid/.../benchmark_baseline

# 8b. GNN-guided run
python gurobi_hpc_runner_v2.py \
    --categories  CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --time_limit  300 \
    --hint_dir    /raid/.../hints \
    --output_dir  /raid/.../benchmark_with_hints
```

Compare `mip_gap` and `runtime` between baseline and GNN-guided runs for the
thesis performance evaluation.

### Step 9 — Academic Evaluation

```bash
python evaluate_model_v2.py \
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
| `confusion_matrix.png` | Heatmap at the optimal decision threshold $\tau^*$ |
| `roc_auc_curve.png` | ROC curve with shaded AUC |
| `pr_curve.png` | Precision-Recall curve (more informative for imbalanced data) |
| `threshold_sweep.png` | P / R / F1 vs. $\tau$ sweep with optimal marker |
| `per_complexity_metrics.csv` | Easy vs. hard instance breakdown (thesis ablation) |
| `evaluation_summary.json` | Machine-readable summary for automated pipelines |

The optimal decision threshold is:

$$\tau^* = \arg\max_\tau \, F_1(\tau) = \arg\max_\tau \frac{2 \cdot P(\tau) \cdot R(\tau)}{P(\tau) + R(\tau)}$$

---

## 7. Adaptive Presolve Strategy

A key design decision in `v4` is the **adaptive presolve** mechanism implemented in
`cfl_gnn_data_generator_v4.py` and `gurobi_hpc_runner_v2.py`.

For well-structured CFL instances, Gurobi with presolve enabled resolves the problem
so quickly that the B&B callback fires very few times, yielding almost no intermediate
incumbent solutions for GNN training.  Disabling presolve intentionally slows the
solver, generating a richer label set.  However, for genuinely hard instances,
disabling presolve makes the search intractable within the time budget.

The solution is a two-phase approach:

**Phase A — Probe solve** (30 seconds, `Presolve=-1`):

```
probe_node_count <= threshold (500)  -->  "easy"  -->  Presolve=0  (slow Gurobi)
probe_node_count >  threshold (500)  -->  "hard"  -->  Presolve=-1 (use reductions)
```

**Phase B — Main solve** uses the presolve setting from Phase A.

The complexity class is recorded in `metadata.json` and propagated into every PyG
graph object as `complexity_class` for downstream stratification.

Both thresholds are tunable via CLI:

```bash
--probe_time           30     # seconds
--complexity_threshold 500    # B&B nodes
```

Calibrate these on 5–10 representative instances before the full run.

---

## 8. Variable Feature Layout

All scripts that access `batch['variable'].x` by column index use the following
layout, which is the single source of truth defined in `build_pyg_dataset_v4.py`:

| Column | Feature | Transform |
| :---: | :--- | :--- |
| 0 | Objective coefficient | Log-scaled: $\text{sgn}(x) \cdot \ln(1 + \|x\|)$ |
| 1 | Lower bound | Log-scaled |
| 2 | Upper bound | Log-scaled |
| 3 | `is_continuous` | One-hot (0 or 1) |
| 4 | `is_binary` | One-hot (0 or 1) |
| 5 | `is_integer` | One-hot (0 or 1) |
| 6 | LP relaxation value | Raw (no log-scale) |

> **Important:** Column indices 3, 4, and 5 have historically been a source of
> off-by-one errors.  All v4/v2 files use `batch['variable'].is_discrete` (a
> pre-stored Boolean mask from ETL) instead of recomputing the mask from raw columns
> at training time.  This eliminates the risk of a silent column-index mismatch.

The constraint node feature layout (5 columns) is:

| Column | Feature | Transform |
| :---: | :--- | :--- |
| 0 | RHS ($b_j$) | Log-scaled |
| 1 | `sense_less_equal` (`<`) | One-hot |
| 2 | `sense_equal` (`=`) | One-hot |
| 3 | `sense_greater_equal` (`>`) | One-hot |
| 4 | Dummy constant (1.0) | None (Gasse et al. convention) |

---

## 9. Variable Hints vs. MIP Start

The pipeline uses **Variable Hints** (`VarHintVal` + `VarHintPri`) rather than MIP
Starts for warm-starting Gurobi.  The key difference:

| Property | MIP Start (`.mst`) | Variable Hints (`.hnt`) |
| :--- | :--- | :--- |
| Feasibility required | Yes (or near-feasible) | No |
| Effect | Sets initial incumbent | Guides entire B&B process |
| When GNN is wrong | Solution may be discarded | Gurobi backtracks naturally |
| Priority support | No | Yes (`VarHintPri`) |
| Multiple hints | Yes (`NumStart`) | No (one per variable) |

The hint priority is derived from the GNN output probability $\hat{p}_i$:

$$\text{HintPri}_i = \left\lfloor \left| \hat{p}_i - 0.5 \right| \times 200 \right\rfloor$$

This maps maximum confidence ($\hat{p}_i = 0$ or $\hat{p}_i = 1$) to priority 100
and complete uncertainty ($\hat{p}_i = 0.5$) to priority 0, giving Gurobi a
continuous confidence signal rather than a hard binary assignment.

All discrete variables always receive a hint; no confidence cutoff discards
variables.  Variables below the optional `--min_priority` threshold may be omitted
if desired.

---

## 10. Solution Pool Collection Strategy

The pipeline uses `PoolSearchMode=1` (collect incumbents as a B&B by-product) rather
than `PoolSearchMode=2` (enumerate the globally $N$-best solutions).

Rationale:

| Mode | Effect | When appropriate |
| :---: | :--- | :--- |
| 0 | Keep only best solution | Default — not useful for training |
| 1 | Collect solutions found during B&B | **This pipeline** — labels reflect B&B trajectory |
| 2 | Actively enumerate $N$-best globally | Solution enumeration problems |

`PoolSearchMode=2` with `Presolve=0` would force an exhaustive search on an
unreduced model, which is incompatible with the time budgets used here.

Additionally, the following parameters are set to ensure pool diversity:
- `Symmetry=0`: prevents pruning of symmetric feasible solutions.
- `DualReductions=0`: prevents dual-based elimination of feasible assignments.
- `PoolGap=0.10`: discards solutions more than 10% worse than the best bound
  before they reach Python or PyTorch.

Only **Phase 1** incumbents (true B&B tree solutions) are stored as training labels.
Phase 0 (NoRel heuristic) and Phase 2 (post-optimality improvement) solutions are
filtered by checking `MIPSOL_PHASE == 1` in the callback.

---

## 11. HPC / Slurm Deployment

### Environment Variables

```bash
export WLSACCESSID="..."
export WLSSECRET="..."
export LICENSEID="..."
export SLURM_CPUS_PER_TASK=8   # Read automatically by gurobi_hpc_runner_v2.py
```

### Step 6 Slurm Script Template

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

torchrun --nproc_per_node=8 train_neural_diving_parallel_v4.py \
    --easy_split    300 50 50 \
    --medium_split  200 30 30 \
    --hard_split    100 15 15 \
    --epochs        200 \
    --hidden_dim    64 \
    --patience      20
```

### Step 8 Slurm Script Template

```bash
#!/bin/bash
#SBATCH --job-name=gurobi_benchmark
#SBATCH --array=0-499
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/bench_%A_%a.log

conda activate neural_diving

python gurobi_hpc_runner_v2.py \
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
and in `metadata.json`.  This enables:

1. **Stratified splits** — ensure both easy and hard instances appear in every
   train/val/test split.

2. **Curriculum learning** — begin training on easy instances (more incumbents per
   instance) and gradually introduce hard instances.  The `dataset_statistics_v2.py`
   report provides the per-category incumbent count needed to design the curriculum.

3. **Ablation studies** — `evaluate_model_v2.py` automatically generates
   `per_complexity_metrics.csv` with separate Precision, Recall, F1, and ROC-AUC
   for each complexity class, directly supporting the thesis ablation section.

---

## 13. Repository Policy: Code vs. Data

| What | Where | Synced to GitHub |
| :--- | :--- | :---: |
| All Python source files | `./` | Yes |
| Raw MILPBench `.lp.gz` files | GitHub Release (attached archive) | Via Release |
| Generated raw instance data | `/raid/.../raw_instances/` | No |
| Generated PyG `.pt` graphs | `/raid/.../pyg_dataset/` | No |
| Trained model weights | `/raid/.../real_train_output/` | No |
| Generated `.hnt` hint files | `/raid/.../hints/` | No |
| Evaluation figures and CSVs | `data/analysis/<experiment>/` | No |

All large data directories are listed in `.gitignore`.

The final dataset (bipartite graphs + trained model) should be distributed through
a platform designed for ML research data:
- **Zenodo** (DOI-citable, recommended for thesis reproducibility)
- **Hugging Face Datasets** (versioned, accessible via `datasets` library)
- **Compressed archive** (`.tar.gz`) for direct transfer between cluster nodes

---

## References

- Gasse, M., Chételat, D., Ferroni, N., Charlin, L., & Lodi, A. (2019).
  *Exact Combinatorial Optimization with Graph Convolutional Networks.*
  NeurIPS 2019. [arXiv:1906.01629](https://arxiv.org/abs/1906.01629)

- Gurobi Optimization, LLC. (2024).
  *Gurobi Optimizer Reference Manual, Version 13.0.*
  [gurobi.com/documentation/13.0](https://www.gurobi.com/documentation/13.0/)

- Han, Q., et al. (2023).
  *MILPBench: A Large-Scale Benchmark for Mixed-Integer Linear Programming.*
  [GitHub](https://github.com/MILPBench/MILPBench)
