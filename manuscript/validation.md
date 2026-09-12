# Manuscript build validation

## Local evidence, 12 September 2026

- Quarto 1.10.18 and Pandoc 3.10.0 rendered both HTML and SBC PDF with research
  execution disabled.
- Thirteen standard-library manuscript regression tests passed after the author,
  declaration and page-budget update.
- Source, citation, template-hash, evidence-boundary, rendered-artifact, and
  extracted-PDF-text checks passed.
- All eight A4 PDF pages were visually inspected after the final render.
  Equations, the planned-output table, accented author names, and eight
  bibliography entries are readable, without clipped content.
- The four authors appear in the approved order, with accented names, three
  institution mappings, four emails and four clickable ORCID links. PDF link
  annotations were checked in addition to visual inspection.
- The AI declaration is verbatim and immediately precedes References. The
  manuscript remains eight pages including references; References starts on
  page7, within the conservative 20-page body ceiling.
- The upstream SBC style remains byte-identical. Documented adapter changes
  support Pandoc table widths and presentation metadata; they do not replace
  the supplied template.

The local Windows render used a workspace-local TeX runtime through a temporary
drive alias and a writable Quarto cache. Those runtime files are not publication
sources and are not committed. CI uses Ubuntu and TinyTeX instead.

The repository owner reports public visibility and Pages configured for GitHub
Actions. These are document-integrity checks, not scientific validation. Final
campaign receipts, empirical figures, the updated GitHub Actions result and a
successful live-site deployment are not certified by this local record.
No research job was submitted or modified for this manuscript build.
