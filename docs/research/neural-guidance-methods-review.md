# Neural guidance methods: methodological review

## Research question

The recovered pipeline must determine how GNN predictions should guide a MIP
solver without silently changing the intended experiment.  The immediate
question is whether setting `LB = UB = predicted_value` is an appropriate
replacement for the original Gurobi variable-hint mechanism.

## Hard fixing is a restricted sub-MIP, not a hint

For an integer variable `x_j`, setting both bounds to a predicted value removes
all solutions inconsistent with that value.  Applied to a selected subset, the
operation constructs a valid restricted sub-MIP.  It can accelerate a solve,
but it can also exclude the global optimum or make the restricted model
infeasible.  Results therefore measure a change in feasible region as well as
prediction quality.

Nair et al. describe Neural Diving as generating multiple partial assignments
for integer variables and solving the remaining smaller MIPs.  This supports
partial assignment as a research method, but not the equivalence of one
deterministic high-coverage fixing set with a nonbinding solver hint.  A faithful
replication would also require precommitted coverage, multiple assignments or
samples, feasibility handling, and fallback semantics.

Reference: Vinod Nair et al., *Solving Mixed Integer Programs Using Neural
Networks*, 2020, <https://arxiv.org/abs/2012.13349>.

Confidence-threshold Neural Diving and threshold-aware variants further report
that assignment coverage is a methodological parameter rather than a harmless
implementation detail.  This reinforces the need to separate a future Neural
Diving replication from the recovered baseline.

References:

- <https://arxiv.org/abs/2202.07506>
- <https://arxiv.org/abs/2308.00327>

## Candidate A: Gurobi variable hints

`VarHintVal` communicates a likely variable value and `VarHintPri` communicates
relative confidence.  These attributes influence heuristics and branching but
do not change variable bounds.  An `.hnt` file is an external representation
of the same attributes.

This is the primary recovery candidate because it preserves the feasible
region and matches the established repository intervention.

Official references:

- <https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html>
- <https://docs.gurobi.com/projects/optimizer/en/current/reference/fileformats/otherformats.html>

## Candidate B: Gurobi partial MIP start

The `Start` attribute, `.mst`, and `.sol` inputs provide an initial solution.
A partial start leaves some variable values undefined and asks Gurobi to try to
complete the candidate.  This is distinct from both variable hints and bound
fixing.  Acceptance, completion effort, objective, and any rejection evidence
must be recorded.

Official references:

- <https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html>
- <https://docs.gurobi.com/projects/optimizer/en/current/reference/misc/commandline.html>

## SCIP comparison candidates

PySCIPOpt can create partial primal solutions and submit solutions with
`addSol` or `trySol`.  SCIP also supports primal diving and large-neighborhood
heuristics such as guided diving, RINS, and local branching.  These mechanisms
are useful comparison candidates, but they do not make SCIP a graph-feature
authority and need not imitate Gurobi through artificial bound fixing.

Official references:

- <https://pyscipopt.readthedocs.io/en/latest/api/model.html>
- <https://scipopt.org/doc/html/DIVINGHEUR.php>
- <https://www.scipopt.org/doc/html/HEUR.php>

## Decision for the recovered MVP

| Role | Method | Feasible region changed? | Status |
|---|---|---:|---|
| Primary Gurobi | `VarHintVal`/`VarHintPri` | No | Recover |
| Secondary Gurobi | Partial MIP start | No | Compare separately |
| SCIP comparator | Partial primal solution | No | Compare separately |
| SCIP exploratory | Diving or LNS | Temporarily/restricted search | Future |
| Neural Diving replication | Multiple partial hard assignments | Yes | Suspended |
| PR #37 hard fixing | One deterministic fixing set | Yes | Historical only |

PR #45 must benchmark the primary and secondary candidates against an unguided
control under the same parent, time limit, thread count, seed, hardware, and
objective sense.  Terminal relative MIP gap and optimization wall time are the
primary outcomes.  Read, build, optimize, and total times remain separate.

No method, confidence policy, assignment coverage, or threshold may be chosen
from held-out test performance.  The recovered baseline is selected by the
accepted methodology and validation evidence; a future faithful Neural Diving
replication requires a new precommitted protocol.

## Relation to graph construction

The GNN uses the bipartite variable-constraint representation retained from
Gasse et al.  Because graph features describe the mathematical MIP and its
Gurobi-derived root state, they are constructed once before solver-specific
labels or guidance are attached.

Reference: Maxime Gasse et al., *Exact Combinatorial Optimization with Graph
Convolutional Neural Networks*, NeurIPS 2019,
<https://papers.nips.cc/paper/9690-exact-combinatorial-optimization-with-graph-convolutional-neural-networks.pdf>.

