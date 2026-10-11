# PR85 — Scientific provenance and formulation audit

> Implementation checkpoint, 11 October: the original work register below is
> retained. The [executed offline audit](pr85-scientific-audit.md) now provides
> the parent matrix, checkpoint chains, micro/macro metrics and reproducible
> checks. MINIMIZE is the mandatory author-approved benchmark correction,
> not an undecided choice or equivalence to unchanged-cost maximization.
> Full raw-formulation mapping and historical preprocessing-fit provenance
> remain specific open gates. The PR remains draft; no HPC work or merge.

Status: **in progress / evidence not yet promoted**. Scope approved 2026-10-11. This document is an audit work register, not a report of checks already executed.

## Boundaries

Read-only inspection and offline verification of existing records; no Gurobi calls, model training, new labels, HPC jobs, edits to historical receipts, or merges. The approved scope is described in [submission protocol](submission-protocol-20261010.md). Baseline is `develop` after PR83 and PR84 merges. Treat missing private artifacts as **not verified**; never fabricate file paths or hashes.

## Audit work packages and gates

| Gate | Verification from existing evidence | Required deliverable | Fail condition / implication |
| --- | --- | --- | --- |
| A: parent/sample provenance | Reconcile original 90, admitted 54, excluded 36; canonical identities, difficulty cohorts, derived ancestry and duplication; train 34 / validation 10 / exposed test 10; inspect label-quality selection | Parent-indexed provenance/elegibility matrix, checksum manifest, exception list | Unknown parent or derivation lineage blocks affected claims |
| B: checkpoint/procedure | Identify frozen easy-only and mixed checkpoint hashes; training inputs, graph-feature schema, train-only preprocessing/prenorm and class weights; validation-only selection of checkpoint and decision threshold | Chain-of-custody and reproducible comparison of stored records | Unverified selection or test leakage blocks affected predictive claims |
| C: frozen predictive evidence | Reconcile 20 frozen forward evaluations; confusion-matrix denominators; parent-macro vs micro F1/precision/recall, class prevalence; only recompute PR-AUC/calibration if scores and labels are admissible | Regenerable metric tables with method/parent/source/qualification columns | Summary parity without source scores is not independent rescoring |
| D: CFL mathematical semantics | Transcribe intended objective, fixed/opening and assignment costs, constants, domains, demands, capacity, linking, assignment semantics and units; inspect source sense vs execution sense, objective values and feasibility of recorded solutions | Equation-to-source mapping, source-to-parser-to-solver sense trace and affected-evidence decision | Any unresolved sign, coefficient or constraint mismatch blocks PR86 and corresponding article claims |
| E: warm-start mapping | Compare original MILP variables, parsed indices, graph features, labels, output order and partial-start support; flag LP matched-control dependence on GNN support | Per-stage variable identity/coverage trace with discrepancies | Unresolved variable/order mismatch blocks interpretation of solver comparison |

## Mathematical-sense decision requirement

The authors report that the source benchmark's `MAXIMIZE` header is erroneous and that intended CFL is a minimization problem; they also report that maximization leads to trivially solved hard instances. **Treat these as the working scientific interpretation to be justified from equations and original benchmark semantics, not as an already independently verified equivalence.** Preserve original input bytes and historical run metadata. Audit whether forcing `MINIMIZE` with the original coefficient signs and constants implements the intended objective; test existing feasible solutions / recorded bounds where data permit **without invoking optimization**. Record the exact evidence and limitations. Do not blindly negate coefficients: maximize `f(x)` and minimize `f(x)` are generally distinct problems, whereas maximize `f(x)` corresponds to minimize `-f(x)`. If the intended equation is minimize `f(x)` despite an erroneous maximization declaration, changing the objective sense only requires specific evidence that `f(x)` already has the intended minimization coefficients.

## Audit matrix schema (planned)

One row per parent, including: `parent_id`, `difficulty`, `canonical_role`, `admitted`, `split`, `historically_exposed`, `label_quality_gate`, `original_input_sha256`, `derived_artifact_sha256`, `graph_schema`, `label_source`, `checkpoint_use`, `objective_sense_source`, `objective_sense_executed`, `eligible_for_predictive_claim`, `eligible_for_solver_claim`, `reason_or_unverified`, and `evidence_ref`. Do not fill missing entries by inference.

## Current documented boundaries (not newly audited)

The portable context records 90 parents (30 easy, 30 medium, 30 hard), 54 admitted (30 easy, 24 medium), and a 34/10/10 parent-level split. The exposed test parents are F0, F3, F6, F14, F27, F29, M0, M4, M7 and M12. M13/M26 are excluded canonical training parents; the PR83 inspection qualifies no root candidates. Two frozen models have 20 historical forwards; E0 job3506 contains 18 historical solves. These figures must be reconciled against primary manifests in this PR.

## Completion criteria

For each gate, produce exact input paths/hashes and a regenerable offline verification or explicitly classify the item as blocked/unverifiable, documenting why. Separate **observed**, **independently recomputed**, **historically reported**, **inferred**, and **not verified**. Record check execution instructions and pass/fail results. Review must not imply that draft work registers are executed audits. PR86/87 remain separately authorization-gated.
