<!-- Internal research record; excluded from article and journal supplements. -->

# Preliminary scientific brief for coauthor review

28 October 2026 · working material accompanying PR92.
Requested feedback target: **15 November 2026**.
This brief is prepared for the authors to circulate. No material has been sent
and no response or scientific approval is presumed.

The purpose of early review is to assess the argument while the CPU campaign
continues. The final manuscript will be reviewed again after its results are
qualified. The [completion plan](mvp2-closeout-plan.md) records
that distinction.

## Working title

**Class-aware graph neural warm starts for capacitated facility location:
a controlled computational study**

The title identifies the implemented selection rule, not a demonstrated
causal advantage of class awareness. Coauthors should assess whether that
emphasis accurately describes the contribution. A change in title must not
imply an architectural or generalization result that was not measured.

## Research question and empirical gap

Can partial binary values predicted by a graph neural network help a MILP
solver solve capacitated facility location problems under stated computational
budgets? The article examines when that information helps or harms, including
its preparation cost. This operationalizes the R3 question without promising
improvement or assuming identical terminal behaviour on repeated timed runs.

The unresolved issue addressed by this study is the usefulness of this fixed
prediction-to-Start pipeline under its recorded instance, resource and cost
conditions. A good label predictor is not necessarily a useful solver guide:
approximate incumbent labels may admit alternatives, and a solver can reject,
repair or complete a supplied start. The evidence must therefore connect
prediction, optimization and cost without conflating them.

This is an empirical positioning, not a claim that GNN warm starts are new.
The review supplied by chat 01.04 and the source reconciliation constrain
the argument:

| Precedent | Consequence for our positioning |
| --- | --- |
| [Gasse et al.](https://arxiv.org/abs/1906.01629v3) | The variable–constraint representation and learned branching precedent are architectural foundations; our binary-value target and native Start interface differ. |
| [MIP-GNN](https://doi.org/10.1609/aaai.v36i9.21262) | Neural warm-starting already exists; do not claim the first GNN–MIP integration. |
| [Neural Diving](https://arxiv.org/abs/2012.13349v3) and [Predict-and-Search](https://openreview.net/forum?id=pHMpgT5xWaE) | Sub-MIP completion and restricted search regions differ from a native partial Start that preserves the feasible region. |
| [Cantürk et al.](https://doi.org/10.1613/jair.1.14972) | Uncertainty-based reduction is a relevant primal-guidance precedent, not the same selection/completion policy. |
| [Vargas-Pérez et al.](https://doi.org/10.1109/TCSS.2024.3508452) | Explicit architecture/settings/validation reporting is a useful example; results in opinion-dynamics regression do not justify an architecture winner for CFL. |

The [methods explanation](../../manuscript/supplement/gnn-methods-audit.md) and
[reference review](../../manuscript/reference-review.md) contain the implementation comparison
and access/metadata qualifications. This brief does not repeat or extend the
literature investigation.

## Candidate contributions C1–C3

These are claims for discussion, not declarations of established originality
or journal sufficiency.

**C1 — A specified prediction-to-solver mechanism.** The contribution describes
how a fixed bipartite predictor and class-aware selection supply nonbinding
binary values through Gurobi's native Start interface. Its value is a precise,
auditable mechanism with explicit information boundaries. Architecture novelty,
first integration and a causal advantage of ones-first ordering are not claimed.

**C2 — Conditional effects on optimization.** The evaluation distinguishes
instance and resource regimes, primal/dual progress, time to observed targets
and terminal gap. Existing evidence supports heterogeneous outcomes rather
than uniform acceleration. The longer-horizon CPU contribution remains pending
receipt, cell reconciliation and metric-specific qualification.

**C3 — Bounded computational economics.** Preparation, solver time and training
are kept separate. The GPU comparison shows that faster training can coexist
with worse selected predictive quality and greater assigned GPU-hours.
Accounting scenarios are not measured energy or financial savings, and a
solver-only benefit is not automatically an end-to-end benefit.

Coauthors should decide whether these bounded contributions form a sufficiently
clear and original OR article. If they do not, the current response is to narrow
the argument or reconsider the editorial strategy, not silently introduce
new experiments.

## Method in plain terms

The graph uses variable and constraint nodes connected by coefficient edges.
Seven variable channels, five row channels and one edge channel describe the
original problem and a captured root-relaxation vector. A two-cycle, width-32
Gasse-inspired model predicts binary-variable scores. These are fixed design
choices, not the outcome of a demonstrated architecture search.

Training uses checked incumbent labels, a positive-weighted BCE loss, Adam at
0.001, gradient-norm clipping at 1 and a 100-epoch ceiling. Literature supports
the design principles, not the optimality of those exact values for CFL.
Validation selects the checkpoint and classification threshold. Weighting and
thresholding do not establish probability calibration.

B is Gurobi without an external start. G uses the frozen learned start.
R uses root-relaxation values to match G's supplied-value count and one count,
but chooses its own indices. Thus R depends on G's preparation; it is not
an independent LP-only heuristic. No bound is fixed by supplying Start values.

Method=−1 means automatic continuous/root algorithm selection, not proof that
a MIP solve was non-deterministic. TimeLimit still permits different terminal
work points. Comparisons describe observed outcomes under recorded settings;
one principal solver seed does not estimate search-path variability.

## What the existing evidence does and does not show

The learning cohort contains 54 admitted parents from 90 candidates, partitioned
34/10/10. Labels are feasible under the stated checks and quality threshold,
but may be approximate. The test parents were historically exposed, so this
is not an independent generalization study.

The principal CPU view has 150 seed-42 rows from ten exposed parents. Its 97
reported terminal targets and 53 censures are coverage/outcome categories,
not 97 exact optimality certificates. Thirty numerically sensitive M4/M12
rows form a subset of those observations. The historical six-medium study
has a different population and retains its own tables and limitations.

The completed matched GPU pair records loop speedup 2.167 and job speedup 1.831,
but selected parent-macro F1 decreases by 0.032468. Assigned GPU-hours increase.
This does not establish predictive noninferiority, isolated GPU causality
or downstream solver benefit. The [claim map](../../manuscript/supplement/claim-evidence.json)
binds these existing numbers to their qualified sources.

The CPU12h campaign is still pending. No quality, speedup, threshold-crossing
or cost result from it is supplied in this brief. Scheduler status alone
would not support such a result.

Additional solver seeds, explicit root methods, neural depth/width changes,
training seeds and the shorter diagnostic design remain limitations and future
work in the [sensitivity assessment](../../manuscript/supplement/sensitivity-review-plan.md).
They are not part of the current Sprints.

## Five questions for preliminary author feedback

1. Does the title and research question express a useful OR problem and an
   appropriately bounded contribution?
2. Are C1–C3 sufficiently distinct from the precedents, without relying on
   architecture novelty, selector causality or independent generalization?
3. Is the explanation of the fixed model, dependent R comparator and timed
   solver comparison clear and adequate?
4. Are the exposed population, approximate labels, numerical restrictions
   and adverse GPU-quality finding given sufficient weight?
5. Should the Human–AI traceability material remain a repository review aid,
   or is a short scientific note useful? A full Appendix B requires its own
   definition, primary evidence and author review.

Requested feedback is preliminary. Final scientific review follows the
qualified CPU integration and the complete audit. Authorship, declarations,
publication and submission remain under explicit human control.

## Independent first-pass audit record

This record reuses the completed R3/source reviews; it is not another experiment
or a blanket validation of the repository.

| Aspect | Evidence reviewed or reused | Disposition before the CPU return |
| --- | --- | --- |
| Formulation and B/R/G interface | [R3 methods](mvp2-r3-methods-and-models.md), native model/Start signatures | Documented under the frozen MINIMIZE decision; no renewed generator-certification gate |
| Architecture, hyperparameters and model provenance | [Methods explanation](../../manuscript/supplement/gnn-methods-audit.md), versioned configuration and original checkpoint bindings | Source-linked; historical-fit replay and architecture superiority are not established |
| Root/inference/Start information path | Root and guidance preparation sources linked in the methods explanation | Described separately; no new preparation, inference or solver call |
| Repeatability and metrics | [R3 definitions](mvp2-r3-metrics-and-reproducibility.md) | Conditional interpretation documented; unexported runtime fields remain unavailable |
| Bibliography and positioning | Chat01.04 review, [reference review](../../manuscript/reference-review.md), primary sources above | Current claim-specific positioning prepared; novelty sufficiency awaits coauthors |
| Manuscript structure and historical figures | Existing numerical manifests, source gates, final-head render/visual review from the previous verified article revision | Existing inputs and scopes reviewed; no CPU12h result is inferred |
| Supplement structure and Human–AI material | [Reading order](../../manuscript/supplement/README.md), claim map, conditional Appendix B register | Working review material; final journal packaging and final audit remain pending |

The final post-D0 audit must still reconcile the integrated results, every
published table/figure and claim, documentation and editorial package.
This first passage cannot replace it.
