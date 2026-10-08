# cfl-gurobi-gnn

Research software for learning-guided optimization of Capacitated Facility
Location (CFL) instances. The project is developed through cooperation among
the University of Brasilia, the University of Jaen, and the DaSCI Institute
(Andalusian Research Institute in Data Science and Computational Intelligence).

The repository connects native mixed-integer programming (MIP) solves,
variable-constraint bipartite graphs, a Gasse-style graph neural network (GNN),
and paired solver experiments. Learned guidance is evaluated as an empirical
intervention. The software does not assume that a warm start will improve every
instance.

## Current research result

The MVP 1.0 baseline is a development-only research MVP:

- 54 original-parent graphs were admitted to the learning cohort: 34 training,
  10 validation, and 10 held-out test parents;
- the corrected Gasse model was trained for 100 epochs with seed 42;
- the held-out predictive evaluation covered 10 parents, 5,536,400 binary
  targets, and 5,265 positive targets;
- held-out precision was 0.692293, recall was 0.706363, F1 was 0.699257,
  PR-AUC was 0.774668, and ROC-AUC was 0.999694;
- the validation guidance experiment selected the GNN partial MIP start without
  reading test outcomes: it improved terminal gap on 4 of 6 validation parents,
  with median guided-minus-control gap difference -0.012235;
- the frozen held-out benchmark improved terminal gap on 5 of 6 test parents,
  with mean difference -0.072001 and median difference -0.011642;
- at the common one-hour budget, 4 of 6 guided runs and 3 of 6 controls reached
  a relative MIP gap no greater than 10%.

Four guided test runs and all six controls were right-censored. The six-parent
test sample is too small for a confirmatory population-level claim, and the
large gain on `CFL_medium_instance_20` is influential. After excluding that
parent, 4 of 5 guided runs still won and the median gap difference remained
negative (-0.002135). Accordingly, all current evidence retains
`development_only=true` and `scientific_reporting_eligible=false`.

The [scientific evidence summary](docs/results/pr60-scientific-evidence/README.md)
reports the exact scope, outputs, sensitivity analysis, and limitations. The
[reproducibility guide](docs/reproducibility.md) explains how to reconstruct
contracts without rewriting historical receipts.

The [experimental freeze gates](docs/releases/mvp-1.0.md) distinguish source
promotion, publication rendering and private evidence verification. Public
Pages is deployed from `main`; MVP 2.0 feature work targets `develop` under the
[computational research roadmap](docs/research/mvp2-hpc-roadmap.md). Zenodo
upload remains deferred. The [incumbent evidence status](docs/research/incumbent-augmentation-status.md)
separates implemented augmentation mechanisms from population-scale results.

## Methodological contract

- **Objective sense:** the CFL LP files used here contain an erroneous original
  `MAXIMIZE` declaration. The pipeline records it and forces the effective
  objective sense to `MINIMIZE` without modifying the source bytes.
- **Solver roles:** Gurobi is the priority solver and graph-construction
  authority. SCIP, through PySCIPOpt, is a separately identified comparison.
  Pyomo is not part of the accepted route.
- **Graph identity:** one graph represents one original or independently solved
  synthetic MIP. An incumbent vector is not itself a graph or an independent
  parent.
- **Partitions:** canonical parent folds determine train, validation, and test
  membership. Synthetic descendants inherit their parent and are train-only.
  Test outcomes cannot select checkpoints, thresholds, supports, or methods.
- **Features:** strict graphs use objective coefficients, domains, the linear
  constraint matrix, and a real Gurobi root-`MIPNODE` relaxation. The accepted
  route has no zero-vector fallback.
- **Learning:** training-only statistics define normalization and class weights.
  Validation selects the checkpoint and threshold. Training and validation loss
  are plotted together.
- **Guidance:** the current paired benchmark uses a partial MIP start selected
  on validation evidence. Variable hints remain a distinct nonbinding method;
  neither method is equivalent to `LB = UB` hard fixing.
- **Outcomes:** paired solver comparisons retain terminal MIP gap, optimization
  time, the four wall-time regions, failures, and right-censoring.

## Pipeline

```text
Original CFL LP files
        |
        v
Gurobi parent solves and admissible labels ---- SCIP comparison trajectories
        |
        +---- audited train-parent incumbents
        |                  |
        |                  v
        |         synthetic Local Branching MIPs
        |                  |
        |         independent derived solves
        |                  |
        +------------------+
                 |
                 v
Gurobi-authoritative bipartite graphs and parent-aware manifests
                 |
                 v
Gasse GNN training -> validation selection -> frozen held-out prediction
                 |
                 v
control / root-LP start / GNN start paired solver experiments
                 |
                 v
hash-bound tables, figures, censoring summaries, and influence analysis
```

The complete mapping from stages to JSON, JSONL, CSV, SVG, PNG, checkpoint, and
graph artifacts is maintained in the [output inventory](docs/output-inventory.md).

## Repository map

| Path | Purpose |
|---|---|
| [src/cfl_gnn](src/cfl_gnn/README.md) | Package layers and CLI adapters |
| [configs](configs/README.md) | Frozen splits and experiment policies |
| [scripts](scripts/README.md) | Local and Slurm orchestration |
| [tests](tests/README.md) | Contract, numerical, and licensed checks |
| [docs](docs/README.md) | Architecture, protocols, decisions, and results |
| [data](data/README.md) | External artifact layout and lifecycle policy |
| [sandbox](sandbox/README.md) | Toy bipartite numerical regression input |
| [notebooks](notebooks/README.md) | Exploratory analyses, never acceptance gates |
| [tools](tools/README.md) | Read-only diagnostics and maintenance helpers |

## Computational platform: DaSCI DGX

Operator-reported inventory received on **2026-10-08**, before the planned
in-place update of `tfm_env`. This maps the host and installed environment;
it is not a claim that every experiment used all these resources or versions.

| Component | Observed configuration |
|---|---|
| Compute node | `dgx-dasci`; one-node platform |
| CPU topology | 2 sockets, 40 physical cores, 80 logical CPUs (earlier 2026-10-06 inventory) |
| GPUs | 8 NVIDIA Tesla V100-SXM2-32GB; nominal 32 GB per device, not one pooled memory space |
| Scheduler | Slurm, `batch` partition; current configured GPU resources: `gpu:8` |
| NVIDIA software | Driver and NVIDIA-SMI 550.90.07; NVML 550.90 |
| Driver-reported CUDA | 12.4; distinct from installed toolkit packages and the PyTorch CUDA build |
| Environment | Existing Conda environment `tfm_env`; Python 3.10.20 |
| Learning stack | PyTorch 2.1.2+cu121, torchvision 0.16.2+cu121, torchaudio 2.1.2+cu121, PyG 2.7.0 |
| Numerical/solver stack | NumPy 1.26.4, SciPy 1.15.3, gurobipy 13.0.1 |

`pip check` reported no broken requirements; this is dependency-metadata
consistency, not a GPU execution or numerical-validation test. The inventory
was collected outside a Slurm job. The earlier `nvidia-smi` device query returned
`No devices were found`, although procfs listed eight V100 devices and Slurm
advertised eight GPUs; the cause and allocated GPU functionality remain unproven.

The [dated platform record and manuscript guidance](docs/research/dasci-platform-20261008.md)
preserve the observation, CUDA distinctions, earlier CPU provenance and
per-experiment reporting requirements. The [PR80 environment plan](docs/research/pr80-tfm-env-upgrade.md)
keeps only `tfm_env`; no upgrade is implied by this inventory. Hardware capacity
must be distinguished from allocated CPUs/GPUs, physical affinity, Gurobi thread
limits, measured memory and effective training hyperparameters in each result.

## Installation

Python 3.10 is the reference interpreter used in the recorded DGX runs.
`pyproject.toml` is the canonical dependency specification.

For a standard editable installation:

```bash
python3 -m pip install -e '.[test,projection]'
PYTHONPATH=src python3 -m pytest tests/smoke -q -rs
```

For a pre-provisioned HPC environment, avoid replacing validated CUDA or solver
packages:

```bash
python3 -m pip install -e . --no-deps
PYTHONPATH=src python3 -m pytest tests/smoke -q -rs
```

Install the SCIP comparison only where PySCIPOpt is supported:

```bash
python3 -m pip install -e '.[scip]'
```

GPU installations must select a PyTorch wheel compatible with the host CUDA
driver before installing this project. Gurobi and SCIP licenses are external to
the MIT license. Never commit or print solver credentials. See
[reproducibility](docs/reproducibility.md) for environment capture and DGX
execution requirements.

### Data Download
Due to the very large size of the dataset, the raw data can be downloaded directly from [MILPBench](https://github.com/thuiar/MILPBench), specifically using the following links:

* **CFL_easy**: https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing
* **CFL_medium**: https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing
* **CFL_hard**: https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing

Extract the `.lp.gz` files under `data/raw/MILPBench/CFL/` using the hierarchy
described in [data/README.md](data/README.md). Preserve source hashes. The
repository does not redistribute MILPBench or change its terms.

## Reproducibility boundaries

A passed process exit and matching SHA-256 digest establish execution and byte
identity, not scientific validity. An accepted run must also satisfy the
mathematical, partition, provenance, feasibility, censoring, and eligibility
checks encoded in its report.

Large LP files, graphs, checkpoints, predictions, solver logs, and licenses are
kept outside normal Git history. Share reviewed and sanitized manifests, tables,
figures, and receipts; retain internal path-bearing artifacts in protected
storage. The dataset and full 90-parent population remain future extensions.

## License and citation

Original source code, documentation, and project-generated summaries are
released under the [MIT License](LICENSE), within the authors' rights. This does
not relicense MILPBench, commercial solvers, cited publications, or third-party
templates. See [LICENSE_POLICY.md](LICENSE_POLICY.md) and
[data/LICENSE.md](data/LICENSE.md).

Citation metadata is provided in [CITATION.cff](CITATION.cff). The core model
architecture follows Gasse et al. (2019), *Exact Combinatorial Optimization with
Graph Convolutional Neural Networks*, [arXiv:1906.01629](https://arxiv.org/abs/1906.01629).
