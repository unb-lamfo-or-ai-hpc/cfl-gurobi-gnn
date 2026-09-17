# Sprint B: paired partial-start Gurobi experiment

## Design-only initial delivery

The configuration `configs/experiments/easy_medium_partial_start_v1.json`
precommits a narrow experiment. This PR initially supplies the design and tests,
not a working HPC benchmark launcher. Do not pass this configuration to the old
five-method guidance-policy CLI: its schema and primary intervention differ.
Execution implementation and licensed qualification follow Sprint A's artifacts.

## Question and estimand

Does an easy-only Gasse predictor improve medium-instance optimization relative
to otherwise identical unguided Gurobi? Retain both final gap and optimization
time and separately report end-to-end cost. Lower predictive loss alone is not
evidence for this question. The previously observed medium outcomes inform this
development project; this is not a pristine confirmatory experiment.

The primary intervention is a partial MIP start (`Start`), not variable hints,
hard fixing or local branching. Leave unselected variable starts undefined. Use
the existing label-free ranking and the fixed top10% of canonical binary
variables, with the decision threshold selected only on easy validation. Record
actual coverage and positive/negative predicted assignments. Do not silently
retune on medium outcomes, increase coverage or introduce a repair formulation.

## Staged cohort and budgets

The engineering pilot uses medium instances0 and1, selected by index rather than
their results under the new intervention. Four fresh solves have a maximum
combined optimize budget of four hours, excluding feature preparation/overhead.
Alternate method order by parent-index parity. Use one thread, seed42 and3600s
per optimize call, identical remaining parameters, model and environment.

After pilot review, the target extension is all30medium originals (60 paired
method runs, at most60summed optimize hours including valid pilot runs). Admit
targets independently of prior label gap; retain medium5/6/9 and any other
historical source rejections. Missing/invalid input files and root-capture
failures remain in the denominator and must be reported, not silently replaced.
Extending to30medium is not training on90parents or authorizing new hard solves.
No expanded campaign is submitted automatically by this design PR.

## Reuse and leakage boundaries

Reuse the native solver executor, but qualify its integration with the new
checkpoint and prediction manifest. The old39-parent checkpoint is prohibited
for this experiment. Medium feature construction may read the original matrix,
domains, objective and a real Gurobi root relaxation, but not target labels,
incumbents, final gaps or postsolve statistics. Inference must be label-free;
do not use a loader that requires target solution overlays. Pin model/feature
schema, input hashes, variable order, prediction hashes and checkpoint hash.

Root extraction is a separate preparation solve capped at600s. It may not seed
either method with a solution or reuse its internal solver search state. A new
model is used for each control/start solve. Do not change LB/UB, rows, objective
or domains. Independently validate final solutions on the original MINIMIZE
model. Preserve primal and dual bounds when the time limit is reached.

## Measurements and qualification tests

- Read, build, optimize and total wall-time regions, plus explicitly named
  residual overhead; do not force four numbers to sum by discarding work.
- Root extraction, graph preparation, loading and inference cost. Report the
  guided end-to-end result with cold preparation cost and, separately, the
  clearly labelled reusable-artifact case. Offline training is reported once,
  with any amortization assumption explicit, not hidden in solver speedup.
- Final primal, dual, gap, status and independent feasibility; time to first
  feasible solution and to gap<=10% when observable. Unreached times remain
  censored/missing with reasons, never zero or a fictitious optimum time.
- Start submitted/completed/accepted/rejected/unknown with supporting solver
  evidence. A failed start does not make the final feasible solve invalid.
- Tests for wrong model/checkpoint provenance, variable-order mismatch, target
  label contamination, unintended bound changes, changed artifacts, fair
  per-method parameters and recovery from partial output without overwriting.

First run an inexpensive licensed toy integration check. Then review the two
medium pairs before extending. No inference is claimed from two targets.

## Completion gate

A passing execution gate certifies integrity, not improvement. Deliver paired
per-parent records including failures, a complete planned/observed denominator,
auditable cost decomposition and sanitized hash-checked reports. Scientific
benefit is decided from results in Sprint C, not encoded as a required positive
effect. Hints, SCIP, augmentation arms and hard transfer remain future extensions.

Reference: [Gurobi MIP starts and variable hints](https://support.gurobi.com/hc/en-us/articles/20410834783377-What-are-the-differences-between-MIP-Starts-and-Variable-Hints).
