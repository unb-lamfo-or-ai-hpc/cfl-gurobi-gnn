# PR86 — M4 numerical sensitivity and the unchanged next wave

Updated: 16 October 2026. This records observed diagnostics and the author's
explicit decision to finish the original matrix with this limitation. It does
not certify exact feasibility, prove the cause of the cross-run conflict, change
parameters, or authorize an automatic retry. The original CFL formulation and
mandatory MINIMIZE contract remain frozen.

## What was received

The author ran the bounded read-only audit of four stored vectors and returned
`numeric_audit.json`, SHA256
`62232bb0347a58f13d659abbdee408d38e6549654a20bdbc70e7e81548600cc8`.
Collector commit: `13eaff38457fb5c9aba168f4f2959caaa20fe00c`; auditor LF SHA256:
`081d5d484aed191bae2740a4dd576791c02e6cc0857adfa48bc4fb3c2fee68a5`.
The historical campaign source is separately bound to
`596c87bf004405f6148d381d2ba1764c650ca60c` and original wave return
`ed87d2e280a1941228c7662ff234c24dd31a5906d8f0fe1d98962938fcdfdbe6`.

The audit added zero optimization calls, submissions or scheduler queries.
Model, child and sealed-log identities reconcile. The model has 1,281,600
variables, 2,400 constraints and 2,561,600 nonzeros; nonzero absolute matrix
coefficients range from 9.91667e-5 to 800. All four stored floating-point vectors
pass the original integrality 1e-5 and original-unit feasibility 1e-6 checks.

The collector did not overwrite vectors, change parameters or optimize a
rounded solution. Its receipt is preserved byte-for-byte in
[the numerical evidence directory](../evidence/pr86/m4-numeric-62232bb0347a).
Hashes observed for private solution files now are not historical seals: the
old public worker return did not export those hashes. This limitation remains.

## What rounding actually shows

Only integer coordinates were rounded in memory; continuous values were held
fixed. The following are maximum row violations, not objective differences:

| M4 cell | Integer coordinates changed | Stored row residual | Rounded row residual | Rounded residual / existing 1e-6 tolerance |
| --- | ---: | ---: | ---: | ---: |
| M2 / 1 thread / seed43 | 2 | 1.3210e-11 | 2.5368e-4 | 253.68 |
| M2 / 2 threads / seed42 | 19 | 8.3958e-10 | 2.5368e-4 | 253.68 |
| M0 / 4 threads / seed42 | 25 | 1.2225e-11 | 2.5662e-4 | 256.62 |
| M2 / 8 threads / seed42, reported gap zero | 1 | 1.1876e-11 | 9.91667e-5 | 99.17 |

All four rounded vectors fail the original-unit row test, including the
reported zero-gap vector. Their objective changes have magnitude below 1e-6,
far smaller than the largest cross-run objective/bound discrepancy 0.00459584.
The objective contradiction is therefore not eliminated by a change in the
objective sum alone. Nor is an exactly feasible lower-objective counterexample
established: the tested rounded vectors violate constraints.

Dividing each row residual by its maximum absolute coefficient gives rounded
maxima between 1.2396e-7 and 3.2077e-7, with no normalized row above 1e-6. This
illustrates scale sensitivity; **it is not Gurobi's internal scaling, a newly
approved feasibility rule, a repair, or permission to accept these rounded
vectors**. Extended-precision accumulation (63 fraction bits reported by NumPy)
agrees with the original recomputations; it is not an exact-arithmetic proof.
No allowlisted numerical warning was found in the four sealed logs. Absence
of those messages does not certify numerical reliability.

The defensible conclusion is evidence of sensitivity to integrality tolerance
and coefficient scale. The exact historical cause of the cross-run bound
conflict remains unproven. Neither this audit nor rounding certifies the
reported optimum or a GNN speedup on M4. See also Gurobi's
[tolerances/scaling guide](https://docs.gurobi.com/projects/optimizer/en/current/concepts/numericguide/tolerances_scaling.html).

## Author decision and scientific reporting boundary

On 16 October, after these four-vector findings were presented, the author
explicitly selected: **finish the original matrix with this limitation made
explicit**. Decision ID:
`continue_frozen_matrix_with_explicit_M4_numeric_limitation_20261016`.
This does not approve a tolerance change, repair, replacement solve, new seed,
model selection, new formulation or retrospective promotion of receipt flags.

There are 165 structurally collected observations / 55 groups: 147 retain the
previous scoped review; the 18 current M4 cells are marked numerically
sensitive. Their original objectives, bounds, statuses, times, costs and
memory observations remain in the ledger. **Do not silently discard them or
mix the reported zero-gap runtime into a certified speedup/time-to-target
aggregate.** Any eventual performance synthesis must disclose M4's numerical
limitation and distinguish solver-reported gaps from qualified conclusions.
The future M4/16 observations inherit the parent-level warning. Other parents
are not certified numerically exact by absence of this particular conflict.

The [165-row inventory and four-row diagnostic table](../evidence/pr86/m4-numeric-62232bb0347a)
are generated offline by `scripts/evidence/review_pr86_m4_numeric.py`.
The original raw `remaining_dispatch_admitted=false` and eligibility flags
remain untouched. The separate author decision permits preparing the remaining
original manifest; it does not turn the diagnostic into a solver admission.

## How the next execution is bounded

`pr86_wave55.py` reuses the existing six-job queue, isolated executor, memory
supervisor, held-job profile validation and predecessor checks. It selects
only frozen zero-based positions55–60:

| Position | Parent | Physical-core/thread cap | Seed |
| --- | --- | ---: | ---: |
| 55 | M4 / CFL_medium_instance_4 | 16 | 42 |
| 56 | M7 / CFL_medium_instance_7 | 1 | 42 |
| 57 | M7 | 1 | 43 |
| 58 | M7 | 1 | 44 |
| 59 | M7 | 2 | 42 |
| 60 | M7 | 4 | 42 |

Each group retains the three M0/M1/M2 methods in the frozen order. Reuse
roots3520/guidance3521 and private parent indices7/8, without new starts,
root solves, inference, training or package changes. Recheck the installed
original wave and numeric receipt hashes before admission. The plan binds
the author decision and keeps collected counts distinct from qualification.

The approved 210-solve/70-job ceiling is unchanged. This wave is at most six
serial CPU-only jobs, 18 solves, 3,600s/solve, 4h/64GiB per job: 18 solver hours,
24 serial reservation hours and 100 physical-core reservation hours.
Keep MINIMIZE, MIPGap=1e-4, soft memory48 decimalGB, sampled job stop56GiB,
kernelRAM<=64GiB, one logical CPU per selected physical core, no GPU/exclusive
request, requeue, retry, extension or overwrite. afterok plus predecessor
artifact checks supply separate scheduler and evidence boundaries.

The source-pinned author CLI is released only after four final-head checks
pass. Submission returns six IDs without waiting; status and collect are
one-shot; transfer uses one SCP connection. No dispatch follows this wave
automatically. If complete, collected totals would be183/210 /61/70, with
27 solves /9 groups remaining, not183 scientifically qualified performance
observations. PR86 stays draft until the full campaign analysis is complete.

## Validation and remaining work

Tests cover original hashes/identity, original and rounded feasibility,
non-promotion of gap zero, reproducible assets, frozen groups, two-parent
binding, all18 synthetic admissions, serial dependencies and no-repeat claims.
They do not execute an optimizer or scheduler. Final-head CI also checks the
new shell wrapper syntax. Record final test/CI results in the PR checkpoint.

After the remaining campaign: parent-paired quality/time/cost/memory synthesis,
uncertainty, complete reproducible tables/figures and explicit M4 limitations.
PR87's mandatory one-GPU serial/four-GPU DDP experiment requires its own exact
budget; PR88 manuscript work proceeds in parallel. Synchronize develop/main
only after article/coauthor revision and separate final release approval.
