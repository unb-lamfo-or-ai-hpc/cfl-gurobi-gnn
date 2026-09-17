# Sprint B: paired partial-start Gurobi experiment

## Implemented pilot, pending licensed qualification

The configuration `configs/experiments/easy_medium_partial_start_v1.json`
precommits a narrow experiment. The `run_easy_medium_pilot` CLI now supplies
`plan`, `pair`, `worker` and `audit` commands. Do not pass this configuration to
the old five-method guidance-policy CLI: its schema and primary intervention
differ. Licensed qualification and the paired experiment must precede review.

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
The inherited confidence score is `max(p, 1-p)`, with priority rounded to
`100 * confidence`; these weighted-BCE outputs are not calibrated probabilities.
Assignments use the frozen validation threshold, not 0.5. In particular, a
score below that threshold may yield a zero assignment despite a large score.
The pilot tests this precommitted convention rather than silently recalibrating
it using medium outcomes. A negative result can motivate a subsequent protocol.

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
No expanded campaign is submitted automatically by this PR.

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
model in a fresh child process is used for each control/start solve. Do not change LB/UB, rows, objective
or domains. Independently validate final solutions on the original MINIMIZE
model. Preserve primal and dual bounds when the time limit is reached.

## Measurements and qualification tests

- Read, build, optimize and total wall-time regions, plus explicitly named
  residual overhead; do not force four numbers to sum by discarding work. File
  hash reading is the data-read region; Gurobi parsing is included in model
  construction. Independent feasibility auditing is an additional region.
  Solution export is a diagnostic subcomponent of residual overhead, not an
  additional additive region.
- Root extraction, graph preparation, loading and inference cost. Report the
  guided end-to-end result with cold preparation cost and, separately, the
  clearly labelled reusable-artifact case. Offline training is reported once,
  with any amortization assumption explicit, not hidden in solver speedup.
  Cold cost is preparation plus measured worker-process wall time. Reusable
  cost still includes verification and loading of prediction artifacts. Queue
  time, offline training, plan/audit and pair orchestration are excluded from
  these comparative totals; the pair receipt separately reports orchestration.
- Final primal, dual, gap, status and independent feasibility; time to first
  feasible solution and to gap<=1%, 5%, 6%, 10% when observable. These are
  first-observed times, not exact hitting times. Unreached times remain
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

## Reproducible execution

Use the merged PR55 training directory, including its original plan, wrapper
report, Gasse report, checkpoint, epoch CSV and SVG. Preflight verifies hashes,
100 epochs, the 18/6/6 easy-only split, model version, threshold and absence of
medium/test loading. Raw target LP files, not target solution reports, are the
only medium inputs. No retraining is required.

Activate the qualified environment and export `EXEC_DIR`, `PYTHONPATH`,
`GRB_LICENSE_FILE`, `EASY_TRAINING_DIR`, `BASE_SOURCE_DIR`, `MEDIUM_PLAN_DIR`,
`MEDIUM_RUN_ROOT` and `MEDIUM_AUDIT_DIR`. Directory arguments must not point to
JSON files. Each attempt needs fresh plan/run/audit directories. Preserve
previous attempts; there is deliberately no overwrite or automatic resume.

```bash
PYTHONPATH=src python3 -m pytest tests/smoke -q
CFL_REQUIRE_SOLVER_TESTS=1 PYTHONPATH=src python3 -m pytest \
  tests/smoke/test_easy_medium_pilot_licensed.py -q -rs

python3 -m cfl_gnn.cli.run_easy_medium_pilot plan \
  --training_dir "$EASY_TRAINING_DIR" \
  --mip_root "$BASE_SOURCE_DIR" --plan_dir "$MEDIUM_PLAN_DIR"
```

Do not submit the pilot unless both commands pass, including all four licensed
tests without skips. The numerical tests use tiny models and CPU inference;
the scheduled pilot uses one GPU for label-free preparation/inference, then
one Gurobi thread per solve. No GPU acceleration of Gurobi is implied. The
initial reservation remains 64 GiB host memory, four allocated CPUs, one GPU
and three hours per two-method task. The array is bounded to `0-1%1`.

```bash
submit_medium_pilot() {
  MEDIUM_ARRAY_JOB=$(sbatch --parsable --export=ALL \
    scripts/slurm/dasci/submit_easy_medium_pilot.sbs) || return 1
  MEDIUM_ARRAY_JOB=${MEDIUM_ARRAY_JOB%%;*}
  [[ "$MEDIUM_ARRAY_JOB" =~ ^[0-9]+$ ]] || return 1
  export MEDIUM_ARRAY_JOB
  MEDIUM_AUDIT_JOB=$(sbatch --parsable --export=ALL \
    --dependency="afterany:${MEDIUM_ARRAY_JOB}" \
    scripts/slurm/dasci/submit_easy_medium_pilot_audit.sbs) || return 1
  MEDIUM_AUDIT_JOB=${MEDIUM_AUDIT_JOB%%;*}
  export MEDIUM_AUDIT_JOB
  printf 'ARRAY=%s\nAUDIT_JOB=%s\nPLAN=%s\nRUNS=%s\nAUDIT=%s\n' \
    "$MEDIUM_ARRAY_JOB" "$MEDIUM_AUDIT_JOB" "$MEDIUM_PLAN_DIR" \
    "$MEDIUM_RUN_ROOT" "$MEDIUM_AUDIT_DIR"
}
```

The audit dependency is `afterany`: failed workers must still be reported.
Do not modify the checkout while jobs are pending/running. Runtime verifies
the implementation hashes frozen in the plan. If the audit submission alone
fails, resubmit only that audit against the recorded array, not both jobs.

### Output inventory and review

Each parent directory contains `root_features.json.gz`, `label_free_graph.pt`,
`predictions.json.gz`, `preparation.json`, method-specific JSON reports and
private `.log` files, optional named `.solution.json.gz` artifacts, and
`pair_receipt.json`. Failed preparation produces `preparation_failure.json`;
the control is still attempted. The root/inference artifacts contain no target
labels. Final solution artifacts are outputs only, never prediction inputs.

The aggregate audit writes:

- `easy_medium_pilot_report.json`: integrity gate, denominators and limitations;
- `per_method_outcomes.json` and `.csv`: independently valid method outcomes,
  including valid unpaired controls when guidance fails;
- `per_method_status.json`: all four planned methods, including missing/failing
  evidence;
- `paired_effects.json` and `.csv`: differences only for valid pairs;
- `source_ledger.json`: hashes of verified pair receipts, which bind their
  individual artifacts.

Review both primary outcomes, bounds, first-observed threshold times, actual
start support and Gurobi start diagnostics. A time-to-optimal speedup is emitted
only if both methods attain solver optimal status; censored comparisons retain
gap and elapsed-time differences but do not invent a speedup to an optimum.
Unknown or unsuccessful start completion is a result, not grounds to discard
a valid full-model solve. Gurobi's default completion effort is recorded, not
silently increased. Negative differences favour guidance; no positive effect
is required for the integrity gate. Share sanitized JSON/CSV and hashes, not
raw logs or license files. Standard SVG namespace URLs are not local paths.

Reference: [Gurobi MIP starts and variable hints](https://support.gurobi.com/hc/en-us/articles/20410834783377-What-are-the-differences-between-MIP-Starts-and-Variable-Hints).
See also [Gurobi warm-start semantics](https://docs.gurobi.com/projects/optimizer/en/current/features/warmstart.html)
and [StartNodeLimit](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html#parameterstartnodelimit).
