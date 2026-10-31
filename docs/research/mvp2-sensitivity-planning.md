# Internal sensitivity planning and scientific interpretation

## Hypotheses informed by the partial return — 31 October 2026

Use the received 50 cells as pilot evidence, without changing the current campaign. First separate numerical comparability of M4/M12 from performance; then ask whether favourable and adverse B/R/G contrasts persist under prospectively chosen solver seeds. Distinguish intermediate quality targets from terminal attainment. The final ten cells should inform a proportionate proposal before any new execution decision. Do not launch a factorial seed/root-method/neural-hyperparameter campaign or treat pilot-selected contrasts as confirmatory. Existing-vector/log review and a future new-solve campaign are different activities. No new budget or execution is authorized.

## Optional work-limited repeatability — 30 October 2026

WorkLimit is an optional future design for algorithmic repeatability or equal-work quality comparison, not a retrospective replacement for TimeLimit. No work-unit budget is inferred from Runtime, and no additional execution is authorized or required for the editorial correction. Current B/R/G inputs, seeds, caps and stopping rules remain frozen. S1/S2/S4/S5 continue documentary/offline work; S3 concerns only the existing campaign; S6 retains editorial approval gates. Any future work-limited or cross-engine experiment needs its own prospective estimand, protocol and specific authorization.


30 October 2026: the standalone journal sensitivity supplement is retired in favour of concise future-research discussion in the article. The explanatory text is preserved below as an internal reference. Original prospective budgets remain historical planning, not execution authority. No seed, root method, predictor, training, inference or solve is added to S1–S6.

<!-- Internal prospective planning record; not journal supplement text. -->

# A proportionate response to unresolved sensitivity questions

## What this discussion is for

A useful follow-up should resolve a scientific uncertainty. *Sensitivity*
asks how an observed result changes when a specified choice changes.
*Robustness* asks whether the interpretation survives those changes.
An *ablation* removes or replaces a component to examine its contribution.
These questions overlap, but they are not interchangeable: changing a solver
seed does not test a neural architecture, and faster training does not show
that a Start helps the optimizer.

The present article studies one fixed prediction-to-Start pipeline. This
document explains which additional comparisons could strengthen particular
claims, and what those comparisons would still leave unresolved. The resource
counts below are planning examples, not experimental findings.

Only option A belongs to the current S1–S6 completion work: receive, qualify
and analyze the campaign already authorized. Options B–E and the separate
four-hour diagnostic design remain limitations and future work. They introduce
no new training, inference or solves into the current plan.

The [Sprint/PR plan](mvp2-closeout-plan.md) governs
completion and coauthor review. Existing CPU jobs, starts and settings remain
frozen. A later study would require a separate human decision and a prospective
protocol; neither a reviewer request nor a cost ceiling authorizes it.

## What the present article can defend

The study evaluates a fixed predictor and partial-start policy on explicitly
identified CFL instances. Its results can describe observed improvements,
regressions, censoring and costs. They cannot establish seed-averaged solver
performance, optimal network hyperparameters, or general superiority of
class-aware selection.

This distinction determines whether additional experiments are necessary.
If the article makes those stronger claims, further evidence or weaker wording
is required before submission. If it consistently presents a bounded study,
the untested questions can be stated as limitations and prioritized future
work. That is a defensible scope decision, not a guarantee of acceptance by
Computers & Operations Research.

The [official journal description](https://shop.elsevier.com/journals/computers-and-operations-research/0305-0548)
requires meaningful scientific comparisons and reproducibility. It does not
provide a universal number of seeds or an architecture grid that guarantees
sufficiency. The authors must judge whether our contribution and evidence
meet the journal's standard.

## Four questions that require different experiments

**Search-path sensitivity.** Do B/R/G effects persist when the Gurobi seed
changes, holding the predictor and its starts fixed? These runs assess the
solver's response. They do not test neural initialization.

**Solver-configuration sensitivity.** Does an explicit root LP algorithm
change those effects compared with automatic selection? Method controls the
continuous/root algorithm, not the whole MIP search. A comparison of root
methods does not isolate the effects of all heuristics, cuts or branching.

**Training sensitivity.** Would another initialization or training configuration
produce a predictor with similar validation/test behaviour and solver utility?
This requires training, validation selection and new inference, not merely
changing the Gurobi Seed parameter.

**Mechanism ablation.** Does a particular ingredient account for an improvement?
Examples include removing ones-first ordering at a matched information budget,
or comparing graph structure with a structure-free predictor. Such designs
address causal claims about an ingredient more directly than comparing several
large GNN families.

These questions should not be combined into a full factorial study by default.
An observed benefit at one setting does not establish an interaction between
seed, root method and network capacity.

## Alternatives and their incremental cost

The counts below are transparent planning examples. They assume the four
existing medium parents, all three B/R/G methods, one physical thread, and
a 12-hour solver ceiling. They are not commitments, forecasts or authority
to execute. Retaining all four parents prevents choosing only favourable cases;
M4/M12 still require their existing metric-specific numerical qualifications.

| Option | Question and design | Incremental executions and ceiling | What it would still not establish |
| --- | --- | --- | --- |
| A — finish the existing study | Qualify the CPU return, inspect available logs and report bounded conclusions | No additional training, inference or solves | Variability across seeds, configurations or trained models |
| B — two additional solver seeds | Keep Method=−1, original checkpoint/starts and one fixed thread cap; use two seeds chosen before examining new outcomes | 4 parents × 3 methods × 2 seeds = 24 solves; at most 288 solver-hours | Precise distributional estimates or robustness beyond this small seed/parent set |
| C — explicit root-method check | Method=1, seed 42, same fixed starts and one thread; compare with the corresponding automatic-setting observations | 4 × 3 = 12 solves; at most 144 solver-hours | Repeatability of wall-time termination or a seed×method interaction |
| D — narrow network sensitivity | Compare baseline L=2,d=32 with L=1,d=32 and L=2,d=64, using the same data roles and validation rules | At least two trainings, graph inference and 16 new R/G solves; up to 192 solver-hours for those R/G cells, plus any required B controls | Superiority over GCN/SAGE/GAT, training-seed robustness, or a pure selector effect |
| E — training-seed check | Two additional training seeds with the fixed architecture, followed by validation-selected checkpoints/thresholds and R/G evaluation | At least two trainings, new inference and 16 R/G solves; controls and training resources require their own design | Architectural optimality or solver-seed robustness when solver seed remains fixed |

For D/E, the 16 R/G solves are two new predictors × four parents × two methods.
They are a lower-bound design count, not the complete campaign budget.
R must be rebuilt to match each predictor's actual support and one counts.
The existing R starts cannot simply be reused for a different predictor.
Training time, preparation cost, memory and control runs are not included in
the stated solver-hour subtotal.

For B/C, if the existing 13-hour job-wall convention were separately approved
for a follow-up, the reserved wall ceilings would be 312 and 156 hours,
respectively. At one physical core those would also be reserved physical
core-hours. Queue time is additional and unknown. These are conservative
ceilings obtained by multiplication, not estimated actual consumption.

Using one thread avoids repeating the five-cap scalability experiment.
It narrows the proposed comparison to a serial solver regime without
eliminating wall-clock variation. A parallel cap would be appropriate
only if the scientific question explicitly concerns a parallel regime; it
must be chosen before looking at the new results.

### A shorter diagnostic study, if the later question permits it

A separately designed four-hour study could use all three seeds at one cap:
4 parents × 3 methods × 3 seeds = 36 new solves, with a ceiling of 144
solver-hours. This costs less solver time than adding two 12-hour seeds,
but answers a different question: sensitivity under a four-hour budget.
It cannot establish robustness of the full 12-hour result.

Seed 42 would also need a run with the newly specified four-hour limit.
The first four hours of an existing 12-hour trajectory cannot automatically
be treated as an experiment configured with TimeLimit=14400: stopping
parameters can affect solver behaviour, and recorded horizon observations
have their own timestamp/coverage qualifications. Existing traces can
inform the question, but not silently replace the missing treatment.
This option never changes or truncates the current campaign.

## Why the smallest follow-up would usually start with seeds

A small seed study asks whether the observed direction is sensitive to the
solver search perturbation. It keeps the learned information fixed and changes
one factor. If required, option B would use seed 42 from the qualified existing
one-thread cells and two additional seeds specified prospectively, such as
43 and 44. Three seeds are a modest sensitivity check, not a statistically
justified universal minimum. More could be needed if dispersion changes the
interpretation; no automatic expansion is proposed.

The historical seed 43/44 records belong to a different horizon and cannot
be counted as CPU12h replications. They can inform a clearly labelled historical
discussion. They must not be pooled to claim that the longer-horizon campaign
already has three seeds.

Option C has a narrower purpose. Existing logs should first be examined:
automatic MIP-root selection commonly already uses dual simplex. If that is
what occurred, explicitly setting Method=1 may add little information about
the question that motivated the comparison. A root-method check is useful
when there is a concrete doubt about algorithm selection, not as a ritual
response to the presence of −1 in a configuration file.

Changing Method also does not guarantee an identical terminal state under
TimeLimit. A work-based stopping design could address a different repeatability
question, but it would change the resource boundary and cannot replace or
retroactively reclassify the current time-budget study.

## Conditions for a fair follow-up

A new proposal must specify the question and analysis before its new outcomes
are observed. It should retain all planned parent/method cells, including
failures, censures and adverse results. Checkpoint/threshold selection stays
on validation data; test outcomes must not select a network or a favourable
seed. Existing test exposure remains a limitation even if these rules are
followed.

Paired solver comparisons should use the same parent, solver seed, thread cap,
root-method setting, target and stopping rule. Pairing does not mean that
different starts should generate identical search paths. Multiple seeds are
repeated measurements within parents; they do not turn four parents into
twelve independent problem instances. With only a few seeds, individual
results, direction changes and descriptive spread are more honest than
claims of precise population uncertainty.

For root-method sensitivity with frozen starts, the estimand is the solver
response conditional on the originally prepared information. It is not an
end-to-end comparison in which roots, graph features and predictions are
regenerated under each method. For network sensitivity, keep the originally
defined graph/preparation protocol and report the new training and inference
costs as well as solver outcomes.

An old B record can be reused only if the proposed protocol explicitly
accepts its identity, configuration, horizon and measurement conditions.
Otherwise include new B controls. In particular, an automatic-setting seed 42
run cannot silently become an explicit-Method=1 replication even if its
log suggests dual simplex. A new configuration remains a new treatment.

“Try every Gurobi method” is not a suitable minimal design: barrier and
concurrent options have different memory/thread implications, and some choices
would require additional interpretation. Likewise, a broad GCN/SAGE/GAT grid
would introduce architecture, optimization and selection differences at once.
Neither is necessary merely to explain the fixed model honestly.

These principles follow the emphasis on comparable settings, stopping rules
and transparent parameter selection in
[Beiranvand, Hare and Lucet (2017)](https://link.springer.com/article/10.1007/s11081-017-9366-1)
and the [Gurobi benchmarking guidance](https://support.gurobi.com/hc/en-us/articles/26992650628369-How-can-I-make-accurate-comparisons).
Neither source certifies this particular study or supplies a sample-size
guarantee.

## Recommendation for the current submission

Proceed with option A now: complete the authorized campaign, improve the
explanation of the fixed configuration, and state the missing sensitivity
evidence in the article and supplement. Prepare option B as the first
candidate if stronger solver-robustness evidence is needed. Consider C only
after the existing logs identify a genuine unresolved method question.
D/E should follow a specific predictive or mechanism claim, not precede it
automatically.

The coauthor review before 15 December should decide whether the bounded
contribution is sufficient for submission. The current plan keeps unresolved
sensitivity analyses as future work. If the present evidence is insufficient,
narrow the claims or revisit the submission strategy; do not quietly turn
these prospective studies into Sprint tasks. Any later change to the
experimental scope requires a separate human decision and protocol.

No launcher, CLI command, budget request or new execution accompanies this
assessment. Existing source, data, checkpoint and PR89 evidence remain intact.


## Preserved explanatory discussion from the former standalone supplement

### Sensitivity and directions for further study

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
