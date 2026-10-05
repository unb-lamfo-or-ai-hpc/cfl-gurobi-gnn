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
