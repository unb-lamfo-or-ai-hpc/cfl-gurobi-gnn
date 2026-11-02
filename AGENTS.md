# Repository instructions

## Latest Sprint/PR boundary — 28 October 2026

Use docs/research/mvp2-closeout-plan.md for current delivery boundaries.
PR92 closes the independent methods and preliminary coauthor-review stage;
the next draft PR carries synthesis and final CPU integration. Earlier
criteria requiring PR92 itself to await PR89 are superseded by the author's
explicit scope split. D0 remains reception/reconciliation, followed by metric
qualification. Audit independent aspects now and the complete package after
qualification. No new experiment, merge, publication or submission is authorized.

## Current continuation authority — 26 October 2026

Read `docs/research/mvp2-r3-contract.md` first, then its methods/model and
metrics/reproducibility companions and evidence index. R3 and the author's
26 October transfer decision supersede earlier scheduling, budget-pending
and finish-on-old-machine conditions below. PR89 is already submitted and
running; installed source/plan/starts/parameters remain frozen. Its existing
collection authority is not permission to prepare, submit or solve again.
Work directly on GitHub/Codex; local files are temporary only. Every HPC access
requires the author's intervention; use existing data storage/directories,
never create further home captures or alter the installed campaign.
Merges and editorial submission still need explicit human approval.

## Scope

Read `docs/current_status.md`, `docs/research_context.md`,
`docs/experiment_protocol.md`, and `docs/article_plan.md` for the portable
checkpoint. The approved 2026-10-10 roadmap is in
`docs/research/submission-protocol-20261010.md`; it supersedes older scheduling
proposals, not historical receipts. A proposed budget is not execution authority.

This repository contains the reproducible CFL--GNN research pipeline. Treat
the repository and the evidence directories referenced by its receipts as the
source of truth. Chat histories are context, not experimental evidence.

## Scientific rules

- Current 19 October methodology: read `docs/research/methodology-20261019/`.
  Main MVP2 analysis uses seed42 only (150 PR86 rows); preserve all210 rows,
  but seeds43/44 and multiseed plots are historical, not main conclusions.
  No new seeds, dataset expansion, hyperparameter search or causal class-aware
  claim without its own scientific approval. M4/M12 numerical limits persist.
  GPU PR87 and proposed CPU12h campaign require SEPARATE specific approvals.
  Planning approval is not execution approval; old CLI release is superseded.

- Frozen author decision, 12 October 2026, through the final MVP2 sprint:
  accept the MILPBench CFL formulation as correct except for the erroneous
  MAXIMIZE declaration. Always force MINIMIZE at runtime; preserve original
  files, coefficients, constraints, bounds and variable domains. Do not require
  a generator or renewed semantic certification as an execution gate.
  Still verify implementation/model/variable identity and resource approval.
- Preserve parent-level train/validation/test partitions and instance IDs.
- Never use test labels, future artifacts, or private paths to select a model,
  warm start, threshold, or hyperparameter.
- Distinguish clearly between observation, inference, optimization, training,
  and scientific promotion.
- Do not call Gurobi, submit Slurm jobs, train models, or retry an experiment
  unless the protocol and budget for that operation are explicitly recorded.
- A failed or partial receipt is evidence to preserve, not permission to retry.
- Record the exact commit, environment, parameters, resource allocation,
  input hashes, output hashes, and exclusion criteria for every experiment.

## Operational rules

- Work against `develop` for ordinary research changes. Keep `main` reserved
  for the protected release synchronization agreed by the authors.
- Keep large logs, solver licenses, private paths, credentials, and raw model
  data out of Git. Commit sanitized receipts, manifests, tables, figures, and
  reproducible runbooks instead.
- Use `tfm_env` on `dgx-dasci` unless a documented protocol says otherwise.
- Do not upgrade packages merely to satisfy an auditor. Report the installed
  versions and investigate compatibility only when a real execution requires it.
- Before a PR is ready, run the repository's pinned tests and quality checks;
  document what was not run and why.
- Act proactively within the approved scope. Ask for merge only after the PR
  is ready for review. HPC execution needs its own explicit authorization;
  never treat approval of documentation as approval of jobs or training.

## Documentation rule

Every substantive research change must explain what was changed, how it is
validated, why the design is appropriate, and what remains unqualified. Keep
the portable context files in `docs/` synchronized with the relevant PR.
