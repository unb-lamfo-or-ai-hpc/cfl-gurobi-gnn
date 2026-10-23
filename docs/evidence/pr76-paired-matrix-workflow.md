# PR76 — nonblocking paired-matrix operator workflow

## Checkpoint and scope

PR75 was explicitly approved and merged into `develop` at
`dd67ce4fa518d9858e714407703f46dc6ffbb696`, from reviewed head
`3666edd0f57776acd90adfe2b360fe5716f7789f`. Its installed no-solver probe
has SHA256 `ca2381d4a1396f3d40b76b653bd7f81f591b830b5f38df8d77dfc12ecc1f1602`:
25 tests, zero failures, errors or skips, fourteen dependency hashes.
That is fault-path qualification, not a completed scientific experiment or
qualification of a future allocation's actual memory limits.

PR76 adds an operator workflow, a Slurm batch entry point and offline tests.
PR75 executor, memory guard, existing adapter and their installed-test bytes
are unchanged. The reviewed probe and its dependencies are checked again
before preparing or submitting a flow. No license, LP, optimization, training
or scheduler submission is used to develop or prepare this delivery.
Merge authorization does not approve the matrix's resource budget.

## Frozen prospective budget (not approved by preparation)

| Quantity | Bound |
| --- | --- |
| Parents | Original easy and medium instances; seed 42 |
| Threads | 1, 2, 4, 8, 16; PR75 frozen order |
| Submissions | At most two distinct parent jobs, sequential |
| Optimization calls | At most five per parent, ten total |
| Solver time | 3,600 seconds per call; at most 36,000 total |
| Parent allocation | One node, one task, 16 requested physical cores |
| Slurm resources | `batch`, 64 GiB, 330 minutes, `nomultithread` |
| GPU / exclusive / requeue / automatic retry | None / false / false / false |

Preparation writes both `approval.json` and `operator_approval.json` with
approval gates false. The operator approval must bind the independently
approved matrix approval's hash, the exact source head and plan, and review
of all four evidence CI arms at that head. The workflow has no command that
manufactures approval. No extra instance, seed, extension or replay is allowed.

The original in-memory objective-sense qualification, defaults, Gurobi
13.0.1, no-warm-start policy, censoring and sampled-crossing interpretation
remain those of PR75. Slurm accounting may show 32 logical processors;
this is not proof of 16 distinct physical cores. The unchanged executor
checks actual affinity before solver access.

## Submission state and failure policy

1. Validate the frozen bytes, explicit approvals and global budget binding.
2. Consume a durable, exclusive parent submission claim before `sbatch`.
3. Submit once in hold; persist and fsync the returned job ID before release.
4. Query the held job once and validate allowlisted resource fields.
5. Persist the release-start claim, then issue one release operation.
6. Bind the batch to its job ID and delegate to the unchanged isolated executor.

A timeout, malformed ID, resource mismatch or interruption consumes that
opportunity and stops the remaining matrix. The held or uncertain job and
private evidence are retained for manual reconciliation. The workflow never
resubmits, rereleases, requeues, cancels or clears a claim automatically.
It does not claim exactly-once delivery from Slurm: it guarantees at-most-one
submission command per bound parent and records uncertainty explicitly.

Slurm's [hold/release interface](https://slurm.schedmd.com/sbatch.html) is
used without `--wait`. The field parser follows the
[Slurm 22.05.2 job formatter](https://github.com/SchedMD/slurm/blob/slurm-22-05-2-1/src/api/job_info.c):
`TRES`, `MinMemoryNode`, `OverSubscribe`, `Requeue` and `Restarts` are checked,
not guessed from a later Slurm interface. The parser deliberately accepts
only the frozen profile (`OverSubscribe=OK`, no GRES or additional TRES);
missing or differently represented critical fields fail closed while held.
This is not yet an installed-site qualification of this new wrapper.
Only allowlisted fields are retained; raw site configuration is not exported.

## Memory limits remain mandatory

The PR75 kernel/cgroup RAM bound must be strictly greater than 56 GiB and
no greater than 64 GiB before models or the license are accessed. Its
48-decimal-GB solver soft limit, sampled 56-GiB process-group interruption,
swap checks, child deadlines and prefix-stop policy remain unchanged.
Synthetic fault tests do not establish a real allocation's cgroup limit or
reconcile historical solver, process and Slurm RSS metrics. A failure of
that installed gate stops execution; no weakening or automatic retry follows.

## One-shot status and terminal collection

`status` performs one `sacct` query and returns immediately. `collect` also
queries once unless a sealed return already exists, in which case it performs
read-only validation without another scheduler query. A running job creates
no export or collection claim. A terminal root with nonterminal steps waits
for a later, separately invoked collection; there is no internal polling.

A positive return requires root, batch and solver step completion with `0:0`,
five validated attempts, the held profile, release acknowledgment, batch-start
binding and no executor or workflow STOP. Collection rechecks the private
log-to-result binding before exporting the nested public matrix archive.
Every returned member and nested contract is hash-checked. Private logs are
not included. A failed or missing receipt produces a sanitized negative
diagnostic: unknown optimization counts remain null, never an assumed zero.
Collection interruptions preserve the claim and require manual reconciliation;
they do not overwrite partial exports automatically.

The only possible public members are `operator_plan.json`,
`operator_approval.json`, `submission.json`, `accounting.json`,
`SHA256SUMS.txt` and, for valid parent evidence only, `matrix.tar.gz`.
Unexpected files, links, altered hashes or semantic promotion are rejected.
All returns retain `scientific_reporting_eligible=false`.

## Easy-before-medium gate

Medium is not a Slurm dependency that starts when easy exits. It requires an
independently reviewed, hash-bound `easy.review.json` referring to the sealed
easy return and its exact operator plan, approval and job ID. The operator
then checks easy's terminal accounting again once before submitting medium.
Medium revalidates that same review in its batch entry point. A clean Slurm
exit alone, `ready_for_independent_review=true` alone, or a modified review
cannot open this gate. One job cannot masquerade as both parents.

## Operator interface and handoff

The following commands describe the interface, not authorization to execute
the matrix. The PR handoff supplies an exact-head, hash-checked fresh RAID
checkout and the complete no-solver preparation block. Preserve all earlier
PR75 flows and evidence. Never prepare twice into an existing directory.

```bash
# Safe now, in the separately staged reviewed source: no scheduler query.
python3 -B -m unittest discover -s tests/evidence -p test_paired_matrix_workflow.py -q
python3 -B scripts/evidence/paired_matrix_workflow.py prepare --directory "$FLOW"

# Only after separate exact budget approval and recorded approval hashes:
python3 -B scripts/evidence/paired_matrix_workflow.py submit \
  --directory "$FLOW" --parent easy --approval-sha "$OPERATOR_APPROVAL_SHA"

# Nonblocking; invoke once whenever desired, not in a waiting loop.
python3 -B scripts/evidence/paired_matrix_workflow.py status \
  --directory "$FLOW" --parent easy
python3 -B scripts/evidence/paired_matrix_workflow.py collect \
  --directory "$FLOW" --parent easy

# Read-only validation of the exact downloaded public directory and manifest.
python3 -B scripts/evidence/paired_matrix_workflow.py validate-return \
  --directory "$DOWNLOADED_RETURN" --expected-sha "$RETURN_SHA256"

# Only after independent easy review is written and its hash confirmed:
python3 -B scripts/evidence/paired_matrix_workflow.py submit \
  --directory "$FLOW" --parent medium --approval-sha "$OPERATOR_APPROVAL_SHA" \
  --easy-review-sha "$EASY_REVIEW_SHA"
```

On each release or collection failure, preserve the directory and return only
the sanitized receipt. Do not send raw logs, repeat preparation/submission,
clear locks or retry optimization. Actual license stays at the existing
`/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic`; new artifacts
stay physically under `/raid/vrcelestino/data/cfl-mvp2-evidence`.

## Remaining Sprint B gates

This delivery implements the operator layer; it does not complete Sprint B.
Next are installed no-solver wrapper validation, explicit bounded-matrix
budget, actual-allocation resource qualification, easy execution and
independent review, then medium execution and independent review. Only then
can paired target attainment, censoring and computational costs be analysed
under the frozen contract. There is no scientific promotion, GNN training
or broader performance claim from this engineering delivery.
