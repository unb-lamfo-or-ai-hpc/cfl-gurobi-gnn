# Original-parent GNN confirmation

The development experiment completed 100 epochs on 39 Gurobi-labelled original
parents: 30 easy and nine medium, partitioned into 23 training, eight validation
and eight test parents. Seed 42 and a 10% maximum label MIP gap were fixed.
The original 42-parent target remained incomplete: medium instances 3, 5 and 6
were excluded after four-hour solves still exceeded the gap ceiling. This
solver-admissibility selection limits population-level generalization.

## Observations

Training used the versioned Gasse architecture with alternating prenormalization,
32 hidden channels, two layers, Adam at 0.001, gradient clipping at 1.0 and four
draws per training parent per epoch. Prenormalization used training graphs only.
The minimum validation weighted BCE occurred at epoch 91 (0.0984964). Epoch-100
training and validation losses were 0.0738546 and 0.1880224, respectively; the
final epoch was not automatically selected. The validation-F1 threshold was
0.9933161. Epoch-history classification metrics used the fixed 0.5 threshold and
must not be confused with the selected-threshold held-out metrics.

Eight test parents contained 3,222,800 binary targets, including 3,773 positives.
Aggregate precision, recall and F1 were 0.537548, 0.635569 and 0.582463.
Parent-macro F1 was 0.584889. Reported average precision was 0.609753 and ROC AUC
was 0.999115. These are descriptive outcomes from one split and one seed, not
independent-variable confidence estimates or evidence of solver acceleration.

The Brier score (0.00609632) exceeded the constant-zero baseline (0.00117072),
despite improved ranking. Class-weighted outputs are not established calibrated
probabilities. The positive prevalence was 0.1171%; high accuracy alone is not
a sufficient measure of model quality.

Graph statistics and deterministic PCA/k-means covered all 39 parents. The first
two components explained 93.5165% of descriptor variance. Three clusters are
descriptive, not evidence of three independent populations. Censoring was unknown
in all 39 graph-statistics rows, so their recorded source runtimes cannot be
interpreted as comparable times to optimality.

## Evidence and scope

`audit.json` records a read-only consistency audit of the supplied final ZIP.
All 62 manifest-listed files passed packaged SHA-256 checks. Classification
counts, parent/difficulty aggregates, epoch sequence, report links and graph
receipt hashes were reconciled. The input archive SHA-256 is recorded there.
Graphs, labels, root vectors, the checkpoint and predictions were not included;
their receipt hashes are not independent re-execution. Full ROC and precision-
recall CSVs were withheld for size. Consequently, AUC/AP values are reported
from the hashed evaluator receipt, not recomputed from omitted predictions.

The Slurm job completed with exit code 0 after 09:28:54. This is the combined
training/evaluation job elapsed time, not a separately instrumented training
duration or optimization time. The reported Python-step peak RSS was 4,164,816 K
against a 64 G request. The run used serial CUDA execution; the bundle does not
establish the exact GPU allocation or a complete software-version inventory.

This delivery closes an original-parent research MVP with limitations. Matched
four-arm augmentation, native hint/control benchmarking, multi-seed replication,
calibration, dependency qualification and the 90-parent study remain future
work. Existing failed source gates and `scientific_reporting_eligible=false`
remain unchanged. MIT applies to original project material within the authors'
rights; third-party benchmark and solver terms are preserved.
