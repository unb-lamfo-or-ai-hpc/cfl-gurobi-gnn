# MVP 2.0 Sprint A: traceable evidence and computational baseline

## Objective

Retain the MVP 1.0 question: can learned graph-based partial starts improve
fixed-budget optimization? Add explicit CPU, GPU, memory and preparation-cost
accounting without assuming that larger hardware allocations improve results.
This increment versions sanitized freeze summaries and a reproducible converter,
and specifies a serial/DDP comparison. It schedules no training or solver jobs.

## Serial and DDP comparison

Use serial on one GPU and DDP on one, two, four and eight GPUs. One-GPU DDP
separates implementation overhead from multi-GPU scaling. Establish update and
membership equivalence on one GPU, qualify two, then four and eight. The planned
contract is `configs/experiments/mvp2_gpu_comparison_v1.json`; unresolved runtime
settings must be fixed before execution, not chosen after viewing test results.

For hardware scaling, preserve global batch, initialization, optimizer updates,
learning-rate schedule, sampling mass and validation-only selection. Synchronized
gradients do not alone guarantee equal objectives when ranks have unequal graph
sizes or loss denominators. Account for padded/duplicated samples, normalization,
validation aggregation and checkpoint resume. Measure communication, input
loading, utilization, memory, CPU-seconds and GPU-hours alongside elapsed time.

Evaluate predictive quality and downstream warm-start effects separately.
Retuning the batch or optimizer is a second learning study, not pure hardware
scaling. More GPUs do not guarantee better quality; differences require repeated
seed evidence and a parent-disjoint design.

Use the [PyTorch DDP design](https://docs.pytorch.org/docs/stable/notes/ddp.html)
and [DistributedSampler documentation](https://docs.pytorch.org/docs/stable/data.html#torch.utils.data.distributed.DistributedSampler)
as conceptual references; pin and qualify the installed HPC PyTorch/CUDA/NCCL
versions rather than upgrading implicitly.

## Next gates

Reconcile parent/run/solver identities and distinguish footer rows, events,
duplicates, feasible incumbents and <=10%-gap labels. Recover effective solver
parameters and resource costs, retaining unavailable historical measurements.
Build solution-independent statistics for all 90 parents before CPU/GPU pilots.
Compare easy-only and mixed models before controlled training-parent augmentation
and bounded paired medium/hard experiments. Traceability is not speedup,
significance or augmentation benefit. The manuscript and its section numbering
remain deferred to the future editorial sprint, outside this PR.
