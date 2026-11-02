# PR94 isolated preparation — staged CLI

The operator prepares roots, label-free graphs, frozen-model scores and matched
R/G starts for M5/M6/M9/M13/M20/M26. It has **no evaluation dispatcher**: the
54 optimization comparisons remain unreleased. PR89 is not an input directory,
submission target or source checkout for this operator.

## First intervention: installation and a zero-call preflight

Use the delivered PowerShell installer helper. It verifies the previously
received six-input archive, builds a private path map, transfers two small
files by terminal-password SCP to the existing RAID evidence directory and
prints one Bash command. Run that command in the existing tfm_env session.

The Bash installer creates an exclusive pr94-preparation-COMMIT stage under
the existing evidence root and checks out the reviewed GitHub commit into its
own source directory. Existing stages are never overwritten. It makes no
changes to the installed PR89 source. Git/download failures preserve the partial
stage; no cleanup or retry is automatic.

A bounded metadata search reads only gasse_training_report.json files beneath
the models/analysis layouts. It accepts the previously selected report hash
974236918746711d044e2c0111a1e145d9487b27e20e7953cda6b63058ef3822 and its
original checkpoint hash. Limits are 120 s, 20000 directory entries, 32 MiB report
bytes and 64 MiB for the selected weights file. No tensor/graph is deserialized.
Identical copies are resolved deterministically by the first canonical path,
not by metrics. Absence or a different hash stops installation.

The installer binds all source/scripts, configuration/protocol and qualified
memory-proof files, six model hashes, checkpoint hash and installed package
versions. It preserves the established Python/Gurobi/NumPy/Torch/PyG versions
and records the auxiliary feature-import versions; it installs no packages.
It checks 80 GiB free space, freezes the plan and exports sanitized installation
metadata. The private input paths remain in the exclusive stage. Source
checkout and metadata processing use CPU/I/O; they are not zero-overhead work.

Send the resulting plan hash and metadata ZIP/hash through the supplied
transfer helper. This first intervention runs **zero optimizations, forwards,
training calls or scheduler mutations**. It is useful while the last PR89 job
finishes. It does not submit either preparation job.

## Separate root execution, after installation review

The first preparation job is submitted only by a subsequent explicit author
CLI using submit-roots and the reviewed plan SHA256. Do not run it as part of
installation. Finish the active PR89 campaign before beginning new scientific
execution to avoid adding resource competition.

The operator durably claims the campaign stage before sbatch. It submits held,
checks the returned job identity and requested CPU/RAM/GPU/wall profile, then
releases only that job. A mismatched or ambiguous reply preserves both claim
and any held job; it does not cancel, release another job or retry.

One 2 h job reserves one physical core and 64 GiB. Six sequential supervised
children each have a 1140 s outer deadline and at most one 600 s root call.
Root capture uses the existing first-OPTIMAL node-zero MIPNODE policy.
No model.relax(), fallback vector, label generation or replacement instance is
available. Duplicate claims and changed source/input/environment stop the run.

The qualified hierarchy-aware memory gate, physical CPU affinity and working
storage checks run before model reading and throughout supervision. They use
the recorded 48 GB decimal SoftMemLimit, 56 GiB sampled stop and 64 GiB job limit.
Storage must remain within the 64 GiB working allowance and retain 16 GiB free
during work. The source checkout, including .git bytes, is included. Memory
and storage are sampled guards, not atomic disk quotas or exact peaks.

Use status-roots for a single accounting query and collect-roots only after
root/.batch/.extern are terminal. Collection checks closed artifact hashes and
exports metadata, not vectors or logs. Failed/partial returns are retained and
never promoted to complete. After independent review, review-roots accepts
only the exact returned digest; this records the author's CLI disposition.

## Separate graph/inference/Start execution

submit-guidance requires the same plan hash and the accepted six-root return.
It cannot precede that review. One1 h job reserves four physical cores,64 GiB
and one V10032 GB; a single supervised child has a 3540 s deadline. There is no
CPU fallback or substitute GPU class.

The new wrapper uses the existing label-free feature interface. It verifies
the mathematical model and root order, removes encoder target placeholders,
checks channel 6, edge directions, binary order and finite tensors, then
serializes and reloads the trusted newly generated graph. Logical tensor hashes
and file hashes have different meanings and are recorded separately.

The original checkpoint is loaded once, with the historical module-prefix
handling and frozen normalization state. Graphs are processed sequentially,
with at most one claimed forward each. No normalization fitting, optimizer,
training, target scoring or threshold selection is available. Tests use tiny
synthetic CPU data; that is not evidence of current HPC graph admission.

The G rule and R support/positive-count matching are unchanged. Both retain
abstention, undefined unselected variables and one frozen Start pair per parent
for solver seeds 42/43/44. R/G need not select the same indices. These are
partial starting values, not variable fixing or complete feasible solutions.

collect-guidance checks the closed graph/score/Start bytes and exports only the
six chains' metadata. New artifact hashes remain absent from the repository
until this return is actually received and reconciled. This preparation does
not authorize or launch the 54 evaluation calls.

## Failure and review rules

Never delete claims, overwrite stages, requeue, resubmit or adjust scientific
parameters after an error. Preserve the stderr, incomplete metadata and any
held job, then obtain the specific diagnosis/disposition. A successful Slurm
exit is not scientific qualification, feasibility or a quality result.

The operator is covered by offline fault tests, source/metadata tests and
CPU-only encoder/serialization/model-state fixtures in CI. The old GPU
publication test now checks resource release in protocol metadata instead of
requiring an operational approval phrase in the journal article. GPU result
numbers, negative quality findings and history hashes remain checked.

CLI delivery is tied to the reviewed final source commit and passing CI.
Merges and publication remain separately controlled. PDFs remain deferred.
