# Manuscript validation

Validation covers source provenance, evidence hashes, exact citation coverage,
author order and ORCID icons, the unchanged AI declaration, static rendering,
and the internal 20-page body limit. Publication checks are separate from
research-execution audits and do not certify scientific reporting eligibility.

## Current evidence

The current predictor uses 54 admitted parents (34 training, ten validation,
ten predictive test), 100 epochs, and seed 42. Six medium validation parents
qualify the start policy before a distinct six-parent optimization benchmark.
The predictive and optimization test populations are not interchangeable.
The earlier 39-parent article and its rendering receipts are historical;
they do not validate the current article.

The imported archive SHA256 is
`792e35ddd0e01e2e0ffc393b308d3580a0dcf0e862aa7ec532be1e54b5ba4927`.
The publication contract is
`1a22c76da1f5bc6be978ac6eb7ea340c10b067c5beae1f71aecb617ac09d6b96`.
Thirteen imported files remain byte-identical; derived assets have a separate
source/output hash receipt. CSV line endings are preserved intentionally.

## Source and render checks for the preceding draft

Source checks and 33 manuscript regression tests passed locally. Checks
cover evidence drift, the 100-epoch history, six-parent benchmark membership,
four additional journal references, author identities, declarations,
template provenance, missing outputs, and invalid publication claims.
The combined documentation/manuscript test run passed 40 tests. This is not
a claim that the complete host-dependent research suite was rerun locally.

The initial PDF attempt stopped because `orcidlink.sty` was absent from the
existing TeX installation. After dependency resolution, retained-source
packaging and PDF typography were corrected. The final HTML/PDF build,
extracted-text checks, asset/source hashes, and ZIP manifest checks passed.
All 18 pages of the current PDF were visually inspected; References starts
on page 15, within the internal 20-page body budget. Figures and tables are
readable and ORCID icons are retained. These checks concern the current
Elsevier article, not a previous PDF or the historical 39-parent manuscript.

Final PDF SHA256:
`66c317b7e15ad60811d36b876088d3b2ab57f4dfa3ff0667a6292d715fb8b54c`.
Final editable LaTeX ZIP SHA256:
`e31e7e20bdc1ddc97270c9db60af4552337bfabee0dd772b661756b07141dfb1`.
The archive has 14 files; each payload hash matches its manifest.
Two nonfatal BibTeX warnings indicate missing page ranges for the cited
NeurIPS papers; page ranges have not been invented. All citations resolve.

The current asset generator produces four measured/vector figure sets
(PDF, SVG, PNG) and four in-article tables. It executes no solver or training.
Negative pilot outcomes, regressions, right censoring, influence sensitivity,
and unavailable preparation timings remain explicit in the article.
Five of six favorable terminal-gap effects do not establish statistical
significance or a general end-to-end speedup.

## Author-review editorial revision

The 2 October author review is implemented in `editorial-requirements.md`:
readable definitions, formal dataset and metric citations, introduction and
interpretation of every display, concise captions with notes, grayscale figures,
literature-based Discussion, and a consolidated final section. Complete paired
results and influence diagnostics remain visible; thirteen imported source
files remain byte-identical. Editorial regression tests have been added.

The preceding PDF/ZIP hashes and 18-page inspection above apply only to the
preceding draft. The editorial revision at commit `259c559` rendered successfully
on the author's local machine and was pushed to the existing draft PR #62.
Its PDF SHA256 is
`7e5b95ae543113d10c9815a3525d31e37fd4b67a82ae2a2a9bb3137734388b70`;
the editable ZIP SHA256 is
`5171710449926dbb02b217534072ba0b9589c15a2b8354966ab22c48dce82bec`.
All 23 pages were visually inspected. The body occupies 19 pages and References
starts on page 20. ZIP CRC checks pass; it contains 14 files. Forty-one manuscript
and seven documentation tests pass. The predictive-table header was shortened
from Aggregation to Level and the corrected PDF was rendered and reviewed again
on all 23 pages, including a full-size inspection of Table 2. Its PDF SHA256 is
`b31860a77986cd8594c7ec839d1eb2873be4165027940d27bc7e18af6101ec4d`;
the corrected editable ZIP SHA256 is
`720ceb73470284e1d3ac88cc9807d9176dd95b9d55f247d8d8f55465cf47bde8`.
All thirteen ZIP payload hashes and archive CRC checks pass. No readiness
transition or merge was performed. The prepared archival metadata are not a
claim that a Zenodo draft, reserved DOI or published deposit exists.
This revision performs no research execution or new library synchronization.

## Experimental MVP 1.0 freeze revision - 3 October 2026

All repetitive Source sentences were removed from the article displays and
table generator. Abbreviation, censoring and timing notes remain. A concise
subsection distinguishes benchmark difficulty categories from binary target
classes; a source comment reserves the later structural/PCA/UMAP extension.
No imported CSV, checkpoint, solver outcome or guidance policy was changed.

Forty-two manuscript tests, twenty archive/inventory tests and seven
documentation tests pass locally (69 total). Pages deployment is restricted
to `main`; `develop` retains preview generation. The newest native PDF/TEX
render and all-page visual inspection are still pending. Earlier PDF hashes
above are historical and do not identify this new revision.

Repository promotion and the full private HPC evidence archive are separate
closure gates. The failed archive job 3460 is not certified; the corrected
collector and its synthetic tests do not establish HPC archive completion.
Zenodo draft 23113003 is author-confirmed and unpublished. Its DOI has not been
supplied or independently verified. No data upload occurs in this revision.
