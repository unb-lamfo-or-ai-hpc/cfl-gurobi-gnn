# Manuscript build validation

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
