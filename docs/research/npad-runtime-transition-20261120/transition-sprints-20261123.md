# Current inventory update — 23 November 2026

The [current66 input receipt](current-input-inventory-20261123.md) supersedes the missing-six transfer status below: all 66 .lp.gz inputs are now inventoried with fresh stored hashes. **TR-03:** input receipt/manifest received; historical preservation remains explicit. **TR-04:** approved-source checkout, input path map and CFL-only package admission accepted; project license placement remains pending. See the [admission record](checkout-package-admission-20261123.md). No further original-input transfer is needed. The chronological census/transfer explanation below is retained as history. Scientific Sprints S1–S6 and the TR identifiers are unchanged.

# Named transition Sprints — MVP 2.0 to MVP 3.0

**Updated:** 23 November 2026. **Language:** English for repository and coauthor-facing material.

These identifiers track operational transition work. They do not rename the scientific Sprints S1–S6 or authorize experiments. Earlier provisional T1–T3 delivery labels are superseded by the TR identifiers below.

| ID and name | PR boundary | Received evidence or prepared output | Completion criterion and present status |
| --- | --- | --- | --- |
| **TR-01 — Editorial and Release Readiness** | #101, into develop only | TinyTeX authenticated release lookup; publication handoff and preserved article/supplement links | Exact-revision CI and review completed before a separately authorized develop integration. Draft; no merge or publication in this update. |
| **TR-02 — Runtime Qualification** | #102 | Installation receipt; V100 job 2278626; synthetic project-model/native-license job 2278658 | Scoped library/model-training/license compatibility PASS. Completed for these technical scopes; real CFL driver/data, historical checkpoint, DDP and performance remain unqualified. Do not repeat successful qualification to follow documentary commits. |
| **TR-03 — Data Preservation and Reconciliation** | #102 | DGX job3930 preservation metadata/index and current66 NPAD inventory | Current original-input coverage is complete: 30 easy, 30 medium and six hard. Decoded equivalence is accepted on researcher provenance; compressed identities remain distinct. Historical preservation and any selective reproduction transfer remain explicit; no deletion is authorized. |
| **TR-04 — NPAD Data Admission and Project Checkout** | #102 | Approved clean source61ba422c, 66-file path map, 12 satisfied requirements and CFL-only package receipt | Checkout and package admission completed. Original environment and preexisting target versions preserved. Project license is absent; stable editable-source retention and protected license placement remain follow-up. No real-data experiment is implied. |
| **TR-05 — Methodological Approval and Handover** | #99, maintained separately in Draft | Integrated English protocol and Gurobi note under author review | Incorporate author comments and approved addenda; obtain protocol/budget approval from the researcher/coauthors before scientific implementation. No coauthor communication or new experiment occurs through this plan. |

## Evidence and interpretation

The [current migration receipt](migration-reconciliation-20261123.json) records the checked identities and their scope. The author executes all HPC/SSH/SCP commands. GitHub contains sanitized summaries, source and reproducible records; private inventories, raw path maps, credentials and large payloads remain outside Git.

The DGX preservation job 3930 completed successfully. The metadata ZIP, receipt and index were verified locally. All 299 members match the frozen selection, including 66 original models. There are 251 matches to previously qualified expected hashes and 48 newly recorded preservation hashes. This does not turn historical artifacts into MVP 3.0 experimental results. The archive digest is reported by the DGX receipt; the 6,832,048,460-byte archive was not transferred or rehashed locally.

The first NPAD catalogue receipt is authentic and complete **within its canonical-name filter**, not a complete listing of all existing filenames. It visited 63 entries in four directories and recognized seven LP gzip files. All seven match the DGX counterparts in size but not in stored-file SHA256. Different gzip bytes do not by themselves demonstrate a different MILP. Conversely, matching names and sizes do not prove byte identity. Preserve the existing files and record this distinction without automatic overwrite or duplicate transfer.

The author explicitly waived decompressed-content verification. Continue with filenames, sizes, stored-file hashes and qualified documentary identities; do not add decompression as a gate. The complementary receipt is now received and its exact reconstructed SHA256 is verified: d472a436438daedb04e7934369ca9fbdc99e46c4572f9cbad4c8a7c15c3fe160. It lists 60 files: 24 easy, 30 medium and six hard, with 53 .lp.tar.gz names and seven .lp.gz names. Only E24–E29 are absent by name; their six DGX gzip files total 20,794,882 bytes. Prepare that original-input delta without overwriting or decompressing the existing 60. A .tar.gz name is a recorded wrapper, not a qualified directly readable LP; content and later runtime admission are separate from inventory presence. Required historical artifacts have their own transfer review.

## Acceptance records

Each Sprint records its PR, exact revision, validation, evidence scope, unresolved items and author intervention. Preserve historical receipts and incident records; correct present status through dated superseding records rather than rewriting executed source. All new repository/coauthor-facing prose is English; discussion with the researcher may remain PT-BR.

The original environment is preserved. The target runtime is qualified only for the recorded technical scopes. Native Threads=0 still requires allocation/affinity qualification for later real-data work. Do not pool DGX/Gurobi 13 and NPAD/Gurobi 14 timings as paired performance evidence.

Merges remain separately approved and target develop. A subsequent main synchronization and Pages publication require the approved release flow. Keep #99, #101 and #102 Draft until their respective review decisions.
