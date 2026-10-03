# PR54: first-batch engineering closure

## Scope and evidence status

This closes the implementation and first licensed batch, not the full
20-medium campaign, a 90-parent dataset, or a demonstration of learned solver
acceleration. The campaign contract is
`ca9b2052c8ed69fde53d0b1a3661ea6f1d6474eab61d0fb834b573ea4599b6c5`.

The DGX-DaSCI full smoke suite reported **483 passed** and one non-failing
TypedStorage warning. Medium array 3350, hard job 3351 and audit 3352 produced
six valid task receipts. All six reconstructed receipt hashes matched the
supplied receipts. Independent mathematical feasibility checks passed according
to those receipts; they were not rerun on the review workstation.

The aggregate artifact hashes are supplied evidence, not independently
recomputed copies of the HPC files. The final raw-artifact hash and sanitization
confirmation has not been received. This software engineering closure does
not certify or publish those raw files, and does not waive those checks before
downstream dataset reuse or release. Only this hand-curated, path-free evidence
summary is added to the repository.

## Numerical outcomes

| Parent | Preserved role | Optimization budget (s) | Terminal relative gap | Label admitted |
| --- | --- | ---: | ---: | --- |
| CFL_medium_instance_5 | validation | 28800 | 0.12167058441070388 | no |
| CFL_medium_instance_6 | validation | 28800 | 0.10562871252393151 | no |
| CFL_medium_instance_7 | test | 28800 | 0.03118663090538829 | yes |
| CFL_medium_instance_8 | train | 28800 | 0.022203736269829335 | yes |
| CFL_medium_instance_9 | test | 28800 | 0.11597430248856996 | no |
| CFL_hard_instance_1 | train | 57600 | 0.8147506243325077 | no |

All six solves stopped at the time limit and remain right-censored. A feasible
solution above the admission gap is not mathematical infeasibility or a process
failure. The admission rule remains relative gap at most 0.10 plus independent
mathematical validation; no threshold is relaxed retrospectively.

Forty preserved labels and two new labels yield **42 admitted parents**
(30 easy, 12 medium), with 48 unresolved. This membership differs from the
historical 42-parent confirmation cohort. Only medium instance 8 is a new
training parent; instance 7 remains held out. Admission does not establish that
new graphs or a newly trained network exist.

The six tasks account for 201604.2673014421 optimization wall seconds, summed
across tasks (approximately 56 hours). Together with the PR53 pilot, the known
expansion cost is 259206.41284622857 seconds (approximately 72 hours). This is
neither campaign elapsed time nor complete research cost. Earlier attempts are
not included. Comparing hard instance 0 at eight hours with hard instance 1 at
sixteen hours does not identify the causal effect of doubling the time limit.

## Explicitly unfinished work

- Fifteen medium tasks have not started; they are not classified as failures.
- Twenty-nine hard parents are deferred; the attempted hard parent is still
  above the admission threshold.
- No new dataset or scientific-reporting eligibility is granted.
- Keep the 64 GiB reservations; this small sample does not justify reducing
  memory across the population.
- Subsequent collection batches are paused while the focused easy-to-medium
  guidance experiment is developed. No completed task should be resubmitted.

## Approved next direction

1. Train a fresh easy-only Gasse model using existing, audited Gurobi graphs,
   seed 42 and 100 epochs. Preserve parent folds and select the checkpoint and
   decision threshold exclusively with easy validation data.
2. Compare fresh unguided Gurobi with GNN-generated partial MIP starts on a
   predeclared medium cohort. Reuse the native executor, retain censored and
   rejected outcomes, and account for both optimization and end-to-end costs.
3. Consolidate scientific evidence and figure/table outputs before revising
   the manuscript. A higher classification score alone is not solver benefit.

The previous variable-hint-primary policy remains historical evidence. A
MIP-start-primary experiment uses a new protocol; hints, starts and hard fixing
must never be reported as interchangeable. Original MINIMIZE models and
feasible regions remain unchanged in the primary experiment. The existing
39-parent model is not an easy-only model because it included medium training
parents.

## Reproducibility pointers

The HPC report lists these expected output hashes:

- `admitted_parent_label_index.jsonl`:
  `f58f9cc2ba47b06dbb4865da172d76ac4ae7eddf4efa10f9aa650e2c03a31eae`
- `campaign_runtime_outcomes.csv`:
  `724ca62e773f6319fda238217688ceba8bc91176cd303d8fdb4e24d4d2f7d153`
- `campaign_task_metrics.json`:
  `7c241364df5ac8673f0fc947bacc60f174595449690460baecf8c0e44acfcfb0`

The existing campaign runbook remains the implementation reference. Its later
batch submission examples are not authorization to resume the paused campaign.
