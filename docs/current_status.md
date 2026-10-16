# Current status

## Current checkpoint — 16 October: 165 collected; M4 numeric gate pending

[M4 numerical review](research/pr86-wave49-numeric-review.md) preserves the
jobs3609–3614 original return,18-row table and three-conflict screen. Structural
and per-run tolerance checks passed, but the reported M2/8 lower bound exceeds
three same-model tolerance-feasible incumbents. Cause is not proven. Keep165
collected distinct from147 previously reviewed;18 M4 cells await numerical
qualification.45 main solves/15 groups remain unexecuted. Next: author-run
read-only audit of four stored vectors, model and sealed logs; no optimization,
job, retry, parameter change or next-wave release. PR86 remains draft.
Earlier checkpoints are historical observations, not current dispatch authority.

## Current checkpoint — 15 October: 147 solves reviewed; complete medium M0

[Jobs 3598–3603 review](research/pr86-wave43-review-wave49.md) reconciles
147/210 solves and 49/70 groups. The six easy parents and medium M0 are
complete. There are 127 target-reaching solves and 20 censored observations.
For M0, only M2/16 threads/seed42 reached the target (gap zero, 3204.179 s);
GNN effects are heterogeneous across caps/seeds. CSV147 and complete M0 gap
and sampled-memory figures retain quality, censoring and distinct cost scopes.
Remaining: 63 solves/21 groups. Next positions49–54: M4/1/seeds42,43,44 and
2/4/8/seed42; M4/16 follows later. Six serial jobs,18 solves, up to4h/64GiB
per job,68 physical core-reservation hours within the approved ceiling.
Success would yield165/210 and55/70. Final-head CI precedes CLI release.
Earlier sections are historical snapshots, not the current remaining counts.

## Current checkpoint — 14 October: 129 solves reviewed; six easy parents complete

[Jobs 3592–3597 review](research/pr86-wave37-review-wave43.md) reconciles
129/210 solves and 43/70 groups. All six exposed easy parents are complete:
126 target-reaching solves. The first medium group (parent M0, one thread,
seed 42) adds three valid time-limited observations, censored for time to
target. M2 has a better incumbent than method M0, but a worse gap; report
incumbent, bound and gap separately. Original bytes/flags remain preserved.
CSV129, complete F29 CPU and partial medium quality figures are regenerable.
Remaining: 81 solves/27 groups. Next positions 43–48 complete parent M0:
one-thread seeds 43/44, then 2/4/8/16 threads at seed 42. Six serial jobs,
18 solves, up to 4 h/64 GiB per job and 128 physical core-reservation hours,
within the approved ceiling. Success would yield 147/210 and 49/70.
Final-head CI precedes CLI release. Earlier sections are historical snapshots.

## Current checkpoint — 14 October: 111 solves reviewed; F29 and first medium group next

[Jobs3586–3591 review](research/pr86-wave31-review-wave37.md) reconciles 111/210
solves and 37/70 groups across six exposed easy parents. F0/F3/F6/F14/F27 are
complete; F29 has one thread at seeds42/43. All 18 new solves meet gap<=0.01%,
with valid solutions and no memory/callback stop. F27 is heterogeneous at16
threads; F29 is mixed across its two seeds. Original bytes and flags, CSV111,
complete F27 and partial F29 figures are preserved and regenerable.
Next positions37–42: F29/1/seed44 and2/4/8/16/seed42, then medium M0/1/seed42.
Six sequential jobs,18 solves,64GiB/job,at most4h/job;128 physical-core-hours
reserved within approved210/70. Success would yield129/210 and43/70.
CI at the final published commit precedes CLI release. Earlier sections are history.

## Current checkpoint — 14 October: 93 cells reviewed, F27/F29 next

[Jobs3572–3577 review](research/pr86-wave25-review-wave31.md) reconciles93/210
solves and31/70 groups across five historically exposed parents. F0/F3/F6/F14
complete; F27 has1thread/seeds42,43,44. All18 new solves meet gap<=0.01%,
with valid solutions and no memory/callback stop. Heterogeneous timings and
nonzero gaps remain visible in the cumulative CSV and completeF14/partialF27
figures. The original return bytes and flags are preserved.
Next frozen positions31–36: F27/2,4,8,16/seed42 and F29/1/seeds42,43.
Six serial jobs,18solves,<=24h reservation,128 physical-core-hours,64GiB/job,
inside approved210/70. Success would yield111/210 solves and37/70 groups.
Final-head CI precedes CLI release. Earlier checkpoints remain history.

## Current checkpoint — 13 October: 75 cells reviewed, F14/F27 next

[Jobs3562–3567 review](research/pr86-wave19-review-wave25.md):75/210 cells,
25/70 groups; F0/F3/F6 complete, F14/4,8,16 pending. Original receipt and
failed-transfer directory preserved. All18 new cells meet the gap target;
F14 shows mixed GNN timing effects. Four exposed parents, not75 independent
instances. New cumulative CSV and completeF6/partialF14 figures are regenerable.
Next frozen positions25–30: F14/4,8,16/42 and F27/1/seeds42,43,44. Six serial
jobs,18solves,<=24h reservation,124 physical-core hours,64GiB/job,inside210/70.
No new preparation, retry or later automatic dispatch. Prior sections remain
history. Final main synchronization still follows article revision.

## Current checkpoint — 13 October: 57 cells reviewed, F6/F14 next

[Jobs3555–3560 review](research/pr86-wave13-review-wave19.md):57/210 cells,
19/70 groups; F0/F3 complete, F6/8,16 pending. Original bytes preserved;
57-row CSV, completeF3 and partialF6 CPU figures regenerate offline. All18 new
cells meet the gap target. F6 has heterogeneous method/seed behavior; no
population or independent-generalization claim. Next fixed positions19–24:
F6/8,16/seed42; F14/1/seeds42,43,44; F14/2/seed42. Six serial jobs,18solves,
<=24h reservation,116 physical-core hours,64GiB/job,within approved210/70.
Reuse preparation; no retry or further automatic dispatch. Prior sections are
history. Main synchronization remains after article revision, not before.

## Current checkpoint — 13 October: 39 cells reviewed, F3/F6 next

[Jobs3542–3547 review](research/pr86-f3-review-next-wave.md) adds 18 valid F3
cells: **39/210 cells,13/70 groups** cumulatively, with original bytes preserved.
F0 has all five caps; F3 has 1/2/4/8 and one-thread seeds42/43/44, with16 pending.
The cumulative CSV and partial F3 figure are descriptive, not generalization.
Next six fixed positions13–18: F3/16/seed42, then F6/1/seeds42,43,44 and
F6/2,4/seed42. Up to18 solves,24 serial reserved hours,100 physical-core hours,
64GiB/job, within the existing budget; no repeated preparation or automatic retry.
The same serial executor now has tested two-parent input/bundle binding.
Main/develop synchronization remains postponed until after article revision.
Earlier sections are dated history, not the current execution state.

## Current checkpoint — 13 October: F0 complete, F3 next

The [F0 review](research/pr86-f0-review-f3-wave.md) reconciles jobs3522–3528:
21/210 main cells, seven/70 groups, one independent parent. All reached the
frozen 0.01% gap target, with matched models/parameters and valid returned
solutions. No population speedup claim. Original receipt flags/bytes unchanged.
CPU table, SVG and scoped cost scenarios regenerate from the pinned returns.
Next: six frozen F3 groups (18 cells, <=24 serial reserved hours, <=68 physical
core-hours), inside the approved budget. No repeated preparation, inference,
training or automatic retry. F3/16 threads remains for the following wave.
After success:39/210 cells; no dispatch beyond those six groups.

Author decision: **defer ALL develop/main synchronization until AFTER the
article revision**, including any main-to-develop reconciliation. Work stays in
PR86/develop. Final synchronization requires separate release review/approval;
neither these results nor publication authorizes a merge or HPC submission by
the agent. PR87 mandatory 1/4-GPU training and PR88 manuscript remain next.
The dated sections below are historical checkpoints, not current blockers.

## Latest execution checkpoint — six-job wave approved

Job3522 completed the first F0/one-thread/seed42 group in 546 s. Its original
return `dd1a553b4532` passed independent nested review: three solves, matched
parameters/model, MINIMIZE, both starts accepted, no memory stop. M0/M1/M2
solver seconds: 100.705 / 109.595 / 306.390; no general performance claim.
The author now requests six serial jobs of <=4 h, queued together. The
[six-job wave](research/pr86-job3522-six-job-wave.md) implements the next frozen
F0 groups, 18 calls inside the approved 210; <=24 h serial reservation and
128 physical-core-hours. No repeat preparation. Slurm afterok plus predecessor
artifact validation prevents continuation after failure. Next: final-head CI,
source-pinned CLI, installed collection/review. No wave job submitted by this
publication, no merge; PR86 remains draft. Older sections below are historical.

Updated: 2026-10-12. PR85 merged; PR86 implementation in progress. Jobs3520/3521
completed the ten roots and ten prospective graph/inference/start preparations.
Both public returns passed independent review. M1/M2 starts exist for all ten
parents, without abstention; their acceptance by the solver is not yet observed.
See [job3521 review, costs and exact remaining budget](research/pr86-job3521-review-and-main-budget.md).
The author approved the exact 210-main-solve/70-job ceiling on 12 October.
The nonblocking first-group operator is implemented: only F0/1 thread/seed42,
three methods counted inside that ceiling. Next: execute the final-head CLI,
review its installed return, then enable remaining dispatch. No new root capture,
inference or training is needed. No main job has been submitted here; PR86 is draft.

**Frozen formulation decision (12 October):** the authors accept MILPBench CFL
as correct except for MAXIMIZE. Always force MINIMIZE, preserving original
files and all other mathematical data, through the final sprint. The generator/
semantic-recertification gate is withdrawn. Historical audit limits below are
retained as history, not a renewed requirement. Implementation identity,
preparation provenance and explicit HPC budget remain required.

PR86 baseline `a0ce4f7` passed its four exact-head CI checks. The
[prospective integration](research/pr86-prospective-instrumentation.md) now
connects the isolated child to the existing memory supervisor, validates
physical affinity and admission bindings, seals logs and reconciles paired
groups. Constructor/disposal failure cleanup is specialized without changing
hash-bound historical sources. Tests substitute allocation and solver;
installed qualification is not inferred. Campaign-wide claims/submission,
prospective preparation and scientific/resource admission remain open.
Engineering follows T1 → T2 → stabilization → T3/final-head CI → Ready,
with measured CI stages, no removal of distinct safety boundaries and no
extra PR for technical fixes. No HPC or merge is admitted by these changes.

The published integration `72edf61bc1172f294383df148dc0ae25bc987453` passed all
four evidence CI arms. Its continuation implements the bounded ten-parent
root-preparation operator, public collection/review and a one-connection
PowerShell receiver. Proposed execution: one CPU job, one physical core,
64 GiB, at most 10 sequential root optimizations of 600 s and 12,000 s job wall.
This replaced ten proposed root jobs, not the 210 main solves. The author
subsequently approved this one root job; job3520 completed all ten roots.
See the linked integration document for cost scopes and stopping
conditions. The PR remains draft. Installed guidance subsequently completed
as job3521; the full comparison operator remains pending. Neither reopens
the frozen formulation.

## Integrated baseline

`develop` contains the merged MVP 2.0 baseline through PR #85 at commit
`bb3f28f8078abde5ed4d95461f04fe675be2f37e`. PR84 was
`5d7b00d4c650c3145bd376e8e270711eba984dbd`. PR83 merged as
`8d8c92eff823658458990263b1278e7e220c494d`; PR84 as `5d7b00d` above.
The baseline includes the E0
easy three-method executor evidence for job 3506, the bounded numerical and
resource audits, and the published CPU comparison tables and figures.

The evidence is scientific input, not a blanket claim that every method or
parent has been qualified. Results remain stratified by parent, method,
threads, and resource allocation.

## PR83 documentary closure

PR #83 is merged and closes the installed M13/M26 medium-artifact
continuation. Its first inventory is preserved with SHA256
`9e73c05c776b12dc2b8132c8904cc462b9ce90735e4ebea74101d15537ad08b9`.
It contains two original MILP byte objects and eight metadata candidates. The
inventory does not prove that ten valid graphs or ten solver runs exist.

The installed follow-up inspection completed at source
`2b94cae424e9854102241d55064a772e2c40c584`, receipt SHA256
`11ce18870f44759afc51cfa12b4f26a684fdf246ef6e720b42d7340a49546af0`.
It verified ten pinned hashes and inspected eight profiles, with zero
self-consistent root candidates and no recorded failures. Its scope does not
prove global absence of reusable artifacts. Variable-name indices are not
root solution vectors. It adds zero optimization, inference, training or jobs.
PR83 closes this limitation, not M13/M26 computational qualification. Its
receipt flags remain false. See [PR83](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/83).

## Observed evidence and limits

- PR80: all 54 admitted parents numerically checked; 39 reused + 15 additional,
  not a final sample of 39. Preserve job3503's original return SHA256
  `20ed978d7e6a9c0ccc6a284f15cf54c9df6940a0bc5985c1b836db5f69362f60`.
- PR81/job3505: 20 frozen forwards (two existing models x ten test parents),
  no solver. PR85 reconciles their provenance with the limitations in its closure.
- PR82/job3506: 18 solves (six easy parents x three methods). GNN faster in
  3/6; geometric solver-time ratio 1.1802, not consistent acceleration.
  End-to-end historical preparation cost is not qualified. Detailed
  [review](research/e0-job3506-review.md) remains the evidence source.
- Sprint B CPU evidence already covers five thread caps for its frozen pair.
  It is not a ten-parent, three-method repeatability experiment.

## Approved next sequence and authorization boundary

PR83/84 are merged. PR84 relocated the four portable documents into `docs/`
and consolidated the approved roadmap. The 11 October authorization starts
PR85 implementation and confirms the preliminary PR86/87 protocols; it does
not authorize their exact resource budgets or runs. The author subsequently
merged PR85 and authorized continued PR86 implementation.

1. PR85: merged, audit complete with explicit limitations. The offline auditor reconciles
   54 numerical parents, two checkpoint chains and 20 forwards, exporting micro
   and parent-macro metrics. MINIMIZE is the required correction of the source
   benchmark error, not equivalent maximization. Full raw-formulation mapping
   and historical preprocessing replay remain delimited gates. The installed
   receipt also reconciles two frozen reports and two representative LPs.
   See the [closure and execution boundaries](research/pr85-closure.md).
2. PR86: M0/M1/M2, five CPU caps, repeatability and end-to-end cost. The 210
   solves are a preliminary ceiling, not an approved budget or a submission.
3. PR87: mandatory full-training comparison of 1 GPU serial (no DDP) versus
   4 GPU DDP, with equivalent global batch, samples, updates and final quality.
   No two-GPU substitute and no short benchmark substituted for training.
4. PR88: prepare manuscript structure alongside Sprint D, tying every claim
   to verifiable evidence, without filling unmeasured results.

See [protocols, acceptance gates and risks](research/submission-protocol-20261010.md)
and [schedule/figure plan](article_plan.md).

## Open gates (current)

PR85's [single read-only collection](research/pr85-private-context-runbook.md)
returned SHA256 `15136b4d0d22bc97b82ef5f778bca6dbe0686fb32209980dd62b2df0c907a282`.
The separate [closure](research/pr85-closure.md) reconciles it with the existing
numeric/predictive evidence. Both reports attest train-only prenorm; this is
not independent replay. Representative LP structure is not blanket semantic
qualification of all 54 formulations. No further collection/job is requested
by this closure; unknowns stay explicit and affected execution remains blocked.

- Keep any partial or inconsistent receipt and explain the limitation; never
  convert missing data into zero-cost or zero-runtime evidence.
- Resolve the documented formulation/start/cost gates before new comparative runs;
  documentary audit closure does not itself resolve those execution gates.
- Approve exact resource budgets separately before PR86/87 HPC execution.
- Maintain the five Gurobi thread caps (1, 2, 4, 8, 16) in future paired
  comparisons, without silently repeating already qualified runs.
- Prepare the final E0/C/D/E evidence tables and figures before release review.

## Not yet claimed

No statement here admits M13/M26 to training, test performance, scientific
promotion, or a new solver allocation. No superiority or independent
generalization claim is admitted. Main synchronization remains a separate
release review. A future whole-branch `develop` to `main` merge would include
these documents unless that release explicitly makes another arrangement.

## Independent PR86 planning checkpoint — 11 October

The dated initial checkpoint below describes the first proposal. It is
superseded operationally by the [post-PR85 preparation](research/pr86-starts-and-costs.md):
ten-parent binding code and disjoint cost accounting are locally tested;
the installed ten-parent receipt has now passed independent public review
(`45eab23962f8`), documented in the [installed review](research/pr86-installed-binding-review.md).
Complete prospective executor instrumentation and exact
resource authorization are still pending. The original
proposal bytes remain preserved. No execution gates are cleared by code alone.

This branch starts from develop after merged PR83/84 (5d7b00d). The earlier
checkpoint above is retained; PR85's independent documentary audit is under
review, not merged by this delivery. The authors confirmed mandatory MINIMIZE
as the correction of the benchmark's cost-objective sense, not equivalence.
PR86 now has a [regenerable offline proposal](research/pr86-controlled-comparison.md):
210 planned cells, 70 paired groups, separately counted preparation and an
unapproved resource envelope. No solver, inference, training or job added.
PR85 evidence limitations, start binding, instrumentation and exact budget
approval remain execution gates. PR87 (1/4 GPUs) and PR88 remain on the roadmap.
