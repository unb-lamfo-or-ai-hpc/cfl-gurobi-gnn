# DaSCI computational platform: inventory received 2026-10-08

## Scope and provenance

This record transcribes operator-supplied read-only CLI output from `dgx-dasci`
received during PR80 on 2026-10-08. The exact observation time was not supplied;
the date is the receipt/documentation date. The agent did not execute commands
on HPC. This is not a hash-attested historical environment manifest for previous
jobs, nor evidence of eight GPUs being used simultaneously by an experiment.
No package, driver, dataset, checkpoint or license is changed by this record.

The preceding metadata report identified Python 3.10.20, Linux x86_64,
glibc 2.35, torch-geometric 2.7.0, NumPy 1.26.4, SciPy 1.15.3 and gurobipy
13.0.1. The environment is the existing `tfm_env`, with those scientific
packages reported as pip-managed. These are installed-version observations,
not proof of import, CUDA kernel or checkpoint compatibility.

## Reported host and driver output

```text
dgx-dasci
/usr/bin/nvidia-smi
NVIDIA-SMI version  : 550.90.07
NVML version        : 550.90
DRIVER version      : 550.90.07
CUDA Version        : 12.4
dgx-dasci|batch*|mix|gpu:8
SLURM_JOB_ID=none
NVRM version: NVIDIA UNIX x86_64 Kernel Module  550.90.07  Fri May 31 09:35:42 UTC 2024
Model:           Tesla V100-SXM2-32GB
Model:           Tesla V100-SXM2-32GB
Model:           Tesla V100-SXM2-32GB
Model:           Tesla V100-SXM2-32GB
Model:           Tesla V100-SXM2-32GB
Model:           Tesla V100-SXM2-32GB
Model:           Tesla V100-SXM2-32GB
Model:           Tesla V100-SXM2-32GB
No broken requirements found.
```

The Slurm row was obtained using `%N|%P|%t|%G`: node, partition, state and
configured generic resources. `batch*` identifies the default partition;
`mix` is a transient node allocation state, not a hardware property. `gpu:8`
does not mean eight GPUs were free or allocated to this shell. The 32 GB in the
device model denotes nominal memory per GPU, not a single pooled allocation.

## CPU and memory: separately dated observations

The earlier operator site receipt dated 2026-10-06 reported one node, two CPU
sockets, 20 physical cores per socket and two hardware threads per core:
**40 physical cores and 80 logical CPUs**, not 80 physical cores. It also
reported `/proc/meminfo` `MemTotal=528214372 KiB` and Slurm
`RealMemory=490042 MiB`; these are different system/scheduler quantities, not
interchangeable measurements of a job's usable RAM. They were not remeasured
in the October 8 GPU inventory. CPU model, current memory capacity, GPU-link
topology and operating-system distribution are not established by the latest
output and must not be invented for the manuscript.

## Software layers that must not be conflated

| Layer | Reported value | Interpretation |
|---|---|---|
| NVIDIA kernel driver / NVIDIA-SMI | 550.90.07 | Host driver/tool version |
| NVML | 550.90 | Management-library version reported by NVIDIA-SMI |
| NVIDIA-SMI CUDA field | 12.4 | Driver-reported CUDA support, not an inventory of installed toolkits |
| PyTorch / torchaudio | 2.1.2+cu121 | Installed builds targeting CUDA 12.1 |
| torchvision | 0.16.2+cu121 | Installed CUDA 12.1 build |
| PyG | 2.7.0 | Installed graph-learning package |
| Python / NumPy / SciPy | 3.10.20 / 1.26.4 / 1.15.3 | Installed interpreter and numerical libraries |
| gurobipy | 13.0.1 | Installed Python binding; record solver runtime separately per job |
| Additional pip packages | cuda-toolkit 13.0.2, cuda-bindings 13.2.0, cuda-pathfinder 1.5.3, CUDA runtime 13.0.96, cuDNN-cu13 9.19.0.56 | Installed packages; not proof that PyTorch uses them or that this driver executes them |

For the semantics of NVIDIA-SMI fields, see the
[NVIDIA documentation](https://docs.nvidia.com/deploy/nvidia-smi/index.html).
Any upgrade must evaluate GPU architecture, driver compatibility and the actual
wheel build together; neither the CUDA field nor package coexistence alone
establishes compatibility or incompatibility.

`pip check` found no declared dependency violations. It does not execute CUDA
kernels or test graph loading. The previous device query returned `No devices
were found` outside a Slurm job, while the latest procfs/Slurm inventory shows
eight devices/configured GPUs. The cause of that visibility difference remains
unproven. No device restrictions were disabled and no GPU job was submitted for
this inventory. Use the [tfm_env plan](pr80-tfm-env-upgrade.md) for continuation.

## Use in the article

Suggested platform description (adapt to the final experiment manifests):

> The DaSCI computational platform consists of a single DGX node with eight
> NVIDIA Tesla V100-SXM2 GPUs, each with nominal 32 GB device memory. A separately
> recorded CPU inventory identified two sockets, 40 physical cores and 80 logical
> processors. The platform is managed through Slurm. A software inventory received
> on 8 October 2026 reported NVIDIA driver 550.90.07 and Python 3.10.20, with
> PyTorch 2.1.2+cu121 and PyTorch Geometric 2.7.0 in the existing tfm_env environment.
> This platform inventory is distinguished from the resources and software
> versions recorded for each experimental run.

Do not silently apply this paragraph to all MVP1/MVP2 jobs. For each reported
campaign, bind the Git commit, job IDs, environment capture and evidence hashes
to the corresponding tables. Report allocated CPUs and physical affinity,
Gurobi thread limit (1, 2, 4, 8 or 16), GPU count, per-device memory, precision,
seeds, optimizer, learning rate, global/per-device batch, epochs/updates and
sampling mass. Distinguish requested limits from measured wall time, CPU time,
host peak memory and device peak memory. Separate single-GPU and distributed
runs, including communication costs and equal-work definitions.

The eight-GPU inventory is capacity, not a DDP speedup result. Documentation of
hardware does not change numerical admission or scientific eligibility gates.
No new CLI, package installation, optimization, training or merge is required
to complete this documentation request.
