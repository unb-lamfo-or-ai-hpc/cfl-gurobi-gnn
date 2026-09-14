# cfl-gurobi-gnn

**Research project developed within an international cooperation between the
University of Brasília (UnB), the University of Jaén (UJA), and the DaSCI Institute
(Andalusian Research Institute in Data Science and Computational Intelligence).**

This repository provides a research framework for learning-guided optimization
of **Capacitated Facility Location (CFL)** instances from
[MILPBench](https://github.com/thuiar/MILPBench). It connects solver trajectories,
variable–constraint bipartite graphs, Gasse-style graph neural networks (GNNs),
and controlled optimization experiments. Whether learned guidance improves
solution quality or computational performance is an empirical question, not an
assumed property of the software.

## Research status

The delivered **development-only research MVP** completed original-parent
training and held-out evaluation. The initial cohort comprised **42 original
parents: 30 easy, 12 medium, and no hard instances**. Three medium parents
remained above the 10% label-gap ceiling after four-hour solves. A separately
recorded revision retained **39 parents: 30 easy and nine medium**, with
**23 training, eight validation and eight test parents**. The original
42-parent gate remains incomplete; exclusion conditions the results on solver
label admissibility.

The versioned Gasse model completed **100 epochs**, seed **42**, using real
Gurobi root-relaxation features. The minimum validation weighted BCE occurred at
epoch 91; the validation-selected classification threshold was 0.9933161.
Held-out aggregate F1 was **0.582463** and parent-macro F1 was **0.584889**.
Reported average precision was **0.609753**. The Brier score (**0.00609632**)
was worse than the constant-zero baseline (**0.00117072**), so calibrated
probabilities are not claimed. The [final evidence summary](docs/results/pr50-confirmation/README.md)
documents the source exclusions, graph analyses, audit scope and numerical results.

This was a Gurobi-labelled original-parent experiment, not a completed matched
four-arm comparison or a demonstration of neural solver acceleration. No hard
instances, multi-seed estimates or current-cohort native hint/control benchmark
are included. These analyses and calibration remain future work.

The intended population remains 90 parents (30 per difficulty). Full-population
execution is deferred until the development outputs, reproducibility review,
and initial manuscript are complete. Software tests, a successful Slurm exit,
and an engineering gate do not establish scientific validity or TRL 6.

Start with the [documentation index](docs/README.md),
[reproducibility guide](docs/reproducibility.md), and
[current architecture](docs/architecture.md). The
[legacy technical reference](docs/pipeline.md) is retained for historical
interpretation, not as the current confirmation runbook.

## Methodological contract

- **Mathematical model:** all CFL MILPBench LP files are treated as having an
  erroneous original `MAXIMIZE` declaration. Record that declaration and force
  the effective sense to `MINIMIZE`. Preserve the original files and their hashes.
- **Solver roles:** Gurobi is the priority solver and sole graph-construction
  authority. SCIP, accessed directly through PySCIPOpt, is a matched comparison
  solver. Both may provide independently audited labels. Pyomo is excluded.
- **Sample identity:** build a graph for an original MIP or an accepted synthetic
  MIP, not for each incumbent vector. An incumbent may define the center of a
  Local Branching neighborhood; the resulting modified MIP requires an independent
  solve and a new graph. Such descendants are not independent benchmark parents.
- **Partitioning:** canonical parent folds determine all roles. Descendants
  inherit the parent fold and are train-only. Validation and test use originals
  only; test outcomes cannot select checkpoints, thresholds, or guidance policies.
- **Graph features:** use the objective, domains, constraint matrix, and real
  Gurobi root-`MIPNODE` relaxation. The strict route has no zero-vector fallback.
  Keep graph features separate from labels, MIP gaps, and execution-time metadata.
- **Learning:** preserve the legacy Gasse implementation and explicitly version
  the corrected alternating-message prenormalization. The confirmation protocol
  fixes seed 42 and 100 epochs; training and validation losses share one figure.
- **Guidance:** native Gurobi variable hints are the primary nonbinding
  intervention. Hints are not MIP starts or `LB = UB` fixings. Restrictive
  exploratory methods require recovery on the original full model.
- **Evidence:** report terminal MIP gap and optimization wall time, plus total,
  data-read, and model-build wall times. Retain failures and right-censored runs.
  Do not infer speedup from incomparable budgets or omit preprocessing costs
  from an end-to-end claim.

The [confirmation protocol](docs/research/pr49-confirmation-validation.md) and
[guidance policy](docs/research/literature-backed-neural-guidance-policy.md)
define the applicable controls.

## Pipeline and experimental arms

```text
Original parent MIPs -> independent solver labels and trajectories -> source audit
          |                               |
          |                     train-parent incumbent centers
          |                               |
          |                   synthetic Local Branching MIPs
          |                               |
          |                     independent derived labels
          +-------------------------------+
                          |
            Gurobi-authoritative graph construction
                          |
            graph statistics and descriptive projections
                          |
         parent-aware training -> validation -> held-out evaluation
                          |
         native guidance/control runs -> paired descriptive outputs
```

| Experimental arm | Label solver | Training samples | Graph authority |
|---|---|---|---|
| Gurobi original | Gurobi | Original parents | Gurobi |
| Gurobi augmented | Gurobi | Originals and accepted synthetic descendants | Gurobi |
| SCIP original | SCIP | Original parents | Gurobi |
| SCIP augmented | SCIP | Originals and accepted synthetic descendants | Gurobi |

The four-arm experiment uses its **common eligible parent intersection**, equal
parent mass, and equal optimizer-step budgets. It is distinct from the broader
Gurobi-only revised 39-parent confirmation. Missing paired coverage must be reported,
not silently replaced with unmatched samples.

## Repository navigation

| Directory | Purpose |
|---|---|
| [src/cfl_gnn](src/cfl_gnn/README.md) | Implementation layers and stable CLI adapters |
| [configs](configs/README.md) | Versioned folds, budgets, eligibility, and learning protocols |
| [scripts](scripts/README.md) | Execution helpers and site-specific Slurm launchers |
| [tests](tests/README.md) | Contract, numerical, integration, and licensed solver checks |
| [sandbox](sandbox/README.md) | Preserved toy bipartite compatibility experiment |
| [docs](docs/README.md) | Current guides, decisions, historical protocols, and evidence |
| [data](data/README.md) | Artifact lifecycle and storage policy; not a bundled dataset |
| [notebooks](notebooks/README.md) | Exploratory notebooks, not the acceptance authority |
| [tools](tools/README.md) | Read-only diagnostics and maintenance utilities |

## Environment and first checks

Python 3.10 is the reference interpreter used in the supplied DGX receipts.
A working Gurobi license is required for independent mathematical validation
and authoritative graph construction. PyTorch/PyG must match the selected
CPU/CUDA environment; PySCIPOpt is needed for SCIP comparisons.

In an **already provisioned and validated** environment, install the package
without replacing its solver or GPU dependencies:

```bash
python3 -m pip install -e . --no-deps
PYTHONPATH=src python3 -m pytest tests/smoke -q
```

Some numerical and solver tests require optional libraries or a valid license.
A skipped test is not a passed native validation. See [tests](tests/README.md)
for mandatory-license checks and the toy regression.

The existing [pyproject.toml](pyproject.toml) declares package metadata and the
SCIP extra; it is **not yet a complete runtime dependency specification**.
[requirements.txt](requirements.txt) contains historical CUDA-specific pins.
Do not blindly reinstall them into a working HPC environment. Environment
consolidation and clean-install qualification remain explicit release work;
see the [reproducibility guide](docs/reproducibility.md).

### Data Download
Due to the very large size of the dataset, the raw data can be downloaded directly from [MILPBench](https://github.com/thuiar/MILPBench), specifically using the following links:

* **CFL_easy**: https://drive.google.com/file/d/1z6oNG1ja6CwlsRYViXIzBj0j8Ch6sxdt/view?usp=sharing
* **CFL_medium**: https://drive.google.com/file/d/181Evo5Q6otZRq6EBeQXFcCYlC4kM8zaH/view?usp=sharing
* **CFL_hard**: https://drive.google.com/file/d/13NS9YTTyNsiV6Dth3qsQ7lWWNQs4Pek0/view?usp=sharing


Extract the original `.lp.gz` files under `data/raw/MILPBench/CFL/`, following
the category/LP layout described in [data/README.md](data/README.md). Historical
`.pickle.gz` artifacts are optional migration inputs, not substitutes for the
original mathematical model. Download availability and third-party data terms
are governed by their providers; this repository does not redistribute them
through this documentation change.

## Reproducibility and interpretation

Every accepted result should be traceable to its code revision, configuration,
parent/MIP identity, label provenance, graph hash, checkpoint, and evaluation
partition. A successful hash check establishes byte identity, not mathematical
correctness. Inspect both the gate and its eligibility fields.

Report original-parent counts separately from graphs, synthetic descendants,
and incumbent observations. Distinguish weighted training loss, validation loss,
held-out classification quality, and downstream solver outcomes. Descriptive
PCA/clustering uses outcome-free graph descriptors; it is not a learned GNN
embedding or a basis for selecting folds.

Keep raw instances, solution vectors, graphs, checkpoints, and historical
evidence outside routine Git commits. Publish only reviewed, sanitized outputs;
never commit solver licenses or credential-bearing logs. The
[MIT license](LICENSE) covers this repository's original code, documentation and manuscript content, not external datasets or
commercial solver rights.

Original project-generated metadata, tables and figures are also offered under
MIT within the authors' rights. The [licensing policy](LICENSE_POLICY.md) and
[data notice](data/LICENSE.md) define the exclusions and export requirements.
Historical receipts and running-job inputs must not be rewritten to add tags.

## Literature and software references

- Gasse, M., Chételat, D., Ferroni, N., Charlin, L., and Lodi, A. (2019).
  *Exact Combinatorial Optimization with Graph Convolutional Neural Networks.*
  NeurIPS 2019. [arXiv:1906.01629](https://arxiv.org/abs/1906.01629).
  This is a branching-policy study; the present assignment-prediction pipeline
  is not a claim to reproduce its learning task.
- Nair, V., et al. (2020; revised 2021).
  *Solving Mixed Integer Programs Using Neural Networks.*
  [arXiv:2012.13349](https://arxiv.org/abs/2012.13349).
- [MILPBench repository](https://github.com/thuiar/MILPBench), source of the
  benchmark download links preserved above.
- [Gurobi variable attributes](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html),
  including `VarHintVal`, `VarHintPri`, and `Start`. Record the exact installed
  solver version in each experiment.

The manuscript will use a user-supplied Quarto Manuscript template. No manuscript
template, final scientific result, or dataset DOI is implied by this README.
