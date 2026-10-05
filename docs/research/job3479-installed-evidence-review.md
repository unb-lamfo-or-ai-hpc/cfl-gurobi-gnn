# Job 3479: bounded installed evidence review

The approved PR72 short attempt ran on the original `CFL_easy_instance_17`
training parent with seed 42 and solver `Threads=1`. It used one optimization
call with `TimeLimit=60`, `MIPGap=0.01` and `SoftMemLimit=48`. The Slurm allocation
completed `0:0` after 63 seconds. The returned public package SHA256 is
`fc4b00066a53868e61f07540d8db2d1377ea2da65fc0f405ab592c444b45fc22`;
its plan SHA256 is
`f4c4887c6fff64dfcd40d414fbdd34a76a45061eec8984c5ecdb5ee4a3b1ae84`.
The head executing that attempt was `d7ecfe5272c8b4b997a2bb078287b6fc99db02e1`
(PR72, merged into `develop` as `29bf83a07de35ab03a83365487e27cd992d0a819`).

The public receipt validates one optimizer call, 16 distinct physical cores
bound to 16 logical CPU IDs, and 111 retained samples with zero drops. The
callback recorded 1,098 MIP events and 62 MIPSOL events. The solver stopped at
the 60-second limit with terminal relative gap 0.0891839. The first *sampled*
observation below 10% was at solver time 58.0566 seconds. This is not an exact
first crossing. The 5% and 1% crossing observations are right censored by the
60-second budget. It is one plumbing sample, not a paired comparison result.

## Read-only private-log check

`scripts/evidence/review_installed_job3479.py` runs on `dgx-dasci` in `tfm_env`.
It checks the retained PR72 source head, the reviewed parser and workflow
bytes, the public return-package hash and nested contract, and the **current
private** worker receipt and closed log hashes. The private receipt bytes must
match the nested public archive exactly. The Gurobi log is read only up to
8 MiB; its hash and size must match the closed writer's recorded values. The
existing strict Gurobi 13.0.1 parser compares displayed controls, runtime,
nodes, objective, bound and gap to the API receipt. Unsupported, duplicate or
inconsistent lines remain unqualified. No tolerance is widened for this job.

The script writes one fresh `job3479_private_review.json` and SHA manifest in
an operator-chosen directory below the physical RAID
`/raid/vrcelestino/data/cfl-mvp2-evidence/pr73/`. It exports only allowlisted
numbers, hashes and status codes. The raw Gurobi/console logs, license,
source LP and local absolute paths stay outside the package. No optimization,
job submission, training or retry occurs. An error preserves existing files;
the operator diagnoses it without repeating the job.

```bash
conda activate tfm_env
PR73_OUTPUT=/raid/vrcelestino/data/cfl-mvp2-evidence/pr73/job3479-private-audit-YYYYMMDDThhmmssZ
python3 -B scripts/evidence/review_installed_job3479.py --output "$PR73_OUTPUT"
```

The exact source and hash-check command must be pinned to the eventual PR73
head before operator execution. Do not run a local draft or modify the retained
PR72 source. Once the sanitized receipt returns, compare it independently to
the public package and review any warnings before qualifying a dimension.

## Read-only audit result (2026-10-05)

The operator ran the pinned script from PR73 head
`d72fb81ffa9c393e1c3ede2e9f9743af12cbdea4` without another optimization
or Slurm submission. The allowlisted JSON receipt has SHA256
`0c26533eb90b27b4e1115500997682af3d95713edd6197bc0f8d0a4eeb432eee`.
Its manifest verified on the HPC and after download. A separate Windows check
compared the downloaded receipt with the PR72 public package, including the
source, plan, approval, job identity, callback counts, log hashes and memory
fields. These all agreed. The private raw log was not copied or reparsed on
Windows; the pinned, tested HPC script checked its closed-writer hash and
numeric display against the API receipt.

The result was `receipt_consistent_observations`, with no warnings. The
terminal display agreed under the existing parser tolerances, and the worker
recorded 1,098 MIP and 62 MIPSOL callbacks. Thus the bounded installed
callback **observation** is supported. The displayed presolve, root relaxation
and total solver times were 1.38, 0.29 and 60.02 seconds, respectively; these
are not disjoint CPU-phase costs. The 10% crossing remains a sampled
observation, not an exact first crossing. The receipt still sets
`scientific_reporting_eligible=false`, `root_tree_phase_costs_qualified=false`,
`true_first_crossings_qualified=false` and `memory_metrics_reconciled=false`.
The Slurm step `MaxRSS=200152K` and worker `ru_maxrss=270479360` bytes remain
different, unreconciled observation scopes. No private text entered the
public receipt.

## Interpretation and remaining gates

`terminal_numeric_parity_supported=true` means this log display agrees with
the sealed API receipt under the existing parser and tolerances. It does not
qualify disjoint root/tree CPU costs, exact gap-crossing times or primal
integrals. `installed_callback_observation_supported=true` additionally
requires positive MIP and MIPSOL event counters in the successful worker
receipt. The PR72 receipt's installed/scientific flags are immutable and remain
false; this follow-up does not silently edit them or promote a manuscript claim.

Slurm reported `AllocCPUS=32` and step `MaxRSS=200152K`; the worker reported
16 bound physical cores and `ru_maxrss=270479360` bytes. These are different
observation methods and scopes. Slurm's `MaxRSS` is the largest recorded task
value within a step, and its accounting depends on the site's gather plugin
and sampling configuration. The site configuration and memory time series are
not contained in the returned package, so `memory_metrics_reconciled=false`
and `scheduler_affinity_memory_qualified=false` remain the conservative states.
Do not add the allocation, batch, extern and step CPU or RSS rows together.

After reviewing the sanitized private-log receipt, decide whether the installed
callback observation can be reported as such and what additional evidence is
needed for memory accounting. The larger 3,600-second comparison, replications,
GNN training and any new licensed solve retain separate budget decisions.

Sources: [Slurm `sacct` field definitions](https://slurm.schedmd.com/sacct.html),
[Slurm accounting collection](https://slurm.schedmd.com/accounting.html), and
[Slurm sampling configuration](https://slurm.schedmd.com/slurm.conf.html).
