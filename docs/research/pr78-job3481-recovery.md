# PR78: job 3481 diagnosis and revised operator flow

## Installed diagnostic and implemented recovery

The operator returned diagnostic SHA256
`c82585b53037d2c68262a3d0a0d630038c7e0487ba05c5e4b20f699b3ec0ef49`
from `pr78/site-job3481-GgvTR0mZ/site-job3481.json`. It reports one Slurm node,
two sockets, 20 physical cores per socket, two hardware threads per core:
**40 physical cores and 80 logical CPUs**. Partition batch uses
`select/cons_tres`, `CR_CORE_MEMORY` and `OverSubscribe=NO`; jobs can receive
disjoint cores on the same node without oversubscribing those cores.

Accounting contains only 3481, CANCELLED, Start=None, elapsed zero, NNodes=1.
The saved submission exists; held-profile, release and batch-start markers do not.
This locates the stop after job-ID persistence and before release. The expired
scontrol job record prevents identifying the exact failed field retrospectively.
The earlier squeue display of two nodes is retained as an unresolved observation,
not treated as evidence of an actual two-node allocation.

Source review found a concrete parser incompatibility: Slurm 22.05's
[_sprint_range and pending-job formatting](https://github.com/SchedMD/slurm/blob/slurm-22-05-2-1/src/api/job_info.c)
can represent a fixed count as `1-1`, while v1 requires `1`. The successor accepts
only equal-endpoint ranges, retains their original display values, and still
rejects real multiple-node or variable-range requests. Its sharing check also
uses the site's consumable-core configuration and bounded CPU count, rather than
requiring the single text value OK. See [Slurm resource sharing](https://slurm.schedmd.com/cons_tres_share.html).

Implemented files:

- [paired_matrix_workflow_v2.py](../../scripts/evidence/paired_matrix_workflow_v2.py):
  explicit successor protocol, site preflight before sbatch, singleton-range
  parsing, structured submission failure with stage/job/field, durable ID,
  unchanged one-shot status/collection and independent easy review before medium.
- [recover_pr78_job3481.py](../../scripts/evidence/recover_pr78_job3481.py):
  noninteractive, one-time recovery. Before writing its claim it verifies CI at
  the installed source SHA, the old clean source and approval bytes, diagnostic
  and submission hashes, absent execution/release state and fresh cancelled
  accounting with no start or steps. It preserves the old STOP and creates
  `pr78/recovery-job3481-v2/flow` with a linked recovery receipt.
- [submit_paired_matrix_v2.sbs](../../scripts/slurm/dasci/submit_paired_matrix_v2.sbs):
  one node, one task, 16 physical cores, 64 GiB, 330 minutes, no requeue.

The v1 files remain frozen because published receipts and the original flow bind
their exact bytes. V2 is a separate protocol snapshot; its future changes need
not alter the historical implementation. The matrix executor, worker, callback,
model semantics and memory watchdog are reused without modification.

The cancelled submission is counted: historical ceiling three submissions,
comprising 3481 and at most two successor parents. The execution ceiling remains
ten optimize calls and 36,000 solver seconds. No automatic retry is added.
The user's instruction to continue the revised plan supplies the recovery
authorization; the CLI reuses the existing resource approval without a prompt.

Operator sequence, using the reviewed successor source (concrete SHA in handoff):

```bash
python3 -B "$PR78_SOURCE/scripts/evidence/recover_pr78_job3481.py" prepare
python3 -B "$PR78_SOURCE/scripts/evidence/recover_pr78_job3481.py" submit-easy
# Run separately whenever desired; no wait loop:
python3 -B "$PR78_SOURCE/scripts/evidence/recover_pr78_job3481.py" status
# Run after terminal=true, including failed or cancelled outcomes:
python3 -B "$PR78_SOURCE/scripts/evidence/recover_pr78_job3481.py" collect
```

Preparation or submission failure retains its claim/state and returns a report;
do not rerun those actions. Status and collection are separate from preparation.
The one-time recovery claim prevents changing the source SHA to obtain another
automatic attempt. The actual kernel-memory/affinity gates still run before
license or model access. A successful local/CI test is not an installed result.

The preceding implementation has eleven targeted regression tests, including
complete sealed-return validation and preserved independent medium admission.
The complete local evidence suite ran 405 tests successfully (four platform
skips). Local Ruff 0.16.7 check and format validation passed; exact-head CI
with the repository's pinned Ruff 0.16.8 remains required before preparation.
The local receiver must use v2; the original v1 receiver is not suitable for
the new protocol. PR78 remains draft until the actual returns are reviewed.

The following sections retain the earlier planning context; statements that the
site diagnostic or runtime implementation were pending are superseded above.

## Current disposition

The operator explicitly approved the resource envelope. The helper recorded it,
then created job **3481**, printed a generic stop, and left the job pending with
`JobHeldUser`; the displayed node count was two. The operator reports cancelling
it with `scancel 3481`. Final accounting and the installed state markers have
not yet been independently inspected. PR78 stays draft pending execution/evidence.

The previous false-approval checkpoint is superseded. Recorded authorization:
`ad80043db2f5ae46bd4e957f2a68ec6440736386a5ebb6e712b66380e58cfc9c`.
Operator approval: `2c117f2bc9325673f80a633e185f33709ae90de2faf37b0c020030f913c2971d`.
Matrix approval: `89650a62b9fea5fe197bbd4c008a93e5001d33d3e5abecdf5394f96c4b85fd34`.

Do not rerun the old starters, release 3481, remove locks or overwrite the
original flow. The existing source and evidence remain the historical record.

## Established facts and remaining uncertainty

Both installed Python submission code and batch script specify `--nodes=1`,
`--ntasks=1`, and `--cpus-per-task=16`. The Python command removes environment
overrides beginning with `SBATCH_`, `SRUN_`, and `SLURM_`. The scientific plan
does not require multiple nodes. The operator describes dgx-dasci as one node
with 80 cores; socket/core topology will distinguish physical and logical CPUs.

The existing `--hold` persists a job ID and validates resources before releasing
the job. `JobHeldUser` therefore does not mean ordinary resource contention.
The generic exception handler conceals which validation or command failed.
The two-node display is an observed discrepancy, not proof of its cause.
Do not relax the one-node guard or change CPU/memory settings speculatively.

Current site configuration is not historical proof of submission-time settings.
Cancellation changes the job state/reason. Missing batch markers alone do not
prove zero optimization calls. The diagnostic preserves these distinctions.

## Implemented diagnostic

[inspect_paired_site.py](../../scripts/evidence/inspect_paired_site.py) uses only
the Python standard library and read-only commands. It reports physical/logical
CPU counts, sockets, process affinity, host RAM, Slurm nodes/partition/selection
configuration, current job resource differences, accounting and workflow marker
hashes. Each query runs once with a 20-second timeout; failures are explicit.
No solver imports, prompts, submission, release, cancellation or retry exist.
Only selected fields are output; accounts, raw configuration, private logs and
license information are excluded. A vanished job record is reported as unavailable.

```bash
python3 -B /path/to/reviewed/inspect_paired_site.py \
  --directory /raid/vrcelestino/data/cfl-mvp2-evidence/pr76/operator-ad4800505bae/flow \
  --job-id 3481
```

The operator handoff supplies the concrete file URL, hash and physical RAID
directory. Five regression tests cover two-node differences, field filtering,
physical-core counting, cancelled/expired jobs, read-only preservation and
timeouts. They do not claim validation on dgx-dasci.

## Revised delivery and interaction contract

1. Complete diagnosis in PR78: verify cancellation, inspect release/batch markers
   and compare requested with recorded resources. Identify the failed stage.
2. Refactor submission using the observed single-node configuration. Check the
   supported resource profile before consuming a submission. Retain durable job
   IDs and post-submission validation. Failures must expose the job ID, stage,
   structured resource differences and a usable status command. Status must
   distinguish validation hold, queue waiting, running, cancellation and completion.
3. Use the approval already recorded. Plan and resource decisions are settled
   in Codex; executable handoffs are noninteractive, without phrase retyping or
   second confirmation. A reviewed successor manifest references the prior
   authorization and revised code/plan hashes. Frozen records are not rewritten.
4. Account for the cancelled submission. The original ceiling was two submissions
   and one was used. Replacement easy plus medium would total three historical
   submission events, even if 3481 never ran. Reconcile the old attempt, document
   this revised count and the remaining execution budget before issuing the
   successor command. Cancellation grants no extra solver time. Automatic retry
   remains disabled; manual recovery is an explicit, traceable transition.
5. Submit easy once and return its ID. Query and collect without loops. Review
   actual easy return bytes before medium. Complete both returns, accounting,
   memory checks and scientific limitations in PR78. No PR per helper/receipt.

The runtime repair and replacement launch are pending the site diagnostic;
the read-only inspector is implemented now. The two-node cause is not yet fixed.

The experimental envelope remains the one in the historical runbook: one node,
16 physical cores and 64 GiB per sequential parent, ten optimize calls at most,
3600 seconds per call, original parents/seed/thread order/gaps, and the existing
48-decimal-GB solver, 56-GiB sampled and 64-GiB kernel memory limits. Installed
configuration observations alone do not qualify actual allocations.

Files stay on `/raid/vrcelestino/data/cfl-mvp2-evidence`; the license stays at
`/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic`.

The [MVP2 delivery plan](mvp2-delivery-plan-20261006.md) remains the roadmap:
paired execution/evidence in PR78, then paired analysis and CPU profile selection
to close Sprint B, followed by data/representation, training and warm-start
evaluation. Request merge approval only after the completed PR is ready for review.
