# PR80: one environment, tfm_env, with GPU support retained

## Decision and current status (2026-10-08)

The operator explicitly chose to update **the existing `tfm_env` in place**.
No clone, new Conda environment, or audit venv is to be created. The previous
[CPU-only handoff](pr80-cpu-runtime-continuation.md) and its PR comment
[6065710341](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/80#issuecomment-6065710341)
are **withdrawn**. Do not run their prepare/submit commands. Their code is still
in the branch as development history and needs adaptation before reuse.
This documentation change does not claim that any HPC environment was modified.

## Why update PyTorch?

The installed version reported by the operator is `2.1.2+cu121`. The job-3500
auditor deliberately rejected it **before loading the first graph**, because its
restricted loader required at least 2.6. This was an auditor policy check, not
evidence that the research tensors are corrupt or that the GNN requires a
different architecture. One parent was blocked and 53 were unattempted.

The subsequent implementation raised the minimum to 2.10: PyTorch's official
[GHSA-63cw-57p8-fm3p advisory](https://github.com/pytorch/pytorch/security/advisories/GHSA-63cw-57p8-fm3p)
reports a restricted-unpickler vulnerability through 2.9.1, patched in 2.10.0.
Thus 2.6 alone does not meet the documented current loader policy. The proposed
upgrade addresses loading safety and compatibility of the existing serialized
graphs, not a need to retrain, change GNN layers, or change Gurobi. Historical
scientific results are not invalidated merely by this policy change.

Do not bypass the version gate or introduce `weights_only=False`. A newer
version is not a universal safety guarantee: retain restricted loading,
artifact provenance checks and bounded execution.

## Why not install the earlier CPU wheel in tfm_env?

`tfm_env` is also the environment for the mandatory GPU experiments. Replacing
its CUDA build with `torch+cpu` would remove that capability. Choose an official
CUDA-enabled build only after checking the actual GPU model, NVIDIA driver and
installed compiled extensions. A PyTorch wheel supplies CUDA runtime components;
this procedure must not silently change the host driver or system CUDA toolkit.
Refer to [official PyTorch builds](https://pytorch.org/get-started/previous-versions/)
and [NVIDIA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).

## Next CLI: read-only compatibility inventory

Run on **dgx-dasci**, not Windows PowerShell. No package installation, solver,
training, scheduler submission or dataset load occurs in this block.

```bash
conda activate tfm_env
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
conda list '^(python|pytorch.*|torch.*|pyg.*|numpy|scipy|gurobipy|cuda.*|cudnn|nvidia.*)$'
```

Return the output. Package build fields distinguish PyPI-installed packages
from Conda packages and reveal ABI-coupled extensions. If GPU information is
unavailable outside an allocation, report that failure; do not infer the driver
or submit an unplanned job. Existing metadata alone is insufficient to choose
a CUDA build. This is the only information currently requested from the operator.

## In-place implementation sequence after that inventory

1. Confirm no running work relies on `tfm_env`. Record its package/build
   inventory and dependency specifications under the PR80 evidence directory.
   Prepare a restoration procedure for changed packages; an exported inventory
   alone is not a guaranteed rollback. No second runtime is created.
2. Resolve and review a pinned CUDA-enabled PyTorch build and any necessary
   compatible PyG/torchvision/torchaudio extensions. Keep unrelated scientific
   dependencies unchanged wherever compatible. Stop on an unexplained resolver
   conflict; do not apply a blanket environment upgrade or change host drivers.
3. Adapt the operator and runtime checks to the **active tfm_env interpreter**,
   removing the operational dependence on `STAGE/venv` and CPU-build assertions.
   Test the revised flow before publishing its installation/submission handoff.
4. Apply the reviewed update once in tfm_env, then check dependency consistency,
   real imports, NumPy interoperability and restricted synthetic graph roundtrip.
   Validate GPU functionality in an appropriate allocated context before claiming
   GPU readiness; merely installing a CUDA build is not such proof.
5. Only after runtime preflight passes, resume the bounded numerical audit with
   fresh evidence. Preserve job 3500 and all original graphs/labels/checkpoints.
   Audit remains CPU-executed even though its environment supports CUDA. No
   automatic retry, training or Gurobi optimization is introduced.
6. Review all parent results before admitting E0. Record environment versions in
   subsequent experiments and validate existing checkpoint inference; do not
   assume bitwise or timing equivalence between old and updated runtimes.

PR80 remains draft. No new audit, E0, training, solver run or merge is reported
as performed by this planning change. Installation commands await the required
hardware/driver and package-build facts, not another approval of this decision.
