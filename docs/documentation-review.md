# Academic-English documentation review

## Licensing clarification, 13 September 2026

The owner resumed this PR for MIT licensing clarification while PR50 training
job3307 remains active. The root LICENSE and package license reference already
identify MIT; neither was replaced. LICENSE_POLICY.md and data/LICENSE.md now
cover original documentation, manuscript content and project-generated metadata,
tables and figures within the authors' rights. External MILPBench data, solver
software and third-party resources are not relicensed. Historical receipts and
active-job inputs remain unchanged.

Validation on the isolated branch: **383 passed, 9 skipped**, four NumPy warnings;
five focused documentation tests passed. The first full-suite attempt found a
stale local SCIPOPTDIR pointing to an absent installation; removing that override
only for the validation process allowed the bundled PySCIPOpt wheel to load.
No repository fix or DGX environment change was needed. Nine native Gurobi checks
remain skipped for license availability, not certified as passing.

Final empirical reconciliation still waits for PR50. This licensing update does
not promote the PR to Ready for review or claim completion of the training run.

## Scope and provenance

This independent documentation branch starts from develop commit
`a86ab1088d0948e6d1f6c98d571c411bcd8e94fb` (merged PR49).
It implements the roadmap's “PR52 documentation” scope while
[PR50](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/50)
continues runtime validation. GitHub assigns actual pull-request numbers;
roadmap numbering is not an instruction to create placeholder issues.

The review replaces the root overview, adds directory navigation, distinguishes
historical protocols from current controls, and translates remaining Spanish
comments/docstrings and display messages in the reviewed Python and Slurm files.
Identifiers, CLI flags, serialized field names, file paths, research data, and
numerical policy are not translated or renamed.

## Substantive clarifications

- Preserve the MILPBench download paragraph, category labels, and all three
  Google Drive URLs; add only the Markdown spacing needed for list rendering.
- Record the effective MINIMIZE policy without modifying original LP files.
- Separate Gurobi graph authority from the solver that supplied a label.
- Distinguish the frozen 42-parent confirmation, prior 30-easy diagnostic,
  common four-arm intersection, and deferred 90-parent experiment.
- Treat variable hints, partial MIP starts, and restricted-domain optimization
  as different interventions.
- Explain corrected Gasse prenormalization without editing the legacy model.
- Describe source admission, graph readiness, training completion, and scientific
  eligibility as separate gates.
- Identify historical requirements as such; do not claim the existing package
  metadata is a complete reproducible environment.

## Source preservation

The legacy `models/gasse.py`, toy generator, solver collectors, mathematical
validator, strict graph builder, and current campaign executors are untouched.
The three edited Python modules are the legacy category EDA and serial/DDP
trainer interfaces. Changes are documentation plus translated logger messages;
the training and mathematical operations are not intentionally changed.

The legacy Slurm examples retain commands, variable names, paths, dependencies,
and resource requests. Only prose comments and displayed messages change.
Some still contain site-specific paths or obsolete experiment settings. They
are explicitly documented as historical examples, not endorsed confirmation
launchers or safe defaults for a new installation.

Source-file fingerprints include documentation. The edited serial helper is
also imported by current trainers; even with equivalent executable semantics,
its new byte hash is not the old hash. Keep this branch separate from running
campaigns and review fingerprint changes before integration. Never rewrite old
receipts or alter the shared DGX checkout during active jobs.

## Verification and boundaries

Verification includes preserved download URLs, internal README/guide links,
Python syntax and AST comparison excluding docstrings and display text,
Slurm command/directive comparison excluding comments and display text,
Bash syntax, LF endings, and the available smoke suite. Inspect skipped native
tests explicitly; software validation is not a fresh DGX experiment.

Historical ADRs, dated validation receipts, notebook results, and embedded
research artifacts are not rewritten. New directory guides explain their scope.
Proper names and original bibliographic titles retain their spelling. Current
guides and reviewed source comments use English; no claim is made that arbitrary
external data or historical logs are English-only.

Before marking this PR ready, obtain maintainer approval. Before merge, reconcile
the documentation with the final PR50 implementation and receipts without
claiming results that remain pending. No new DGX job is needed for the editorial
review itself. Dependency clean-install qualification, scientific output review,
and the user-supplied Quarto Manuscript template remain separate work.

## Local receipt (2026-09-12)

- Full smoke suite on the isolated develop-based documentation snapshot:
  **382 passed, 9 skipped**, four NumPy deprecation warnings.
- The nine skips require a working Gurobi license; no fresh native Gurobi
  acceptance is claimed.
- Four documentation regression tests passed, including preserved download
  URLs and relative-link resolution.
- Three edited Python modules have equivalent ASTs after excluding docstrings
  and logger display text. Nine edited Slurm scripts retain operational
  commands, variable expansions, and scheduler directives; Bash syntax and
  LF checks passed.
- Counts refer to this branch, which does not contain PR50's additional tests.
  They are not directly comparable to the 412-test DGX source-increment receipt.
