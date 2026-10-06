# PR78: job 3481 diagnosis and revised operator flow

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
