# MVP 1.0 experimental freeze

This release retains the 54-parent original-instance development study, validation-qualified class-aware partial starts and the six-parent optimization demonstration. It is not a population-level effectiveness certificate or a journal-submission approval.

The publication assets retain all thirteen immutable PR60 inputs. Learned starts improve terminal gap on five of six test parents, but effect magnitudes are sensitive to medium 12 and 20. The mixed model's cohort comprises 30 easy and 24 medium instances; fitting uses 34 parents, with ten validation and ten predictive-test parents. No augmentation benefit or hard-instance transfer is established by this release.

## Independent closure gates

1. Source and publication gate: current manuscript tests, imported input hashes, fresh HTML/PDF render, editable LaTeX archive, full PDF visual inspection and canonical commit identifiers.
2. Repository gate: PR62 merged into `develop`, reviewed `develop` promoted into `main`, `develop` synchronized with `main`, Pages deployment from `main` verified. Do not force-push, overwrite tags or merge unrelated open PRs.
3. Private evidence gate: corrected collector run under raid-backed staging; original source and archive member hashes match; final archive verification and SHA256SUMS checks pass; withheld coverage is explicitly reconciled. No raw MILPBench files or credential-named files/directories are intentionally included. Invalid JSON remains invalid and is inventoried, not repaired into scientific evidence.
4. Release tag gate: reserve `mvp-1.0.0` only if absent and all preceding gates have receipts. Retain source SHA, PDF/LaTeX hashes and evidence verification receipt. A source-only merge does not certify a still-running evidence archive.

Zenodo draft 23113003 remains unpublished. No upload is authorized by these gates. The private original-byte archive may contain host paths and opaque binaries and is not a sanitized public deposit. Its filesystem directory name `upload` is a historical collector convention, not upload permission. The reserved DOI is not yet verified.

The failed archive job 3460 and its partial files must be retained. They lack a completed-part provenance journal and cannot be certified as resumable merely because tar files exist. Use a new directory for the corrected private freeze. New interruptions can resume only completed journaled parts against an unchanged inventory and collector policy.

MVP 2.0 feature work targets `develop`, while public Pages continues to show `main`. The separate [HPC roadmap](../research/mvp2-hpc-roadmap.md) does not alter frozen training or test outputs.
