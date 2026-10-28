# A proportionate response to unresolved sensitivity questions

This is a proposal for coauthor review, not an experiment authorization.
The current CPU campaign, model, starts and parameters remain frozen.
The purpose is to decide which additional evidence would answer a specific
scientific question, rather than to accumulate configurations.

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
| C — explicit root-method check | Method=1, seed42, same fixed starts and one thread; compare with the corresponding automatic-setting observations | 4 × 3 = 12 solves; at most 144 solver-hours | Repeatability of wall-time termination or a seed×method interaction |
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
It also removes parallel reduction as a factor in this particular comparison,
without eliminating wall-clock variation. A parallel cap would be appropriate
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
one factor. If required, option B would use seed42 from the qualified existing
one-thread cells and two additional seeds specified prospectively, such as
43 and44. Three seeds are a modest sensitivity check, not a statistically
justified universal minimum. More could be needed if dispersion changes the
interpretation; no automatic expansion is proposed.

The historical seed43/44 records belong to a different horizon and cannot
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
Otherwise include new B controls. In particular, an automatic-setting seed42
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
contribution is sufficient for submission. If it is, unresolved sensitivity
analyses can remain future work and be performed if justified by subsequent
review. If it is not, postponement until reviewer demand would leave a known
gap in the central argument: narrow the claims or obtain separate approval
for the required study before submission.

No launcher, CLI command, budget request or new execution accompanies this
assessment. Existing source, data, checkpoint and PR89 evidence remain intact.
