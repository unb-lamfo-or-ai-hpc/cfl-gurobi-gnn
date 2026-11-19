## A.8. Mathematical foundations of inference, labels and training {#sec-gnn-mathematical-foundations}

This section develops the mathematical description of the Gasse-inspired 2 × 32 implementation. It complements the concise method specification above and distinguishes the historical training protocols. Numerical settings and counts reported here describe those historical protocols; they do not establish the results of a different training population.

### A.8.1. Scope and main distinctions

Four distinctions are essential. First, the network contains two bipartite convolution layers, rather than merely two dense hidden layers. Each convolution contains four small multilayer perceptrons (MLPs), each with two affine transformations. Second, the LP relaxation supplies an input feature, whereas supervised labels come from a feasible integer incumbent. Third, the MIP gap qualifies the incumbent globally; it does not determine a separate label quality for each variable. Fourth, the 26,753 trainable parameters are shared across nodes and graphs, rather than assigned separately to millions of MILP variables.

The information flow is:

1. Original MILP: matrix $A$, objective coefficients $c$, right-hand sides $b$, bounds and variable domains.
2. Root relaxation: a continuous vector $r$.
3. Integer MILP incumbent: a source of binary labels $y$.
4. Bipartite graph: seven variable features, five constraint features and one edge feature.
5. Variable and constraint encoders, convolution 1, convolution 2 and an output MLP: embeddings of width 32 and 26,753 trainable parameters.
6. Logits, followed by sigmoid scores.
7. During training, comparison with $y$ through weighted binary cross-entropy (BCE); during inference, no access to $y$.

The graph represents the optimization problem. The incumbent supplies supervision for learning binary decisions.

### A.8.2. Representing a MILP with millions of variables

Consider
$$
\begin{aligned}
\min_{\mathbf{x}}\quad &\mathbf{c}^{\top}\mathbf{x}+c_0\\
\text{subject to}\quad&A\mathbf{x}\ \bowtie\ \mathbf{b},\\
&\boldsymbol\ell\leq\mathbf{x}\leq\mathbf{u},\\
&x_j\in\mathbb R,\ \mathbb Z\ \text{or }\{0,1\},
\end{aligned}
$$
where the last line denotes the specified domain of each variable, and $\bowtie$ denotes the row-specific constraint sense. Let $n$ be the number of variables, $m$ the number of constraints, $A\in\mathbb R^{m\times n}$ the sparse constraint matrix, and $E=\operatorname{nnz}(A)$ its number of nonzero coefficients.

The bipartite graph has $n+m$ nodes. Every nonzero $A_{ij}$ creates an edge between constraint $i$ and variable $j$. Even with a million variables, this representation does not construct a dense million-by-million matrix. It stores the $E$ nonzeros and their endpoint indices.

#### A.8.2.1. Variable features

The seven channels are
$$
\mathbf{x}^{V}_j=
\begin{bmatrix}
\phi(c_j)\\
\phi(\ell_j)\\
\phi(u_j)\\
\mathbb 1[x_j\text{ is continuous}]\\
\mathbb 1[x_j\text{ is binary}]\\
\mathbb 1[x_j\text{ is integer}]\\
r_j
\end{bmatrix}\in\mathbb R^7,
\qquad
\phi(t)=\operatorname{sgn}(t)\log(1+|t|).
$$
The first three channels use this signed logarithm after the encoder's handling of nonfinite values and numerical clipping. The LP channel is not log-transformed; its numerical sanitization follows the feature builder. In the qualified root artifacts, its alignment and finite values are checked explicitly. The resulting input matrix is
$$
X_V\in\mathbb R^{n\times7}.
$$

#### A.8.2.2. Constraint features

Each constraint has five attributes:
$$
\mathbf{x}^{C}_i=
\begin{bmatrix}
\phi(b_i)\\
\mathbb 1[\leq]\\
\mathbb 1[=]\\
\mathbb 1[\geq]\\
1
\end{bmatrix}\in\mathbb R^5,
\qquad X_C\in\mathbb R^{m\times5}.
$$
The final channel is the constant one. A row norm is computed during data preparation, but is not one of these five input channels.

#### A.8.2.3. Edge features

For $A_{ij}\neq0$, the edge feature is
$$
e_{ij}=\phi(A_{ij}),\qquad X_E\in\mathbb R^{E\times1}.
$$
These channels are implemented in the graph feature builder and in the constructor that reconciles the original MILP matrix. Section A.8.9 identifies their versioned sources.

### A.8.3. Matrix inference through two convolutions

#### A.8.3.1. Initial encoders

Using row vectors for batched node features, the variable encoder is
$$
H_V^{(0)}=\operatorname{ReLU}(X_VW_V+b_V),
\qquad
W_V\in\mathbb R^{7\times32},\quad b_V\in\mathbb R^{32},
$$
where biases are broadcast across rows. Thus $H_V^{(0)}\in\mathbb R^{n\times32}$. Similarly,
$$
H_C^{(0)}=\operatorname{ReLU}(X_CW_C+b_C)
\in\mathbb R^{m\times32},
\qquad W_C\in\mathbb R^{5\times32}.
$$
Embeddings are learned latent representations of MILP attributes, not labels.

#### A.8.3.2. Variable-to-constraint propagation

For each edge $(i,j)$, concatenate the endpoint embeddings and coefficient feature:
$$
\mathbf z_{ij}^{(\ell)}
=\left[\mathbf h_{C,i}^{(\ell)}
\Vert\mathbf h_{V,j}^{(\ell)}\Vert e_{ij}\right]
\in\mathbb R^{65}.
$$
Here, individual embeddings are written as columns. The message MLP $g_C$ gives
$$
\mathbf m_{ij}^{C,\ell}
=W_{C,2}^{(\ell)}
\operatorname{ReLU}\left(
W_{C,1}^{(\ell)}\mathbf z_{ij}^{(\ell)}
+\mathbf b_{C,1}^{(\ell)}\right)
+\mathbf b_{C,2}^{(\ell)}.
$$
The matrices have shapes $32\times65$ and $32\times32$, respectively; the message has 32 components. For constraint $i$,
$$
\mathbf a_{C,i}^{(\ell)}
=\sum_{j:A_{ij}\neq0}\mathbf m_{ij}^{C,\ell}.
$$
Aggregation is a sum, not a mean or attention operation. Fixed prenormalization then gives
$$
\widetilde{\mathbf a}_{C,i}^{(\ell)}
=\frac{\mathbf a_{C,i}^{(\ell)}-\boldsymbol\beta_C^{(\ell)}}
{\boldsymbol\sigma_C^{(\ell)}}.
$$
Division is componentwise, with the implementation's positive lower bound on fitted standard deviations. The update MLP $f_C$, of dimensions $64\to32\to32$, gives
$$
\mathbf h_{C,i}^{(\ell+1)}
=\operatorname{ReLU}\left(
f_C^{(\ell)}
\left[\mathbf h_{C,i}^{(\ell)}
\Vert\widetilde{\mathbf a}_{C,i}^{(\ell)}\right]\right).
$$

#### A.8.3.3. Constraint-to-variable propagation

The reverse direction uses the newly updated constraint embeddings:
$$
\mathbf z_{ij}^{V,\ell}
=\left[\mathbf h_{C,i}^{(\ell+1)}
\Vert\mathbf h_{V,j}^{(\ell)}\Vert e_{ij}\right],
\qquad
\mathbf m_{ij}^{V,\ell}=g_V^{(\ell)}(\mathbf z_{ij}^{V,\ell}).
$$
The $g_V$ MLP also has dimensions $65\to32\to32$. For each variable,
$$
\mathbf a_{V,j}^{(\ell)}
=\sum_{i:A_{ij}\neq0}\mathbf m_{ij}^{V,\ell},
$$
followed by prenormalization and
$$
\mathbf h_{V,j}^{(\ell+1)}
=\operatorname{ReLU}\left(
f_V^{(\ell)}
\left[\mathbf h_{V,j}^{(\ell)}
\Vert\widetilde{\mathbf a}_{V,j}^{(\ell)}\right]\right).
$$
This completes one bipartite convolution.

#### A.8.3.4. Matrix form

Define sparse incidence matrices
$$
P_V\in\{0,1\}^{E\times n},
\qquad P_C\in\{0,1\}^{E\times m}.
$$
Each row represents an edge and selects its variable and constraint endpoint. Batched endpoint embeddings are
$$
Z_C^{(\ell)}
=\left[P_CH_C^{(\ell)}
\Vert P_VH_V^{(\ell)}\Vert X_E\right]
\in\mathbb R^{E\times65}.
$$
Applying MLPs rowwise and aggregating gives
$$
M_C^{(\ell)}=g_C^{(\ell)}(Z_C^{(\ell)})
\in\mathbb R^{E\times32},
\qquad
A_C^{(\ell)}=P_C^\top M_C^{(\ell)}
\in\mathbb R^{m\times32},
$$
$$
H_C^{(\ell+1)}
=\operatorname{ReLU}\left(
f_C^{(\ell)}\left[
H_C^{(\ell)}\Vert\operatorname{PN}_C(A_C^{(\ell)})\right]\right).
$$
For the reverse direction,
$$
Z_V^{(\ell)}
=\left[P_CH_C^{(\ell+1)}
\Vert P_VH_V^{(\ell)}\Vert X_E\right],
$$
$$
M_V^{(\ell)}=g_V^{(\ell)}(Z_V^{(\ell)}),
\qquad
A_V^{(\ell)}=P_V^\top M_V^{(\ell)},
$$
$$
H_V^{(\ell+1)}
=\operatorname{ReLU}\left(
f_V^{(\ell)}\left[
H_V^{(\ell)}\Vert\operatorname{PN}_V(A_V^{(\ell)})\right]\right).
$$
The rowwise MLP notation transposes the individual-column convention above. These expressions describe the implementation's indexed aggregation, $\texttt{scatter\_add\_}$, MLP and ReLU operations; explicit incidence matrices need not be materialized.

Repeating for $\ell=0,1$ gives two complete convolutions and four directional message-passing stages.

#### A.8.3.5. Network output

After the second convolution, $H_V^{(2)}\in\mathbb R^{n\times32}$. A mask selects the $n_B$ eligible binary-domain variables:
$$
H_B=H_V^{(2)}[\mathcal B]\in\mathbb R^{n_B\times32}.
$$
The output head is
$$
U=\operatorname{ReLU}(H_BW_{H1}+b_{H1}),\qquad
\mathbf z=UW_{H2}+b_{H2},
$$
$$
\widehat{\mathbf p}=\sigma(\mathbf z),\qquad
\sigma(z)=\frac{1}{1+\exp(-z)}.
$$
The code initially returns logits; sigmoid is applied when converting them into scores. There is one scalar estimate per eligible binary variable, even for a graph with millions of nodes. Weighted BCE does not by itself establish that these scores are calibrated posterior probabilities.

Computation depends mainly on $E$, the node counts and width 32, rather than on a dense quadratic matrix over all variables.

### A.8.4. Root relaxation, incumbents and MIP gap

#### A.8.4.1. What is relaxed?

For a binary variable, the basic LP relaxation replaces $x_j\in\{0,1\}$ with $0\leq x_j\leq1$. More generally, it drops integrality while preserving linear constraints and applicable bounds:
$$
\begin{aligned}
\min_{\mathbf x}\quad&\mathbf c^\top\mathbf x+c_0\\
\text{subject to}\quad&A\mathbf x\ \bowtie\ \mathbf b,\\
&\boldsymbol\ell\leq\mathbf x\leq\mathbf u.
\end{aligned}
$$
The optimum $\mathbf x^{LP}$ may be fractional. @tbl-foundation-lp-example illustrates the distinction between relaxed values and integer labels.

| Variable | LP relaxation | Integer incumbent |
|:--|--:|--:|
| $x_1$ | 0.83 | 1 |
| $x_2$ | 0.14 | 0 |
| $x_3$ | 0.52 | 1 |
| $x_4$ | 0.02 | 0 |

: Illustrative relaxation and labels. {#tbl-foundation-lp-example}

These values are examples, not observations from the experimental instances. The GNN receives the relaxation channel and learns, using the incumbent labels, to predict binary values.

#### A.8.4.2. Capturing the root vector

The historical implementation does not simply call $\texttt{model.relax()}$ and solve a separate LP. Its root-capture routine uses $\texttt{Presolve=0}$, $\texttt{NodeLimit=1}$, $\texttt{Threads=1}$, $\texttt{Seed=42}$, a $\texttt{MIPNODE}$ callback, an optimal node-relaxation status, a zero explored-node count, and $\texttt{cbGetNodeRel(variables)}$.

The first qualifying vector is captured in original-variable order, and that preparation optimization is terminated. The returned values describe the node relaxation, not a feasible integer solution. The general root callback interface can expose successive cutting-plane passes, so the capture event and its settings matter; a generic root observation should not automatically be called the solution of an independently solved, uncut LP. The qualified first-root capture is identified separately from later root observations in the source record.

#### A.8.4.3. No need to traverse the entire tree

One root relaxation jointly assigns values to all variables in that relaxation, including those never selected for branching. The solver does not solve each variable independently. The captured vector is
$$
\mathbf r=[r_1,r_2,\ldots,r_n]^\top.
$$
Labels are not missing merely because a variable was not visited in the branching tree.

#### A.8.4.4. Origin of binary labels

Labels come from a separate feasible integer incumbent of the original MILP, rather than directly from branching decisions. For incumbent $\mathbf x^{inc}$ and eligible binary variable $j$, the ideal mathematical definition is
$$
y_j=x_j^{inc}\in\{0,1\}.
$$
Stored floating-point values require the documented integral-domain, feasibility and tolerance checks; exact binary membership must not be inferred from solver status alone. The labels describe the full assignment, independently of node-exploration order. An incumbent can exist even if optimality has not been proved.

#### A.8.4.5. What the MIP gap qualifies

For minimization, let $UB$ be the best feasible incumbent objective and $LB$ the best lower bound reported by the solver. The usual relative gap is
$$
g=\frac{|UB-LB|}{|UB|},
$$
with special handling for a zero objective and nonfinite bounds. This is a global measure, not a variable label. Numerical qualifications of primal feasibility and bound validity remain necessary; a reported zero gap is not an independent exact-arithmetic certificate.

The historical supervised-data admission limit was
$$
g\leq0.10,
$$
together with feasibility, identity, provenance and integrity checks. This means up to 10%, not 0.10%. A graph-builder field marks $\texttt{is\_optimal}$ when $g\leq10^{-4}$; that stricter auxiliary flag is not the general label-admission rule or a separate proof of exact optimality.

#### A.8.4.6. Historical graph admission

Admission checks require correspondence between model and solution identities; an existing feasible incumbent; complete and consistent variable values; a finite gap within the specified limit; a correctly captured and aligned root vector; preservation of the matrix, attributes and label identities in the graph; and an eligible binary domain for every label used by BCE.

@tbl-foundation-admission reports the resulting historical population.

| Class | Candidates | Admitted |
|:--|--:|--:|
| Easy | 30 | 30 |
| Medium | 30 | 24 |
| Hard | 30 | 0 |
| Total | 90 | 54 |

: Historical graph admission. {#tbl-foundation-admission}

The 54 admitted parent instances were divided into 34 training, ten validation and ten test parents. Exclusion of the other 36 does not establish mathematical infeasibility; those instances did not meet the learning-population admission contract. Applying this predictor to hard instances examines transfer beyond the classes represented in training, rather than demonstrating generalization automatically.

### A.8.5. How labels influence embeddings and parameters

Labels are not directly transformed into embeddings. Attributes and connectivity determine embeddings; labels enter the loss and thereby influence the weights learned during training.

#### A.8.5.1. Forward pass

For training graph $(X_V,X_C,X_E,\mathcal E)$, with labels $\mathbf y=(y_1,\ldots,y_{n_B})$,
$$
\mathbf z=F_\Theta(X_V,X_C,X_E,\mathcal E),
\qquad
\hat p_j=\sigma(z_j).
$$
The 26,753 trainable parameters are denoted by $\Theta$. The labels do not enter $F_\Theta$. Supplying them as inference features would cause target leakage.

#### A.8.5.2. Weighted supervised loss

The implementation uses $\texttt{BCEWithLogitsLoss}$ with a positive-class weight:
$$
\ell_j=-\left[w_+y_j\log(\hat p_j)
+(1-y_j)\log(1-\hat p_j)\right],
\qquad
L_g(\Theta)=\frac{1}{n_B}\sum_{j=1}^{n_B}\ell_j.
$$
This is the per-graph mean. The positive weight is estimated from training labels:
$$
w_+=\frac{N_0}{N_1},
$$
where $N_0$ and $N_1$ count zeros and ones. For the historical mixed checkpoint,
$$
w_+\approx1132.976.
$$
This reflects extreme imbalance and increases the influence of errors on rare ones. It neither adds trainable parameters nor creates independent examples.

#### A.8.5.3. From a label to a gradient

Before mean reduction,
$$
\frac{\partial\ell_j}{\partial z_j}
=\begin{cases}
\hat p_j,&y_j=0,\\
w_+(\hat p_j-1),&y_j=1,
\end{cases}
$$
or, equivalently,
$$
\frac{\partial\ell_j}{\partial z_j}
=\left[1+(w_+-1)y_j\right](\hat p_j-y_j).
$$
For $y_j=1$ and $\hat p_j=0.2$,
$$
1132.976(0.2-1)\approx-906.38.
$$
With $y_j=0$, the same score gives derivative $0.2$. Thus rare positives can contribute strongly to the gradient. The per-graph mean additionally divides these contributions by $n_B$.

#### A.8.5.4. Backpropagation

The chain rule propagates loss derivatives through the output MLP, $f_V$, $g_V$, $f_C$, $g_C$, the first convolution and the initial encoders:
$$
\nabla_\Theta L_g
=\frac{\partial L_g}{\partial\mathbf z}
\frac{\partial\mathbf z}{\partial\Theta},
$$
with consistent Jacobian orientations. ReLU satisfies
$$
\operatorname{ReLU}(a)=\max(0,a),
\qquad
\operatorname{ReLU}'(a)=
\begin{cases}1,&a>0,\\0,&a<0.\end{cases}
$$
At zero, the implementation defines a subgradient. ReLU is not trainable; it controls which computational paths propagate gradients.

#### A.8.5.5. Adam updates

After backpropagation, gradient clipping imposes a maximum norm of one. Adam uses historical learning rate $\eta=0.001$. For clipped gradient $g_t$,
$$
m_t=\beta_1m_{t-1}+(1-\beta_1)g_t,\qquad
v_t=\beta_2v_{t-1}+(1-\beta_2)g_t^2,
$$
$$
\hat m_t=\frac{m_t}{1-\beta_1^t},\qquad
\hat v_t=\frac{v_t}{1-\beta_2^t},
$$
$$
\Theta_{t+1}
=\Theta_t-\eta\frac{\hat m_t}{\sqrt{\hat v_t}+\epsilon}.
$$
Products, squares and division are componentwise. Adam defaults apply where not overridden by the recorded configuration. Updates are repeated over training graph presentations.

#### A.8.5.6. Presentations versus optimizer updates

With 34 training parents and four deterministic presentations per parent per epoch, there are
$$
34\times4=136
$$
presentations per epoch and, over 100 complete epochs,
$$
136\times100=13\,600
$$
presentations. A serial batch-one protocol with one valid update per presentation therefore has 13,600 optimizer steps. These remain repeated presentations of 34 parent graphs, not 13,600 independent instances.

The later matched serial/DDP comparison uses the same 13,600 presentations but a global batch of four: $136/4=34$ updates per epoch and $3\,400$ updates per arm over 100 epochs. Its loss is the mean of four per-graph BCE means. Changing global batch changes the optimization schedule; the two update counts describe distinct historical protocols.

Checkpoint selection uses the smallest validation weighted BCE, followed by F1-based threshold selection on validation scores. Prenormalization is separate from Adam: training-population moments are fitted and stored as nontrainable buffers.

### A.8.6. Deriving the trainable parameter count

An affine map with $d_{\mathrm{in}}$ inputs and $d_{\mathrm{out}}$ outputs contains
$$
P=(d_{\mathrm{in}}+1)d_{\mathrm{out}}
$$
parameters, including biases. The counts below follow from the implemented dimensions.

#### A.8.6.1. Encoders

@tbl-foundation-encoders gives the two input maps.

| Component | Dimensions | Parameters |
|:--|:--|--:|
| Variable encoder | $7\to32$ | $7(32)+32=256$ |
| Constraint encoder | $5\to32$ | $5(32)+32=192$ |
| Subtotal | | 448 |

: Encoder parameters. {#tbl-foundation-encoders}

The encoders contribute 448 parameters independently of graph size.

#### A.8.6.2. One bipartite convolution

Each convolution has four MLPs, each with two affine maps. @tbl-foundation-convolution accounts for both layers of each MLP.

| Component | First map | Second map | Total |
|:--|:--|:--|--:|
| $g_C$ | $65\to32:\ 2\,112$ | $32\to32:\ 1\,056$ | 3,168 |
| $g_V$ | $65\to32:\ 2\,112$ | $32\to32:\ 1\,056$ | 3,168 |
| $f_C$ | $64\to32:\ 2\,080$ | $32\to32:\ 1\,056$ | 3,136 |
| $f_V$ | $64\to32:\ 2\,080$ | $32\to32:\ 1\,056$ | 3,136 |
| Subtotal | | | 12,608 |

: Parameters in one convolution. {#tbl-foundation-convolution}

Two convolutions contribute
$$
P_{\mathrm{convs}}=2(12\,608)=25\,216.
$$

#### A.8.6.3. Output MLP

@tbl-foundation-head gives the maps from a width-32 embedding to a scalar logit.

| Map | Parameters |
|:--|--:|
| $32\to32$ | 1,056 |
| $32\to1$ | 33 |
| Subtotal | 1,089 |

: Output-head parameters. {#tbl-foundation-head}

The hidden affine map and scalar output together contribute 1,089 parameters.

#### A.8.6.4. Total and sharing

The total is
$$
P_{\mathrm{total}}=448+25\,216+1\,089=26\,753.
$$
@tbl-foundation-distribution shows its distribution.

| Component | Parameters | Share |
|:--|--:|--:|
| Encoders | 448 | 1.67% |
| Convolution 1 | 12,608 | 47.13% |
| Convolution 2 | 12,608 | 47.13% |
| Output MLP | 1,089 | 4.07% |
| Total | 26,753 | 100% |

: Distribution of trainable parameters. {#tbl-foundation-distribution}

Prenormalization adds no trainable parameters: $\beta$ and $\sigma$ are fitted buffers. The two convolutions have separate weights. Sharing occurs across nodes and edges within a layer, not between the two layers.

#### A.8.6.5. Millions of variables and memory

The parameter count remains 26,753 as graph size grows. Activations and computational work grow instead. For $n=1\,000\,000$,
$$
H_V\in\mathbb R^{1\,000\,000\times32},
$$
which contains 32 million float32 values, approximately 128 MB for this single variable-embedding tensor. Edge messages can require much more memory: $Z_C\in\mathbb R^{E\times65}$ grows with matrix nonzeros.

Parameters, activations, stored gradients and Adam's moving-average states are different memory components. Inference does not retain the full backpropagation computation graph and generally needs less memory than training, although its edge tensors can still be large.

### A.8.7. Consolidated interpretation

@tbl-foundation-questions connects the four conceptual questions to the mathematical description.

| Question | Interpretation |
|:--|:--|
| How is matrix inference performed? | Encoders $7/5\to32$, two alternating bipartite convolutions with sum aggregation, an output head $32\to32\to1$, and sigmoid; connectivity comes from the sparse MILP matrix. |
| Where do relaxations and labels come from? | The relaxation is captured at the first qualified root MIPNODE; labels come from a separate feasible integer incumbent. Gap qualifies that incumbent globally. |
| How do labels become embeddings? | They do not become embeddings directly. Features and connectivity create embeddings; labels enter weighted BCE and the gradients that update weights. |
| How are parameters obtained and updated? | There are 448 encoder, 25,216 convolution and 1,089 output parameters. Backpropagation computes gradients; Adam updates weights. |

: Interpretation of inference and training. {#tbl-foundation-questions}

These distinctions separate representation, supervision and optimization. In particular, prediction quality and downstream solver utility remain different outcomes.

### A.8.8. Scientific implications

First, reference-label quality limits the meaning of learning. An incumbent within the historical 10% admission limit need not be optimal. The model learns decisions of qualified incumbents, not necessarily a unique mathematical optimum.

Second, the LP feature already carries global information from an optimization problem. The network need not infer every global relation solely through local message passing. Obtaining that feature has a computational cost that belongs in the economic assessment.

Third, 26,753 parameters are neither 26,753 decisions nor 26,753 learned MILP variables. The shared function's transfer depends on the structure represented by the 34 historical training parents, label quality and architectural suitability.

The mathematical description alone supplies no reason to change the architecture. It instead motivates examining incumbent quality, the rarity of ones and population selection when interpreting learned partial Starts.

### A.8.9. References and implementation sources

Gasse et al.'s [Exact Combinatorial Optimization with Graph Convolutional Neural Networks](https://proceedings.neurips.cc/paper/2019/file/d14c2267d848abeb81fd590f371d39bd-Paper.pdf) provides the methodological reference for bipartite MILP representations and message passing. Its original task is imitation learning for branching; the present implementation learns binary incumbent assignments for partial MIP Starts.

The versioned implementation sources are:

- [gasse.py](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3700d90af6bdc1beab72a420cd7d0c965b7005bf/src/cfl_gnn/models/gasse.py): affine maps, convolutions, output head and parameter count.
- [gasse_calibrated.py](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3700d90af6bdc1beab72a420cd7d0c965b7005bf/src/cfl_gnn/models/gasse_calibrated.py): alternating-message prenormalization fitted on training data.
- [build_dataset.py](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3700d90af6bdc1beab72a420cd7d0c965b7005bf/src/cfl_gnn/graph/build_dataset.py): feature encoding and numerical sanitization.
- [gurobi_graph_artifact.py](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3700d90af6bdc1beab72a420cd7d0c965b7005bf/src/cfl_gnn/graph/gurobi_graph_artifact.py): root capture and incumbent-derived labels.
- [gasse_reconnected.py](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3700d90af6bdc1beab72a420cd7d0c965b7005bf/src/cfl_gnn/training/gasse_reconnected.py): historical training and checkpoint/threshold selection.
- [Matched GPU protocol](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3700d90af6bdc1beab72a420cd7d0c965b7005bf/configs/experiments/pr87_matched_gpu_v1.json): 13,600 presentations and 3,400 updates per arm.
- [Gurobi cbGetNodeRel](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/python/model.html#Model.cbGetNodeRel), [root callback semantics](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/numericcodes/callbacks.html), and [MIP gap](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/attributes/model.html#mipgap): interpretation of solver observations.

The central relationship is
$$
\boxed{
\underbrace{r_j}_{\text{LP relaxation: an input feature}}
\ \longrightarrow\
\underbrace{\widehat p_j}_{\text{GNN score}}
\ \overset{\text{training loss}}{\longleftrightarrow}\
\underbrace{y_j}_{\text{incumbent-derived label}}
}.
$$
The arrow on the left abbreviates the full graph-based input, not a predictor of $r_j$ alone. The label influences the prediction function during training; it is absent from inference. This separation establishes the mathematical interpretation without requiring additional training or solver runs.
