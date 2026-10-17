# PR86 — 93 reviewed solves and the F27/F29 continuation

## Results and evidence

Jobs3572–3577 completed the six frozen groups25–30. The original return is
[preserved byte for byte](../evidence/pr86/jobs3572-3577/public_return.json),
SHA256 `a54d71775afcff941d496236bfb18f92569a0cc15b8ffadac68978c33c700968`,
at source `99d9b33cd49016dc561c1c8580a3013df298effc` and plan
`453f42c948cfd39503e326010227afb848346439b3bedba6b63426eefd4ecfc3`.
The original validator passed before adding this continuation. The separate
review pins those identities, checks the frozen cells and serial dependencies,
and reconciles solutions, parameters, MINIMIZE, memory supervision and costs.
Original receipt flags remain intact. All18 new solves meet the0.01% gap target;
the12 external starts are accepted, with no memory/callback stop or censoring.

The cumulative [CSV](../evidence/pr86/jobs3572-3577/campaign_results.csv) has
**93/210 solves and31/70 groups**, covering five historically exposed parents.
F0/F3/F6/F14 have all five thread caps and the three one-thread seeds; F27 has
one thread at seeds42/43/44. Remaining:117 solves and39 groups. These are
retrospective controlled observations; seeds are nested within parents.

| Job | Parent / threads / seed | M0 solver s | M1 solver s | M2 solver s |
| --- | --- | ---: | ---: | ---: |
|3572|F14 /4 /42|133.214|67.115|113.996|
|3573|F14 /8 /42|86.082|65.825|130.130|
|3574|F14 /16 /42|71.264|71.471|155.771|
|3575|F27 /1 /42|57.690|61.622|42.214|
|3576|F27 /1 /43|65.353|66.485|57.907|
|3577|F27 /1 /44|59.717|58.126|47.280|

M2 is faster than M0 in four new groups and slower in two. Across all seven
F14 groups it is faster in three and slower in four. Keep these heterogeneous
outcomes. M2 gaps for F14/4,8,16 are0.00814066%,0.00968709%,0.00339610%;
F27/seed42,43 gaps are0.00400999%,0.00491503%. Other new gaps are zero.
Reaching the common target does not make terminal quality identical. Report
gap with time and avoid claiming overall superiority from incomplete coverage.
Slurm elapsed sum1590s (26min30s) excludes queues and differs from solver time.

- [Complete F14 CPU figure](../evidence/pr86/jobs3572-3577/f14_cpu.svg)
- [Partial F27 CPU figure, seed42](../evidence/pr86/jobs3572-3577/f27_cpu_partial.svg)
- [Review](../evidence/pr86/jobs3572-3577/review.json) and [manifest](../evidence/pr86/jobs3572-3577/manifest.json)

Regenerate offline with `python3 -B scripts/evidence/review_pr86_wave25.py --output NEW_DIRECTORY`.
Figures show measured points; F27 caps2/4/8/16 stay pending. The CSV retains
all three seeds, gaps, returned bounds, start states and scoped cost fields.
Preparation allocation scenarios remain distinct from measured whole-job cold
costs. Sampled cgroup peaks and Slurm MaxRSS retain their different scopes.

## Next six jobs: what, how and why

Continue the original manifest at positions31–36 (zero-based): F27/2,4,8,16
threads/seed42, then F29/1 thread/seeds42,43. This completes F27 before starting
the next parent. F29/seed44 and caps2/4/8/16 follow later. The order was frozen
before results; heterogeneous outcomes do not select or remove cells.

The existing serial executor is reused through `pr86_wave31.py` and
`operate_pr86_wave31.sh`, with F27 private index4 and F29 index5. Reuse
roots3520 and guidance3521. The new policy binds the reviewed93-cell prefix
and each parent's model/root/start/preparation cost. It checks held resources,
afterok dependencies and predecessor artifacts before launch. Immutable claims
and stopping gates protect each admitted group. No automatic dispatch follows
these six jobs; the next return needs independent review.

Within the approved210-solve/70-job campaign, this wave has18 solves in six
sequential jobs, each up to4h and64GiB, one node, CPU only, with at most3600s
per solve. Reservation ceilings:24 serial hours,128 physical-core-hours;
solver ceiling:18h. These are limits, not duration predictions. Successful
review would bring the campaign to111/210 solves and37/70 groups.

Tests exercise all18 admissions, both parent bundles, F29 index5, rejection
of the wrong parent and dependency, repeat submission rejection, and exact
regeneration of the93-row outputs. The receiver uses one SCP connection and
preserves earlier download attempts. T1 covers this new policy/review; T2
covers the preceding policy and shared queue/first-group boundaries; T3 runs
the complete evidence suite in the final GitHub CI matrix before CLI release.

Keep tfm_env and the installed package versions, MINIMIZE and the existing
memory limits. PR86 remains draft until the full matrix and analysis are
reviewed. PR87's mandatory1-GPU/4-GPU training has a separate exact budget;
PR88 manuscript work proceeds in parallel. Final develop/main synchronization
in both directions follows article revision and final release approval.
