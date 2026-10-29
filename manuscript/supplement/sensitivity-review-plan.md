# Sensitivity and directions for further study

The reported comparisons evaluate a fixed predictor and partial-Start policy
on identified facility-location instances. They describe observed improvements,
regressions, censoring and costs. They do not estimate performance averaged
over solver seeds, establish optimal neural hyperparameters, or isolate the
causal contribution of class-aware selection. These limitations motivate
several distinct research questions.

## Search-path sensitivity

Changing the solver seed while holding the predictor, stored Starts, parent
and resource cap fixed would assess sensitivity to the solver's search.
It would not test neural initialization. Multiple seeds would provide repeated
measurements within each parent, rather than additional independent instances.
With few parents or seeds, individual contrasts and direction changes would
remain more informative than precise population-level uncertainty claims.

The historical seed43/44 observations have a different scope from the
principal seed42 analysis. They do not supply replications of a longer-horizon
treatment and cannot establish training-seed robustness. The interpretation
of any cross-seed analysis depends on retaining the same endpoint, stopping
rule and information supplied to the solver.

## Root algorithms and time-limited optimization

An explicit root-method comparison could examine whether the automatic
choice materially affects the supplied-Start comparison. Method controls the
continuous/root algorithm, not the entire MIP search. Automatic selection
commonly chooses dual simplex for a MIP root; a comparison with explicit
Method=1 could therefore reproduce an already-used algorithm rather than
introduce a substantively different mechanism.

There is also a distinction between holding an algorithm fixed and repeating
a wall-time endpoint. Even deterministic work can end at different points
under a time limit. Work-based stopping addresses a different measurement
question and is not interchangeable with a fixed-time treatment. Likewise,
the first four hours of a twelve-hour trace are not automatically a solve
configured with a four-hour limit. Stopping parameters and observation coverage
remain part of the experimental definition.

## Neural configuration and training variability

The present two-cycle, width-32 network is one fixed configuration. A controlled
depth or width comparison would examine representation capacity and propagation
distance while retaining the data roles and validation rules. A training-seed
comparison would instead examine variation in fitted weights and selected
checkpoints. These designs address different questions and would require new
predictions as well as training measurements.

For each new predictor, R's Start would need to match that predictor's actual
support and positive count. Reusing the earlier R Start would change the
comparison. Training, root/graph preparation, inference and solver time would
remain separate costs. A higher classification score alone would not establish
greater optimization utility.

GCN, GraphSAGE and attention-based models offer broader alternatives, but a
comparison among them would vary architecture, training behaviour and model
selection together. A narrow, interpretable comparison is better suited to
a specific capacity question than an undifferentiated architecture grid.

## Mechanism ablations

A mechanism ablation asks whether a component explains an observed effect.
For example, removing ones-first selection at the same assignment budget would
address that ordering rule more directly than comparing two unrelated networks.
A structure-free predictor could examine the value of graph information,
provided that the available features and selection protocol were comparable.

The existing B/R/G comparison does not isolate these mechanisms. R and G
match assignment count and class composition, but differ in the supplied
values and share neural-dependent preparation. Their contrast concerns the
complete starting information, rather than a pure effect of the selector
or an independent LP-only pipeline.

## Comparability and interpretation

A sensitivity analysis requires a defined question, factor contrast and
analysis rule before inspecting its new outcomes. Parent-level partitions,
validation-only selection and the exposure limitations of the data remain
relevant. Favourable seeds or parents cannot replace the originally specified
comparison set. Failures, unavailable observations, adverse outcomes and
censoring contribute to the interpretation rather than disappearing from it.

Paired comparisons concern the same parent, solver seed, cap, endpoint and
stopping rule. Different Starts need not generate the same search path:
changing that path is one way they can help or harm. Numerically sensitive
M4/M12 outcomes remain subject to their metric-specific restrictions, even
in a longer or repeated solve.

These distinctions follow the emphasis on comparable settings, stopping rules
and transparent parameter selection in
[Beiranvand, Hare and Lucet (2017)](https://link.springer.com/article/10.1007/s11081-017-9366-1)
and the [Gurobi benchmarking guidance](https://support.gurobi.com/hc/en-us/articles/26992650628369-How-can-I-make-accurate-comparisons).
Neither supplies a universal seed count or certifies the adequacy of a particular
study.

The additional comparisons described here were not part of the reported
fixed-model evaluation. They remain future work. The conclusions are therefore
conditional on the recorded instances, predictor, settings and measurement
boundaries, without claims of robust superiority or architectural optimality.
