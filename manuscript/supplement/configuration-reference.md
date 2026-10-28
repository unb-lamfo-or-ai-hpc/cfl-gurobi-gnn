# Configuration reference: inputs, parameters and selected settings

This companion to the [methods explanation](gnn-methods-audit.md) identifies
the settings behind the study. It is intended to let a reader answer three
questions: what information enters a stage, which choices control it, and
where those choices can be checked. It is candidate material for the data/
methods appendix and scientific supplement, not a new experiment.

A **fixed setting** was specified without a demonstrated comparative search.
A **selected setting** was chosen by a stated validation rule. A **recorded
runtime value** comes from an existing receipt. These sources have different
evidential roles. In particular, a documented default is not a substitute
for a missing runtime record.

Links below point to fixed GitHub revisions. The ongoing CPU campaign is
described using its separate installed source; none of its inputs or settings
is changed here.

## 1. Data inputs and information boundaries

The optimization inputs are compressed LP models from MILPBench, rather than
spreadsheets. The neural inputs are derived graphs and a stored root-relaxation
vector. Reference solutions provide training/evaluation labels. Those objects
have different roles and must retain their original identities.

| Input or choice | Content and setting | Source and interpretation |
| --- | --- | --- |
| Original optimization model | Objective coefficients/constant, linear rows, right-hand sides, variable names, bounds and domains from the original LP | [Data layout](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/data/README.md) and [upstream download links](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/README.md); raw LP files are external, not redistributed by this appendix |
| Objective convention | MINIMIZE at runtime; original bytes and mathematical coefficients retained | [R3 author decision](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/docs/research/mvp2-r3-contract.md); source MAXIMIZE declarations are preserved as provenance |
| Candidate and admitted populations | 90 candidates; 54 admitted parents: 30 easy, 24 medium, no hard | [Data/model record](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/docs/research/mvp2-r3-methods-and-models.md); quality-selected admission, not random population sampling |
| Parent partitions | 34 train, 10 validation, 10 historically exposed test parents | [Canonical fold table](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/configs/splits/cfl_90_seed42_folds.csv) and [parent inventory](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/docs/evidence/e0/pr85/parents.csv); folds 0/1 correspond to test/validation, remaining folds to training, subject to admission |
| Label-quality ceiling in training configuration | Relative label gap 0.10 (10%) | [Mixed-cohort training configuration](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/configs/training/gasse_pr57_54_v1.json); checked reference incumbents can be approximate |
| Root feature | First eligible optimal root-node MIPNODE relaxation; full original variable alignment | [Root capture](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/scripts/evidence/pr86_root_preparation.py); not a separate model.relax() solve and not necessarily the final root after all cuts |
| Information supplied to the GNN | Model features, stored root values and binary-variable mask | [Guidance preparation](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/scripts/evidence/pr86_guidance_preparation.py); reference labels used by a separate audit do not enter the neural forward |
| CPU checkpoint | SHA256 `a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028` | [Checkpoint bindings](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/docs/evidence/e0/pr85/checkpoints.csv); the mixed historical model, not either later GPU checkpoint |

Historical six-medium optimization results and the principal ten-parent CPU
comparison remain separate populations. Repetition across methods, caps or
seeds does not create additional independent parents. Canonical identities
and the original exposure limitations remain in the linked inventory.

### How numbers become graph features

The [feature encoder](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/src/cfl_gnn/graph/build_dataset.py) and
[strict graph builder](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/src/cfl_gnn/graph/gurobi_graph_artifact.py)
provide the channel order below. It matters because a trained weight expects
the same feature in the same position at inference.

| Object | Ordered channels |
| --- | --- |
| Variable (7) | Objective coefficient; lower bound; upper bound; continuous, binary and integer indicators; captured root-relaxation value |
| Constraint (5) | Right-hand side; less-than, equality and greater-than sense indicators; constant one |
| Coefficient edge (1) | Nonzero matrix coefficient |

Numerical objective, bound, right-hand-side and edge channels are clipped
to [−60000,60000], then transformed by signed log(1+absolute value).
Infinite values are mapped to the corresponding clipping limit. The root
channel is clipped without the logarithm. The strict route rejects malformed
or nonfinite root vectors and NaN model inputs; a generic legacy fallback in
the encoder is not the admitted strict input path. Feature tensors are float32.
These transformations affect the learning representation, not the original
LP coefficients used by Gurobi. The encoding audit records clipping rather
than treating it as lossless.

## 2. Historical predictor: fixed settings and validation choices

The complete [mixed training configuration](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/configs/training/gasse_pr57_54_v1.json)
is implemented by the [trainer](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/src/cfl_gnn/training/gasse_reconnected.py),
the [network](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/src/cfl_gnn/models/gasse.py) and its
[versioned prenormalization](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/src/cfl_gnn/models/gasse_calibrated.py).
The methods explanation gives the rationale and limits of these choices.
No comparative architecture or hyperparameter search is reconstructed here.

| Setting | Value or rule | Status and meaning |
| --- | --- | --- |
| Model version | gasse_v2_alternating_prenorm | Fixed implementation; coefficient-aware messages and separate constraint/variable updates |
| Propagation cycles / hidden width | 2 / 32 | Fixed capacity; not demonstrated optimal |
| Node/edge dimensions | 7 / 5 / 1 | Determined by the encoding above |
| Message/update functions | Two-layer MLPs, sum aggregation, ReLU | Fixed architecture; no component ablation in the present study |
| Prenormalization | Fixed alternating constraint/variable statistics fitted on training graphs | Training-only fitted state; not probability calibration |
| Optimizer / learning rate | Adam / 0.001 | Fixed; no learning-rate scheduler invoked in the relevant path |
| Other Adam arguments | Installed-runtime defaults, not independently tuned | Their numerical beta/epsilon settings are not separately exported by this JSON; do not invent a historical parameter sweep |
| Gradient clipping | Global gradient norm limited to 1 | Fixed stabilization threshold |
| Training seed | 42 | Fixed training initialization/sampling setting; distinct from the Gurobi seed |
| Historical graph batch | One graph per update | Original serial training path |
| Parent sampling | Four deterministic balanced draws per training parent per epoch | Equal parent presentation counts; variable targets remain dependent within a parent |
| Epoch ceiling / patience | 100 / 100 | Fixed schedule controls; historical report completes 100 epochs |
| Loss | Per-graph mean BCEWithLogitsLoss with training-fitted positive weight | Reference-label agreement, not an optimization certificate |
| Positive-class weight | Training negative/positive count ratio; reported mixed weight 1132.975830 | Fitted on training labels, not tuned on test performance |
| Retained checkpoint | Minimum validation weighted BCE | Data-dependent selection; historical retained epoch 34 differs from 100 completed epochs |
| Classification threshold | Maximum pooled validation F1; retained CPU threshold 0.9991843104362488 | Validation-selected; not a calibrated probability cutoff |
| Threshold candidates and ties | Observed validation scores plus 0, 0.5, 1; prefer higher F1, then closer to 0.5, then lower threshold | Deterministic selection rule in the trainer |
| Smoke fallback threshold | 0.5 for incomplete smoke scope | Configuration fallback, not the retained CPU threshold |
| Calibration report | 10 bins; per-parent and per-difficulty reporting enabled | Reporting settings; fitting a threshold does not calibrate scores |

The separate easy-only historical reference is retained in the
[easy configuration](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/configs/training/gasse_easy_transfer_v1.json) and
[checkpoint table](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/docs/evidence/e0/pr85/checkpoints.csv).
Its threshold and weights are not substituted for the mixed CPU reference.
Historical checkpoint/summary discrepancies already recorded in that table
remain disclosed; this appendix does not replay training or rescoring.

### Inference and assignment selection

Inference uses evaluation mode without gradients and the frozen checkpoint.
The sigmoid produces binary-variable scores; validation determines the
threshold. With n eligible binary variables, the requested support is
min(n,20000,max(1,floor(0.10n))). G selects predicted ones first, then fills
with confident predicted zeros; variable names break ties. It abstains when
no one is predicted.

R clips stored LP values to [0,1], matches G's actual assignment count and
one count, and chooses its own indices by LP ranking. B supplies no external
Start. Unselected variables remain GRB.UNDEFINED; no original bound is fixed.
The exact rules are in the
[selection implementation](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/src/cfl_gnn/experiments/pr58_guidance.py).
Metadata named confidence or priority in an assignment file does not itself
show that a Gurobi hint or branching-priority setting was applied.

## 3. Root preparation and CPU solver settings

Preparation and the later optimization runs have different purposes. In
particular, disabling presolve for root-feature capture is not the same
configuration as leaving presolve automatic during a paired solve.

| Root-preparation setting | Fixed value |
| --- | --- |
| Model sense | MINIMIZE |
| Threads / Seed | 1 / 42 |
| Presolve / NodeLimit | 0 / 1 |
| TimeLimit | 600 seconds |
| SoftMemLimit | 48 GB decimal |
| Logging controls | OutputFlag=1, LogToConsole=0 |

The [root-preparation source](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/scripts/evidence/pr86_root_preparation.py)
sets and verifies this map. These completed preparation steps are not repeated.

The CPU table below reproduces the recorded search/tolerance map from
[historical job3522 return](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/docs/evidence/pr86/job3522/public_return.json),
member `run/attempt-0/child.json`, `result.parameters`.
The pending CPU12h contract explicitly reuses that map with its admitted
TimeLimit and Threads. It is checked in the
[frozen PR89 contract](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9ab7823c6886d19e9ec865141a1cd35b3c3c16e5/scripts/evidence/pr89_cpu_contract.py);
the table is not a new effective-parameter capture from the still-running jobs.

| Parameter | Principal CPU study | Existing CPU12h campaign | Meaning |
| --- | --- | --- | --- |
| Threads | 1, 2, 4, 8, 16 by cell | Same five caps | Solver thread cap; allocated SMT CPU accounting is a separate resource measure |
| Seed | 42 in principal analysis | 42 | Solver search perturbation; historical 43/44 rows are not CPU12h replications |
| TimeLimit | 3600 s | 43200 s | Solver time ceiling; not measured successful time-to-target |
| MIPGap | 0.0001 | 0.0001 | Relative terminal tolerance, equal to 0.01% |
| MIPGapAbs | 1e-10 | 1e-10 | Absolute objective-gap stopping tolerance |
| Method | −1 | −1 | Automatic continuous/root algorithm selection |
| Presolve | −1 | −1 | Automatic presolve |
| Cuts | −1 | −1 | Automatic cut control |
| Heuristics | 0.05 | 0.05 | Heuristic effort control |
| MIPFocus | 0 | 0 | Default balanced search focus, recorded explicitly |
| StartNodeLimit | −1 | −1 | Automatic Start-completion node control |
| SubMIPNodes | 500 | 500 | Sub-MIP heuristic node control |
| FeasibilityTol | 1e-6 | 1e-6 | Solver primal feasibility tolerance |
| IntFeasTol | 1e-5 | 1e-5 | Solver integrality tolerance |
| SoftMemLimit | 48 GB decimal | 48 GB decimal | Solver soft memory limit, separate from the scheduler's GiB allocation |

The [CPU solver path](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/scripts/evidence/pr86_solver.py) also enables
sanitized messages with OutputFlag=1 and LogToConsole=0. Private logs are not
publication inputs. ConcurrentMIP was not exported in this parameter map:
its effective value remains unavailable, not an inferred default.
Method=−1 alone does not identify a non-deterministic MIP algorithm, and
time-limited termination can vary even with otherwise reproducible work.

Independent vector checks use feasibility tolerance 1e-6 and integrality
tolerance 1e-5. Recomputed objective agreement uses relative tolerance 1e-8
and absolute tolerance 1e-6, in the
[audit implementation](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/src/cfl_gnn/validation/mathematical.py).
These floating-point checks do not establish exact feasibility or remove
M4/M12's metric-specific numerical restrictions.

### Observations and resource limits

| Control | Existing principal CPU evidence | Existing CPU12h campaign |
| --- | --- | --- |
| Recorded threshold fractions | 0.01, 0.05, 0.06, 0.10 | 0.10, 0.05, 0.01, 0.0001 |
| Temporal interpretation | First observed callback crossings; terminal flag distinct | First observed crossing and prior point; no continuous exact-time claim |
| Horizon observations | Retain the historical observation scheme | 3600, 14400, 28800, 43200 s, with actual brackets/staleness |
| Trajectory sampling | Existing historical recorder | 30-second sampling plus terminal; crossing/horizon updates occur separately |
| CPU12h scheduled resources | Not a retrospective claim about all historical allocations | One node/task, zero GPU, 65536 MiB RAM, 46800 s job wall |
| CPU12h supervision | Not substituted for solver Runtime | Child deadline 45000 s; sampled job memory guard 56 GiB; solver SoftMemLimit as above |

The [frozen temporal recorder](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9ab7823c6886d19e9ec865141a1cd35b3c3c16e5/scripts/evidence/pr89_cpu_temporal.py)
and [CPU12h resource record](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9ab7823c6886d19e9ec865141a1cd35b3c3c16e5/docs/research/pr89-cpu12h.md)
define these controls. A threshold, reporting cadence and memory guard are
not interchangeable with solver stopping criteria. Missing data remain missing.
The qualified final return must still reconcile every planned cell and its
actual settings; no current result is inferred from this table.

## 4. Matched GPU training is a separate configuration

The [matched-pair configuration](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/configs/experiments/pr87_matched_gpu_v1.json)
and [training implementation](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/scripts/evidence/train_pr87.py)
define the completed one-seed comparison. Its newer weights do not replace
the CPU checkpoint.

| Control | Recorded design |
| --- | --- |
| Model and input dimensions | Same named model version, two cycles, width 32, input dimensions 7/5/1 |
| Arms and order | Seed42 serial1 followed by DDP4; one versus four V100 GPUs |
| Physical CPU allocation | 4 versus 16 cores; CPU resources change with GPU resources |
| Initialization and data | Training-only fitted state and matched initial-state/schedule identities checked |
| Batch objective | Four per-graph weighted-BCE means per global update |
| Serial update / distributed update | Accumulate four losses divided by four / average one gradient per rank |
| Schedule | 100 epochs, 4 draws per training parent, 34 updates/epoch, 3400 updates and 13600 presentations per arm |
| Optimizer / learning rate / clipping | Adam / 0.001 / norm 1; clipping once after global aggregation |
| Optimizer defaults | Default beta/epsilon arguments; protocol specifies zero weight decay; no separate tuning |
| Precision | Float32, no AMP, TF32 disabled |
| Loader workers / PyTorch CPU threads | 0 workers; 4 threads and 1 inter-op thread per process |
| CUDA controls | cuDNN benchmark false, deterministic true; CUBLAS_WORKSPACE_CONFIG=:4096:8 |
| DDP | NCCL; explicit fitted-buffer broadcast, DDP broadcast_buffers=false; process-group timeout 42000 s |
| Validation | All ten validation parents on rank0 each epoch, using the unwrapped model |
| Checkpoint selection | Minimum parent-mean validation weighted BCE; earliest tie; selected epochs 99/92 |
| Threshold and test selection | Existing maximum pooled validation-F1 rule; test is not used for selection |
| Early stopping / resume | False / false; both arms complete the same update count |
| Job wall / host memory | 43200 s / 131072 MiB per job |
| Sampled host stop / monitoring cadence | 112 GiB / 5 s |
| Descriptive quality-loss margins | Absolute 0.02 for parent-macro F1 and trapezoidal PR-AUC; not a statistical noninferiority margin |

These are configuration and selection records, not evidence that floating-point
trajectories are identical. The
[completed-pair review](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/c76b076591ff977a092fc5d7d6bf42a074f05133/docs/research/pr87-completed-pair-review.md)
keeps speed, selected quality and assigned GPU-hours separate. Parameter
documentation does not convert its lower selected F1 into a positive result.

## 5. How to use this reference in the final manuscript

A claim should identify its population, checkpoint, solver setting, endpoint
and clock. References to “the configuration” are insufficient when the
historical predictor, root capture, principal CPU study and later GPU pair
have different settings. The explanatory text states why choices are
reasonable; the linked files establish the values actually specified or
recorded. The complete files also retain protocol identifiers and historical
authorization metadata that are not neural hyperparameters.

Older proposal flags are preserved as dated evidence. They do not reverse
later explicit execution decisions or supply current scientific qualification.
Unexported effective fields, historical-fit limitations and M4/M12 restrictions
remain visible. The additional studies in the
[sensitivity discussion](sensitivity-review-plan.md) are future work outside
S1–S6. No new root capture, inference, training, seed or solve accompanies
this appendix. Final supplement packaging and author review remain pending.
