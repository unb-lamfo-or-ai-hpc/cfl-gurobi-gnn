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
> Slurm deployment scripts are in [`docs/pipeline.md`](docs/pipeline.md).

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
        | Step 1 — collect_incumbents
        v
per-instance/  [original_features.pickle.gz, incumbents.parquet, metadata.json]
        |
        +-----> Step 2 — audit_collection  (Phase 1 EDA & Data Validation)
        |
        | Step 3 — build_dataset
        v
pyg_dataset/  [data_0.pt ... data_N.pt]
        |
        | Step 4 — audit_dataset / graph diagnostics
        |
        | Step 5 — train_serial  (smoke test)
        | Step 6 — train_distributed  (full DGX run)
        v
best_model.pt
        |
        | Step 7 — generate_hints
        v
hints/  [instance_gnn_hint.hnt]
        |
        +-----> Step 8 — benchmark_gurobi  (baseline + GNN-guided)
        |
        +-----> Step 9 — evaluate  (thesis evaluation figures)
```

---

## Repository Structure

```
.
├── docs/                       # Architecture, decisions, and pipeline reference
├── src/cfl_gnn/
│   ├── cli/                    # Stable command-line entrypoints
│   ├── artifacts/              # Dependency-free persisted-data schemas
│   ├── pipelines/              # Solver + sampling-strategy composition
│   ├── solvers/gurobi/         # Gurobi collection, hints, and benchmarks
│   ├── graph/                  # MILP-to-PyG transformation and dataset access
│   ├── models/                 # Gasse and Liang architectures
│   ├── training/               # Serial and distributed training
│   ├── evaluation/             # Academic model evaluation
│   └── analysis/               # Collection and graph diagnostics
├── scripts/slurm/dasci/        # Reproducible HPC launchers
├── tests/                      # Dependency-free structural smoke tests
├── notebooks/                  # Research notebooks
├── data/                       # Existing experiment artifacts (unchanged)
└── pyproject.toml              # Python package metadata
```

---

## Full Pipeline Execution Sequence

Follow this dependency-ordered sequence for reproducible results.

### Instance-level baseline folds

The planned baseline contains 30 easy, 30 medium, and 30 hard parent
instances. Its canonical five-fold assignment is versioned at
`configs/splits/cfl_90_seed42_folds.csv`. Generate it and, when collected
artifacts are available, audit the current partial inventory without changing
any existing fold assignment:

```bash
python3 -m cfl_gnn.cli.plan_instance_folds \
    --inventory_root /raid/.../intermediate_lps \
    --available_output /raid/.../available_rotation_0.csv \
    --rotation 0
```

Partial inventories are suitable for pipeline development only. Final academic
evaluation uses all five rotations and requires the complete planned population
or a separately reviewed missing-data protocol. The derived CSV records this as
`population_status=development_partial`; use `--strict_inventory` as the final
completeness gate. See
[`ADR 0002`](docs/decisions/0002-instance-level-cross-validation.md).

Build one graph for every currently eligible parent instance in a separate
output root. The builder selects the minimum-objective valid solution across
the final solution pool and true branch-and-bound incumbents:

```bash
python3 -m cfl_gnn.cli.build_instance_dataset \
    --manifest configs/splits/cfl_90_seed42_folds.csv \
    --base_raw_dir /raid/.../intermediate_lps \
    --base_pyg_dir /raid/.../bipartite_graphs/instance_baseline
```

Use `--strict_inventory` only for the final complete-population gate. Until
then, generated graphs and `instance_dataset_summary.json` are development
artifacts. See
[`ADR 0003`](docs/decisions/0003-parent-instance-label-selection.md).

**STEP 1 — Data Generation**
```bash
python3 -m cfl_gnn.cli.collect_incumbents \
    --categories           CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --input_dir            /path/to/milpbench_lp_files \
    --output_dir           /path/to/intemediate_lps \
    --time_limit           3600 \
    --probe_time           30 \
    --complexity_threshold 500 \
    --pool_size            20 \
    --pool_gap             0.10 \
    --threads              8
```

**STEP 2 — Phase 1 EDA & Data Validation** *(requires Step 1 complete)*
```bash
python3 -m cfl_gnn.cli.audit_collection
```

**STEP 3 — PyG ETL** *(requires Step 1 complete)*
```bash
python3 -m cfl_gnn.cli.build_dataset \
    --categories    CFL_easy_instance CFL_medium_instance CFL_hard_instance \
    --gaps          0.10 0.85 0.90 \
    --base_raw_dir  /raid/.../raw_instances \
    --base_pyg_dir  /raid/.../pyg_dataset
```

**STEP 4 — Dataset Validation** *(requires Step 3 complete)*
```bash
python3 -m cfl_gnn.cli.audit_dataset \
    --categories CFL_easy_instance CFL_medium_instance CFL_hard_instance

python3 -m cfl_gnn.cli.graph_statistics

python3 -m cfl_gnn.cli.graph_clustering
```

**STEP 5 — Serial Training: Smoke Test** *(requires Step 4 validated)*
```bash
python3 -m cfl_gnn.cli.train_serial \
    --easy_split 10 2 2 --medium_split 5 1 1 --hard_split 5 1 1 \
    --epochs 10 --hidden_dim 32
```

**STEP 6 — Parallel Training: Full DGX Run** *(requires Step 5 passed)*
```bash
torchrun --nproc_per_node=8 -m cfl_gnn.cli.train_distributed \
    --easy_split    300 50 50 \
    --medium_split  200 30 30 \
    --hard_split    100 15 15 \
    --epochs 200 --hidden_dim 64 --patience 20
```

**STEP 7 — Generate Variable Hints** *(requires Step 6 complete)*
```bash
python3 -m cfl_gnn.cli.generate_hints \
    --model_path /raid/.../best_model.pt \
    --lp_file    /raid/.../CFL_easy_instance_0.lp.gz \
    --output_dir /raid/.../hints \
    --hidden_dim 64
```

**STEP 8 — Gurobi Warm-Start Benchmark** *(requires Steps 1 and 7 complete)*
```bash
# Baseline run — control group
python3 -m cfl_gnn.cli.benchmark_gurobi \
    --input_dir  /path/to/milpbench_lp_files \
    --output_dir /raid/.../benchmark_baseline \
    --time_limit 300 --threads 8

# GNN-guided run — with variable hints
python3 -m cfl_gnn.cli.benchmark_gurobi \
    --input_dir  /path/to/milpbench_lp_files \
    --output_dir /raid/.../benchmark_with_hints \
    --hint_dir   /raid/.../hints \
    --time_limit 300 --threads 8
```

**STEP 9 — Academic Evaluation** *(requires Steps 3 and 6 complete)*
```bash
python3 -m cfl_gnn.cli.evaluate \
    --model_path      /raid/.../best_model.pt \
    --base_root       /raid/.../pyg_dataset \
    --experiment_name parallel_v4 \
    --easy_split      300 50 50 \
    --medium_split    200 30 30 \
    --hard_split      100 15 15
```

---

## Getting Started

### Prerequisites
* Python 3.10+
* Gurobi Optimizer with a valid license
* PyTorch and PyTorch Geometric (for the GNN)

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

### Installation
Clone the repository:
```bash
git clone https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git
cd cfl-gurobi-gnn
```

Install the required dependencies:
```bash
pip install -r requirements.txt
pip install -e . --no-deps
```
---

### Data Download
Due to the very large size of the dataset, the raw data can be downloaded directly from [MILPBench](https://github.com/thuiar/MILPBench), specifically using the following links:
* **CFL_easy**: https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing
* **CFL_medium**: https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing
* **CFL_hard**: https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing

After downloading, please extract and place the raw `.lp.gz` files into the `data/raw/MILPBench/CFL/` directory. It is also necessary to add the `.pickle.gz` files to the directory, which should contain folders for each instance `CFL_easy_instance_0` ... `CFL_hard_instance_29`.

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
