# Why this GNN, and what its experiments can establish

This supplement explains the modelling choices behind the CFL study and the
limits of the evidence. It should be read alongside the manuscript, especially
its distinction between prediction quality and optimization performance.
A network can predict many binary values correctly and still provide an
unhelpful starting point to a mixed-integer solver. Conversely, a small set
of useful assignments can improve a solve without maximizing classification
accuracy. The experimental question concerns that connection.

The implementation discussed here is the fixed Gasse-inspired model used to
prepare the CPU starts. The ongoing longer-horizon campaign reuses those
starts and the original checkpoint. Nothing in this methodological discussion
changes that campaign or constitutes a new experiment.

## Reading the prediction-to-optimization pipeline

Capacitated facility location asks where to open facilities and how to serve
demand while respecting capacities and minimizing cost. Its mixed-integer
linear programming (MILP) model contains discrete decisions coupled by
linear constraints. The solver must find good feasible solutions and assess
how far their objective values may be from the best possible value.

The neural network supplies selected binary values intended to help that
search. It does not replace the mathematical model or certify solution quality.
The stages answer different questions:

1. **Prepare structural information.** A stored root-relaxation vector and
   the model's coefficients describe the problem before the later B/R/G solves.
2. **Predict binary values.** A frozen graph neural network (GNN) converts
   these inputs into scores. No learning takes place during this inference.
3. **Select a partial Start.** A policy chooses a limited number of suggested
   values. Gurobi attempts to complete them while solving the original model.
4. **Evaluate the outcome.** Prediction quality, Start acceptance, solution
   quality, elapsed time and preparation cost are assessed separately.

An *incumbent* is the solver's best known feasible solution, subject to its
numerical tolerances. A *parent* is an original problem instance. A *checkpoint*
stores learned weights and associated model state. An *embedding* is a
learned vector summarizing a node's information. A *logit* is an unrestricted
network output; the sigmoid maps it to a score between zero and one.

B, R and G are the article's names for historical methods M0, M1 and M2.
A medium parent called M0 is an instance identifier, not method M0.

## 1. Why represent the MILP as a bipartite graph?

A linear constraint couples variables through its nonzero coefficients.
Representing variables and constraints as two kinds of nodes therefore gives
the network access to the structure that the solver sees. A variable receives
information from the constraints in which it participates; a constraint
combines information from its incident variables. Coefficients remain edge
attributes, so two otherwise similar connections can convey different
numerical information.

This choice follows [Gasse et al. (2019)](https://arxiv.org/abs/1906.01629v3).
Their network learns a branching decision within SCIP. Our adaptation learns
binary values from checked incumbent solutions and passes selected values
to Gurobi as a partial start. The prediction target, loss and solver interface
are consequently different. It would be inaccurate to describe the present
model as a complete reproduction of their method.

It is also useful to distinguish this model from other familiar GNNs.
[GCN](https://arxiv.org/html/1609.02907v4) uses degree-normalized propagation;
[GraphSAGE](https://arxiv.org/html/1706.02216v4) combines a node representation
with an aggregate of its neighbours; [GAT](https://arxiv.org/html/1710.10903v3)
and [GATv2](https://arxiv.org/html/2105.14491v3) learn attention weights over
neighbours. Our model uses coefficient-aware message functions, sum aggregation
and separate variable/constraint updates. These alternatives are conceptually
relevant, but their existence does not establish an empirical ranking on CFL.
The repository's optional BiGNN attention block is dense dot-product attention,
not a GAT or GATv2 experiment.

### From coefficients to predictions

The input has seven variable channels: transformed objective coefficient,
lower and upper bounds, three type indicators and the captured root-relaxation
value. Rows have five channels: transformed right-hand side, three sense
indicators and a constant. Each edge carries one transformed coefficient.
Signed logarithms and clipping control the range of numerical inputs;
they do not change the coefficients, domains or feasible region of the
optimization model. Clipping can discard scale information, so it is an
encoding choice with limitations, not an exact representation of every number.

Message passing can be understood as an exchange of summaries. A constraint
collects information from the variables that occur in it. Each variable then
receives information from its constraints, including their other variables.
Learned message functions determine which combinations of features are useful.

To connect this description to the equations, let $v_j^{t-1}$ be variable j's
current embedding and $c_i^{t-1}$ constraint i's embedding before cycle t.
Each cycle updates constraints first, then variables:

$$
c_i^t=\operatorname{ReLU} f_C^t\!\left[c_i^{t-1}\Vert
 P_C^t\!\left(\sum_{j\in N(i)}g_C^t[c_i^{t-1}\Vert v_j^{t-1}\Vert e_{ij}]\right)\right],
$$

$$
v_j^t=\operatorname{ReLU} f_V^t\!\left[v_j^{t-1}\Vert
 P_V^t\!\left(\sum_{i\in N(j)}g_V^t[c_i^t\Vert v_j^{t-1}\Vert e_{ij}]\right)\right].
$$

Here $N(i)$ and $N(j)$ are the relevant neighbours, $e_{ij}$ is an encoded
coefficient and $\Vert$ joins vectors. The sums combine incoming messages.
Each g or f is a small feed-forward network with two learned linear
transformations and a rectified linear unit (ReLU) between them; ReLU replaces
negative activations by zero. P is a fixed affine normalization fitted on
training graphs. The second equation uses the newly updated constraints,
so information from other incident variables reaches a variable in the same
cycle. The final prediction head produces one logit per binary variable.

Two cycles allow information to travel up to four edges in the bipartite
graph. This is a reason to consider more than one cycle when predictions
depend on interacting constraints. It does not imply that four-edge
neighbourhoods are sufficient for all CFL decisions. Shared message functions
also permit application to different graph sizes, but architectural
applicability is not evidence of independent statistical generalization.

## 2. Why these hyperparameters?

A defensible explanation must separate three things: the value actually used,
the methodological reason for considering it, and evidence that it performs
better than alternatives. Our records establish the first. Literature and
the structure of the task can inform the second. For most fixed choices,
the third has not been measured.

In particular, no inspected configuration or historical receipt documents
a search that selected two cycles and width 32 over one cycle and width 64.
The configuration must therefore be treated as fixed, not optimal. The
rationale below explains why it is a reasonable starting point; it does not reconstruct an
undocumented original decision or turn a fixed setting into a validated optimum.

### Network capacity and numerical scale

The upstream Gasse baseline uses one cycle and width 64. The present two-cycle,
width-32 adaptation trades a longer local information path against a smaller
representation. Both are meaningful design dimensions: depth determines how
far information propagates, while width affects the capacity and cost of
the learned message functions. For this implementation, their leading dense
message cost scales approximately with L(E+N)d², where L is the number of
cycles, E and N are edge/node counts, and d is width. This is an analytical
scaling argument, not a measured speed or memory comparison with Gasse's
different implementation.

A shallow model with modest width is therefore a parsimonious starting point
for large coefficient graphs. Neither Gasse's results nor this argument proves
that 2×32 is preferable on our instances. The correct claim is evaluation of
one fixed model. Claims of architectural superiority would require controlled
comparisons that are currently absent.

Sum aggregation preserves the contribution of repeated incident messages,
but its magnitude depends on node degree. Fixed prenormalization addresses
activation scale. In the version used here, variable-side statistics are fitted
after the corresponding constraint update, using training graphs only.
This differs from the legacy fit procedure. The versions and their buffers
cannot be interchanged retrospectively; “calibrated” in a source filename
does not mean that output probabilities have been calibrated.

### Learning the predictor, handling imbalance and selecting its output

[Kingma and Ba (2015)](https://arxiv.org/abs/1412.6980) provide the basis for
Adam and identify 0.001 as a useful default learning rate in their experiments.
This supports using it as a conventional starting point. It does not show
that it is optimal for this GNN. The implementation fixes that rate and does
not invoke a learning-rate scheduler in the relevant training paths. Other
Adam arguments use the installed runtime defaults and were not tuned separately.

Gradient-norm clipping limits the size of an unusually large gradient before
an update. [Pascanu et al. (2013)](https://proceedings.mlr.press/v28/pascanu13.html)
explain this stabilization principle in recurrent-network training. That
reference motivates the operation; it is not CFL-specific evidence for our
threshold of 1. The threshold is a fixed implementation choice whose
sensitivity remains unmeasured.

The loss addresses a different concern. Training labels say whether each
binary variable is zero or one in a checked reference incumbent. Such an
incumbent need not be an exact optimum or the only useful solution.
Learning its labels is a prediction task, not an optimality proof.

Positive labels are rare. Predicting mostly zeros can look accurate while
missing the decisions that motivate a positive-first Start policy.
The training loss is binary cross-entropy (BCE), with positive errors weighted
by the training negative-to-positive ratio. This gives missed positive labels
more influence during learning; it does not create additional positive examples.

The weighting changes the meaning of a score. For an idealized conditional
probability p that the reference label is one and a positive loss weight w,
the expected loss is $-wp\log q-(1-p)\log(1-q)$. It is minimized at
$q^\star=wp/(wp+1-p)$. This is a property of the loss, not a new fitted result.
For 0<p<1 and w>1, the minimizing score is shifted upward relative to p.
A score close to one therefore need not be a calibrated probability that
the proposed assignment is correct. A threshold chosen for validation F1
does not remove this distinction.

Precision measures how often predicted ones agree with the reference labels;
recall measures how many reference ones are recovered. F1 combines them.
These metrics assess the predictor; the solver must still determine whether
the selected values lead to useful feasible solutions.

The 100-epoch limit bounds the training schedule. Validation loss, rather
than the last epoch, selects the retained checkpoint; validation F1 selects
the classification threshold. These are actual data-dependent selections.
The architecture, learning rate and epoch ceiling are fixed settings.
This distinction is important because observing a useful validation minimum
does not justify every other hyperparameter retrospectively.

| Choice | Value used | Rationale and evidential limit |
| --- | --- | --- |
| Propagation / width | Two cycles / 32 channels | Local structural context with modest capacity; no comparative tuning evidence |
| Messages / activation | Coefficient-aware MLPs, sum, ReLU | Preserve typed variable/constraint interactions; no aggregation or activation ablation |
| Prenormalization | Alternating, training-only, fixed buffers | Control activation scale without fitting on validation/test; version-specific |
| Optimizer / rate | Adam / 0.001 | Literature-supported default, not a CFL-selected optimum |
| Clipping | Gradient norm 1 | Stabilization safeguard; numerical threshold not validated by sensitivity analysis |
| Sampling | Four draws per training parent per epoch | Equal presentation counts across parents; does not make binary variables independent samples |
| Historical graph batch | One graph | Actual original training path; no batch-size search |
| Matched GPU batch | Four graphs globally | Equal work per serial/DDP update, not a prediction-quality optimization |
| Training / checkpoint | At most 100 historical epochs, patience 100; validation-loss selection | Selected historical checkpoint is epoch 34, not the terminal state |
| Matched GPU schedule | 100 epochs, no early stopping | Validation selects epochs 99/92; both arms complete the same update budget |
| Positive weight / seed | Training class ratio / 42 | Imbalance handling and fixed initialization setting; no training-seed robustness estimate |
| Classification threshold | Original CPU 0.9991843104362488, selected by validation F1 | Model-specific decision rule, not evidence of probability calibration |
| Start policy | Requested support bounded by 10% and 20,000 values; ones before zeros; abstention if no predicted one | Limit the information supplied and retain rare positives; no causal selector or support-fraction ablation |

The batch distinction deserves emphasis. Historical serial training and the
later matched GPU experiment have different update schedules. In the latter,
four graph-mean losses form one update. Its serial arm accumulates four
losses divided by four; DDP averages one gradient per rank. Clipping and
Adam are applied once after that aggregation. This matches the mathematical
objective, not necessarily the floating-point trajectory.

The observed GPU comparison remains an adverse quality finding: training
is faster, but selected parent-macro F1 falls by 0.032468 and assigned
GPU-hours increase. A higher speedup does not justify replacing the original
CPU checkpoint or claiming downstream optimization benefit.

## 3. From a relaxation to scores and a partial Start

A linear relaxation allows integer-constrained variables to take fractional
values. It can describe the optimization landscape without being a feasible
mixed-integer solution. The root relaxation is considered at the initial node
of the solver's search. Here its recorded vector is a feature source and
comparator input, not a predicted integer solution. In the existing preparation, Gurobi reads the original
MILP under the minimization convention. A callback captures variable values
at the first optimal root-node LP event and terminates that preparation.
A callback is code invoked when the solver reaches a specified event.
The implementation calls `cbGetNodeRel` at an eligible `MIPNODE` event to
read the relaxation values. It does not call `model.relax()` as a separate
LP solve. Nor does the captured vector necessarily describe the final root
bound after every possible cutting-plane pass.

The captured values are aligned with original variable identities and enter
the graph. A frozen model in evaluation mode maps that graph to binary-variable
scores without gradient computation. Labels inspected by the encoder belong
to a separate feasibility audit; they are not supplied to the neural forward
or used to choose a start.

### Why R depends on G

For n eligible binary variables, the requested assignment budget is
$K=\min\{n,20000,\max(1,\lfloor0.10n\rfloor)\}$.
This limits the number of supplied values, not the feasible region.
The absolute cap binds for the medium parents, so their coverage is below 10%.

G first selects predicted ones in descending score order. If fewer than K
are available, it fills the remaining slots with predicted zeros in descending
zero-confidence order. Variable names break ties. If no one is predicted,
the policy abstains and supplies no assignments.

Let k be the number actually supplied and q the number assigned one.
R ranks the stored root values, clipped to [0,1]: the q largest receive one,
followed by the k−q smallest remaining values receiving zero, with name-based
tie breaking. R matches the amount of supplied information and its one/zero
composition, rather than copying G's selected indices.

For a schematic example of this matching, suppose G supplies
$x_a=1,x_b=0,x_c=0$. R could instead supply $x_d=1,x_e=0,x_c=0$.
Both contain three assignments and one positive, yet suggest different
variables. This invented example illustrates count matching only; it is not
an experimental result or an application of the study's support formula.

Thus R depends on G's preparation. It asks how LP-ranked information compares
with learned information at a matched support/composition budget. It does
not estimate the performance or preparation cost of a standalone LP heuristic.

### What the solver receives

A fresh copy of the model receives the selected values through Gurobi's
`Start` attribute. Other variables remain unspecified, using
`GRB.UNDEFINED`; the original bounds are preserved. A supplied value of one
is a candidate starting value, not a constraint requiring the final solution
to keep that value. B supplies no external Start, while Gurobi's internal
heuristics remain available.

The [Gurobi Start documentation](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html#attr:Start)
describes attempts to complete partially supplied starts. Supplying values
does not ensure acceptance, improvement or feasibility of the partial
prediction as a complete solution. Here a loaded-start message records solver
acceptance under its numerical conventions. It is not an exact feasibility
certificate or evidence that the later search improves. B, R and G preserve
the same mathematical model and compare its response to different information.

## 4. What repeatability means for the solver comparison

Three questions should not be conflated. Can another researcher reconstruct
the same experiment? Would the solver follow the same algorithmic path on
an identical run? Would it stop at exactly the same state after a specified
number of seconds? Complete provenance supports the first; the other two
also depend on algorithms, environment and stopping conditions.

Method=−1 specifies automatic selection of the continuous algorithm. It
controls the continuous algorithm, including the MIP root relaxation; it does
not select the entire MIP search strategy. The
[Gurobi 13.0 parameter manual](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html#parameter:Method)
describes dual simplex as the usual automatic MIP-root choice and deterministic
concurrent variants for some large roots. Its usual automatic choice for a
standalone continuous LP is different. Automatic selection alone is therefore
not evidence that our MIP jobs ran a non-deterministic algorithm.

The [official determinism guidance](https://support.gurobi.com/hc/en-us/articles/360031636051-Is-Gurobi-deterministic)
conditions repeatability on inputs, version and machine, and distinguishes
parallel optimization from time-dependent stopping. Seed 42 fixes a search
perturbation; it neither makes all seeds equivalent nor ensures identical
wall times. Even an explicitly deterministic root algorithm would not make
a time-limited solve stop at exactly the same work point.

We retain Method=−1 because it belongs to the frozen protocol. Existing logs
can clarify which root algorithm actually ran; absent information must remain
unavailable. In particular, ConcurrentMIP was not exported in the inherited
parameter dictionary, so its effective value must not be reconstructed from
a documented default. No job is rerun to fill such a field.

### What can be concluded from the existing runs?

The comparisons are observations under a specified configuration. Within each
parent, thread cap and seed, B/R/G use the same parameter settings and differ
in their external starts. Identical search paths are not required: changing
the search is precisely how a start can help or harm. What is required is
consistent model identity, resource/stopping rules and a clear account of
which outcome is compared.

For each eligible parent we can report the observed primal objective, dual
bound, terminal gap and follow-up. We can compare recorded time to a common
target when both runs attain it and show censored runs separately. We cannot
estimate across-seed variability from one seed, treat thread caps as repeated
trials, or generalize an observed timing ratio into a stable expected gain.
Numerical restrictions on M4/M12 remain independent of these timing issues.

This is a narrower claim than robust superiority, but it is still informative:
it shows where one frozen predictor helps, fails or costs more under the
reported conditions. Gurobi's
[comparison guidance](https://support.gurobi.com/hc/en-us/articles/26992650628369-How-can-I-make-accurate-comparisons)
recommends accounting for performance variability, including using different
seeds when instances are limited. Our single-seed principal analysis does not
meet that stronger robustness objective. Transparent reporting is necessary;
it does not make the missing variability estimate disappear.

### Reading prediction and optimization outcomes together

For minimization, a feasible incumbent gives an upper bound on the best
objective, while a valid solver lower bound describes what might still be
achievable. Improving the incumbent and strengthening the lower bound are
different forms of progress. Their relative separation is the MIP gap;
a smaller gap is not synonymous with a better incumbent.

| Observation | What it can support | What it does not establish |
| --- | --- | --- |
| Higher validation or test F1 | Better agreement with the specified labels and averaging rule | A better Start or faster optimization |
| A user Start is loaded | Solver acceptance under its conventions | Exact feasibility, optimality or a later gain |
| A 10% gap crossing is recorded | That endpoint was observed by the recorded time | Attainment of the tighter terminal criterion |
| A time limit is reached | The solver stopped because its time budget ended | That every gap target was unobserved, or that runtime is a successful time-to-target |
| Optimal status or zero displayed gap | A numerical solver outcome under the stated tolerances | An exact mathematical certificate; M4/M12 restrictions remain |
| A shorter training loop | Less elapsed time inside that loop | Lower whole-job cost, preserved F1 or better CPU starts |

The configured terminal MIPGap of 0.0001 corresponds to 0.01%, whereas
10% is a separate, less demanding descriptive threshold.
The [historical endpoint reconciliation](../../docs/research/mvp2-r3-metrics-and-reproducibility.md#historical-endpoint-reconciliation--28-october)
explains why the archived terminal `right_censored` flag is not the censoring
indicator for every threshold. Missing observations and numerically restricted
comparisons require their own dispositions.

The completed evidence chains also answer different questions. Historical
six-medium optimization results retain their original population. The principal
CPU comparison uses ten exposed parents at seed 42; method/cap rows are repeated
conditions within those parents. The later GPU pair studies training speed,
quality and assigned resources with a different update schedule. Its faster
loop and lower selected F1 cannot be transferred into a claim about the original
checkpoint's downstream utility. These boundaries are carried into the article;
the longer-horizon CPU return remains pending.

## 5. What further experiments would add

Changing a seed is a robustness check, changing Method is solver-configuration
sensitivity, and removing a model/policy component is an ablation. They answer
different questions. A large Cartesian product of all three would be costly
and difficult to interpret.

The companion [sensitivity assessment](sensitivity-review-plan.md) recommends
completing the existing evidence and keeping these unresolved questions visible
in the manuscript now. A small, separately approved follow-up can be designed
if a coauthor or reviewer identifies a specific claim that needs it. Two
additional solver seeds at one fixed thread cap would address search-path
sensitivity more directly than an immediate survey of GCN, GraphSAGE and GAT.
Testing an explicit root method would be justified by a concrete configuration
question, not by assuming Method=−1 invalidates the campaign.

Deferral is defensible only when the conclusions are limited accordingly.
A limitations paragraph cannot support a present claim of seed robustness,
architectural superiority or causal benefit from class-aware ordering.
If any of these becomes central to the claimed contribution, the missing
comparison must be addressed or the claim removed before submission.
Reviewer requests are a possible trigger for follow-up, not the sole test
of scientific sufficiency.

## Finding exact values and source files

Use the [configuration reference](configuration-reference.md) to locate the
inputs and parameter values discussed here. It separates root preparation,
historical training, CPU solves and the matched GPU pair, with links to their
versioned files. The rationale above explains why a choice is reasonable;
the reference identifies whether its value was fixed, selected on validation
data or recorded in an existing receipt.

## Implementation and evidence sources

The narrative above uses the
[28 October source snapshot](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/tree/e5c3ba0e77ea87905fa7986a70567523166156df).
The [model](../../src/cfl_gnn/models/gasse.py),
[versioned prenorm](../../src/cfl_gnn/models/gasse_calibrated.py),
[training configuration](../../configs/training/gasse_pr57_54_v1.json)
and [matched updates](../../src/cfl_gnn/training/matched_gpu.py)
establish the implemented choices. Static layer counting gives 26,753
trainable scalars for the configured model, excluding prenorm buffers;
this is not a runtime memory measurement.

The upstream comparison uses
[learn2branch at commit 57e82603](https://github.com/ds4dm/learn2branch/tree/57e82603fba39c34ff81baf9bd0b5768f5a1a860).
Its facilities generator and branching data are not our benchmark cohort.
No generator or formulation certification is reopened.

[Root preparation](../../scripts/evidence/pr86_root_preparation.py),
[guidance preparation](../../scripts/evidence/pr86_guidance_preparation.py)
and the [native solver path](../../scripts/evidence/pr86_solver.py)
document the interface. The [R3 methods](../../docs/research/mvp2-r3-methods-and-models.md),
[metric definitions](../../docs/research/mvp2-r3-metrics-and-reproducibility.md),
[completed GPU review](../../docs/research/pr87-completed-pair-review.md)
and [numerical claim map](claim-evidence.json) retain exact provenance and
qualifications. The installed CPU source and original checkpoint remain
unchanged; the final CPU return is still pending.
