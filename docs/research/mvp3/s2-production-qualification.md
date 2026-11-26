# S2 production environment and resource qualification preparation

Status, 26 November 2026: prepared for author review and staged CLI execution. No production environment has been qualified by this preparation, no job has been submitted, and no scientific call is released. PR104 and PR105 were approved and integrated into `develop`; PR105 merge is `d50a71b1254afa66f2d60869adc0d8472a95816a`. The local five-cell S1-B qualification at `dab3b99ef8172d320223d05f74155eeeac063768` remains historical evidence with its original scope. Existing S1-A/S1-B files, receipts, sealed contracts and scientific protocol are preserved.

The isolated package `cfl_gnn.mvp3.production`, entry `scripts/mvp3/qualify_production.py`, preparation wrapper `scripts/mvp3/prepare_production.ps1` and policy `configs/mvp3/production/v1.json` prepare separate, explicit stages. Importing them does not load gurobipy, create a native environment or contact Slurm. No implementation calls SSH, SCP, sbatch or scancel. Submission commands are rendered as proposals for the author.

## License and environment routes

On Windows the preparation wrapper sets `GRB_LICENSE_FILE=C:\gurobi1400\gurobi.lic` in the Python child using `ProcessStartInfo.Environment`. It does not change the parent's environment or PowerShell profile. Preparation checks existence only; it never opens, copies or hashes license contents and never starts Gurobi.

The previously recorded NPAD routes are `/home/vrrcelestino/venv313_g14/bin/python` and `/home/vrrcelestino/cfl-gurobi-gnn/secrets/gurobi.lic`. The Linux batch child sets `GRB_LICENSE_FILE` to that existing own-project Linux path. The Windows license is not transferred. The original `/home/vrrcelestino/venv313` and installed home checkout are left intact. Their recorded state is context, not fresh qualification. No package installation or environment mutation is included.

The portable source bundle is built from Git blobs at an exact clean commit with a receipt for nine successful CI jobs. It includes only the MVP3 source, entries and versioned configuration; no data, private returns, license or Git directory. Archive and external manifest SHA256 values bind the transferred bytes. Runtime rechecks the exact file set, sizes and hashes. Use a new private ASCII scratch directory without spaces, outside the installed checkout. Outputs must be outside the extracted bundle; Python bytecode generation is disabled. Preserve the original archive, manifest, CI receipt and every stage output.

## Proposed technical budget, separate from 177 scientific calls

| Profile | Prospective family | Allocation | Maximum native work |
| --- | --- | --- | --- |
| intel-256 | easy/medium | One exclusive Intel node, 2 sockets x 16 physical cores x SMT2, 1 task, 64 logical CPUs, 192 GiB, zero GPUs | One synthetic 20-binary root call, 10 native seconds |
| intel-512 | hard | Same CPU topology, 384 GiB, zero GPUs | One synthetic 20-binary root call, 10 native seconds |

There are exactly two prospective slots, at most two jobs and two native sessions within this plan, one call per slot, a 60-second child wall guard and a five-minute Slurm limit per job. The observed raw log guard is 16 MiB; it is not an OS disk quota. All attempts use exclusive new output directories, durable intent before optimize, sealed receipts, no requeue, no retry and no resume that overwrites an attempt. Failed admission can consume zero calls, but still consumes that attempt's output namespace.

The author must confirm that no other Gurobi sessions or unrelated jobs are active before separately releasing submission. Own-job snapshots are checked at discovery and admission; they cannot prove the global absence of other sessions or prevent future activity outside this plan. This limitation is retained in receipts.

The synthetic probe preserves `Threads=0`, `ConcurrentMIP=1`, `Seed=42` and the approved root parameters, changing only the technical TimeLimit to 10 seconds. No primary input path, training or inference is accepted. Native defaults, including typed infinities, and every noncredential effective parameter are retained. The original fixture is independently identified and its captured root vector is replayed against original rows and bounds.

## Author stage 1: read-only discovery

The review handoff supplies a concrete source commit, portable archive, SHA256 values and a single discovery command. Manually transfer the archive using the established author workflow. Verify its supplied SHA256 before extracting into an exclusive new directory. Do not clone over or update the installed home project. The concrete command uses these arguments:

```bash
GRB_LICENSE_FILE=/home/vrrcelestino/cfl-gurobi-gnn/secrets/gurobi.lic \
  /home/vrrcelestino/venv313_g14/bin/python -B \
  /ABSOLUTE_ASCII_BUNDLE/scripts/mvp3/qualify_production.py \
  --bundle /ABSOLUTE_ASCII_BUNDLE --manifest-sha256 MANIFEST_SHA256 \
  discover --output /NEW_ASCII_PRIVATE_OUTPUT \
  --license-file /home/vrrcelestino/cfl-gurobi-gnn/secrets/gurobi.lic \
  --installed-repo /home/vrrcelestino/cfl-gurobi-gnn \
  --data-root /home/Projeto_LAMFO_LAPPS/data/CFL
```

This stage uses bounded, read-only scontrol, squeue, sacctmgr and installed-Git HEAD reads, plus Python distribution metadata and license-path existence. It creates no Env, makes no optimize call and submits no job. The private `discovery.json` records current Slurm version, selected resource/configuration fields, own account/QOS associations, own jobs, target package metadata, installed source and candidate nodes. It strips unselected scheduler configuration fields; license contents and credential parameters are excluded. A command failure records its missing reason and blocks proposal generation. Do not retry automatically or substitute guessed historical values.

Production data inventory checks only names and stored sizes against the 66-parent catalogue; it never opens, hashes or decompresses inputs. Available output filesystem bytes/inodes are recorded, with quotas explicitly unverified. Neither check establishes scientific input readiness.

Return `discovery.json` for review. Historical compute/preempt defaults and node names are not silently selected. Missing deployment dependencies remain an explicit environment preparation gap even if a later tiny native probe succeeds. Inventory alone does not qualify native license initialization, compute-node resources or scientific S2 readiness.

## Author stage 2: render and review allocation proposals

After reviewing the fresh discovery, use `plan` with its path, a new output directory, observed partition/account/QOS, one observed node per profile, the pinned Python/license paths and an explicit prospective author approval reference. The parser's `--help` lists every mandatory argument. The reference is external author context, not a machine-generated signature or permission inferred from this document.

`plan` verifies exact source, complete discovery, closed own-job snapshot, Gurobi 14.0.0 metadata, license path and observed account/QOS/node membership. It writes immutable `plan.json`, its SHA256, two `.sbs` files and `proposal.json`. The latter includes exact `sbatch --test-only` and prospective submission strings, but executes neither. `--test-only` itself is an author scheduler interaction and requires the corresponding CLI decision. No guessed account, QOS or node appears in the generated commands.

For the recorded Slurm 22.05.11 interface, the job output represents JOB_SHARED_NONE as OverSubscribe=NO. Admission checks that value together with the complete node CPU allocation; the partition configuration word EXCLUSIVE must not be expected as the only job-output spelling. The old formatter also emits TRES instead of AllocTRES and can fall back to request text. Legacy TRES is admitted only for the RUNNING job with independent actual per-node Nodes/CPU_IDs/Mem corroboration; a request string alone cannot qualify allocation. Newer AllocTRES remains supported. See the [pinned job formatter](https://github.com/SchedMD/slurm/blob/slurm-22-05-11-1/src/api/job_info.c) and [pinned sharing formatter](https://github.com/SchedMD/slurm/blob/slurm-22-05-11-1/src/common/slurm_protocol_defs.c). Fresh discovery still establishes the actual target version.

Review all bytes and budgets before releasing either submission. The reviewed bundle path and manifest are bound into the plan; worker admission rejects another bundle, source, policy, interpreter, node, partition, account or QOS. Preserve proposal scripts and command output. If test-only or submission fails, keep that evidence and request a new concrete decision before another attempt.

## Author stage 3: separately released compute probes

Submit only the two reviewed scripts, after a specific author CLI release. Neither preparing the plan nor a source merge grants that release. The entry uses srun with one task, 64 CPUs, SMT2 and CPU binding. Admission precedes native initialization and records:

- Actual RUNNING job identity, own UID, one reviewed Intel node, exclusive allocation, 64 logical CPUs and the exact CPU/memory AllocTRES reservation, no GPU, five-minute limit and zero restarts.
- Effective process affinity, per-CPU sysfs package/core/sibling topology: 32 physical cores, two packages, 16 cores each, both SMT siblings available.
- PID membership in the exact job memory cgroup, v1 or v2 mount mapping, complete readable ancestor limit chain, requested enforced memory limit and kernel job peak counter. For v1, the kernel's hierarchical_memory_limit must agree with the computed chain; disabled hierarchy cannot imply an enforced ancestor cap. A hidden ancestor hierarchy or unavailable peak is ineligible, with no relaxation to scheduler samples.
- Native Gurobi 14.0.0, fresh original model, original identity before/after optimize, parameter/default snapshot, full root vector, root audit and native automatic-thread header. The expected header is 32 physical cores, 64 logical processors, up to 32 threads.

`Threads=0` has a documented automatic soft ceiling of 32. Allocation, native header and observed activity are separate facts. Task CPU ticks and actual-thread messages are retained with sampling limitations; a tiny model need not use every available thread. The kernel peak is the last live observation before worker exit, not a post-teardown counter. Scheduler MaxRSS is collected separately, including step rows, and must not be relabelled as kernel peak memory.

## Author stage 4: closed-job reconciliation

After both jobs are terminal, invoke `collect` with the exact plan path/SHA256 and a new output directory. Collection verifies source and plan bindings, admission/log/attempt seals, one durable intent and one return per slot, exact tiny-model identity, native parameter profile, independent full-vector replay and actual parent `sacct` COMPLETED / 0:0 accounting at the reviewed node with the required resources. Missing accounting, failed jobs, altered evidence and partial returns stay ineligible; there is no repair, automatic retry or invented result.

Even a successful review sets `scientific_S2_released=false`, `real_CFL_memory_or_performance_qualified=false` and `real_CFL_license_size_capacity_qualified=false`. These probes establish narrow technical compatibility and enforcement of the proposed resource envelopes. A 20-binary model tests license initialization/use but cannot establish license capacity for the much larger CFL models. The probes do not saturate RAM, demonstrate CFL runtime/scalability, verify production input contents, qualify a learned predictor or release the primary 177 calls. Original compressed data and the accepted decoded-equivalence provenance remain untouched; there is no repeated decompression/hash gate. Actual input and license-size admission remain explicit follow-on gates before scientific collection.

The follow-on S2 scientific collection needs its own concrete input/clock/admission plan and author release. Keep failures, raw private logs, scheduler returns and all earlier evidence intact. Main, the installed HPC checkout and original environment remain unchanged throughout this preparation.

## Offline validation and references

The MVP3 test suite uses API doubles and synthetic cgroup/Slurm/Git fixtures. It covers v1/v2 membership and incomplete limits, topology/affinity/resource rejection, source/plan/receipt mutation, exact bounded proposals, native admission before Env, one-call accounting, independent root replay, missing/altered scheduler evidence and continued scientific nonrelease. CI runs on Windows/Linux with Python 3.10/3.13 alongside the historical evidence suite. No native or scheduler execution is part of these checks.

Primary interface references: [Gurobi parameters](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html), [Slurm sbatch](https://slurm.schedmd.com/sbatch.html), [CPU management](https://slurm.schedmd.com/cpu_management.html), [sacct](https://slurm.schedmd.com/sacct.html), [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) and [legacy v1 memory documentation](https://docs.kernel.org/admin-guide/cgroup-v1/memory.html). The legacy v1 text flags its age; qualification uses the target's observed interface and does not infer features from a documentation version.
