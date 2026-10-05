# Post-PR66: bounded read-only phase observations

PR66 was merged into develop at
`7b5930300a562c7f9c989ad4c511e7f9875cc2a8`. This follow-up advances Sprint A
reconciliation and interpretation of the bounded Sprint B screen. It does not
complete either the historical incumbent ledger or a replicated scaling study.
MVP 1.0, main, Pages and Zenodo remain unchanged.

## Question and scope

Job 3468 completed ten attempts. All medium attempts reached the time limit;
their one-node counters alone cannot distinguish LP solution, cuts, heuristics
or other root-node work. Recover the existing private logs without optimizing
again. This is evidence collection, not a new experiment or a parameter change.

The standard-library-only collector reads precisely the ten
`<attempt>/gurobi.private.log` siblings of the preserved plan. Every input plan,
execution receipt and attempt receipt must match the already reviewed public
job-3468 bytes. The original manifest itself is pinned. No original LP, license,
checkpoint, shell stdout log or unlisted file is opened. No solver library,
Slurm submission, GPU initialization or training is used. Each log is limited
to 8 MiB; symlinked logs and changing sources are rejected.

## What the observations mean

| Field | Interpretation |
| --- | --- |
| model_read_setup_seconds | Existing worker measurement, including environment/model setup; not LP presolve. |
| optimize_wall_seconds | Existing external wall clock around optimize; not CPU consumption. |
| presolve_display_seconds | Single recognized solver display duration; rounded, possibly unavailable. |
| root_relaxation_display_seconds | Single recognized root-LP display duration; inspect its completion/interruption state. |
| solver_total_display_seconds | Rounded terminal solver runtime, checked against the original receipt. |

A completed root relaxation is not completion of root-node processing: cuts and
heuristics may still consume time at the root. Never compute a tree-search
duration by subtracting presolve and relaxation from total runtime. Never sum
nested/concurrent log durations or substitute work units for CPU seconds.
Missing, duplicate, unsupported or interrupted observations stay distinguishable.
No displayed duration becomes a per-phase CPU/GPU cost.

The parser accepts only Gurobi 13.0.1 headers and frozen control values. Terminal
node count, objective, bound, gap and rounded runtime must agree with the public
receipt before any phase observation is exported. This consistency check cannot
prove historical log authenticity: these logs were not hash-bound during the
original execution. Their SHA256 hashes establish identity at collection time,
not a retroactive execution-time signature. Provenance states this limitation.

The three-member output package contains only numeric/enum observations,
known public parent identities and hashes: JSON, CSV and their SHA256 manifest.
Private line text, filesystem paths, license identifiers and raw logs are not
included. Inputs remain untouched, and a fresh output directory is required.
All scientific eligibility, phase CPU-cost qualification and tree-duration
qualification flags remain false.

## CLI, once the reviewed branch is installed

```bash
conda activate tfm_env
SOURCE=/raid/vrcelestino/data/cfl-mvp2-evidence/pr66/screen-20261004T215016Z-nDCYJh/plan
RESULT=/raid/vrcelestino/data/cfl-mvp2-evidence/pr67/phase-job3468-$(date -u +%Y%m%dT%H%M%SZ)
python scripts/evidence/collect_pr66_log_phases.py "$SOURCE" --output "$RESULT"
printf 'RESULT=%s\n' "$RESULT"
```

Run from the reviewed isolated worktree, not an unrelated dirty checkout. No
job monitoring is required. Keep both failed job 3466 and completed job 3468.
Return the printed package hash and the allowlisted package for independent
review. Missing/unsupported evidence is a valid outcome; do not rerun the solver
to fill it or upload private logs. A collector failure does not authorize cleanup.

## Reviewed collection and stopping decision

The returned 3,058-byte package has SHA256
`389ff4a14e65d5e199668d2569a5157731c85a36f6d2eaec0fa9d16a2073e6ff`.
Its three original exports are preserved byte-for-byte under
[`docs/evidence/pr67/job3468`](../evidence/pr67/job3468/).
Independent offline review checked outer/internal hashes, member allowlisting,
all ten original attempt identities and exact JSON-to-CSV projection.
The outer compressed package remains in operator/local evidence; the public
manifest authenticates its two exported payloads, not a rebuilt archive.

Nine logs passed the existing consistency gate. For the qualified medium
attempts (caps 1, 2, 4 and 8), displayed presolve spans 13.67–14.45 seconds and
the initial root LP completed in 2.46–3.41 seconds. Thus those four attempts did
not time out before that initial LP finished. This does not identify the cause
of later time consumption or measure complete root-node or tree-search work.
The two-instance, one-seed, ordered shared-node screen is not a general scaling
study or a basis for selecting a thread cap by observed best runtime.

`medium-threads16` remains **unqualified**, with all displayed phases null.
A hash-checked, read-only numeric diagnostic returned by the operator isolates
the failed check: node count, objective, bound and gap agree with the receipt;
displayed runtime is 300.10 seconds versus API Runtime 300.20282006263733 seconds.
The absolute difference, 0.10282006263730636 seconds, exceeds the unchanged
0.051-second gate. The diagnostic JSON is a recorded operator return, not an
independent replay of the raw log or a cryptographically signed attestation.

Gurobi defines Runtime as elapsed optimization wall time; its TimeLimit
documentation allows additional termination computations after the limit.
These facts do **not** establish why this footer and API attribute differ.
Neither simple rounding nor a particular cleanup routine is asserted as the
cause. Runtime remains authoritative in the original attempt receipt. No
display phase is promoted, no threshold is widened to fit this observation,
and no solver result, source log, original package or collector is changed.

This is the collection's complete bounded outcome: **nine consistent logs and
one explicitly unqualified log**, not ten successful phase recoveries. Missing
phase evidence is an accepted stopping outcome, not a reason to resubmit 3468.
The review closes this read-only collection question while leaving historical
incumbent/lineage certification and scientific eligibility open. A future
logging protocol can bind logs during execution and distinguish observation
times; it is not retroactively applied to this run.

## Next gates toward MVP 2.0

1. Review this collection and continue explicit historical attempt/job joins and
   full-vector incumbent/lineage audits; do not certify counts from solution_count.
2. Freeze the easy-only 18/6/6 and matched mixed 34/10/10 learning contracts,
   preparation costs, parent mass, optimizer updates and validation policy.
3. Qualify serial then two-GPU DDP before four/eight GPUs. Obtain a separately
   approved training/resource budget before submitting anything.
4. Preregister paired warm-start transfer and resource comparisons before using
   new outcomes to select policies. Larger CPU matrices remain unapproved.

Reference: [Gurobi MIP logging](https://docs.gurobi.com/projects/optimizer/en/current/concepts/logging/mip.html).
The documented distinction between root relaxation and root-node cuts/heuristics
motivates the conservative separation above; this follow-up makes no causal
claim about why the five medium attempts timed out.

Timing references: [Runtime](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/model.html#runtime)
and [TimeLimit](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html#timelimit).
These document metric/termination semantics, not the cause of the recorded
0.10282006263730636-second footer discrepancy.
