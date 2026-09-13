# Manuscript build validation

## Interim-results and licensing revision, 13 September 2026

- Twenty standard-library manuscript tests pass. The source/rendered/PDF-text
  integrity gate passes, including the seven generated-asset hashes.
- A hash-bound, sanitized extract of the supplied rejection diagnostic supports
  three figures (cohort, rejected-parent gaps, four timing regions) and one CSV.
  This is not an independent revalidation of the underlying remote artifacts.
- Quarto rendered HTML and a 14-page A4 PDF. References begins on page13;
  the body remains below the 20-page ceiling. All pages were visually checked;
  unchanged pages1-7 also match the preceding render pixel-for-pixel.
- Four actual ORCID icons and their URI annotations remain present. The fifteen
  references, accented names and exact AI declaration are preserved.
- The adapter imports float for in-place result figures; original SBC style and
  all third-party licensing notices remain unchanged. Provenance hash updated.
- MIT is explicit for original manuscript/project content and original output
  metadata within the authors' rights. External data and resources are excluded.
- Job3307 remains RUNNING at the last supplied observation, 08:12:14. No accepted
  final training/evaluation metrics, invented curves, solver improvement or
  scientific eligibility is claimed. All remaining output families are reserved
  in the article and results register.
- No DGX job, research source, active input or immutable receipt was changed.
  PDF text was extracted with pdfplumber locally; CI uses Poppler pdftotext.

The record below describes the previous version, not the current page count.

## Local evidence, 12 September 2026

- Quarto 1.10.18 and Pandoc 3.10.0 rendered both HTML and SBC PDF with research
  execution disabled.
- Sixteen standard-library manuscript regression tests passed after the L2O,
  ORCID-icon and bibliography update.
- Source, citation, template-hash, evidence-boundary, rendered-artifact, and
  extracted-PDF-text checks passed.
- All ten A4 PDF pages were visually inspected after the final render.
  Equations, the planned-output table, accented author names, and fifteen
  bibliography entries are readable, without clipped content.
- The four authors appear in the approved order, with accented names, three
  institution mappings, four emails and four clickable ORCID icons, rendered by
  the maintained orcidlink package v1.1.1. PDF link annotations were checked in
  addition to visual inspection; the identifiers are not printed as text.
- The AI declaration is verbatim and immediately precedes References. The
  manuscript is ten pages including references; References starts on
  page9, within the conservative 20-page body ceiling.
- The upstream SBC style remains byte-identical. Documented adapter changes
  support Pandoc table widths and presentation metadata; they do not replace
  the supplied template.

The local Windows render used a workspace-local TeX runtime through a temporary
drive alias and a writable Quarto cache. Those runtime files are not publication
sources and are not committed. CI uses Ubuntu and TinyTeX instead.
On Windows, the maintained orcidlink package was installed in that local TeX
runtime from its upstream distribution; no substitute text macro is used.

The six-page project extract and seven new Zotero items were reviewed. Related
work now situates the study in L2O, distinguishes the learning targets, and
does not transfer continuous/QP/MINLP guarantees to the CFL predictor. The
fifteen bibliography entries exactly match the cited keys. Primary sources
resolve the tutorial identifier, author-order discrepancies, and revision dates.

The repository owner reports public visibility and Pages configured for GitHub
Actions. These are document-integrity checks, not scientific validation. Final
campaign receipts, empirical figures, the updated GitHub Actions result and a
successful live-site deployment are not certified by this local record.
No research job was submitted or modified for this manuscript build.
