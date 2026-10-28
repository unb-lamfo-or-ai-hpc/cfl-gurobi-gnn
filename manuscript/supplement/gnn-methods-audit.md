# GNN foundation, implementation and solver-interface audit

28 October 2026 · working coauthor-review material · CFL-GNN-LIT-ARCH-2026-02.
Documentary baseline: [PR92 source 7bd4b345](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/7bd4b34556cc9c4f01d063bab74a38e4d058bd7c).
The [R3 contract](../../docs/research/mvp2-r3-contract.md) governs experiments.
This audit does not rerun a model, certify a checkpoint fit retrospectively, or
change the installed PR89 source. The author's current instruction permits
editorial GitHub changes, superseding the attached mandate's read-only
repository restriction; its prohibition on new experiments remains in force.

## E1 — Critical assessment and five priorities

**Adopt with reservations.** The mandate correctly separates architecture,
predictive validity and optimization utility. A bipartite message-passing model
is a defensible way to use the MILP coefficient structure and shared weights
across instance sizes. This is a modelling rationale, not evidence that two
32-dimensional cycles are optimal or outperform a structure-free predictor.

The mandate is too broad if treated as nine independent reports, a general GNN
survey or an implicit architecture benchmark. Consolidate E1–E9 here, in the
existing numerical supplement and in the accelerated completion plan. Preserve
R3's scientific question; qualify the word “deterministic” by actual solver
configuration and stopping rule. Do not rewrite the question to promise gains.

Five immediate priorities are: (1) distinguish our implementation from Gasse's
branching model; (2) expose actual fixed/selected hyperparameters and unknown
choice rationales; (3) explain root capture, inference and B/R/G dependencies;
(4) reconcile serial/DDP mathematical work with its adverse quality finding;
(5) align every claim with its population, evidence and limitations. References
absent from the manuscript are candidates, not a checklist for inclusion.

Choose E8 alternative **B**: documentary foundation plus analysis of existing
records, without new inference, training or solves. A is sufficient for some
editorial issues but leaves reusable provenance unexamined. C, a new controlled
architecture comparison, is deferred beyond this submission unless separately
authorized. No budget or acceptance forecast is invented for C.

## E2 — Architectural distinctions

Notation: h is a node embedding, N(i) its neighbours, rho a nonlinearity,
and || concatenation. Equations below identify representative operators;
they are not claims that all variants have identical inputs or cost.
N and E denote node and edge counts, d a common hidden width.

| Family and representative update | Centre / edge treatment | Scaling and transfer limits | Evidence in this project |
| --- | --- | --- | --- |
| MLP: h_i'=rho(W h_i+b) | Centre only; no graph edges | O(N d²) for dense hidden layers; shared weights accept different N but ignore structure | Conceptual comparator, not a matched executed baseline |
| Kipf–Welling GCN: H'=rho(Dtilde^(-1/2) Atilde Dtilde^(-1/2) H W) | Self-loops and degree-normalized sum; canonical operator has no arbitrary coefficient-edge channel | Sparse propagation O(E d+N d²); degree normalization differs from our learned coefficient messages | Not the architecture used in PR86/89 |
| GraphSAGE: h_i'=rho(W[h_i || AGG({h_j})]) | Centre concatenated with neighbour aggregate; mean/pool/LSTM variants and sampling differ; canonical form does not consume MILP coefficients automatically | Full-neighbour work depends on E; sampled work on fan-outs and depth; inductive function does not establish CFL generalization | Not a qualified campaign comparator |
| GAT: h_i'=rho(sum_j alpha_ij W h_j), alpha=softmax_j LeakyReLU(a^T[Wh_i||Wh_j]) | Masked neighbour attention; original additive form has static neighbour ranking; coefficient features need an explicit extension | Sparse attention roughly O(N d²+E d) per head; cost depends on heads; not dense global attention | No matched GAT experiment |
| GATv2: e_ij=a^T LeakyReLU(W[h_i||h_j]), followed by neighbour softmax/aggregation | Changes order of projection/nonlinearity, allowing query-dependent ranking; not equivalent to GAT | Similar sparse-order costs with variant-dependent projections; greater attention expressivity is not guaranteed downstream gain | No matched GATv2 experiment |
| Gasse-inspired bipartite model | Separate variable/row embeddings; coefficient-aware messages, sum, fixed prenorm; V→C→V | Dense message MLPs give approximately O(L(E+N)d²) time and O(E d+N d) forward activations per cycle; autograd/storage add overhead | Actual frozen architecture; empirical comparison is B/R/G, not architecture ranking |
| Repository BiGNN / BiGNN+ATT | Two encoder stages, same GasseBipartiteConv; optional softmax(QK^T/sqrt(d))V on variable embeddings within each graph | Attention adds O(n_v² d) work and O(n_v²) scores per graph; padding can increase memory | Implemented in liang.py; presence of code is not a qualified principal training result; neither variant is GAT/GATv2 |

Primary foundations: [GCN](https://arxiv.org/html/1609.02907v4),
[GraphSAGE](https://arxiv.org/html/1706.02216v4),
[GAT](https://arxiv.org/html/1710.10903v3),
[GATv2](https://arxiv.org/html/2105.14491v3),
[Gasse v3](https://arxiv.org/abs/1906.01629v3).
These papers support operator distinctions, not an empirical ordering on CFL.
Repository sources: [gasse.py](../../src/cfl_gnn/models/gasse.py),
[gasse_calibrated.py](../../src/cfl_gnn/models/gasse_calibrated.py),
[liang.py](../../src/cfl_gnn/models/liang.py).

Sum aggregation retains multiplicity information but changes scale with degree;
prenorm addresses activation scale without proving degree invariance. Two
alternating cycles permit variable information to traverse up to four bipartite
edges. They do not solve arbitrary global dependencies. Shared operators and
sum aggregation are permutation equivariant in exact arithmetic when features
and identities are permuted consistently; floating-point ordering and the
name-based selection tie-break need separate treatment. Over-smoothing and
information bottlenecks are theoretical concerns, not diagnosed causes of our
observed errors. Neither deeper layers nor attention is an automatic remedy.

### Actual propagation and adaptation from Gasse

With t=1,...,2, initial embeddings are ReLU(linear(features)). The implementation is

$$
c_i^t=\operatorname{ReLU} f_C^t\left[c_i^{t-1}\,\Vert\,
 P_C^t\left(\sum_{j\in N(i)}g_C^t[c_i^{t-1}\Vert v_j^{t-1}\Vert e_{ij}]\right)\right],
$$
$$
v_j^t=\operatorname{ReLU} f_V^t\left[v_j^{t-1}\,\Vert\,
 P_V^t\left(\sum_{i\in N(j)}g_V^t[c_i^t\Vert v_j^{t-1}\Vert e_{ij}]\right)\right].
$$

Each f/g is Linear→ReLU→Linear. P is a fixed affine prenorm.
The second direction uses the **fresh** row embeddings. The final two-layer
MLP produces one logit per binary variable; sigmoid is applied for scoring.

The upstream comparison is pinned to
[learn2branch 57e82603](https://github.com/ds4dm/learn2branch/tree/57e82603fba39c34ff81baf9bd0b5768f5a1a860),
not an unspecified mutable master.

| Dimension | Upstream baseline | CFL-GNN campaign model |
| --- | --- | --- |
| Decision / solver interface | Imitate strong-branching candidate choice inside SCIP | Predict binary incumbent values, then native Gurobi partial Start |
| Loss / output interpretation | Candidate softmax cross-entropy | Positive-weighted binary BCE; sigmoid scores are not calibrated probabilities |
| Depth / width | One V→C→V cycle, width64 | Two cycles, width32 |
| Inputs | 19 variable / 5 row / 1 edge channels, solver-state features | 7 variable / 5 row / 1 edge channels, custom signed-log/clipping and captured root values |
| Message / encoder implementation | Separate linear left/edge/right transforms added, prenorm and nonlinear maps; deeper initial embeddings | Concatenated edge inputs through MLPs; single linear node encoders; distinct normalization layout |
| Data | Generated facilities instances and branching samples | Existing MILPBench parents and quality-screened incumbent labels |
| Evidence | Original paper's experiments | Historical CPU evidence and separate matched GPU pair; no full reproduction claim |

See upstream [baseline model](https://github.com/ds4dm/learn2branch/blob/57e82603fba39c34ff81baf9bd0b5768f5a1a860/models/baseline/model.py),
[training](https://github.com/ds4dm/learn2branch/blob/57e82603fba39c34ff81baf9bd0b5768f5a1a860/03_train_gcnn.py),
[feature extraction](https://github.com/ds4dm/learn2branch/blob/57e82603fba39c34ff81baf9bd0b5768f5a1a860/utilities.py),
and [facilities generator](https://github.com/ds4dm/learn2branch/blob/57e82603fba39c34ff81baf9bd0b5768f5a1a860/01_generate_instances.py).
That generator writes binary facility y and bounded continuous allocation x,
with demand/capacity and strengthening constraints. It is not the identity of
our benchmark formulation. No generator is run and no new formulation gate
is opened by this comparison.

The legacy prenorm fit computes variable-side statistics before the row update;
v2 fits them after that update using all training graphs in deterministic order
and population moments. These versions are not interchangeable. The name
“calibrated” in the source file refers to prenorm handling, not a fitted
probability calibration map. Existing checkpoint provenance remains binding;
reading today's fit procedure does not reproduce a historical fit.

For the configured 7/5/1, width32, two-cycle model, static dense-layer counting
gives 26,753 trainable scalars: 448 encoders + 2×12,608 message/update layers +
1,089 head. Prenorm buffers are excluded. This is a source-derived count,
not a runtime measurement or model loading. It does not quantify memory:
edge activations, graph sizes, autograd, optimizer and device runtime matter.

## E3 — Hyperparameter and historical-decision matrix

Sources: [frozen training configuration](../../configs/training/gasse_pr57_54_v1.json),
[serial implementation](../../src/cfl_gnn/training/gasse_reconnected.py),
[matched-pair configuration](../../configs/experiments/pr87_matched_gpu_v1.json),
[matched worker](../../scripts/evidence/train_pr87.py),
[selection](../../src/cfl_gnn/experiments/pr58_guidance.py),
and the [R3 checkpoint audit](../../docs/research/mvp2-r3-methods-and-models.md).
The PR57 configuration entered the reviewed history at
[39c40f1c](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/commit/39c40f1c2967501bfcfc9df58c95ad79234f8a63).
The gasse.py history reaches
[d8219438](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/commit/d82194383312b1d8c5a293258a8517038300b091).
These establish versioned choices, not an unrecorded tuning study.
No inspected configuration, receipt or history establishes why 2×32 was
empirically preferred to 1×64. Record that rationale as unavailable.

| Group / parameter | Actual value and origin | Selection, alternatives, sensitivity and implication |
| --- | --- | --- |
| Network: cycles / width | 2 / 32; project adaptation, versus upstream1/64 | Fixed; no qualified architecture search or sensitivity; not “best architecture” |
| Network: features | 7 / 5 / 1; project encoder | Fixed; signed log/clipping can lose scale information; no feature ablation |
| Network: aggregation / activations | Sum / ReLU, final linear logit; Gasse-inspired adaptation | Fixed; not mean aggregation or attention; sensitivity unmeasured |
| Network: prenorm | v2 alternating train-only population moments, frozen buffers | Versioned correction, not validation-selected; do not refit the CPU checkpoint |
| Optimizer / learning rate | Adam / 0.001 in serial and matched worker | Fixed; no scheduler invoked in these paths; no learning-rate search |
| Adam subsidiary settings | Worker constructs Adam with lr only; PR87 config specifies default betas/eps, zero weight decay | Runtime defaults are inherited, not tuned; do not silently substitute modern defaults into a historical runtime |
| Initial state | PyTorch module initialization and seed controls; PR87 binds tensor-state and schedule hashes across arms | Not claimed identical to upstream orthogonal initialization; no seed robustness study |
| Historical serial graph batch | 1; four draws of each of34 train parents per epoch | 136 updates/epoch, unlike PR87; not a serial member of the matched globalbatch4 comparison |
| Matched serial / DDP batch | Global4: serial four graph accumulations / DDP one graph per rank | 34 updates/epoch, same ordered groups; no batch-size search |
| Gradient clipping | Norm1, after accumulation or averaged gradients | Fixed; before each Adam update; sensitivity unmeasured |
| Epochs / early stopping | Historical maximum100, patience100; matched100 with early stopping disabled | Historical selected epoch34 differs from terminal100; matched selected99/92. Selection is not tuning epoch count on test |
| Loss / class weight | Mean binary weighted BCE per graph; weight from train negatives/positives | Not class-frequency weighting fitted on test; PR87 weight1132.97583 is pair-specific |
| Sampling / seed | Parent-balanced four draws/epoch, seed42 | Fixed schedule; the one-seed pair cannot establish stochastic robustness |
| Checkpoint selection | Minimum validation weighted BCE; earliest retained strict improvement | Actual validation selection, not minimum test loss |
| Threshold | Maximum pooled validation F1; original CPU0.9991843104362488; matched serial≈0.998544, DDP≈0.997792 | Different frozen models have different validation thresholds; not probability calibration |
| Start support | min(n,20000,max(1,floor(0.10n))) | Fixed policy; no support-fraction ablation |
| Start ordering / abstention | Ones by descending score, then zeros by descending1−score; names break ties; abstain if no predicted one | Implemented policy, not demonstrated causal advantage of prioritization |
| RELAX support | Match actual G count k and number q of ones | Dependent comparator; not identical indices or independent LP tuning |

No new parameter range is prescribed. The existence of augmentation arms or
BiGNN code does not establish a fair architecture comparison.

## E4 — Serial/DDP mathematical and empirical reconciliation

For graph g with n_g binary targets define
L_g=(1/n_g) sum_j BCE_w(s_gj,y_gj). The matched objective per update is
L=(1/4) sum_(g in batch) L_g. This is a mean of four **graph means**, not
one mean over all variables. Large graphs therefore do not gain additional
weight merely by containing more binary targets.

[matched_gpu.py](../../src/cfl_gnn/training/matched_gpu.py) divides each
serial graph loss by four before backward, accumulates all four gradients,
clips once, then steps Adam once. DDP backward uses one unscaled graph-mean
loss per rank; the default four-rank reduction averages gradients, followed
by one clipping/update. Dividing each DDP loss by four again would be wrong.
Both use the same34-parent schedule, four presentations/parent/epoch,
100epochs, 13,600 graph presentations and3,400 updates. Initialization,
prenorm buffers and positive weight are bound across arms; buffers are
broadcast explicitly before DDP with broadcast_buffers=False. Validation
uses all ten validation parents on the unwrapped rank0 model each epoch.

The loss definitions and gradient regression support mathematical matching.
They do not prove bitwise trajectory identity. The installed PyTorch2.1.2
[DDP documentation in source](https://github.com/pytorch/pytorch/blob/v2.1.2/torch/nn/parallel/distributed.py)
is the version anchor, rather than a later API manual. Actual histories diverge;
their cause is unproven. Do not attribute the F1 decrease as fact to reduction
order, NCCL, a sampler error or overfitting.

The [completed review](../../docs/research/pr87-completed-pair-review.md)
and [numerical claim manifest](claim-evidence.json) retain loop speedup2.167,
job speedup1.831, selected parent-macro F1 loss0.032468, and increased assigned
GPU-hours. CPUs scale4→16. This is one descriptive matched-work case with a
negative quality finding, not noninferiority, isolated GPU causality,
energy/financial savings or downstream Gurobi benefit. The PR89 CPU model
remains the original mixed checkpoint SHA256
a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028.

## E5 — Root relaxation, inference, starts and validity

### Three separate operations, already performed

1. **Capture a root vector once.** The historical
   [root preparer](../../scripts/evidence/pr86_root_preparation.py)
   reads the original model through NativeModel, forces MINIMIZE and sets
   Threads=1, Seed=42, Presolve=0, NodeLimit=1, TimeLimit=600,
   SoftMemLimit=48, OutputFlag=1 and LogToConsole=0. It calls optimize(observer).
   At GRB.Callback.MIPNODE it requires MIPNODE_STATUS==GRB.OPTIMAL and root
   node count near zero, reads cbGetNodeRel(ordered_variables), records
   MIPNODE_OBJBND, then calls terminate(). It captures the first qualifying
   root-node LP event. It does **not** call model.relax().optimize(), round
   an incumbent, or wait for every possible root cut pass. The captured bound
   is not asserted to equal the final best bound of the later MIP solve.
2. **Encode and infer once.** The
   [guidance preparer](../../scripts/evidence/pr86_guidance_preparation.py)
   binds model/root/checkpoint hashes and original variable identities.
   The graph encoder gives the captured values to variable channel6
   (zero-based), alongside original objective/bounds/types and coefficient
   edges. Reference labels serve a separate encoder feasibility audit;
   they are not forward inputs. The model is loaded strictly, put in eval
   mode and evaluated under torch.no_grad(). Logits→sigmoid→frozen threshold
   and class-aware selection produce G, not a new Gurobi solve.
3. **Construct R and solve fresh models.** R selects q largest root values
   as ones and k−q smallest remaining values as zeros, matching G's actual
   k/q, with name tie-breaks. It uses root values to choose its own indices.
   R therefore depends on G's preparation. B has no external start;
   R/G set selected binary Var.Start values and leave other variables
   GRB.UNDEFINED. The native backend attempts completion/repair.
   Start is neither a bound fixation nor proof of acceptance/feasibility.
   Each campaign cell then invokes the frozen solver once; receipt
   reconciliation, not source inspection alone, establishes actual calls.

This is a description of executed paths, not an alternative runbook.
PR89 reuses these roots, predictions and starts; none should be regenerated.
See official [cbGetNodeRel](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html#Model.cbGetNodeRel)
and [Start](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html#attr:Start).

### Seed42 and parallel determinism

Seed chooses an algorithmic search perturbation;42 is a reproducible protocol
choice, not a guarantee of identical terminal outcomes. With fixed inputs,
version, machine and suitable algorithms, parallel Gurobi can be deterministic.
Changing the thread cap changes the configuration; wall-time termination may
stop at different work points. Automatic/concurrent algorithm selection must
also be considered. See [official guidance](https://support.gurobi.com/hc/en-us/articles/360031636051-Is-Gurobi-deterministic)
and the [parameter reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html).

The frozen [PR89 parameter constructor](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/9ab7823c6886d19e9ec865141a1cd35b3c3c16e5/scripts/evidence/pr89_cpu_contract.py)
merges a hash-checked PR86 job3522 result with explicit cell settings and
TimeLimit=43200. Reading that embedded receipt gives:

| Parameter | Frozen inherited/requested value |
| --- | --- |
| Threads / Seed | Cell cap1/2/4/8/16 /42 |
| TimeLimit / SoftMemLimit | 43200 /48 |
| MIPGap / MIPGapAbs | 0.0001 /1e-10 |
| Method / Presolve / Cuts | −1 /−1 /−1 |
| Heuristics / MIPFocus | 0.05 /0 |
| StartNodeLimit / SubMIPNodes | −1 /500 |
| FeasibilityTol / IntFeasTol | 1e-6 /1e-5 |

Receipt source: [job3522 public return](../../docs/evidence/pr86/job3522/public_return.json),
outer SHA256 dd1a553b453289b23dbed3d52bd4bd7e0ac93eb2b4283597b788e406fcab6825,
decoded child SHA256 a10bcb4ed2a3e4b54a4ec268725cdf017ebc7432d57b4b16ed0531238ff2e104.
These are frozen requested values, not a newly collected effective-parameter
record for every PR89 cell. Method=−1 retains automatic selection, so a
strong determinism guarantee cannot be inferred from Seed42 alone.
ConcurrentMIP was not exported in that parameter dictionary; its effective
runtime value is **unavailable here**, not retroactively filled with a default.
No parameter is changed to improve this wording. WorkLimit is not substituted
for the authorized time limit. Existing parameter/log evidence may qualify
the assessment at final collection; no repetition is needed or authorized.

### Predictive and experimental validity

| Issue | Evidence and defensible interpretation | Remaining boundary |
| --- | --- | --- |
| Label quality | Feasible admitted incumbents with relative gap≤0.10 | Approximate, potentially multiple valid solutions; agreement is not optimality |
| Population | 54 admitted of90;34/10/10 split | Quality-selection bias, no hard generalization, exposed tests |
| Class imbalance | Test positives5265/5,536,400 | Accuracy or an all-zero Brier score alone can mislead; retain precision/recall, AP and parent-macro views |
| Weighted BCE | Train-fitted positive weight; validation threshold | Scores are not automatically calibrated event probabilities |
| Checkpoint | Validation-selected, original identities frozen | No test selection, retrospective substitution or retraining |
| Solver utility | Existing B/R/G parent-level comparisons | Predictive F1 does not establish solver gain; no causal selector ablation |
| Numerical/censoring | M4/M12 restrictions and observed follow-up | No exact-optimum or certified-speedup claims outside metric eligibility |
| PR89 | Approved60 submitted jobs, final return pending | No CPU12h results in this audit |

For the idealized conditional weighted-BCE risk, if p=P(y=1|x), its minimizer
is q*=w p/(w p+1−p). This elementary loss calculation explains why a sigmoid
near one under class weighting is not itself a calibrated probability.
It is not an estimate of this finite network's calibration. Validation-F1
thresholding and fitted probability calibration are different procedures.
Brier/ECE diagnostics do not turn label agreement into optimization utility.

## E6 — Critical bibliographic reconciliation

Use citations to support an actual sentence or methodological choice. Do not
import every missing Zotero item or count citations as scientific progress.
The earlier inventory found42 GNN items; collection overlap also requires
DOI/title matching because Gasse exists under distinct keys. That inventory
is not redone here. Zotero was used only to read the existing Vargas-Pérez PDF;
**no items, collections, metadata or attachments were modified**.

| Candidate group | Decision for this revision | Access / purpose |
| --- | --- | --- |
| Gasse and existing primal-guidance precedents | A: essential, already cited | Paper v3 plus pinned upstream code distinguish branching from partial starts |
| Kipf–Welling, Hamilton et al., Veličković et al., Brody et al. | A for the concise architecture distinction; add only these four foundations | Primary author full-text versions checked; one bibliographic record per work |
| Vargas-Pérez et al., DOI10.1109/TCSS.2024.3508452 | A for a specific reporting comparison, not a CFL efficacy claim | Full13-page PDF from Zotero; TablesIII–V visually checked |
| Broader MPNN/expressivity/benchmarking/calibration literature | B when an exact supplementary claim needs it; existing calibration citations retained | No assertion that every suggested work has been critically read |
| Social-dynamics applications with no transferable method point, unrelated domain winners | C or D for this article | Do not cite merely because an author or journal is prestigious |
| Fresh GCN/SAGE/GAT experiments | C: prospective | Not performed and not necessary to claim fixed-model conditional effects |

Vargas-Pérez, Giráldez-Cru, Mesejo and Cordón (IEEE TCSS12(2),725–737,
2025; online2024) infer bounded-confidence parameters in opinion dynamics.
This is regression with MSE, not imbalanced binary primal-value prediction.
Their TableIII varies layers{4,5}, width{16,32}, learning rate
{0.01,0.001,0.0001}, batch{2,4,8}:36settings×4architectures×2scenarios=288runs.
Those runs belong to that study, not CFL-GNN. MLP, GCN, GraphSAGE and GATv2
are compared; GATv2 should not be renamed GAT.

The synthetic datasets contain180 graphs per scenario derived from nine base
topologies and20 feature/threshold configurations, split115/29/36. Their own
footnote notes repeated topologies with different node features. Thus graph
count is not independent-topology count. External-topology evaluation is
a different generalization setting from our exposed benchmark parents.
GraphSAGE leads their synthetic comparisons, but the real-topology homogeneous
case also favours GATv2 in some comparisons. No universal architecture winner
or parameter-transfer justification follows for CFL. What transfers is the
clear separation of candidate settings, validation selection, test metrics,
parameter counts and training clocks.

The current article uses short claim-specific comparisons; it does not
become a GNN survey. No missing DOI or article pagination is invented.
The public Pages version may lag this PR.

## E7–E9 — Editorial integration, decisions and next action

The manuscript should explain the optimization problem first, then the
representation, actual update, supervised target, frozen selection and native
Start interface. Keep detailed architecture/hyperparameter tables here and
essential equations in the main text. Separate prediction, optimization,
training efficiency and bounded cost; retain adverse outcomes.

The [accelerated plan](../../docs/research/mvp2-20261028-accelerated-plan.md)
advances S1/S2/S4/S5 now. Final CPU-dependent S3 and the cross-artifact audit
remain gated by the existing campaign's terminal return. This document is
partial R2-D8 input, not a declaration that SO1–SO8 have been achieved.

Author decisions still needed at scientific review: defensibility of C1–C3
and final title, adequacy of fixed-model/no-architecture-ablation limits,
the bounded IIEA-S treatment, and final editorial/data-rights declarations.
No routine GitHub edit needs renewed permission. Merge, release, submission
and any future experiment retain separate human gates.

**One next operational priority:** finish source-linked editorial integration
in PR92 and circulate its existing-evidence review pack when verified. CPU
execution continues unchanged; the researcher supplies any later HPC query
or final collection command execution under the original contract.
