# NPAD runtime transition — 20 November 2026

This operational record and guarded installation proposal do not change the manuscript, historical evidence, learning partitions, model checkpoint or MVP3 experimental protocol. The author executes every HPC/SCP command. No merge, publication or scientific campaign is authorized by this record.

## Received compatibility evidence

The author completed the minimal DGX compatibility test in job 3917. Python 3.13.18 and gurobipy 14.0.0 loaded the qualified E0 instance, initialized the existing license and returned normally from one optimization. The result JSON reproduced SHA256 df4d14344cd7dea2689ce8357ade6d80fa42060c6b25d45b4ffb47ce758fd64b when reconstructed from the pasted output; full native files were not independently transferred.

The instance is CFL_easy_instance_0, input SHA256 c5c6703a158ced73c7d20ae6c969146c306bd6d71c56163724965d561eb255d1. The run forced MINIMIZE, had no external Start and retained native defaults except TimeLimit=300. Status 9 was TIME_LIMIT, with SolCount 10, Runtime 300.7371549606323s, primal 13.294302903797014, dual 4.557835239808002 and relative gap 0.657158763961499. This is a scoped **GO for native load/license/one optimization on DGX**, not a performance comparison or NPAD/GNN qualification.

The reservation was two CPUs per task and one task. Slurm reported four allocated logical CPUs; the initial process affinity contained four IDs. Gurobi reported 32 software threads with Threads=0. Those observations do not establish access to 32 physical cores or a strong-scaling result. Preserve the run; reconcile resource reservation and software parallelism in the prospective protocol rather than silently changing this test.

## Why the first NPAD installation stopped

The NPAD inventory found two existing Conda prefixes, both with 69 distributions and Python 3.13.15. The original environment had gurobipy 13.0.3; the Gurobi14 environment had14.0.0. Both contained the editable Agrologistic distribution, NumPy 2.5.2 and SciPy 1.18.1. Neither contained Torch/PyG. No additional environment was created.

The add-only installer stopped at its dependency check **before package resolution or PyTorch installation**. The reported conflicts were Agrologistic's installed requirement gurobipy>=13.0.2,<14 and Dash's missing pydantic>=2.10. The original stage, claim, snapshots, tool archive and failure log remain preserved. The author subsequently changed four local Agrologistic source requirements to gurobipy>=13.0.2,<15 and retained a timestamped backup. That source edit does not by itself refresh editable distribution metadata.

The author explicitly authorized this CFL task to reconcile the installed metadata of the existing Gurobi14 prefix, address pydantic and continue the guarded GNN installation. Changes to the **Agrologistic GitHub repository** belong exclusively to project01.01. This PR makes no changes there.

## Executed reconciliation and received package receipt

The author executed the private CLI successfully and returned its metadata receipt. The [template](reconcile-npad.template.sh) is its sanitized archival form; do not repeat this completed installation. Instantiate the placeholders for the existing user, parent-stage basename and source-backup basename; do not run the placeholder template directly. The exact private instance was checked against this template. No credentials, license contents, raw models, private inventories or path maps are committed.

The continuation performs these operations in order:

1. Check the original environment inventory and preserved failed parent, then create an exclusive new continuation claim. Never remove, overwrite or reuse the parent claim.
2. Compare the local source pyproject against the author's exact backed-up edit and verify the declared Gurobi14 range. Check the editable package's location and standard setuptools build requirements without installing new build dependencies.
3. If necessary, refresh only the editable Agrologistic distribution with --no-deps and --no-build-isolation. The script does not edit source pyproject or code. The backend may regenerate build metadata. The installed project version may be reconciled to the already declared source version; that exception is recorded. No extras are enabled.
4. Verify that the original environment inventory and all other existing package versions in the Gurobi14 prefix remain unchanged. Freeze the refreshed inventory. Accept only the already diagnosed missing-pydantic condition as repairable before installation; any other dependency failure stops.
5. Resolve and hash-lock Torch 2.7.1+cu118, PyG 2.7.0, PyArrow 24.0.0, scikit-learn1.7.2, tqdm4.67.3 and pydantic. Retain an already installed compatible pydantic version; select 2.13.4 if absent. Reject any plan that changes another existing version. Reinstall pydantic at the selected same version only when the prior checker did not recognize it.
6. Install the reviewed additions, run the dependency check and verify exact before/after inventories. Write a metadata receipt with package and lock identities. No Torch/Gurobi import, CUDA/license initialization, forward, training, solve or Slurm submission occurs.

This permits a specific metadata repair and package installation, not a general upgrade. Conflicts or partial installation are preserved for diagnosis without automatic retry, rollback or claim removal. A package receipt is not proof of CUDA/GNN execution. The author returned the [sanitized installation receipt](installation-receipt.json) with exit 0: 37 distributions were added, yielding 106 while preserving the original prefix and all preexisting non-project versions. Its reconstructed private JSON matches SHA256 8dfbedf6e5d26d7d6c9a019cde6ffab051c8c06c008b9dcfbdd1598579c2cca0. The receipt confirms installed metadata accepts Gurobi14 and pydantic2.13.4 is present. There was no Torch/Gurobi import, CUDA/license initialization, training, solve or Slurm submission in this installation.

## Resource and interpretation boundaries

The live NPAD preflight confirmed 32 physical cores/64 logical CPUs on Intel partitions and 128/256 on amd-512. The user's association exposes QOS preempt, explicitly MaxTRESPU=cpu=1000, MaxJobsPU=10 and MaxSubmitPU=100. These are not guaranteed node allocations and remain subject to inherited and partition limits. The CPU partition QOS compute limits walltime to 2 days, and V100 QOS gpu-short to 6 h, despite larger MaxTime values in sinfo. MaxMemPerCPU is8000MiB on Intel/V100 and4000MiB on AMD.

The global configuration is PreemptType=preempt/qos, PreemptMode=CANCEL, PreemptExemptTime=00:00:00, select/cons_tres with CR_CPU_MEMORY and task/affinity,task/cgroup. Record scheduler preemption separately from scientific TimeLimit, memory censoring and numerical failure. No automatic resubmission or scientific retry is introduced. Larger memory and GPU inventories do not guarantee Benders feasibility or four-GPU admission.

Source/checkpoint/data identities must be qualified before a later GPU/GNN CLI. Do not mix DGX/Gurobi13 historical timings with NPAD/Gurobi14 timings as one paired experiment. No new Sprint plan, Benders implementation, full retraining or scientific parameter change accompanies this transition. PR99/101 remain draft and unaffected.

## Verification and handoff

Local Python 3.13 checks passed 25 synthetic cases: 9 locked-plan cases and 16 source/metadata/dependency cases. The runbook passed bash -n. The [reproducible checker](check_runbook.py) uses temporary fixtures only: it never executes the shell, contacts HPC or changes packages. It requires Python>=3.11 and packaging. CI checks implementation contracts, not target GPU/runtime or scientific validity.

Run python docs/research/npad-runtime-transition-20261120/check_runbook.py for the synthetic checks. The CI evidence matrix parses the shell and runs these fixtures on Python3.12. Its historical tensor job remains a separate implementation check, not Gurobi14/Python 3.13 qualification.

The installation receipt is now received; provide this PR link to project01.01 for its own repository reconciliation. The author confirms forecasting/all are legacy inactive extras. Their torch>=2.8 requirement is retained as history: Torch 2.7.1 does not qualify those extras, but this is not a blocker for the scoped CFL runtime test and author requested no automatic update.

The next prepared, not submitted operation is one V100 library-runtime job: one task, eight Slurm CPUs, 48G, a 15min reservation and a 300s process deadline, with no requeue. It imports the installed numerical/data libraries and Torch/PyG, checks NumPy-Torch interoperability and a tiny fixed CUDA scatter sum, then round-trips its own synthetic HeteroData. It loads no real instances or historical checkpoints and performs no neural forward, backward/optimizer step, training, Gurobi import, license initialization or solve. See the [submission](gpu-runtime-submit.template.sh) and [read-only terminal collection](gpu-runtime-collect.template.sh) templates. They bind the received installation receipt and exact environment inventory at submission and again inside the batch worker; a later environment change stops the check. No GPU execution is claimed.

Real-data/source/checkpoint bindings and a separately reviewed technical GNN pilot remain subsequent gates. Finalize the new-chat checkpoint after environment qualification.

Primary operational references: [Slurm QOS](https://slurm.schedmd.com/qos.html), [preemption](https://slurm.schedmd.com/preempt.html), [Gurobi Threads](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html#parameterthreads), and [uv package management](https://docs.astral.sh/uv/pip/packages/).
