# Experimental design

The following specification transcribes the approved v3 design. It defines planned observations and controls, not a submitted campaign.

| Component | Planned design | Interpretation and control |
| --- | --- | --- |
| Unit | One original MILPBench CFL parent | Graph draws, targets and methods are nested observations, not independent instances. |
| Population | 30 easy, 30 medium, H0/H5/H10/H15/H20/H25 | 66 parents for characterisation. |
| Learning split | 21E+21M train; 5E+4M validation; 4E+5M test | 42/9/9; exact IDs frozen deterministically in S1, not selected in this preparation PR. |
| Hard transfer | Six hard parents outside learning partitions | Evidence concerns those selected parents; not independent population-wide generalisation. |
| Root run | Presolve=0; Heuristics=0; Method=-1; Threads=0 | Complete original-variable MIPNODE root vector with event/cut provenance; no claim of an automatically cut-free LP. |
| Label run | Native presolve/heuristics; MIPFocus=0; MIPGap=0.0001 | Audited feasible incumbent labels, separate from root features; coverage accepted before training. |
| Main evaluation | 15 parents x B/R/G = 45 fresh calls | Seed42; ConcurrentMIP=1; Method=-1; Threads=0; no additional concurrent-MIP/seed/thread arms. |
| Pairing | Same mathematical model and hardware class within parent | Predeclared rotating method order; no overlapping calls for the same parent. |
| R/G treatment | R independent root rounding/ranking; G frozen neural probabilities | Value/probability tails <=0.1 or >=0.9; cap 10% of binaries; other Starts undefined. |
| Quality targets | 0.10; 0.05; 0.01; 0.0001 | Four target observations from one trajectory; numeric factors require common attainment and positive times. |
| Training | 1 versus 4 V100; 100 epochs; global batch4 | 168 graph presentations and 42 updates per epoch; 4200 updates per arm. |
| Analysis | Per-parent paired factors, attainment, quality, effort and cost/reuse | Separate easy/medium test and hard-transfer summaries; descriptive finite-cohort interpretation. |
| Conditional work | Up to six diagnosed-hard feasibility runs; Benders only after specific design/approval | Not part of 177 primary calls; no automatic extension, exclusion, retry or replacement. |
| Release | At most two jobs and two Gurobi sessions; exact source/input/resource contracts | All HPC execution uses the author CLI; this preparation opens no scientific run. |

## Coverage and identities

The 66-row instance register enumerates original IDs and E/M/H aliases. E/M learning roles remain TO_FREEZE_S1 until the deterministic split is reviewed. The 45-cell evaluation template uses four easy and five medium test slots, whose original IDs remain blank; these are slot labels, not selected parents. The six hard IDs are fixed. All result fields are empty and each cell is PLANNED. A missing or unsuccessful feature/label run receives a reasoned disposition; it is never converted into a fabricated vector or silently dropped.

## Comparison contract

Use T_B/T_G and T_R/T_G, with values above one favouring G, for common qualified targets and comparable positive clocks. Preserve attained, censored, memory/numerical and infrastructure outcomes separately. Recompute per-instance factors before summaries; do not invert an arithmetic mean. End-to-end and cumulative reuse factors include their declared preparation costs. Training speedup remains T_serial/T_DDP, with GPU-normalised efficiency divided by four.
