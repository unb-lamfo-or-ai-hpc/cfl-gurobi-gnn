# Jobs3645–3650: 201 cells; M12 numeric review — 18 October 2026

## What, how and why

The original wave61 return SHA256 is
`4088a2d464ec1d1874b249b7aeed0e720a55bf36e35dfb329d859fb853b709d7`.
The source-tree validator passed before changes. A separate pinned review
checks original source34e470752988,plan05685508e7dd,manifest positions61–66,
predecessor review/author decision, six job IDs3645–3650,serial dependencies,
allocation,18 nested solves,model/start/parameter identities,MINIMIZE,
existing tolerance checks and absence of callback/memory stops.
No historical dependency pins are rebuilt against newer source bytes.
Original returns, including false eligibility flags, are preserved.

Six jobs completed0:0 and sum54216s=15h03min36s of scheduler elapsed,
excluding queues; this is not CPU work or solver runtime. All12 supplied
starts were accepted. Four solves reported target termination;14 are censored.
The raw pasted shell/PowerShell prompts are not a JSON evidence source.
[Original receipt,review,CSV201 and four figures](../evidence/pr86/jobs3645-3650/).

## Observed results and scientific limits

| Parent / threads / seed | M0 final gap % | M1 % | M2 % |
| --- | ---: | ---: | ---: |
| M7 /8 /42 |55.4921|50.9540|13.0219|
| M7 /16 /42 |40.4965|40.4965|13.1437|
| M12 /1 /42 |6.0714|6.4599|0 reported|
| M12 /1 /43 |7.6777|10.0394|0 reported|
| M12 /1 /44 |6.5105|6.9043|0 reported|
| M12 /2 /42 |6.0802|6.5312|0.0026926 reported|

M7 now has all21 observations, five caps at seed42 and one-thread seeds43/44.
All21 are censored. M2 has lower terminal gap than M0 in four/five seed42
groups and five/seven groups overall, not uniformly. Report quality differences,
not time-to-target speedup from nearly equal timeout runtimes. No conflict
appeared for M7 in the same same-model bound/incumbent screen; that is not an
exact certificate. High thread counts do not monotonically improve quality.

M12's four M2 runtimes (582.390–685.428s) appear lower than the eight3600s
timeouts, but its reported lower bounds exceed two same-model tolerance-feasible
incumbents. M2/1/seeds42,43,44 report primal=bound4.741382854739205;
M0/1/42 reports4.741101359773271 and M1/1/42 reports4.740932705476565.
M2/2/42 lower bound4.741255187252368 also exceeds both. Eight comparisons
involve six unique stored vectors. Differences0.000153827–0.000450149,
or0.003245–0.009495%, are smaller than the frozen0.01% gap target but exceed
the pre-existing same-model numerical screen. Do not equate this with M4's
larger discrepancy, prove a solver defect, assert exact integer feasibility,
or claim GNN speedup/unequivocal optimality from these statuses.

The M4 audit is not a certificate for M12. No new parameter/tolerance, repair,
objective sense, support or seed is selected from these outcomes. MINIMIZE
and the authors' frozen CFL premise remain unchanged.

## Denominators and bounded next action

201/210 cells,67/70 groups,ten historically exposed parents. Of201,168 retain
the previous/non-M4/M12 scoped review;21 M4 cells remain sensitive;12 M12
cells now await numerical qualification.132 *reported* target-reaching cells
include the one disputed M4 report and four unqualified M12 reports;69 are
censored. No blanket scientific promotion. Nine solves/three jobs remain:
original M12/4,8,16/seed42, within the approved210/70 budget.

Do not release these final groups yet. The next author CLI is a read-only
audit of the six existing M12 vectors,original model and sealed logs. Reuse
the tested M4 array/bundle readers without modifying their historical source.
Load Gurobi only to read the model and forceMINIMIZE; never call optimize.
Recompute stored objective/bounds/integrality/rows at original tolerances;
round integers only in a temporary in-memory copy, leaving continuous values
unchanged. Record original-unit and normalized diagnostic residuals and
extended-precision observations. These are diagnostics, not a repair or new
acceptance rule. Export only scalar summaries/hashes/allowlisted log flags.
New private-vector hashes attest current bytes,not historical seals.

Limits: six sequential vectors,one model,16GiB virtual-address-space cap,
512MiB decompressed per vector,1200s wall cap,no scheduler call/job,
optimization,inference,training,package upgrade,raw-log/vector export or retry.
New files only under `/raid/vrcelestino/data/cfl-mvp2-evidence/pr86/`.
The existing private license is read,not copied. Preserve partial output on
failure; no automatic continuation. A separate independent return validator
binds source/helper bytes,receipt hash,all six cells,model/child/log hashes,
original tolerances and false execution/scientific gates. It does not assume
whether rounded vectors will pass. Interpretation follows the actual return.

## Sprint completion and coauthor handoff

1. Interpret the six-vector audit. If needed, seek a narrowly scoped scientific
   decision on M12,not implicit extension of the earlier M4 authorization.
2. Execute the final three original groups only after this gate is delimited;
   do not rerun the201 collected cells or preparation3520/3521.
3. Reconcile210 rows,70 groups,all attempts/failures,matched method comparisons,
   CPU curves,quality/censoring,memory,one-thread seed variation and scoped
   preparation/attempt cost. Separate sensitive parents,never replace them.
4. Produce the CPU-delivery balance and a detailed Project01/chat01.02 prompt from
   the final qualified evidence,including negative/heterogeneous findings,
   denominators,hyperparameters and claim-to-receipt links. Prepare the
   coauthor presentation there; do not describe this Sprint as already closed.
   PR86 closes the CPU delivery,not all of Sprint D: mandatory PR87 matched
   serial/4-GPU training remains part of that Sprint and of MVP2.
5. T1 -> relatedT2 -> stabilization -> four final-headT3 checks -> Ready.
   Request merge only then. Technical corrections remain in PR86.

PR87 mandatory1-GPU serial/4-GPU DDP training still requires its exact separate
budget and matched global work/quality protocol. PR88 manuscript proceeds in
parallel; subsequent analysis/review precedes final develop/main synchronization.
No augmentation,architecture search or unnecessary refactor; December2026
submission remains the objective. This CPU matrix alone does not complete MVP2.
