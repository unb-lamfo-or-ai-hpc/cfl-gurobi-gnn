# Technical qualification and data migration sequence

## Purpose and order

Job2278626 established that the installed libraries can use the allocated V100,
exchange arrays with NumPy and serialize a synthetic graph. It did not execute
a neural model, backpropagation, an optimizer update or the NPAD Gurobi license.
The author now requests those technical checks, followed by an organized move
of the CFL working materials from DGX to NPAD. The original NPAD venv313 must
remain unchanged. No new scientific campaign or historical model replacement
is implied.

The order is: qualify the environment; inventory and review the DGX materials;
perform only a reviewed cleanup; then clone the approved CFL revision and
migrate the required data. The inventory can proceed while the technical job
is queued. It does not authorize cleanup before the environment is qualified.

## One bounded technical job, before the repository clone

The [submission template](submit-training-license.template.sh) uses the existing
Gurobi14 environment and waits for all five exact-source CI jobs before creating
a stage or calling sbatch. It verifies both installed environment inventories
and the completed GPU receipt. It downloads four small, hash-checked source
files into scratch. This is not a repository clone, an editable installation,
or a dependency update. The three historical project modules are pinned to
16c2b29f97356e9ece7d72bbf12c3bf3fbcc289f and are not modified.

| Component | Technical workload | What a PASS establishes |
| --- | --- | --- |
| GNN | Four own synthetic bipartite graphs; three serial Adam updates | The project's Gasse architecture can fit prenormalization, run forward/backward, produce finite gradients, update parameters and round-trip its own model/optimizer state |
| Gurobi14 | One trivial MINIMIZE MILP with 2,501 binary variables and one constraint | The configured license can initialize and solve a model above the bundled restricted-license variable limit |
| Original environment | Metadata inventory before submission and after terminal collection | Whether the original distribution-name/version inventory still matches its reviewed value |

The GNN uses gasse_v2_alternating_prenorm with 7 variable features, 5 constraint
features, one edge feature, hidden width32 and two layers. Its unchanged
serial_step primitive is extracted from the hash-checked matched_gpu module,
without importing the research scheduling or data-loading pipeline. The test
uses seed42, Adam learning rate0.001, gradient clipping1.0 and float32. These
choices exercise existing interfaces; they are not a new training protocol.
No real instance, learned checkpoint, validation/test split or full 100-epoch
research driver is loaded. Three updates do not establish predictive quality,
convergence, full-data memory feasibility or DDP compatibility. Its new
synthetic state must never replace a historical model.

The reservation is one node, one V100, ntasks=1, eight Slurm CPUs, 48G and
15minutes. The worker has a600s process deadline and no requeue/retry. The
license-check MILP has Threads=1 and TimeLimit=30s; all other solver parameters
retain their native values. These are technical-test settings, not a change to
the prospective MVP3 Threads=0 protocol. The expected primal and dual are both1.
No CFL performance conclusion can be drawn from this deliberately trivial MILP.

For this test only, GRB_LICENSE_FILE points to the existing Agrologistic
secrets/gurobi.lic under the author's NPAD home. The credential file is not
copied, printed, hashed or committed. After the CFL clone, its own secrets
location will become the project-specific configuration through a separately
reviewed step. The present scripts neither create that clone nor migrate a
credential. See Gurobi's [license-file configuration](https://support.gurobi.com/hc/en-us/articles/360013417211-Where-do-I-place-the-Gurobi-license-file-gurobi-lic)
and [restricted-license limit](https://support.gurobi.com/hc/en-us/articles/360051597492-How-do-I-resolve-a-Model-too-large-for-size-limited-Gurobi-license-error).

The two checks report their results separately. A license failure does not
silently suppress the training check, provided the worker is still running.
An allocation failure, preemption or process deadline may prevent either check
from completing; it is not an optimization result. Native logs remain private.
The [terminal collector](collect-training-license.template.sh) prints structured
results and log sizes, never raw license logs. A failure is preserved for
diagnosis without another submission.

## DGX inventory before cleanup

The [inventory program](dgx_migration_inventory.py) examines only metadata in the
eight named roots below. The author runs it on DGX; Codex has no SSH session.
It verifies the discodatos alias against the canonical data directory, avoids
following symlinks, excludes secrets and Git objects, records file sizes,
timestamps, inode/link identities and read-only Git/worktree state, and queries
the author's queue once. It reads no instance, graph, checkpoint or credential
contents. It creates only one new private ZIP in the existing evidence area.
Time and entry bounds make incompleteness explicit. No retry is automatic.

| Directory | Review required before any cleanup |
| --- | --- |
| CFL | Identify original instance files and any unique source data |
| cfl-gurobi-gnn | Identify canonical source, uncommitted work and ignored data |
| cfl-gurobi-gnn-archive | Check source versions and unique files; the name does not prove redundancy |
| cfl-gurobi-gnn-pr57_54 | Preserve training/split provenance and any unique preparation products |
| cfl-gurobi-gnn-quarantine | Preserve failure evidence and investigate unique files |
| cfl-gurobi-gnn-worktrees | Reconcile worktree references and frozen source installations |
| cfl-mvp2-evidence | Preserve plans, claims, logs, roots, Starts, receipts and historical checkpoints |
| cfl-zenodo-staging | Reconcile preservation/deposit manifests; do not infer that a deposit exists |

File names, sizes or timestamps do not prove duplicate content. Logical byte
totals can count hardlinks more than once. A later transfer manifest must bind
file content hashes before any duplicate is removed. Missing roots, external
links, active jobs, dirty worktrees or incomplete scans remain unresolved
conditions; they are not deletion candidates.

The cleanup review must preserve original paths used by frozen plans and
receipts. Do not rename or remove an evidence stage, quarantine or worktree
simply to make the directory tree shorter. Actual cleanup commands will be
prepared only after the returned inventory identifies concrete files, retained
copies and reference impacts. No recursive deletion or move is included here.

## Inputs beyond the Git clone

The .gitignore is a useful starting point, not a complete migration manifest.
The following inputs must be reconciled with the external CFL directory and
the evidence inventory:

| Ignored path | Migration role |
| --- | --- |
| data/bipartite_graphs/ | Graph tensors and their source-instance bindings |
| data/intermediate_lps/ | Intermediate model representations and derivation provenance |
| data/raw/MILPBench/CFL/ | Original CFL instances or links to their retained originals |
| data/real_train_output/*.pt | Training outputs/checkpoints, classified by role and provenance |
| data/metadata/ | Instance identities, feature metadata, partitions and artifact maps |

Each transferred file needs source/destination mapping, byte size, SHA256,
artifact role, source revision or receipt when available, and a verification
result. Reconcile relative and absolute symlink targets without accidentally
copying files outside the reviewed roots. Preserve split identities and the
historical model independently of newly created technical-test outputs.
Credentials, environments, caches and unrelated Agrologistic materials are
outside the dataset transfer by default.

After environment qualification and the DGX organization gate, clone only the
approved develop revision into a dedicated NPAD CFL directory; do not include
draft PR99/101 or reuse the Agrologistic working tree. Transfer the reviewed
inputs without deleting the DGX originals, then compare hashes, counts and
required provenance. Keep historical manifests unchanged and place any NPAD
path mapping in a new migration receipt. Verify scratch retention and durable
preservation arrangements before treating an NPAD working copy as the sole
retained copy. Only then qualify a real-data CFL training pilot or native CFL
solve under its own concrete CLI. No such pilot or campaign is submitted here.
