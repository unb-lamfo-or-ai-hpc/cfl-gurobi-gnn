# Article plan

## Proposed narrative

1. Introduce CFL, the computational bottleneck, and the gap between generic
   MILP solving and learned graph guidance.
2. Define the parent-level dataset, graph construction, labels, split, and
   leakage controls before presenting results.
3. Describe the GNN architecture and training protocol, including the two
   hidden layers of 32 units only as a documented hyperparameter, not as an
   unexplained result.
4. Define the three solver arms and distinguish root-relaxation preparation
   from GNN inference and from Gurobi optimization.
5. Report quality, time, preparation cost, CPU thread scaling, GPU allocation,
   memory, and exclusions with tables and figures generated from public
   manifests.
6. Discuss limitations, reproducibility, HPC implementation, and the exact
   claims supported by qualified pairs.

## Required outputs

- cohort/partition table with F/M identifiers and train/validation/test counts;
- descriptive sample table: parents, artifacts, bytes, labels, instances,
  attempts, qualified results, and exclusions;
- three-arm paired solver table by parent and thread cap;
- CPU scaling figure for 1/2/4/8/16 threads;
- GPU allocation/throughput figure when the corresponding runs are qualified;
- preparation-versus-solver-cost figure;
- gap, incumbent quality, runtime, and memory summaries;
- a manifest linking every public row and figure to source commit and receipt.

## Submission discipline

The manuscript must not call an observation a result when its receipt is
unqualified. Failed or unavailable historical runs are described as limitations.
The article should state the installed environment (including PyTorch and
CUDA versions) exactly as used; package upgrades are not required for the MVP.
The final release should be synchronized to protected `main` only after the
authors review the complete evidence and approve that release PR.
