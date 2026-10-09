# PR80: two useful outputs, one existing environment, one allocation

**9 October: Job3503 is complete and independently reviewed, with all 54 parents
and four forwards. See [closure and visual outputs](pr80-closure-job3503.md).
The execution blocks below are historical. Do not submit again.**

## Job3502: current continuation (supersedes the Job3501 instructions below)

Job3502 ended FAILED/2:0 after 492 seconds. The application returned partial
evidence, not an infrastructure or GPU failure. Its immutable
[public return](../evidence/pr80-job3502-return.json) has SHA256
`83366f115e15fbbf6a548cf404abf27f4b05d6ecff04fa5cc43d673c1fbef2c4`.
All five nested hashes were verified; all 30 reused easy rows equal Job3501.
Nine additional medium parents passed: M0, M1, M2, M4, M15, M16, M17, M18, M19.
The remaining 15 stop at `variable_identity_and_label/label_objective_sense`.
All expanded metadata files were read within the new cap. No inference,
training or optimization occurred. There are now 39 qualified observations,
not 39 new observations in Job3502, and 15 unqualified ones.

**What and why:** `src/cfl_gnn/solvers/gurobi_solution.py` writes lowercase
`minimize`; confirmation labels write uppercase `MINIMIZE`. The existing PR57
loader already normalizes case. The new auditor mistakenly required uppercase
for both schemas. Accept exactly these two minimization spellings, not missing
values, maximization or an inferred default. This is a demonstrated code/schema
incompatibility. The Job3502 receipt did not export the rejected field values;
confirmation for each pending installed label remains the continuation's job.
Record each newly accepted label's original spelling. Do not mutate labels,
graphs, model sense, thresholds, features or mathematical tolerances.

**How:** `submit-remaining` now verifies Job3502's exact return before submission,
reuses its 39 passed rows without alteration, and checks only the 15 pending
medium parents. The batch repeats receipt verification. If all 54 qualify,
execute the same four frozen-model validation forwards. Otherwise preserve the
partial return without automatic retry. No package changes or new training.
One fresh directory; unchanged ceiling: 1 GPU, 4 CPUs, 32 GiB, 45 minutes.
Never submit again from the Job3501 or Job3502 directories. Use the exact-head
CI-approved continuation block in PR80. Regression tests cover both label
spellings, rejection of invalid senses, immutable reuse and exactly 15 launches.

## Job3501 return and historical continuation

**Do not repeat the initial submit block.** Job3501 finished FAILED/2:0 after
322 seconds because the application reported an incomplete audit.
The reviewed [public return](../evidence/pr80-job3501-return.json) has SHA256
`be0b445bc170c947338304a193c7cedfb693ba5f1b6d905a176cbb8d0179b685`.
The pasted Windows attachment differed only in outer CRLF line endings;
normalizing those to LF reproduces this exact original hash. All five nested
member hashes were independently verified. `.gitattributes` preserves the bytes.

- All 30 easy originals passed feasibility, label and numerical graph checks.
  Each has 160,400 variables, 800 constraints and 320,400 matrix nonzeros.
  The easy sample and descriptive tables are useful completed evidence.
- All 24 medium originals stopped at `compressed_metadata/expanded_json_limit`:
  the auditor's **32 MiB decompressed JSON cap**, not a mathematical failure.
  Their graph loading had already succeeded; medium model/label checks did not
  complete. This does not establish that all medium numerical inputs are valid.
- Inference was not attempted. No training or optimization occurred; GPU
  inference functionality has not yet been established by this job.

The correction raises only the bounded metadata-reader capacity to **512 MiB
per expanded JSON file**, inside the unchanged 16 GiB child address-space and
32 GiB job limits. This is an engineering ceiling, not a measured medium file
size or a change to acceptance tolerances. The reader records bytes observed,
whether the entire file was read, and the active cap, including on limit failure.
Duplicate keys, invalid numbers, data identities and mathematical tolerances
remain checked. Actual expanded sizes will be available from the continuation.

Use **`submit-remaining` in a fresh pinned directory**, not `submit` in the
job3501 directory. Before any submission, the operator verifies the original
public return against the hash above. The batch verifies it again, reuses its
30 easy observations unchanged, and attempts only the 24 incomplete medium
audits. The new receipt identifies prior job evidence and reused parents;
these are historical observations, not 30 new measurements. The original
directory is never modified. Inference still rechecks the graph/checkpoint
bytes it consumes and runs only after complete combined numerical admission.

If all remaining checks pass, the same allocation performs the four planned
validation forwards. Otherwise it preserves a partial return. This is one
operator-launched continuation of incomplete work, not an automatic retry.
The resource envelope below is unchanged; no package update, new training,
solver optimization or replay of valid easy audits is authorized by the script.

Regression coverage includes a real gzip JSON larger than 32 MiB, exact-limit
acceptance, over-limit rejection/diagnostics, changed-prior rejection, and a
mocked collector demonstrating exactly 24 medium child launches and preservation
of all 30 easy result objects. These are offline tests, not HPC inference
evidence. Use the latest exact-head CI-approved command in the PR.

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
bash "$STAGE/source/scripts/evidence/operate_pr80_integrated.sh" submit-remaining
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
