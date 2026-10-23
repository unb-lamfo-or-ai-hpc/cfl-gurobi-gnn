# PR78: installed hierarchy and bounded continuation

The sanitized `qualification.json` is the exact job 3485 receipt returned by
the operator, SHA256
`71591edbffe32de84792d6b75d38661618291057e95f2fce6812729bed70a63c`.
The allocation completed with exit 0. No solver or matrix retry was run by
the qualification. Its historical `candidate_integrated_into_executor=false`
is retained: integration happened afterwards, in this PR.

## Finding and correction

The installed hybrid hierarchy exposes the memory controller through cgroup v1.
The leaf has an effectively unlimited RAM limit; the step and job ancestors
enforce 64 GiB. Rejecting the leaf alone rejected this valid hierarchy.
The qualified v3 gate follows membership and mount data to the job anchor,
validates hierarchical accounting, and rechecks limits and usage each sample.
The maximum usage from leaf through job anchor includes sibling usage.
This is not an exact peak RSS measurement, a swap qualification, or a
reconciliation of historical Slurm and worker RSS.

The original guards and executor/workflow remain frozen. New
`paired_memory_runtime.py`, `paired_matrix_executor_v2.py`, and
`paired_matrix_workflow_v3.py` integrate the exact qualified guard bytes.
The new protocol exports explicit leaf, job, and effective scoped limits;
it does not mislabel the unlimited leaf as a capped leaf.
Regression tests cover export validation, isolated child selection, stopped
matrices, ambiguous submission, no repeated release, and predecessor binding.

## Operator-invoked continuation, not automatic retry

`recover_pr78_job3482.py` requires the exact failed job 3482 return and old
source/approval fingerprints, absent executor claim and parent output, terminal
accounting, the job 3485 receipt, and four passing CI arms at the new source SHA.
The frozen predecessor obtains its matrix claim before solver entry. These
checks establish the pre-executor stop without altering any historical receipt.
Old sources, approvals, claims, private logs and returns remain untouched.

The operator may invoke one fresh continuation using the already recorded
resource authorization. A stable exclusive recovery claim prevents repetition.
The successor has at most two sequential parent submissions, ten optimization
calls, and 36,000 solver seconds. Counting cancelled 3481 and failed 3482, the
explicit historical matrix-submission ceiling is four; diagnostic allocations
3483–3485 are not matrix submissions and remain separately recorded.

Only `easy` can be submitted through the recovery helper. `medium` remains
blocked pending independent review of the complete easy return. Each parent
retains one node, one task, 16 physical cores, CPU only, shared node, 64 GiB,
19,800 seconds, no requeue. Solver soft limit is 48 decimal GB, sampled stop
56 GiB, enforced kernel RAM limit at most 64 GiB. Parent models, seed 42,
thread order 1/2/4/8/16, easy gap 1%, medium gap 10%, and comparison semantics
are unchanged. No extension, training, scientific promotion, or merge is
authorized by this technical continuation.

## Commands after installing the reviewed, exact CI-green source

Run normal Python in `tfm_env`, never optimized Python. From the pinned source:

```bash
python3 -B scripts/evidence/recover_pr78_job3482.py prepare
python3 -B scripts/evidence/recover_pr78_job3482.py submit-easy
```

Preparation performs no optimization or submission. Execute each command once;
stop on any error and return the sanitized output. Do not delete the claim or
repeat preparation/submission. There is no interactive approval phrase.
The operator-facing launcher runs these steps with stop-on-error handling.

Nonblocking queries and collection:

```bash
python3 -B scripts/evidence/recover_pr78_job3482.py status
# Only after terminal=true:
python3 -B scripts/evidence/recover_pr78_job3482.py collect
```

The public return is under
`/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/recovery-job3482-v3/flow/return-easy`.
Download its fixed public allowlist in one SFTP session and independently
validate hashes and the nested contract. Never export private solver logs.
PR78 remains draft until execution evidence has been independently reviewed.
