# PR75 — paired matrix executor and prospective memory-stop policy

## State and provenance

PR74 was merged into `develop` at
`ba5bf12a5bffe8b5465926494542655a6ee74220`, following explicit user approval of
head `f8f895d10d495bc9335e8dc351f10d6507674828` and four passing evidence CI arms.
This delivery implements the longer-budget executor; it does **not** execute
the comparison or close Sprint B. The installed synthetic fault receipt is
still required before PR75 closure. No new licensed optimization, scheduler
submission, training or scientific promotion is authorized by this PR.

The PR69 compiler, PR70 preflight, PR71 single-attempt worker and PR72 workflow
are byte-unchanged. The new execution protocol is
`paired_matrix_isolated_executor_v1`; old requests/receipts remain valid under
their original protocols. Reviewed PR73 callback audit and PR74 current-site
receipt are bound by their original SHA256 values, not silently requalified.

## Exact experimental scope

- Same original train parents: `CFL_easy_instance_17` and `CFL_medium_instance_1`.
- Seed 42 only; Threads 1, 2, 4, 8, 16 in the frozen within-parent SHA256 order.
- Two parent blocks, easy before medium; five serial attempts per block.
  Medium cannot start until the independently validated easy block is complete
  and uses a different Slurm job ID. No parallel parent blocks or attempts.
- Fresh process, model and environment for every attempt; one `optimize` call.
  Gurobi 13.0.1, ThreadLimit 16, original LP/role hashes, MINIMIZE in memory only,
  unchanged algorithm defaults, no warm start or GPU. Stored LPs stay unchanged.
- Up to 3600 s solver time per attempt. Easy MIPGap 0.01; medium MIPGap 0.10.
  Child deadline 3780 s plus bounded termination/reaping; parent deadline 19800 s
  (330 min), with a whole-child reserve checked before every launch.
- Proposed scheduler profile: shared node, batch, one task, 16 physical cores,
  `--hint=nomultithread`, 64 GiB, no GPU, exclusive allocation or requeue.
  Actual scheduler accounting is separate from configured thread limits.

Total prospective ceiling remains 10 optimization calls / 36000 solver seconds
and two parent blocks. The plan is initially unapproved. An exact source/plan
approval record must separately attest reviewed four-arm CI, the installed
no-solver fault probe and explicit resource/submission approval. There is no
CLI command that manufactures approval. Merge is not resource approval.

## Three memory layers, with explicit limitations

1. **Gurobi SoftMemLimit = 48 decimal GB** (`48 × 10^9` bytes). This is the
   existing solver-allocation soft limit; it can terminate gracefully with
   `MEM_LIMIT`. It is not a strict process-RSS or kernel limit. We do not change
   search defaults, resume optimization or reduce Threads after a memory stop.
2. **Sampled job-leaf cgroup interruption at 56 GiB**, every 0.25 s inside the
   batch supervisor. This observes current job-leaf charged memory, not Slurm
   MaxRSS or worker `ru_maxrss`. On threshold, observation loss, cgroup migration
   or kernel-limit change, terminate only the newly created child process group,
   wait up to 10 s, escalate to SIGKILL and reap. Retained group descendants also
   force a stop. Polling can miss short peaks; it is not a hard memory guarantee.
3. **Required prospective kernel RAM bound:** before model/license access, both
   supervisor and child must resolve an unambiguous mounted cgroup v1 memory or
   v2 job leaf belonging to the current Slurm job, with finite RAM limit strictly
   above 56 GiB and no greater than 64 GiB. v1 additionally requires hierarchical
   accounting. Namespace-relative roots, hybrid/ambiguous membership, unlimited
   leaves and unknown layouts fail closed. Only files are read; no cgroup/site
   configuration is changed. Swap enforcement is not qualified.

The stricter layout acceptance is a safety gate, not a claim that every valid
Slurm installation has this layout. Rejection requires reviewing the observed
allocation safely; it does not authorize bypassing the gate. PR74's current
accounting-plugin observation alone cannot qualify any of these kernel limits.
Historical RSS reconciliation is not required and must not be manufactured.

Definitions and implementation basis: [Gurobi parameter reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html),
[Gurobi memory guidance](https://support.gurobi.com/hc/en-us/articles/360013195772-How-do-I-avoid-an-out-of-memory-condition),
[Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html),
[Linux cgroup v1 memory](https://www.kernel.org/doc/Documentation/cgroup-v1/memory.txt),
and [Slurm cgroup configuration](https://slurm.schedmd.com/cgroup.conf.html).
Site configuration is not inferred from the latest documentation.

## Stop, replay and export policy

Only validated `gap_target` and `time_limit` stops permit the next attempt.
Memory limit, callback failure, worker failure, watchdog, invalid receipt/log,
deadline reserve exhaustion or missing memory observations stop all remaining
attempts. A durable global STOP prevents medium from continuing. Global
approval/directory binding and consumed parent/child start markers prohibit
replay in the same or another directory. No resume, automatic retry, replacement
instance, additional seed, solver extension or outcome-conditioned selection.

Python interruptions and SIGTERM are handled by terminating/reaping the owned
group and preserving a STOP. SIGKILL/node failure can prevent a final receipt;
claims and private partial outputs are retained and require reconciliation,
never a fabricated zero-optimization count or automatic resubmission.

Closed Gurobi and console logs are hash-bound to each result after disposal and
rechecked at export. Logs remain private on RAID. Public packages contain only
the plan, approval, parent receipt, per-attempt requests/receipts and checksum
manifest. The independent validator reads bounded archives in memory, refuses
links, traversal, duplicates, unexpected members, sparse/PAX entries, hidden
trailing data, malformed JSON and inconsistent terminal/callback observations.
No raw logs, vectors, license metadata or system paths are exported.

Memory-stopped or failed attempts are not silently dropped or converted to
successful pairs. Solver runtime, sampled peak cgroup usage and worker peak RSS
remain separate scopes. First observed target times are sampled observations,
not exact continuous crossings; missing/late targets remain censored. A completed
executor block still has `scientific_reporting_eligible=false` pending the
separate scientific/accounting review.

## Interfaces and immediate no-solver handoff

The executor has `prepare`, `run-parent`, `export-parent` and `validate-package`.
It deliberately has **no scheduler submission interface**. `run-parent` is a
batch-only approval-bound entry point, not permission to use it now. Parent
claims bound execution, not arbitrary external `sbatch` commands; the next
operator wrapper must independently enforce the two-submission/no-requeue
budget, held-job ID persistence, exact batch profile and one-shot accounting.
Do not reuse the PR72 single-attempt submission wrapper for this matrix.

Immediate permitted step on dgx-dasci: use the reviewed pinned source, run
`paired_matrix_no_solver_probe.py --output <fresh-RAID-directory>`, then
`paired_matrix_executor.py prepare --directory <fresh-flow>`. The probe uses
synthetic Gurobi APIs, small real POSIX child processes and injected counters;
it reads no LP/license and makes no scheduler query/submission. It does not
allocate 56 GiB or certify kernel limits in a future allocation. All probe
tests must pass with **zero skips**. Preserve any failure receipt; do not rerun
to replace it. Return only `no_solver_fault_probe.json`, its manifest, printed
SHA and the prepared plan SHA. Never send mock/private log text.

After returned-receipt review, archive exact bytes, run final CI and mark PR75
ready before requesting merge. Then finish the nonblocking operator wrapper and
present the exact prospective budget for separate approval. Under that approved
workflow, launch easy once; query status once when desired; collect after
terminal state, review the guard/result/accounting package, and only then allow
medium once. No interactive waiting loop and no dependency that automatically
launches medium merely because Slurm reports COMPLETED.

## What remains to close Sprint B

The installed callback observation and historical/current resource-scope audit
are complete (PR73/74). This PR delivers isolated longer-budget execution,
memory-stop rules and offline fault/export validation. Remaining gates are the
installed no-solver fault check, nonblocking bounded operator wrapper, exact
separate budget, actual allocation memory gate, authorized same-pair matrix,
independent accounting/log review, and paired target/censoring/cost analysis.
Two parents and one seed remain a development comparison, not population-wide
scaling evidence. No GNN training is started by these steps.
