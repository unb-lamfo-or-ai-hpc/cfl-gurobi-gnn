# Job 3479: resource scopes and the next Sprint B gate

PR73 was merged into `develop` as `fd44e850032aa0106b9b096a8998abe31182bf32`.
Its bounded installed-callback observation is supported; it did not authorize a
comparison, qualify memory safety, or complete Sprint B. PR74 combines the
offline resource review, byte-stable imported receipts and a read-only site
configuration collector. No new solver run, training or submission is involved.

## Reproducible inputs and output

The already returned PR72 package SHA256 is
`fc4b00066a53868e61f07540d8db2d1377ea2da65fc0f405ab592c444b45fc22`.
The PR73 sanitized audit SHA256 is
`0c26533eb90b27b4e1115500997682af3d95713edd6197bc0f8d0a4eeb432eee`.
`scripts/evidence/review_qualification_resources.py summarize` validates the
outer and nested member lists, hashes and original contracts before cross-binding
the audit to source, plan, approval, job, logs, callback counters and RSS fields.
It never extracts or reads a private log. The imported audit bytes are protected
from checkout newline conversion by `.gitattributes`; their hashes are not
replaced to accommodate Windows CRLF.

The derived [public review](../evidence/pr74/job3479/job3479_resource_review.json)
has SHA256 `9d89915872dfd0fa35e113cbf73683de02cbd7c0fbdc48ddce5bccc3ba1e1b10`.
The corresponding [manifest](../evidence/pr74/job3479/SHA256SUMS.txt) is archived
beside it. Reproduce it offline in a fresh directory whose parent already exists:

```bash
python -B scripts/evidence/review_qualification_resources.py summarize \
  --package /path/to/verified/qualification_package.tar.gz \
  --output /path/to/fresh-resource-review
```

## What the single qualification actually measured

| Observation | Value | Scope and interpretation |
| --- | ---: | --- |
| Slurm allocation elapsed time | 63 s | Entire allocation, not just optimization |
| Reported `AllocCPUS` | 32 | Logical scheduler accounting; not 32 solver threads |
| Logical allocation CPU-hours | 0.56 | `32 * 63 / 3600`; reserved accounting product, not executed CPU time |
| Allocation `TotalCPU` | 61.286 s | Reported user + system CPU; step rows are **not added again** |
| Reported consumed CPU-hours | 0.0170239 | `61.286 / 3600`; distinct from reserved CPU-hours |
| Solver runtime | 60.020082 s | Gurobi clock, including instrumented callback execution |
| Supervisor wall time | 61.876574 s | Fresh-child orchestration; different boundaries from Slurm |
| Child process CPU time | 60.808365 s | Current process clock, not allocation-wide accounting |
| Read/setup wall time | 1.628955 s | Child phase; not presolve-only time |
| Optimization wall time | 60.020601 s | Wall clock around `optimize(callback)` |
| Cleanup wall time | 0.012046 s | Disposal phase; excludes other lifecycle work |
| Callback accumulated wall time | 0.019565 s | Instrumented callback sections only |
| Callback accumulated CPU time | 0.014213 s | Instrumented current-process CPU sections |
| Worker `ru_maxrss` | 270,479,360 bytes | Process high-water mark as recorded by the worker |
| Slurm step `MaxRSS` | `200152K` | Scheduler step metric; not equated to worker high-water mark |

The callback wall fraction is approximately **0.03260%** of solver runtime;
its CPU fraction is approximately **0.02337%** of child process CPU time.
Neither fraction estimates the counterfactual slowdown caused by callbacks:
there is no matched uninstrumented control, and instrumentation excludes some
dispatch and clock costs. Nothing is subtracted from runtime. One easy-instance
60 s sample cannot establish overhead or memory behaviour for medium instances,
16 threads, or 3,600 s runs.

The three child phases do not partition the entire child lifecycle: terminal
inspection, hashing, log sealing and serialization have separate boundaries.
Displayed presolve/root times remain observations, not disjoint CPU costs.
Exact first crossings remain unqualified. All scientific-promotion flags stay
false; the sealed PR72 receipt is unchanged.

## Read-only current Slurm context

The `site` action runs exactly two bounded queries, sequentially:
`scontrol --version` and `scontrol show config`, with a 20 s timeout each.
It exports only a version and allowlisted values for `JobAcctGatherType`,
`JobAcctGatherFrequency`, `JobAcctGatherParams`, `TaskPlugin` and `ProctrackType`.
Unknown values become null/redacted field names; other configuration fields,
stdout/stderr and private paths are not exported. Query failures are sanitized
and never automatically retried. Fresh output is restricted to a direct child
of the canonical physical RAID `cfl-mvp2-evidence/pr74` directory.

This is a **current configuration observation**, not evidence of the settings
used by historical job 3479. Per-job accounting-frequency overrides and changes
since execution remain unknown. Even a successful query leaves
`historical_job3479_configuration_verified=false`, memory reconciliation false
and higher-budget safety unqualified. If access is denied, return the sanitized
receipt; do not send raw `scontrol` output or change permissions.

Slurm documents [MaxRSS and step accounting](https://slurm.schedmd.com/sacct.html),
[accounting plugins and sampling](https://slurm.schedmd.com/slurm.conf.html), and
the [cgroup v2 memory metrics](https://slurm.schedmd.com/cgroup_v2.html).
These sources explain why procfs high-water marks and scheduler/cgroup sampling
cannot be reconciled solely by converting units. Current Slurm documentation
must not be used to assume cgroup v2 behaviour for the reported older site
version: the cgroup implementation and historical job settings remain unknown.

## Returned configuration and independent review

The collector receipt was returned from
`pr74/site-context-20261005T222514Z-1604764` and observed at
`2026-10-05T22:25:14.353152+00:00`. The downloaded 960-byte JSON has SHA256
`1f0cdb91c6abe628335265fa1a22059530d845789b84c4fd6ff6a3c9876f699f`;
the original 102-byte manifest has SHA256
`f44f2f346663ecbab243f80eac8c2d6284f986c0d5b27aba0e60a3989c7b5a74`.
Both downloaded hashes and the canonical allowlisted JSON contract were checked
independently on Windows. The exact [JSON bytes](../evidence/pr74/job3479/current_slurm_resource_context.json)
and [manifest bytes](../evidence/pr74/job3479/current_slurm_resource_context.SHA256SUMS.txt)
are archived here; the manifest is renamed only to preserve the separate,
existing resource-review manifest. Its contents are unchanged.

The observed collector source is `0cc3195282bf33659660f5a9a2f2975500ba4bcd`.
The query succeeded and reported Slurm **22.05.2**, current
`JobAcctGatherType=jobacct_gather/cgroup`, task accounting frequency **30 s**,
an empty allowlisted `JobAcctGatherParams` list, and `proctrack/cgroup`.
`TaskPlugin=null` is retained as unavailable/redacted. This does **not** establish
that the plugin is absent, that affinity/cgroup binding is disabled, or why its
value was not retained: raw configuration was deliberately not exported. Do not
widen the parser, substitute a guessed default, or repeat the HPC query to make
that field look complete.

**Resource-safety decision:** accept this receipt as a successful, bounded
current-site observation only. Historical memory reconciliation and safety for
longer/larger runs remain **unqualified**. A 30 s current sampling setting and a
cgroup accounting plugin do not prove the cause of the job3479 RSS difference;
there is no retained historical configuration, per-job sampling override, cgroup
version or memory-enforcement policy here. No allocation or solver control was
changed. `comparison_submission_ready=false` and
`scientific_reporting_eligible=false` remain unchanged, with zero added
optimizations and submissions. This closes the narrow PR74 evidence-review
scope, not the higher-budget execution gate.

Ten PR74 offline tests now include the returned receipt's exact bytes, schema,
collector source, current configuration, missing `TaskPlugin` and all conservative
decision flags. Require the full four-arm CI at the closure head before making
the PR ready for review; merge still requires separate explicit authorization.

## Where Sprint B goes next

1. **PR74 narrow review completed:** the sanitized current configuration receipt
   and explicit non-qualification decision are recorded above. Longer-budget
   memory enforcement/stop handling still require a reviewed prospective safety
   policy; numerical equality between old RSS metrics is not a prerequisite and
   must not be manufactured. Missing fields remain unknown.
2. Finish the longer-budget comparison executor: the current isolated worker is
   still a short-qualification worker. Preserve fresh models/processes, serial
   attempts, one-shot submission/collection, callback/log binding, fail-closed
   resource checks, memory-stop handling and offline export validation. Tests
   must cover interruptions and no-retry behaviour before larger execution.
3. Present the exact reviewed plan and separate resource budget for the first
   paired matrix (same easy/medium parents, seed 42, Threads 1/2/4/8/16).
   The existing [comparison contract](cpu-comparison-contract.md) remains a
   proposal, not approval. No optimization is authorized by PR73/PR74 merges.
4. Execute only that authorized matrix, collect once after terminal status,
   review coverage/log parity/targets/censoring/costs, and produce paired speedup
   and efficiency with the stated limits. Do not select a winning thread count
   from the old 300 s screen as if it were replicated scientific evidence.

These are the remaining Sprint B delivery gates, not a promise of four separate
PRs. Combine implementation, tests, evidence and documentation wherever safe.
Replications, additional parents, training/DDP and warm-start evaluation remain
separate later stages. Follow-up CLI is pinned to the final public head and
script SHA in the PR conversation; no local-only handoff is authoritative.
