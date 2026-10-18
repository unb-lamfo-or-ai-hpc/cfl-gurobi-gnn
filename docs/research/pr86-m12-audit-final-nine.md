# M12 audit and the final nine solves — 18 October 2026

## What was received

The author returned the six-vector, read-only audit with SHA256
`c34d043463cb4f3e6ea389ac00b96b779b4a0b23e5c5cf62bda404b60047e7a2`.
Collector commit: `3a2e3bfbc9fb8eb0341603d20f6593ad1bf6a416`.
Auditor source SHA256:
`5b463d2e8b3a95941c0e42f208954dbe95d47e2404f5d9777b89b9920f97f247`.
It binds the original wave61 return `4088a2d464ec` and original model
`c93c8862e4819d1a2b62e721d907afe07b79039d12b953cdb881525c7d251801`.
The independent validator passed before changes. No optimization, scheduler
query, submission, inference or training was added. Original files and all
false eligibility/admission flags remain byte-identical.

The [versioned review and diagnostic table](../evidence/pr86/m12-numeric-c34d043463cb/)
pin collector/helper bytes, all six cell identities, model/child/sealed-log
hashes, original tolerances and extended-precision parity. Newly observed
private-vector hashes are not historical seals or exported variable values.

## Observations: do not conflate M12 and M4

| Stored vectors | Original tolerance checks | Integer-rounded in-memory copy | Largest original-unit row residual after rounding |
| --- | --- | --- | ---: |
| M0 and M1, 1 thread, seed42 (two vectors) | Pass | Row check fails; one integer value changed per vector | 0.0000416587 |
| M2, 1 thread, seeds42/43/44; 2 threads, seed42 (four vectors) | Pass | Pass; no integer values changed | 0 |

The controls' integrality residual is about `5.20734e-8`, within the frozen
`1e-5` integrality tolerance. Their original stored row residuals are about
`1.3e-11`, within `1e-6`. Rounding their integer values while leaving continuous
values unchanged produces a row residual 41.6587 times the existing row
tolerance. Their objective changes are only `-3.15101e-8` and `-1.53836e-7`.
Neither rounding nor row normalization is a repair or a new acceptance rule.
The four M2 vectors have zero *observed floating-point* integrality and row
residuals, unchanged by this diagnostic rounding. Their reported objective
is `4.741382854739205`. The three one-thread M2 runs report a zero gap;
the two-thread run reports approximately `0.0026926%`.

The eight prior comparisons used the two lower, tolerance-feasible control
incumbents, not demonstrated exact integer-feasible counterexamples to M2's
bounds. This delimits the numerical screen; it does not prove its cause or
prove an exact optimum. In M4, by contrast, all four previously audited rounded
vectors failed original-unit rows, including its reported zero-gap GNN vector.
Do not transfer that outcome to M12, or use the positive M12 diagnostics to
retroactively certify M4. No model or solver parameter was changed.

All row-normalized diagnostic residuals are below `1e-6`; no allowlisted
numerical-warning flag was reported. Neither fact proves the absence of
numerical sensitivity. Extended precision has 63 mantissa bits on this host;
it is not exact rational arithmetic. The root model has 1,281,600 variables,
2,400 constraints and 2,561,600 nonzeros, with observed nonzero coefficient
magnitudes from `4.16587e-5` to `800`. These observations are not a new
independent reconstruction of the authors' frozen CFL formulation.

## Author decision and permitted continuation

On 18 October the author explicitly chose: **finish the original nine solves
with the stated M12 tolerance limitation**. This is a separate decision from
the earlier M4 authorization. Decision ID:
`continue_final_nine_with_explicit_M12_tolerance_limitation_20261018`.

Keep all M12 observations and show their sensitivity explicitly; do not use
them as an exact-optimality certificate or certified-speedup result. Keep the
original M4 limitation too. No outcome-based replacement, rerun, changed gap,
parameter, start, objective sense, new seed or preparation is admitted.
Scientific qualification is metric-specific, not a rewrite of raw receipt flags.

Current inventory remains **201/210 cells, 67/70 groups**: 168 scoped observations
outside M4/M12, 21 M4-sensitive and 12 M12-sensitive observations. Six M12
stored vectors were audited, not all 12. The author decision permits the final
nine original cells; the diagnostic receipt itself does not submit or admit them.

## What the final operator does

| Zero-based manifest group | Parent | Physical-core/thread cap | Solver seed | Methods |
| ---: | --- | ---: | ---: | --- |
| 67 | M12 | 4 | 42 | Frozen-order M0/M1/M2 |
| 68 | M12 | 8 | 42 | Frozen-order M0/M1/M2 |
| 69 | M12 | 16 | 42 | Frozen-order M0/M1/M2 |

Reuse root3520, guidance3521 and private parent index9. Three **serial**
CPU-only, shared-node jobs: one node/task, 64GiB/job, at most4h/job and3600s
per solve. Maximum nine solver hours,12 serial reservation hours and112
physical-core reservation hours inside the approved210/70 and1320 core-hour
ceiling. Reservation capacity is not measured CPU consumption. Keep MINIMIZE,
physical affinity,48decimalGB solver soft limit,56GiB sampled stop and kernel
RAM cap<=64GiB. No GPU, exclusivity, requeue, retry, extension or overwrite.

The existing queue now derives its exact size from the validated plan, allowing
only six historical jobs or this three-job tail; it rejects budget overflow.
All bundles and held profiles are recorded before releasing the root; release
is tail-first. `afterok` and predecessor artifact validity protect different
boundaries. No fourth job or automatic later wave exists. Submit returns
three IDs without waiting. Status is one-shot; collect requires all three jobs
terminal. The receiver uses one SCP and a new 64-character return SHA256.

Installed preparation binds the original wave61 return and this audit to
their independent review and the two separate author decisions. Do not rerun
either audit or the201 collected solves. Preserve stage, claim, IDs and partial
returns on failure. T1, related T2, source stabilization and four successful
exact-head CI checks precede release of the source-pinned CLI.

## Closure after the return, not before it

If complete and independently reconciled, the matrix reaches210/210 cells
and70/70 groups. Then regenerate paired CPU/quality/censoring/memory/seed and
scoped-cost tables/figures, retaining sensitive strata and every attempted cell.
Do not call timeout runtimes completed times to target, treat seeds as parents,
or call modeled preparation allocation measured standalone cold whole-job cost.

Prepare the CPU-delivery balance and detailed Project01/chat01.02 handoff from
those final evidence-linked outputs: what MVP2 has achieved, current state,
observed positive/negative results, limits, remaining tasks and presentation
figure/table guidance. PR86 stays draft until execution and analysis close;
merge only after Ready and explicit approval. Sprint D/MVP2 still includes
mandatory matched1-GPU serial/4-GPU DDP PR87 with its separate budget;
PR88 manuscript proceeds in parallel. Final develop/main synchronization
remains after article revision. December2026 submission stays the priority.
