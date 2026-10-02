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

Source checks and 28 manuscript regression tests passed locally. Checks
cover evidence drift, the 100-epoch history, six-parent benchmark membership,
four additional journal references, author identities, declarations,
template provenance, missing outputs, and invalid publication claims.
The combined documentation/manuscript test run passed 35 tests. This is not
a claim that the complete host-dependent research suite was rerun locally.

The initial current PDF attempt stopped because `orcidlink.sty` was absent
from the existing TeX installation. HTML and figure generation succeeded.
The rendering workflow permits installation of missing TeX packages; the
PDF, extracted text, page budget, and complete visual review remain pending
until a successful render. No previous PDF is accepted as current evidence.

The current asset generator produces four measured/vector figure sets
(PDF, SVG, PNG) and four in-article tables. It executes no solver or training.
Negative pilot outcomes, regressions, right censoring, influence sensitivity,
and unavailable preparation timings remain explicit in the article.
Five of six favorable terminal-gap effects do not establish statistical
significance or a general end-to-end speedup.
