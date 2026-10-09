# Repository instructions

## Scope

This repository contains the reproducible CFL--GNN research pipeline. Treat
the repository and the evidence directories referenced by its receipts as the
source of truth. Chat histories are context, not experimental evidence.

## Scientific rules

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

## Documentation rule

Every substantive research change must explain what was changed, how it is
validated, why the design is appropriate, and what remains unqualified. Keep
the portable context files in `docs/` synchronized with the relevant PR.
