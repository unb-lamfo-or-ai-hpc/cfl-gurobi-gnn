# MVP parent-label rescue

This gate completes only the labels that were declared missing by the corrected
six-parent vertical-slice audit. It does not rerun or replace the paired
one-hour benchmark. The benchmark remains the fixed-budget comparison of
Gurobi and SCIP; rescue runs are label-generation provenance and must not be
reported as benchmark observations.

## Precommitted tasks

The input is the immutable `label_rescue_tasks.jsonl` written by the PR #31
audit. For the validated development slice it contains three tasks:

1. Gurobi, `CFL_medium_instance_2`, train, `default` profile;
2. SCIP, `CFL_medium_instance_2`, train, `feasibility` profile;
3. Gurobi, `CFL_medium_instance_5`, validation reference, `default` profile.

Each task uses at most four hours and four million nodes with one thread and
seed 42. It starts in a fresh process, receives no warm start, and cannot
consume a solution from the other solver. The CFL objective is forced to
minimization through the shared parent-solve implementation.

## Integrity boundary

Before a task starts, the runner verifies the vertical-slice contract, rescue
manifest hash, source benchmark contract, source MIP hash, and every benchmark
artifact hash. The same benchmark fingerprints are recomputed after the solve.
The execution report is eligible only when the benchmark is unchanged, the
new run is independent, and its terminal relative MIP gap is at most 10%.

The aggregate audit fails closed unless all three reports match the
precommitted task identities, contract hashes, artifact hashes, and eligibility
checks. Its outputs are:

- `mvp_label_rescue_audit_report.json`;
- `per_label_rescue_task_audit.jsonl`.

Paths written to contracts and reports are relative. Generated data remains
development-only and is not yet eligible for scientific reporting.

## Next gate

After all three labels pass, compose the authoritative six-parent label index.
Then apply the symmetric local-branching operator only to the four
solver/train-parent pairs and independently solve their descendants. Validation
and held-out test parents remain original-only.

