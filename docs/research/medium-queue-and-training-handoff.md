# Remaining medium collection and training handoff

## Status and revised boundary

The operator reports task3368_5 completed in1h50m11s, with exit0 and approximately
3.91GiB peak process RSS. Its terminal gap and admission status are not yet
available. Task3368_6 is running;3368_7–9 and audit3369 remain pending. Completion
before the eight-hour limit is not, by itself, an optimality certificate.

The approved continuation queues the ten unstarted medium20–29 originals, in
two five-task batches. It does not rerun the active medium10–14 batch, medium5/6/9
quality-rescue cases, or any hard instance. The42 previously admitted labels are
immutable. Additional valid labels from the active batch are retained by the
cumulative original campaign audit, not overwritten by the queue plan.

## Submission now, execution after verified prerequisites

Create a **separate detached Git worktree**, pinned to the queue implementation.
Fetching a commit and adding a worktree do not require changing the active
checkout used by3368/3369. Keep both source directories intact and pinned until
their jobs finish. Use an absolute license path from the original checkout.

The new queue preparer validates the accepted first-batch preflight and source
hashes, preserves its42-label baseline, and requires all ten future target
directories to be absent. It deliberately does not inspect partial directories
of the active batch as completed results. It writes
`remaining_medium_queue_plan.json`; no solver or scheduler is invoked by that
Python preparation operation.

The explicit Bash submission helper schedules this chain:

| Stage | Original PR54 indices | Parents | Dependency |
|---|---|---|---|
| Existing audit | — | medium10–14 | Existing job3369 |
| Batch2 | 10–14 | medium20–24 | afterok:3369 |
| Batch2 audit | — | Cumulative receipts | afterany:batch2 |
| Batch3 | 15–19 | medium25–29 | afterok:batch2-audit |
| Batch3 audit | — | Cumulative receipts | afterany:batch3 |

These are original campaign batch indices; PR57's first continuation was batch1
in that numbering. Each array uses concurrencyone,64GiB per worker and12hours
Slurm wall time. Each fresh Gurobi solve retains28800seconds,one thread,seed42,
MINIMIZE and no warm start. The ten new tasks can consume80additional optimize
hours sequentially, excluding overhead and queue time. Two allocated Slurm CPUs
do not establish two Gurobi threads; retain the effective solver parameter map.

Every worker verifies the predecessor's report contract, declared output hashes
and corresponding valid source receipts **before** invoking the unchanged PR54
executor. Valid high-gap outcomes do not block the next original batch, but they
remain inadmissible as labels. An execution/audit failure blocks dependent solves;
invalid dependencies are cancelled rather than left indefinitely pending. Audit
jobs use afterany to retain failure and missing-task evidence. Do not manually
release or remove dependencies to bypass these checks. This follows the official
[Slurm dependency semantics](https://slurm.schedmd.com/sbatch.html#OPT_dependency).

The helper writes each submitted ID immediately to `submission.txt` in the queue
directory and a fixed reservation directory under the original run root. This
prevents accidental duplicate chains even with a different timestamp. A partial
submission is not rolled back: inspect its saved IDs before recovery. Do not
delete the reservation and repeat the submission blindly. Operational receipts
contain HPC paths and are not public evidence artifacts.

Existing outputs remain the three PR54 artifacts per audit:
`gurobi_expansion_campaign_report.json`, `campaign_task_metrics.json`,
`campaign_runtime_outcomes.csv`, plus `admitted_parent_label_index.jsonl`.
The report binds the other three files. The final audit has attempted all20
originally pending medium tasks, not certified that all30medium labels qualify.

## Sprint1 completion and Sprint2 launch criteria

1. Review all original-medium attempts, verify hashes and independent feasibility,
   and freeze the admitted cohort at gap<=10%. Retain failures, censoring and
   exclusions. Do not enlarge the threshold to fill a requested population or
   pursue open-ended rescues before the MVP training experiment.
2. Preserve canonical parent splits and exposure records. medium0/1 are already
   development-exposed; they cannot become a newly claimed untouched test set.
3. Build/verify one Gurobi-authoritative bipartite graph per admitted original or
   distinct derivative, including a real root relaxation and aligned labels.
   An admitted solution is not itself a validated graph/training manifest.
4. Qualify assignment identity, the calibration implementation and bounded
   completion effort; these Sprint1 controls remain unfinished. The empirical
   calibrator for the new final checkpoint is necessarily fitted after Sprint2
   training, on validation or grouped out-of-fold predictions, never held-out
   targets. Do not reuse an old calibrator as certification of a retrained model.

After the cohort, split and graph contracts are frozen, two resource-separated
branches can run concurrently:

- **GPU branch:** original-only easy+medium training, seed42, at least100epochs,
  minimum validation-loss checkpoint, training and validation losses on the same
  figure, class-specific predictive metrics and calibration diagnostics. No
  validation or test parent is used for gradient updates.
- **CPU branch:** collect missing SCIP comparison incumbents on training parents,
  verify the Gurobi/SCIP centers, generate distinct local-branching derivatives,
  independently solve/label them with Gurobi and construct authoritative graphs.
  Retain origin, gap, discovery/solve time, radius, Hamming diversity, redundancy
  and full cost. Descendants remain train-only in their parent fold.

Then run matched training conditions: originals; originals plus Gurobi-derived
instances; originals plus SCIP-derived instances. Freeze the parent population,
architecture, label-quality gate and training budget for comparisons; if paired
source availability differs, report that missingness and use a prespecified
matched-parent comparison rather than silently changing populations. Keep equal
parent mass and match optimizer-update exposure, not only the number of epochs.
Oversampling is an experimental hypothesis, not an established prerequisite for
success. Optimal centers with different radii may produce identical labels;
duplicate descendants must not be counted as independent experimental evidence.

No production training or derivative jobs are submitted by the medium queue.
Their final data manifest does not yet exist. Scheduling a training process to
discover whichever files happen to be available would invalidate cohort control.

## Sprint3 demonstration and hard-instance deferral

Freeze checkpoint, calibration, coverage and completion budget before the paired
optimization experiment. Compare learned starts with unguided Gurobi and
matched-support/non-neural starts, reporting primal and dual progress, terminal
gap, first-observed quality times, censoring and cold/reusable end-to-end costs.
Success requires observed benefit under the stated protocol, not a passed
engineering gate. Include mixed or negative outcomes.

Hard instances enter only a final predeclared out-of-distribution demonstration;
no further hard labeling campaign is scheduled now. Historical hard0/1 results
are already exposed development evidence. A new genuinely held-out claim must
respect that exposure. A12/16-hour budget does not guarantee gap<=10%; the hard
demonstration may remain censored and must be reported as such. Article revision
remains deferred until these three sprints provide their actual outcomes.
