# PR86: ten roots reviewed; prospective guidance preparation

## What was observed

Job **3520**, source `f58a7b899ab594a7dfac4ed7df4579be9612ab28`,
completed ten sequential root optimizations for F0/F3/F6/F14/F27/F29 and
M0/M4/M7/M12, all effective MINIMIZE. The original public return SHA256 is
`4b431deb2736b9f780582425c0d77b1e86dbe297abbfffcb48c4027f15549815`.
Its bytes are preserved in [job3520](../evidence/pr86/job3520/public_return.json).
The original validator passed on the source tree used by the job, before
adding new preparation code. The separate pinned review deliberately does
not recompute an old whole-source dependency manifest against a newer tree.

| Observed scope | Seconds | Interpretation |
| --- | ---: | --- |
| Capture, summed over ten parents | 269.923 | Includes model loading, checks, optimization, signature and disposal; **not** Gurobi Runtime |
| Root export, summed | 9.843 | After capture, disjoint from it |
| Supervised children, summed | 286.986 | Includes capture/export; do not add these again |
| Batch observed interval | 287.448 | Includes the supervised children |
| Slurm elapsed | 288 | Scheduler accounting scope, not the same timer |

Sampled cgroup peak: 2,164,248,576 bytes (about 2.016 GiB). Slurm batch MaxRSS:
1,924,732K. They have different observation scopes and are not reconciled peaks.
AllocCPUS=2 is scheduler logical accounting, not evidence of two Gurobi threads.
The configured root cap is Threads=1. No inference, training or main solve was
performed. The public reviewer does not reopen private roots: collection hashes
bind them, and the next installed stage must recheck the actual files.

Regenerate the review and [per-parent table](../evidence/pr86/job3520/root_costs.csv)
with `scripts/evidence/review_pr86_job3520.py --receipt RECEIPT --output NEW_DIR`.
The review qualifies only the named preparation observations, not algorithmic
speedup, new generalization or solver acceptance of a warm start. Original
eligibility flags remain false.

## Next useful delivery: one GPU preparation job

**What:** construct ten fresh graphs from the unchanged original MINIMIZE
models and these ten roots; apply the already selected **mixed** checkpoint
once per parent; construct the frozen GNN and LP-matched partial starts.

**How:** reuse production `build_graph_artifact`, the audited model class/state
dictionary loader, and existing class-aware/matched-LP selection functions.
Do not use old predictions with new roots, fit prenorm or select a new threshold.
The production encoder reads the existing reference labels solely for its
independent feasibility audit. Forward/selection uses features, binary identity
and frozen probabilities; no labels enter start selection. MIP files, root
vectors, mathematical signature, variable order, checkpoint and output hashes
are checked. No `optimize`, backpropagation or optimizer-step call is present.
Reading models with Gurobi for graph construction is not a solver optimization.

**Why:** this closes the missing prospective graph/inference/start costs without
retraining or rerunning roots. Fresh graph construction is measured instead
of calling a cached graph load a cold preparation cost.

Proposed bounded resources, **not yet authorized**: one batch job, one node,
four physical CPU cores, one V100, 64 GiB host RAM, maximum 3,600 s wall and
3,540 s child deadline. At most ten forwards in a single supervised child;
zero optimization calls, zero training, zero main solves. Reservation ceilings:
one GPU-hour and four physical-core-hours; neither is an observed cost. Keep
tfm_env unchanged. The existing qualified 56-GiB sampled stop and <=64-GiB
kernel gate supervise the child. Device OOM, missing roots/labels, hash/shape
mismatch or timeout stops the job; no replacement, requeue or automatic retry.
Historical twenty-forward inference took 179 s, but that does **not** prove
the duration/memory of ten fresh graph builds. One hour is a bounded proposal,
not a completion guarantee.

Outputs: private graphs, probabilities and starts on HPC; public identity,
support/abstention, disjoint costs, GPU peaks, runtime and sanitized failure
receipt. A single downloaded JSON is sufficient for independent review. This
job does not validate full-solution feasibility or Gurobi start acceptance.

## Timing and interpretation

Record shared discovery/checkpoint initialization once. Per parent, record
features (including input checks, graph build/export/reload), inference
(including device transfers and prediction materialization), GNN assembly,
LP assembly, and private export separately. Synchronized forward time is a
nested subset of inference, **not an extra additive region**. Child/supervisor
residuals retain import, validation and teardown overhead; queue delay is not
model preparation. Failed partial intervals remain incomplete, not zero.

M1 depends on M2's support/positive budget: its counterfactual cost must include
GNN assembly as well as graph/inference and LP assembly. Campaign totals count
the common work once. Do not plug the existing five-region cost helper into
the eventual campaign until this dependency, shared initialization, private
export and residuals have been explicitly reconciled. Historical cost results
are not retroactively changed by this preparation.

## Remaining PR86 gates

Review this installed preparation return, including any abstention/failure;
bind the exact starts and complete the campaign operator; approve the exact
210-solve (or prospectively reduced) resource envelope; then run the controlled
comparison and generate CPU/repeatability/cost tables and figures. None of
those executions is admitted by this root review. PR86 remains draft. PR87's
mandatory 1/4-GPU matched full training and PR88 manuscript remain separate.
