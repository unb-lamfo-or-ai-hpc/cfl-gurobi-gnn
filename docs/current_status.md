# Current status

Updated: 2026-10-10. Documentary checkpoint; no new experiment authorized.

## Integrated baseline

`develop` contains the merged MVP 2.0 baseline through PR #82 at commit
`91630762bf0b86ec153e2882c42dc83161eebe4a`. The baseline includes the E0
easy three-method executor evidence for job 3506, the bounded numerical and
resource audits, and the published CPU comparison tables and figures.

The evidence is scientific input, not a blanket claim that every method or
parent has been qualified. Results remain stratified by parent, method,
threads, and resource allocation.

## PR83 documentary closure

PR #83 is a separate draft branch for the installed M13/M26 medium-artifact
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
  no solver. Existing predictive evidence still needs the PR85 provenance audit.
- PR82/job3506: 18 solves (six easy parents x three methods). GNN faster in
  3/6; geometric solver-time ratio 1.1802, not consistent acceleration.
  End-to-end historical preparation cost is not qualified. Detailed
  [review](research/e0-job3506-review.md) remains the evidence source.
- Sprint B CPU evidence already covers five thread caps for its frozen pair.
  It is not a ten-parent, three-method repeatability experiment.

## Approved next sequence and authorization boundary

PR84 relocates the four portable documents from repository root to `docs/`
and consolidates the approved roadmap. PR83/84 are independent branches based
on `develop`, with no merge authorized by the 10 October request. No claim
here asserts that the PR83 closure receipt is already merged into this branch.

1. PR85: approve the final scope in the
   [protocol proposal](research/submission-protocol-20261010.md#pr85--final-scope-for-approval)
   before implementation. Audit parent partitions, checkpoint provenance,
   predictive validation, mathematical formulation and objective convention.
2. PR86: M0/M1/M2, five CPU caps, repeatability and end-to-end cost. The 210
   solves are a preliminary ceiling, not an approved budget or a submission.
3. PR87: mandatory full-training comparison of 1 GPU serial (no DDP) versus
   4 GPU DDP, with equivalent global batch, samples, updates and final quality.
   No two-GPU substitute and no short benchmark substituted for training.
4. PR88: start manuscript structure alongside Sprint D, tying every claim
   to verifiable evidence. Implementation is not authorized by this checkpoint.

See [protocols, acceptance gates and risks](research/submission-protocol-20261010.md)
and [schedule/figure plan](article_plan.md).

## Open gates (current)

- Keep any partial or inconsistent receipt and explain the limitation; never
  convert missing data into zero-cost or zero-runtime evidence.
- Complete PR85's formulation and provenance audit before new comparative runs.
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
