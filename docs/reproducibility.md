# Reproducibility guide

## What a reproducible run requires

Retain the code revision, configuration hashes, frozen parent manifest, original
MIP hashes, named labels and their provenance, graph receipts, model version,
checkpoint, and evaluation ledger. Record Python, solver, Torch/PyG, CUDA/driver,
hardware, seed, threads, solver parameters, and scheduler resources. A portable
summary may omit private paths, but its artifact identities must remain traceable.

A content hash is not an independent feasibility test. Admission also requires
consistent variable identity, finite values, domains, integrality, linear-row
feasibility, objective sense and objective reconstruction, and admissible gap
provenance. Do not reuse a different pool member's gap as the selected label's
certificate.

## Environment qualification

The reference DGX interpreter is Python 3.10. The repository currently has
package metadata in [pyproject.toml](../pyproject.toml), an optional
`pyscipopt>=6.1,<7` extra, and a historical
[requirements file](../requirements.txt) with CUDA-specific pins. These files
do not yet constitute a fully qualified, portable environment lock.

Relevant runtime components include Gurobi, NumPy, pandas, PyArrow, SciPy,
Torch, PyG, scikit-learn, Matplotlib, seaborn, and tqdm. SCIP comparisons require
PySCIPOpt; optional UMAP projections require umap-learn; tests require pytest.
This list explains component roles and is not a replacement lockfile. Solver
licenses and compatible CUDA wheels must be provisioned separately.

For an already qualified environment:

```bash
python3 -m pip install -e . --no-deps
PYTHONPATH=src python3 -m pytest tests/smoke -q -rs
```

Do not upgrade or reinstall packages in an environment used by active jobs.
Future dependency consolidation must reconcile imports, extras, GPU installation
instructions, and a clean-install test before claiming one-command reproduction.

Configure `GRB_LICENSE_FILE` using a readable local license file. Some launchers
accept `GUROBI_LICENSE_FILE` and export the native variable internally; inspect
the selected launcher. Never print license contents, use `set -x` around
credentials, or commit a license. WLS credentials are not scientific artifacts.

## Route selection and preflight

Use the [current protocol index](README.md), not the numbered legacy sequence.
Work from the repository root in the intended host and environment.
Use `python3 -m cfl_gnn.cli.<entrypoint>`, not `python3 -m src.cfl_gnn...`.

Before submitting a job:

1. Resolve upstream directories from accepted reports, not from guessed job IDs.
2. A variable ending in `_DIR` must identify a directory, not its JSON report.
   Remove accidental leading spaces and confirm the hostname.
3. Verify the upstream gate, required eligibility flags, expected parent
   population, and hashes. Missing data is not a successful empty audit.
4. Run the selected CLI's documented dry-run where supported. An inventory-only
   gate does not authorize training.
5. Check Slurm scripts for LF endings, allocation limits, and explicit working
   directory resolution. A spooled script path is not the repository root.

Use shell functions with `return`, or explicit conditionals, for interactive
preflight failures; an unguarded `exit` can close the user's shell. Do not submit
a dependent job when its input gate failed. Never switch branches or pull into
the shared checkout while its array or dependent audit is still active.

The [completed confirmation summary](results/pr50-confirmation/README.md)
and its evidence audit distinguish the original 42-parent protocol from the
39-parent revision. The final job completed training and evaluation; no
additional run was required for the documentation reconciliation.

## Experimental acceptance

- Initial confirmation: 30 easy and 12 medium parents; canonical rotation 0
  had 24 train, 10 validation and eight test parents. The separate final revision
  retained 30 easy and nine medium parents (23/8/8), with no hard parents.
- Labels: at most 10% relative MIP gap plus independent feasibility/provenance
  checks. Preserve inadmissible and censored records. The three exclusions
  (medium3/5/6) and selection bias are recorded explicitly; the strict42gate
  was not converted to success and the ceiling was not increased.
- Features: Gurobi-authoritative real root relaxation, no zero fallback.
- Learning: seed 42, 100 full epochs, training-only normalization and class
  weighting, checkpoint/threshold selection using validation only.
- Outputs: joint train/validation loss plot, held-out per-parent quality,
  graph statistics and projections, and solver gap/time comparisons.
- Paired arms: common parent intersection, train-only descendants, equal parent
  mass and optimizer-step budgets. A Gurobi-only confirmation is not four-arm evidence.
- Native benchmarking: equal precommitted optimization budgets, fresh independent
  processes as specified, retained censoring, and explicit inference/preprocessing costs.

Weighted BCE scores are not automatically calibrated probabilities. Accuracy is
insufficient with rare positive targets; interpret precision, recall, F1, average
precision, Brier/ECE, and constant-zero/root-LP diagnostics together. Descriptive
graph projections must not select folds or models.

The final evidence package contains 62 hash-checked files, 100 epoch rows,
39 graph receipts and eight-parent evaluation tables. Graph tensors, original
labels, root vectors, checkpoint and predictions were not transferred for this
review. Full ROC/PR tables were withheld for size. Their receipt hashes and
reported AUC/AP values are not independent raw-artifact verification.
Graph statistics recorded unknown censoring for all 39 rows; their heterogeneous
source runtimes are descriptive, not a solver speed comparison. Epoch losses
are graph-averaged weighted BCE; held-out BCE is unweighted per target.

## Publication and archiving

Keep raw data, graph tensors, labels, checkpoints, and raw solver logs out of
routine documentation commits. Compressed files can still contain private paths
or credentials; inspect contents, not just names. Preserve historical evidence
before proposing quarantine, and never archive inputs still referenced by a
current manifest merely to reduce directory size.

Verify output ledgers against actual files; inspect figures visually as well as
checking syntax/hashes. Label development-only results explicitly and report
coverage and censoring. The initial manuscript uses a supplied Quarto template.
The full 90-parent experiment and subsequent manuscript extension remain deferred.
