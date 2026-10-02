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

## Source and render checks

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
