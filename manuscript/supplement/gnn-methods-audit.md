# Appendix A: Model and Method Details {#sec-supp-methods}

This appendix follows the information supplied to the solver: mathematical coefficients and a root-relaxation vector become graph features, neural scores and selected binary values. The distinction matters because a prediction, a partial candidate and an accepted feasible incumbent are different objects. The numerical settings and their sources are collected in Appendix C.

## A.1. Representation and information exchange

A variable node represents a column of the MILP; a constraint node represents a linear row. A nonzero matrix coefficient creates an edge between them. A constraint can therefore collect information from the variables that determine its activity, and a variable can receive information from the constraints in which it participates. Coefficients describe those connections rather than merely indicating that they exist.

The encoder supplies seven variable channels, five constraint channels and one edge channel. Numerical features are clipped and transformed to control scale. This encoding is a learning representation; it does not modify the coefficients used by the solver. Root values are aligned with the original variable identities, so that a prediction is returned to the correct binary column.

The representation is inspired by @gasse2019, but the target is different: their model predicts branching choices, whereas this study predicts binary reference values and supplies partial Starts. The upstream facilities generator and branching dataset are not the evaluated MILPBench population.

Let $v_j^{t-1}$ and $c_i^{t-1}$ be the variable and constraint embeddings before propagation cycle $t$. The constraint update precedes the variable update:

$$
c_i^t=\operatorname{ReLU} f_C^t\!\left[c_i^{t-1}\Vert
P_C^t\!\left(\sum_{j\in N(i)}
g_C^t[c_i^{t-1}\Vert v_j^{t-1}\Vert e_{ij}]\right)\right],
$$

$$
v_j^t=\operatorname{ReLU} f_V^t\!\left[v_j^{t-1}\Vert
P_V^t\!\left(\sum_{i\in N(j)}
g_V^t[c_i^t\Vert v_j^{t-1}\Vert e_{ij}]\right)\right].
$$

Here $N$ denotes neighbours, $e_{ij}$ an encoded coefficient and $\Vert$ concatenation. Each message or update function is a small feed-forward network with two learned linear transformations and a ReLU between them. ReLU replaces negative values by zero. The sums aggregate incoming messages. Each $P$ is a fixed affine prenormalization fitted on training graphs. The second equation uses the newly updated constraints, allowing information from other incident variables to reach a variable within the same cycle.

The implementation uses two cycles and width 32. Two cycles permit propagation over up to four bipartite edges; that is not evidence that this neighbourhood suffices for all CFL decisions. Sharing message functions permits inputs of different sizes, but architectural applicability is distinct from statistical generalization.

## A.2. Architectural context and fixed hyperparameters

GCN uses degree-normalized propagation [@kipf2017]. GraphSAGE combines a node representation with an aggregation of its neighbours [@hamilton2017]. GAT and GATv2 learn attention weights [@velickovic2018; @brody2022]. The evaluated network instead uses coefficient-aware message functions, sum aggregation and separate constraint/variable updates. The optional dense attention block elsewhere in the repository is not a GAT or GATv2 experiment.

Other graph-based optimization tasks include search-node comparison [@labassi2022], objective prediction [@scavuzzo2024] and cut selection [@zhang2026]. Expressiveness results for branching and quadratic optimization concern their stated tasks [@chen2024branching; @chen2024quadratic]. In a different application, @vargas2025 compare GNN variants for opinion-dynamics regression. These studies motivate attention to representation and validation, but none establishes a preferred architecture for the present CFL Starts.

A recorded value, a methodological rationale and evidence of comparative performance have different roles. The configuration establishes what was used. Task structure and literature can explain why it is reasonable to consider a choice. Only a relevant comparison could establish that it is preferable.

The upstream branching baseline uses one cycle and width 64. The two-cycle, width-32 adaptation exchanges information over a longer local path with smaller embeddings. For this implementation, the leading dense-message cost scales approximately as $L(E+N)d^2$, with cycles $L$, edge/node counts $E,N$ and width $d$. This analytical argument motivates a modest fixed capacity; it is not a measured comparison with the different upstream implementation or evidence of optimality.

| Choice | Value or rule | Rationale and evidential scope |
|:--|:--|:--|
| Propagation and width | Two cycles; 32 channels | Typed structural exchange with modest capacity; no comparative architecture selection |
| Message functions | Coefficient-aware MLPs, sum and ReLU | Preserve variable--constraint interactions; no component ablation |
| Prenormalization | Training-only alternating fixed statistics | Controls activation scale; fitted buffers are version-specific |
| Optimizer and rate | Adam; 0.001 | Conventional default motivated by @kingma2015; no CFL learning-rate search |
| Gradient clipping | Global norm 1 | Limits large updates; stabilization motivated by @pascanu2013, not validation of this numerical threshold |
| Historical sampling | Four balanced draws per training instance per epoch | Equal instance presentations; dependent binary targets are not independent instances |
| Training budget | At most 100 historical epochs; patience 100 | Fixed ceiling; validation loss, rather than the last epoch, selects the retained checkpoint |
| Classification threshold | Maximum pooled validation F1 | Validation-selected decision rule, not probability calibration |
| Start support | At most 10% and 20,000 values, with ones first | Limits supplied information; no support-fraction or selector ablation |

Sum aggregation depends on node degree, which motivates prenormalization of activation scale. In the version used here, variable-side fitting follows the corresponding constraint update and uses training graphs only. A source filename containing “calibrated” describes this versioned internal normalization, not calibrated output probabilities. Legacy fitted buffers are not interchangeable with this state.

## A.3. Labels, loss and selected outputs

A label says whether a binary variable is zero or one in a checked reference incumbent. The incumbent may be approximate and need not be the only useful feasible solution. Positive labels are rare, so the weighted BCE loss increases their contribution using the training negative-to-positive ratio.

This weighting changes the interpretation of a score. For an idealized conditional reference-label probability $p$ and positive weight $w$, expected loss is

$$-wp\log q-(1-p)\log(1-q).$$

It is minimized at $q^\star=wp/(wp+1-p)$. For $0<p<1$ and $w>1$, the score is shifted upward relative to $p$. This is a property of the loss, not a fitted result. It explains why a high sigmoid score is not automatically a calibrated probability and why selecting a validation-F1 threshold does not provide calibration.

Precision measures agreement among predicted ones; recall measures recovery of reference ones; F1 combines them. These are predictive criteria. The solver must still determine whether the selected values yield a useful feasible incumbent and improve optimization.

The original CPU predictor and the matched GPU pair use distinct schedules. Historical training updates after one graph. In the matched comparison, four graph-mean losses form one update: serial training accumulates four losses divided by four, while DDP averages one gradient per rank. Clipping and Adam occur once after this aggregation. This matches the objective and work per update without requiring identical floating-point trajectories.

## A.4. Relaxation, inference and partial-Start construction

A linear relaxation permits fractional values for integer-constrained variables. Its solution is informative about the model but need not be a feasible mixed-integer solution. Preparation reads the original model under MINIMIZE and records the first optimal root-node relaxation at an eligible MIPNODE event using cbGetNodeRel. A callback is code invoked when the solver reaches a specified event. The capture terminates that preparation run; it does not use a separate model.relax() solve or claim to include every later root cut.

The captured vector, coefficient features and binary mask are aligned with original variable identities. A frozen model in evaluation mode maps the graph to binary-variable scores without gradients. Labels read by a separate feasibility audit are not neural inputs and do not select the Start.

For $n$ eligible binary variables, requested support is
$K=\min\{n,20000,\max(1,\lfloor0.10n\rfloor)\}$. Support means the variables for which values are supplied, not a restricted feasible region. On medium instances the absolute cap binds, so the actual coverage is about 1.68--1.74%, rather than 10%.

G selects predicted ones in descending score order, then fills remaining positions with predicted zeros in descending zero-confidence order. Variable names resolve ties. If there is no predicted one, it abstains. Let $k$ be the actual number of assignments and $q$ the number assigned one. R clips LP scores to $[0,1]$, assigns one to the $q$ largest, and zero to the $k-q$ lowest remaining values.

For example, G might supply $x_a=1,x_b=0,x_c=0$ while R supplies $x_d=1,x_e=0,x_c=0$. Both have three assignments and one positive, but different supports. This schematic example illustrates matching only; it is not an experimental result or an application of the support formula.

| Step | B | R | G |
|:--|:--|:--|:--|
| Starting information | None supplied externally | Stored LP ranking plus G's actual $(k,q)$ | Frozen GNN scores and selected threshold |
| Selection | No external assignments | Highest $q$ LP scores, then lowest $k-q$ remaining | Predicted ones first, then confident zeros |
| Solver input | No external Start | Native partial Start | Native partial Start |
| Unselected variables | Original domains | Original domains; Start unspecified | Original domains; Start unspecified |
| Interpretation | Internal solver heuristics remain available | LP-ranked, G-dependent matched control | Full learned starting information |

A fresh model receives the assignments through Start, with GRB.UNDEFINED elsewhere. A supplied one is a starting value, not a constraint fixing the final solution. A loaded-start message records acceptance under the solver's numerical conventions; it does not prove exact feasibility, optimality or later performance. R's dependence on G is also a computational dependency: its comparison is not the cost of an independently prepared LP heuristic.

## A.5. Position among related solver interfaces

The table distinguishes how information is supplied, not a replicated performance ranking. The problems and endpoint definitions of the cited papers differ from this study.

| Work and problem scope | Predicted information | Solver interface and feasible-region treatment |
|:--|:--|:--|
| @gasse2019: learned branching on MILP families | Branching decision | Variable selection within search; a different target from a primal Start |
| @khalil2022: binary MILPs | Variable biases from near-optimal solutions | Solver guidance including warm-starting; a direct precedent for neural Starts |
| @nair2020: diverse mixed-integer programs | Multiple partial integer assignments | Remaining smaller MIPs are solved; assignments restrict the associated subproblem |
| @han2023: MILP benchmarks | Variable predictions | Search within a ball around predicted values, rather than unrestricted native Start completion |
| @canturk2024: learned primal MILP heuristics | Predictions with uncertainty | Reduction and guided subproblem search; different restriction/selection mechanisms |
| Present CFL study | Scores for binary incumbent labels | One partial candidate per G condition; original full feasible region retained |

Primal solution quality, primal-dual gap and computation time must be interpreted within each work's solver, stopping rule and dataset. Neural Diving combines diving and branching components in its evaluated solver; Predict-and-Search reports its own search procedure. Their aggregate improvements cannot be attributed to the interface alone or imported as CFL effect sizes.

For computational economics, comparable accounting would need to align training, feature construction, inference, candidate generation and solver time. This study does not normalize those papers' preparation costs to its CFL protocol and draws no claim that they omit such costs. Its measured and scenario-based accounting concerns its own B/R/G pipeline.

## A.6. Repeatability and scientific interpretation

Gurobi documents deterministic conventional parallel MIP under controlled model, parameter, attribute, version and hardware conditions [@gurobideterminism2025]. Different starts and thread counts are different inputs and can yield different search paths. Concurrent MIP is a distinct mechanism that runs independent searches; requesting multiple threads does not by itself identify that mode.

The recorded Method=-1 selects the continuous/root algorithm automatically; it does not mean that dual simplex was explicitly requested or that the MIP run was necessarily nondeterministic. The actual selected root algorithm and unexported settings remain unavailable. Seed 42 holds one search perturbation fixed, without controlling all other inputs.

TimeLimit can stop otherwise repeatable search after different amounts of work as timing conditions change. WorkLimit is a distinct, work-based budget, not a conversion of elapsed seconds or a retrospective replacement. Appendix C explains the configuration record, software guarantees and interface differences.

The comparisons describe observed outcomes under each configuration. They do not estimate across-seed variance, demonstrate stable expected speedups or make thread conditions independent trials. Start acceptance, first observed 10% crossing, terminal status and exact optimality are distinct. MIPGap=0.0001 equals 0.01%, not the 10% descriptive threshold.

M4/M12 retain their metric-specific numerical restrictions. More elapsed time or a solver-reported optimal status does not automatically remove them. Missing data, censoring and numerically restricted comparisons retain separate dispositions.

## A.7. Implementation sources

Fixed-revision sources document the
[model](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/e5c3ba0e77ea87905fa7986a70567523166156df/src/cfl_gnn/models/gasse.py),
[versioned prenormalization](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/e5c3ba0e77ea87905fa7986a70567523166156df/src/cfl_gnn/models/gasse_calibrated.py),
[root capture](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/e5c3ba0e77ea87905fa7986a70567523166156df/scripts/evidence/pr86_root_preparation.py),
[guidance preparation](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/e5c3ba0e77ea87905fa7986a70567523166156df/scripts/evidence/pr86_guidance_preparation.py)
and [native Start path](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/e5c3ba0e77ea87905fa7986a70567523166156df/scripts/evidence/pr86_solver.py).
The [upstream implementation](https://github.com/ds4dm/learn2branch/tree/57e82603fba39c34ff81baf9bd0b5768f5a1a860) is retained as architectural provenance. Source identities do not replace the per-model and per-outcome qualifications.
