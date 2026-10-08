# PR80: two useful outputs, one existing environment, one allocation

## What changed and why

Operator decision, 2026-10-08: retain **only `tfm_env`**, with no package update.
The numerical auditor no longer requires PyTorch >=2.10 (nor >=2.6).
Job 3500 demonstrated a policy rejection, not invalid numerical data. Its files
remain immutable. We now finish the numerical work that was never performed
and immediately use qualified inputs for frozen-model inference in the same job.
No standalone GPU smoke job, environment rebuild, or Sprint B replay is needed.

The existing project deserializes internally generated PyG graphs with
`weights_only=False`. This route is reused **only for the graph bytes bound to
the previously reviewed artifact receipt**. The same file descriptor is hashed
before loading. This is trusted historical pickle loading, not a restricted
unpickler or sandbox: hashes establish identity, not harmlessness. Do not use
this operator with untrusted external graphs. Checkpoint state dictionaries
retain `weights_only=True`, also with a same-descriptor hash check. No claim is
made that old library vulnerabilities have been patched.

## Delivery 1: numerical audit and sample description

Audit 54 unique originals (30 easy, 24 medium), not 84 independent observations.
Reuse selected graph/root/label hashes and canonical parent roles. Read original
models with Gurobi, but never call optimize, relax, or presolve. Check feasibility,
variable order, coefficient/feature consistency and graph-label alignment.

Produce `numeric/numeric.json`, `parent_statistics.csv` and
`descriptive_statistics.csv`. Tables distinguish train/validation/test and
difficulty, report variable types, constraints, nonzeros, matrix density,
discrete-label prevalence and **declared** label gap. Summaries report observed
and missing counts, min/quartiles/max/mean; quantiles use linear interpolation
(type 7). Missing or failed measurements are not zeros. Declared gaps do not
become new optimality certificates.

## Delivery 2: existing models, predictions and partial starts

After complete numerical admission, load the previously selected easy-only and
mixed training plans by their reviewed byte hashes. Require a unique qualified
training report/checkpoint binding per plan; never choose a model using these
new outcomes. Keep saved normalization, architecture and validation-selected
threshold. Missing or ambiguous bindings stop inference with a diagnostic.

Run **at most four forwards**, one graph at a time: two frozen models x F1/M11.
Both parents have validation roles, not training roles. F1 is shared validation;
M11 is medium transfer for the easy model and previously used validation for
the mixed model. This is useful pipeline/validation evidence, **not an untouched
test set**, inferential superiority, or a speedup benchmark.

Reuse existing metric and guidance functions. Export full predictions locally
on the HPC, plus class-aware GNN starts and root-LP starts matched on support and
positive assignments. Coverage remains 10%, capped at 20,000 discrete binary-domain
targets, with existing abstention policy. Labels are used only for evaluation,
never prediction inputs or start ranking. Root values are previously computed
Gurobi relaxation values, not newly generated GNN values. No start is submitted
to Gurobi; feasibility, acceptance and solver benefit remain unmeasured.

`inference.json` records confusion counts, precision/recall/F1, ROC/PR areas,
thresholds, training protocol, checkpoint hashes, forward and case wall times,
GPU allocated/reserved peaks and start support. Full prediction/start JSONs stay
under `run/predictions/`; their hashes are returned, not private logs.
Forward timing excludes historical root construction and model loading; case wall
time is broader but is not end-to-end solver cost. One forward is not a timing
replication study. Seed 42 and backend settings are recorded; bitwise CUDA
determinism is not asserted. Later CPU/GPU scaling and repeated evaluation remain
mandatory scientific work.

## Frozen resource envelope and stop conditions

- One submission, one node, batch partition; 4 physical CPU cores requested,
  32 GiB host memory, 1 GPU, at most 45 minutes; no exclusive allocation.
- Numerical audit: up to 1,800 s total, 90 s and 16 GiB address space per parent,
  one CPU affinity per child. Numerical workers do not see the GPU.
- Inference: at most 600 s; maximum four forwards, no retraining, threshold
  fitting, normalization fitting, optimizer or solver call.
- No requeue, automatic retry, package installation or environment creation.
  A submission marker prevents repeating submit, including uncertain replies.
- Failures preserve partial outputs. Do not resubmit on FAILED/TIMEOUT/OOM;
  collect the existing return and investigate only that failure.
- The script records versions rather than inferring runtime from package names.
  See [observed platform](dasci-platform-20261008.md): expected torch 2.1.2+cu121,
  PyG 2.7.0, Python 3.10.20; actual versions are recorded again in `runtime.json`.
- The Slurm outcome and application outcome are separate. A package can be
  validly transferred while containing a partial/failed experiment.

## Operator sequence

Use the exact PR80 head whose four evidence CI checks passed, supplied in the
PR execution comment. Fetch it into the existing repository, create a **fresh**
worktree at `/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/integrated-<12-char SHA>/source`,
and activate `tfm_env`. No directory is reused or deleted.

```bash
# STAGE is the fresh pinned directory established by the execution handoff.
bash "$STAGE/source/scripts/evidence/operate_pr80_integrated.sh" submit
# Returns immediately. Run status when convenient; no polling loop.
bash "$STAGE/source/scripts/evidence/operate_pr80_integrated.sh" status
# Only after a terminal scheduler state (also collect failures):
bash "$STAGE/source/scripts/evidence/operate_pr80_integrated.sh" collect
```

Collection prints `PR80_RETURN_SHA256`, a 64-character **file hash**, not a
40-character Git commit. Download only `public_return.json` with the supplied
`receive_pr80_integrated.ps1`: one SCP invocation/connection, then verification
of outer and member hashes and scope. Preserve failed downloads for diagnosis.

The public return includes allowlisted summaries/tables and Slurm accounting.
It excludes raw solver logs, licenses, full configurations and model weights.
Independent review of both outputs closes the PR80 audit and fixes the E0
solver inputs. PR80 remains draft until that review; no merge is authorized here.
