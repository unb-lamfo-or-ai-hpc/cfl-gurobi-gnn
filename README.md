# cfl-gurobi-gnn

**Research project developed within an international cooperation between the
University of Brasília (UnB), the University of Jaén (UJA), and the DaSCI Institute
(Andalusian Research Institute in Data Science and Computational Intelligence).**

This repository provides an end-to-end framework to solve
**Capacitated Facility Location (CFL)** problem instances from the
[MILPBench](https://github.com/MILPBench/MILPBench) benchmark.
The pipeline generates diverse solution trajectories using Gurobi, trains a
**Graph Neural Network (GNN)** to perform *Neural Diving*, and injects the GNN
predictions into Gurobi as **Variable Hints (`.hnt`)** to accelerate
Branch-and-Bound convergence.

> Full technical documentation, CLI references, feature layout tables, and
> Slurm deployment scripts are in [`src/PIPELINE.md`](src/PIPELINE.md).

---

## Pipeline Architecture

The pipeline is structured into four functional pillars:

1. **Generation and Adaptive Solving** — Captures diverse incumbent solutions
   using an adaptive presolve strategy that classifies each instance as *easy*
   or *hard* before the main solve.
2. **ETL (Extract, Transform, Load)** — Converts MILP instances into stratified
   `HeteroData` bipartite graph objects with complexity metadata propagated into
   every graph.
3. **Training** — Distributed (DDP) and serial training of a Gasse-style GNN
   with data-driven loss calibration and DDP-safe early stopping.
4. **Inference and Benchmarking** — Generates `.hnt` files to warm-start Gurobi
   and assesses GNN-guided performance against a no-hint baseline.

### Dependency Flow

```
Raw MILPBench .lp.gz files
        |
        | Step 1 — cfl_gnn_data_generator_v4.py
        v
per-instance/  [original_features.pickle.gz, incumbents.parquet, metadata.json]
        |
        +-----> Step 2 — transformer_v2.py  (independent raw LP audit)
        |
        | Step 3 — build_pyg_dataset_v4.py
        v
pyg_dataset/  [data_0.pt ... data_N.pt]
        |
        | Step 4 — test_pyg_dataset_v4.py
        |          dataset_statistics_v2.py
        |          graph_clustering_v2.py
        |
        | Step 5 — train_neural_diving_serial_v4.py  (smoke test)
        | Step 6 — train_neural_diving_parallel_v4.py  (full DGX run)
        v
best_model.pt
        |
        | Step 7 — generate_mip_hints.py
        v
hints/  [instance_gnn_hint.hnt]
        |
        +-----> Step 8 — gurobi_hpc_runner_v2.py  (baseline + GNN-guided)
        |
        +-----> Step 9 — evaluate_model_v2.py  (thesis evaluation figures)
```

---

## Repository Structure

```
.
├── src/
│   ├── PIPELINE.md                          # Full technical documentation
│   ├── gnn/
│   │   └── models/
│   │       └── gasse.py                     # GNN architecture (GasseGNN)
│   └── graph_transform/
│       └── milp_dataset_v2.py               # NeuralDivingDataset (PyG, cached I/O)
│
├── cfl_gnn_data_generator_v4.py             # Step 1: Gurobi data extraction
├── gurobi_hpc_runner_v2.py                  # Step 1 / Step 8: HPC parametric runner
├── transformer_v2.py                        # Step 2: Raw LP metadata audit
├── build_pyg_dataset_v4.py                  # Step 3: PyG ETL pipeline
├── test_pyg_dataset_v4.py                   # Step 4: Dataset schema audit
├── dataset_statistics_v2.py                 # Step 4: Statistical summary
├── graph_clustering_v2.py                   # Step 4: PCA / UMAP visualisation
├── train_neural_diving_serial_v4.py         # Step 5: Single-GPU smoke test
├── train_neural_diving_parallel_v4.py       # Step 6: DDP multi-GPU training
├── generate_mip_hints.py                    # Step 7: GNN inference to .hnt files
├── ml_scheme_v2.py                          # Shared training and plotting utilities
├── evaluate_model_v2.py                     # Step 9: Academic evaluation
├── README.md                                # This file
└── .gitignore
```

---

## Full Pipeline Execution Sequence

Follow this dependency-ordered sequence for reproducible results.

**STEP 1 — Data Generation**
```bash
python3 cfl_gnn_data_generator_v4.py \
    --input_dir            /path/to/milpbench_lp_files \
    --output_dir           /raid/.../raw_instances \
    --time_limit           300 \
    --probe_time           30 \
    --complexity_threshold 500 \
    --pool_size            20 \
    --pool_gap             0.10 \
    --workers              8
```

**STEP 2 — Raw Data Audit** *(independent, can run alongside Step 1)*
```bash
python3 transformer_v2.py \
    --input_dir   /path/to/milpbench_lp_files \
    --output_file /raid/.../instance_metadata.parquet
```

**STEP 3 — PyG ETL** *(requires Step 1 complete)*
```bash
python3 build_pyg_dataset_v4.py \
    --categories    CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --base_raw_dir  /raid/.../raw_instances \
    --base_pyg_dir  /raid/.../pyg_dataset
```

**STEP 4 — Dataset Validation** *(requires Step 3 complete)*
```bash
python3 test_pyg_dataset_v4.py \
    --categories CFL_easy_instance CFL_medium_instance CFL_hard_instance

python3 dataset_statistics_v2.py

python3 graph_clustering_v2.py
```

**STEP 5 — Serial Training: Smoke Test** *(requires Step 4 validated)*
```bash
python3 train_neural_diving_serial_v4.py \
    --easy_split 10 2 2 --medium_split 5 1 1 --hard_split 5 1 1 \
    --epochs 10 --hidden_dim 32
```

**STEP 6 — Parallel Training: Full DGX Run** *(requires Step 5 passed)*
```bash
torchrun --nproc_per_node=8 train_neural_diving_parallel_v4.py \
    --easy_split    300 50 50 \
    --medium_split  200 30 30 \
    --hard_split    100 15 15 \
    --epochs 200 --hidden_dim 64 --patience 20
```

**STEP 7 — Generate Variable Hints** *(requires Step 6 complete)*
```bash
python3 generate_mip_hints.py \
    --model_path /raid/.../best_model.pt \
    --input_dir  /raid/.../raw_instances \
    --output_dir /raid/.../hints \
    --hidden_dim 64
```

**STEP 8 — Gurobi Warm-Start Benchmark** *(requires Steps 1 and 7 complete)*
```bash
# Baseline run — control group
python3 gurobi_hpc_runner_v2.py \
    --input_dir  /path/to/milpbench_lp_files \
    --output_dir /raid/.../benchmark_baseline \
    --time_limit 300 --workers 8

# GNN-guided run — with variable hints
python3 gurobi_hpc_runner_v2.py \
    --input_dir  /path/to/milpbench_lp_files \
    --output_dir /raid/.../benchmark_with_hints \
    --hint_dir   /raid/.../hints \
    --time_limit 300 --workers 8
```

**STEP 9 — Academic Evaluation** *(requires Steps 3 and 6 complete)*
```bash
python3 evaluate_model_v2.py \
    --model_path      /raid/.../best_model.pt \
    --base_root       /raid/.../pyg_dataset \
    --experiment_name parallel_v4 \
    --easy_split      300 50 50 \
    --medium_split    200 30 30 \
    --hard_split      100 15 15
```

---

## Prerequisites

### Python Environment

```bash
conda create -n neural_diving python=3.10
conda activate neural_diving

pip install gurobipy pandas pyarrow numpy scipy
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install torch-geometric
pip install umap-learn seaborn scikit-learn matplotlib tqdm
```

### Gurobi License

A valid **Gurobi 13.0** license is required.
For WLS (Web License Service), export the following variables before running any
script:

```bash
export WLSACCESSID="your-access-id"
export WLSSECRET="your-secret"
export LICENSEID="your-license-id"
```

All scripts read these variables through `gp.Env(empty=True)`.

> This pipeline uses `v.PoolNX` and `model.Params.SolutionNumber` as the canonical
> Gurobi 13.0 solution pool API.  The deprecated `v.Xn` attribute is not used.

---

## Repository Policy: Code vs. Data

| Artefact | Location | Synced to GitHub |
| :--- | :--- | :---: |
| All Python source files | `./` | Yes |
| Raw MILPBench `.lp.gz` files | GitHub Release (attached archive) | Via Release |
| Generated raw instance data | `/raid/.../raw_instances/` | No |
| Generated PyG `.pt` graphs | `/raid/.../pyg_dataset/` | No |
| Trained model weights | `/raid/.../best_model.pt` | No |
| Generated `.hnt` hint files | `/raid/.../hints/` | No |
| Evaluation figures and CSVs | `data/analysis/<experiment>/` | No |

The final dataset and trained model should be distributed through
[Zenodo](https://zenodo.org) (DOI-citable, recommended for thesis reproducibility)
or [Hugging Face Datasets](https://huggingface.co/datasets).

---

## References

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
