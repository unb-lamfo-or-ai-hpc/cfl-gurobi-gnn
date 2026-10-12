# Current status

Updated: 2026-10-12. PR85 merged; PR86 implementation in progress. No new experiment authorized.

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
Complete prospective executor instrumentation, formulation mapping and exact
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
