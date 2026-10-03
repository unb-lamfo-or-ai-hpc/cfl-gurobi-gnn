# Reproducibility guide

## Reproducible unit of evidence

A reproducible result is a chain of immutable identities, not merely a command
that exits successfully. Retain:

1. the Git commit and experiment configuration hashes;
2. parent identity, partition role, source MIP hash, and effective objective
   sense;
3. label solver, feasibility audit, terminal gap, budget, and censoring state;
4. graph receipt, feature policy, variable ordering, and graph hash;
5. model version, seed, training-only statistics, selected checkpoint, and
   threshold or support policy;
6. per-method solver receipts and the final artifact manifest.

A SHA-256 match establishes byte identity. It does not replace mathematical
validation, partition checks, or scientific interpretation.

## Environment

Python 3.10 is the reference interpreter for the recorded DGX runs. The
canonical requirements are declared in [pyproject.toml](../pyproject.toml):

- core numerical and data packages: NumPy, pandas, PyArrow, SciPy,
  scikit-learn, Matplotlib, seaborn, and tqdm;
- learning packages: PyTorch and PyTorch Geometric;
- priority solver API: gurobipy;
- optional extras: `scip` for PySCIPOpt, `projection` for UMAP, and `test` for
  pytest.

The compatibility [requirements.txt](../requirements.txt) delegates to the
project metadata. GPU hosts must install a PyTorch build compatible with the
local CUDA driver. Solver licenses, CUDA drivers, and scheduler modules are
external system dependencies and cannot be expressed as Python packages.

For a new CPU-oriented environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e '.[test,projection]'
PYTHONPATH=src python3 -m pytest tests/smoke -q -rs
```

For an already qualified HPC environment:

```bash
python3 -m pip install -e . --no-deps
PYTHONPATH=src python3 -m pytest tests/smoke -q -rs
```

Record at least `python --version`, `pip freeze`, Torch/PyG versions, CUDA and
driver versions, solver versions, hostname, GPU model, CPU allocation, memory,
seed, thread count, and Slurm resource request. Do not upgrade packages while
active jobs depend on the environment.

## Solver and license setup

The DaSCI execution contract uses the readable local file
`/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic`. Configure the
native variable without printing the file:

```bash
export GRB_LICENSE_FILE=/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic
test -s "${GRB_LICENSE_FILE}" && echo GUROBI_LICENSE_PRESENT
```

Never commit the license, credential-bearing logs, WLS secrets, or shell traces
that expose credentials. A Gurobi license does not fall under the repository's
MIT grant.

## Data layout

The raw hierarchy is:

```text
data/raw/MILPBench/CFL/
  CFL_easy_instance/LP/CFL_easy_instance_<id>.lp.gz
  CFL_medium_instance/LP/CFL_medium_instance_<id>.lp.gz
  CFL_hard_instance/LP/CFL_hard_instance_<id>.lp.gz
```

Large generated artifacts remain outside Git. The authoritative lifecycle is:

```text
raw -> intermediate parent/derived solves -> bipartite_graphs
    -> models -> analysis/publication outputs
```

Resolve upstream directories from accepted reports and manifests, not guessed
timestamps. A shell variable ending in `_DIR` must contain a directory rather
than the path of a JSON report.

## Preflight and execution

Before submitting work:

1. update or create an isolated checkout from the intended remote commit;
2. confirm a clean worktree without deleting unrelated user data;
3. run the relevant smoke tests and dry-run plan;
4. verify upstream gates, hashes, parent counts, role assignments, and
   `development_only`/`scientific_reporting_eligible` fields;
5. verify LF line endings in Slurm scripts and inspect requested CPU, memory,
   GPU, wall time, array concurrency, and dependency type;
6. submit the computation and audit as separate jobs, with the audit depending
   on successful completion of the full array;
7. archive `sacct`, plans, reports, hash checks, and sanitization results.

Use shell functions with `return` for interactive checks. An unguarded `exit`
can close the user's terminal. Do not change a shared checkout or environment
while jobs are running from it.

## Current accepted development chain

| Stage | Population and purpose | Acceptance boundary |
|---|---|---|
| PR #57 | 54 parents: 34 train, 10 validation, 10 test; 100 epochs | predictive development result only |
| PR #58 | six validation parents; control, root-LP start, GNN start | method selected without test outcomes |
| PR #59 | six frozen test parents; same three methods and one-hour budget | held-out paired development benchmark |
| PR #60 | tables, figures, censoring and influence analysis | synthesis only; no new solver runs |

The held-out prediction report contains 5,536,400 targets and 5,265 positives,
with F1 0.699257 and PR-AUC 0.774668. The frozen solver benchmark reports 5/6
terminal-gap wins, but four guided runs and every control are right-censored.
All current reports therefore remain development-only and are not a
confirmatory claim.

See the [output inventory](output-inventory.md) for exact artifact names and the
[PR #60 summary](results/pr60-scientific-evidence/README.md) for numerical
interpretation.

## Sanitization and sharing

Shareable JSON, JSONL, CSV, Markdown, and SVG artifacts must not contain private
absolute paths, license locations, credentials, or usernames. Internal plans
may require absolute paths for replay; classify them as protected rather than
rewriting them after execution. Inspect compressed archives internally before
sharing.

Verify every output declared in a manifest against its SHA-256 value. Also
inspect figures visually; valid XML is not a scientific figure review. Preserve
failed and censored records. Never convert missing artifacts or an incomplete
population into a passed scientific gate.

## Publication and archival boundary

Git contains source, configuration, tests, documentation, and sanitized small
evidence. LP files, graph tensors, checkpoints, full predictions, and solver
logs require an external research archive with a manifest, source terms, and
checksums. A future Zenodo release should assign separate records or clearly
version intermediate MIPs, graph datasets, embeddings, model artifacts, and
result tables. MIT applies only within the authors' rights and does not override
MILPBench or solver terms.
