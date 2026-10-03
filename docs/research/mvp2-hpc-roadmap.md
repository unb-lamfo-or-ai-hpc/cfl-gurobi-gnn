# MVP 2.0: learning-assisted optimization and computational scaling

## Research objective and release boundary

The active first CPU experiment is now the
[PR66 lean shared-DaSCI screen](pr66-reconciliation-thread-pilot.md): seed 42,
one randomly drawn fitting parent per easy/medium class, five thread caps,
300 seconds and 10% target, one shared sixteen-core job. Earlier broader CPU
matrices below are expansion ideas, not approved initial execution budgets.

The next study will assess whether learned partial starts improve solution quality and time-to-target across CFL difficulty classes, and whether those gains remain useful after accounting for CPU, memory, GPU and preparation costs. Favorable effects are hypotheses, not acceptance requirements. An informative negative experiment is retained.

MVP 1.0 is an experimental development release, not a submission-ready scientific certification. Freeze its source, 54-parent model, prediction policy and original outcomes separately from MVP 2.0. Development occurs on feature branches targeting `develop`; public Pages deploys only `main`. No new standalone hard-instance label campaign is planned. Zenodo draft 23113003 remains unpublished; its numeric record identifier is not a verified DOI.

## Corrections to the current interpretation

- Label admission at gap <=10% is different from optimal termination. The 54-parent cohort contains 30 easy and 24 medium parents, but only 34 parents supplied gradient updates; ten supplied validation and ten predictive testing.
- PR59 tested medium 0, 4, 7, 9, 12 and 20. These are not the six medium parents excluded from label admission. Medium 12 has an admitted held-out label. Medium 9 and 20 were outside the labelled training cohort.
- Terminal gaps improved on five of six test parents; two runs terminated before the optimization limit. The largest effects came from medium 12 and 20. Other gap improvements, target crossings and primal-objective changes must not be conflated.
- The PR57 training launcher requests one GPU, eight CPU cores, 64 GiB and CUDA execution. This is a serial training configuration, not eight-GPU DDP. Actual allocations, device utilization and costs require job receipts; requesting a GPU alone does not prove utilization.
- A reported zero gap must be read alongside solver status, stopping tolerance, objective and bound. Recover the individual easy-parent solve receipts before asserting that every easy model was mathematically solved exactly within 3,600 seconds.
- Barrier is not known to have degraded these experiments. Recover `Method`, `NodeMethod`, `Crossover`, root-feature capture settings, solver version and failure logs before attributing a causal effect. Distinguish root feature preparation from the downstream MIP solve.

## Sprint A: complete the computational and incumbent evidence ledger

Estimated effort: 2-3 working days, excluding external access delays.

1. Verify the private MVP 1.0 archive and retain malformed/incomplete artifacts as such. Exclude raw benchmark inputs, credentials and operational duplicates; archive and member hashes are separate checks. Do not upload private path-bearing archives to Zenodo.
2. Produce one row per original parent and solver attempt: original LP SHA256, class, role, source/run contract, effective MINIMIZE sense, solver/version/parameters, budget, status, primal, dual, gap, solve wall time, CPU time, memory, recorded incumbent events, distinct audited solutions, independently labelled derived MILPs and training usage.
3. Reconcile reported incumbent counters with Parquet rows and variable-order hashes. A row count is initially an inventory observation, not proof of a unique feasible incumbent. Separate callback events, solver-pool solutions, repeated vectors, approximate labels and derived models. Keep repeated attempts disjoint.
4. Recover Slurm allocations for training and collection, including failed jobs and evaluation recovery. Attribute costs by phase and scope; missing historical CPU/GPU utilization is unavailable, not zero.
5. Characterize all 90 original models without solution labels: variables by type, constraints by sense, nonzeros/density, numerical ranges, graph degrees and graph sizes. Explain the benchmark difficulty categories separately from rare positive prediction targets. Reserve descriptive tables and PCA/UMAP figures in the manuscript. Network-based visualization is a later methodological investigation; no present novelty claim is made.

Deliverables: `parent_solver_ledger.csv`, `incumbent_inventory.json`, `augmentation_lineage.csv`, `hardware_usage.csv`, `class_descriptive_statistics.csv`, structured missing-evidence report and SHA256 manifest. Closure requires traceability, not all 90 successful solves.

## Sprint B: CPU parallelism and root-relaxation resource pilot

Implementation details and proposed budget gates are specified in the
[computational reconciliation and thread-pilot protocol](computational-reconciliation-and-thread-pilot.md).
Select within-class parents by varying structural composition rather than
dimensions, which the recovered PR65 collection found constant within each class.

Estimated effort: 3-5 working days plus controlled cluster execution.

Precommit an easy/medium pilot subset selected by class and label-free structural composition, not by observed improvement. Test `Threads` in {1,2,4,8,16}. Set Slurm CPU allocation and solver thread limits explicitly, record BLAS/OpenMP settings and constrain aggregate memory/concurrency. Keep seeds, solve budgets, tolerances and source models matched. Preserve the existing 64 GiB reservation initially; increase only after measured resource qualification in a newly versioned profile. Log out-of-memory and allocation failures, rather than dropping them.

Separate (a) parallelizing one solve, (b) independent-instance array throughput and (c) concurrent MIP portfolio search. Record wall-time speedup, parallel efficiency, aggregate CPU-seconds and peak memory: sixteen cores for half the time is not automatically cheaper. Where memory or root capture is problematic, compare automatic, dual-simplex and barrier root strategies on the pilot, checking root-feature semantics and mathematical equivalence. Do not select these settings using the final test results.

Consider concurrent MIP as a secondary portfolio experiment with the same total CPU allocation and separate nondeterminism accounting. A Benders or other decomposition requires verifying exploitable structure and an exact reconstruction/certificate contract; it is not an immediate assumption that these binary models decompose into independent subproblems. Distributed Gurobi requires compatible licenses/runtime and is distinct from threads on one DGX host.

Deliverables: paired resource curves, memory/time Pareto frontier, an explicit fixed resource profile and pilot-only selection receipt. Expand to all 30 easy models only after resource checks. Verify actual optimum statuses and gaps; do not promise monotonic scaling.

## Sprint C: easy-only versus mixed training and DDP qualification

Estimated effort: 4-6 working days plus training.

Use the 30 easy originals as an easy-only dataset with parent-disjoint fitting, validation and testing. The existing 18/6/6 split is a reproducible starting point: "30-instance training" must not mean fitting on all thirty while also claiming a held-out easy test. Medium and hard are external transfer populations for this model. Retain the original 54-parent checkpoint as a historical comparator, and train a matched mixed model with the same architecture, loss, sampling mass, epochs, seeds and selection conventions where required. Run at least 100 epochs with all curves retained; checkpoint selection uses validation only.

Qualify serial versus DDP on 1,2,4,8 GPUs. Hold effective global batch, parent sampling mass and optimizer updates constant for a scaling comparison; handle graph-size imbalance, normalization and distributed validation aggregation explicitly. Record data loading, communication, epoch time, peak device/host memory, GPU-hours and utilization. First qualify two GPUs, then four and eight; do not submit an unqualified eight-GPU job. A separate accuracy study may change global batch or optimization settings, but must not masquerade as pure hardware scaling.

Deliverables: easy-only and mixed per-parent predictive metrics, precision-recall curves, calibration, minority-class confusion counts, training/validation loss, cold inference cost and DDP numerical/data-membership checks. Compare AP and F1 against prevalence-aware baselines; pooled ROC-AUC alone is insufficient. Larger training data are a possible improvement, not a guaranteed one.

## Sprint D: controlled Gurobi/SCIP-derived augmentation

Estimated effort: 4-6 working days plus independent labelling.

After the ledger identifies available incumbents, create genuinely changed synthetic MILPs on fitting parents only. A different incumbent on an unchanged matrix is another target, not another independent graph. Descendants inherit parent roles. Independently solve and audit each derived model; an incumbent feasible for its parent is not automatically a feasible or <=10%-gap label for a modified MILP.

Compare original-only, Gurobi-derived, SCIP-derived and combined training arms with equal parent mass, matched source-parent sets, controlled numbers of derivatives and duplicate detection. If a matched arm is unavailable, report the missingness and retain the attainable ablation instead of claiming a four-arm result. Do not oversample validation/test parents or use their incumbent vectors as predictor inputs.

Deliverables: solver-specific available/unique/feasible incumbent counts, derivative yield and rejection reasons, structure/target diversity, matched training ablations and lineage hashes. Benefits are measured experimentally; correlated oversampling is not guaranteed to improve transfer.

## Sprint E: preregistered medium and hard warm-start evaluation

Estimated effort: 4-6 working days plus bounded optimization.

Easy-only transfer can evaluate all 30 medium parents because none supplies fitting or policy selection for that model. For the mixed model, separate previously fitted medium parents from genuinely held-out parents: fitted-parent results are in-distribution diagnostics, not generalization evidence. The six label-rejected medium parents form a difficulty-selected, historically inspected development subgroup with mixed original roles; they are not a new untouched test set.

Compare unguided, matched root-LP and GNN starts with identical resource profiles and rotated method order. Use the same explicit time limit within each resource comparison, initially 3,600 seconds, with any longer-budget sensitivity fixed before new results. For hard, precommit a structurally diverse bounded pilot followed, if safe, by a larger fixed set (for example twelve parents). Hard control runs belong to that paired warm-start experiment; they are not an open-ended hard label-recovery campaign. No standalone hard training-label solves are scheduled.

Use multiple paired solver seeds, selected before outcomes, and identify the parent as the primary independent unit. Treat seed runs and derivatives as nested observations. Report terminal gap, primal/dual movement, time to specified gaps, primal integral if instrumented, start acceptance/completion and cold/reusable total cost. Preserve censoring. Report paired confidence intervals and a prespecified inference procedure appropriate to the final parent count; do not infer time-to-optimal speedup from two runs at the same timeout. Keep the old six-parent study as descriptive development evidence because its outcomes are already known.

Deliverables: complete per-parent/seed tables, resource-normalized comparisons, effect uncertainty, influence diagnostics and all negative outcomes. Experimental success is a measured favorable effect with reproducible boundaries, not a requirement that drives post-hoc selection.

## Sprint F: scientific synthesis and submission revision

Estimated effort: 3-5 working days after evidence closure.

Rewrite the Computers & Operations Research manuscript around the computational question, learning contribution and measured tradeoffs. Introduce/interpret each table and figure; retain concise captions, no repetitive Source sentences and no bold prose. Integrate class characterization, CPU/thread scaling, GPU/DDP scaling, incumbent/augmentation yields and bounded hard transfer. Concentrate study limitations in final considerations without concealing adverse results in the data tables. Reassess contribution and journal fit with the coauthors; do not equate an engineering gate with submission readiness.

Only after approval promote MVP 2.0 from `develop` to `main`, update Pages and prepare a rights-reviewed public Zenodo deposit. Keep MVP 1.0 recoverable by source tag and private hash-bound evidence. Obtain the actually reserved DOI before inserting it.

## Primary technical references

- [Gurobi Threads, Method and ConcurrentMIP parameters](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html): installed-version semantics must be checked. More threads can increase memory and do not imply monotonic speedup; Method controls continuous/root-relaxation algorithms, not the entire branch-and-bound method.
- [PyTorch Distributed Data Parallel design](https://docs.pytorch.org/docs/main/notes/ddp.html): distributed training synchronization and explicit data partitioning. The runtime and framework version used on the HPC remain part of the experimental contract.

The attached Vargas-Pérez et al. network-visualization article is reserved for later methodological review. Its method has not been analyzed or implemented as part of this release.
