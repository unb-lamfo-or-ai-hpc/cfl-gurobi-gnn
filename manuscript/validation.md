# Manuscript build validation

## Local evidence, 12 September 2026

- Quarto 1.10.18 and Pandoc 3.10.0 rendered both HTML and SBC PDF with research
  execution disabled.
- Ten standard-library manuscript regression tests passed.
- Source, citation, template-hash, evidence-boundary, rendered-artifact, and
  extracted-PDF-text checks passed.
- All eight A4 PDF pages were visually inspected after the final render.
  Equations, the planned-output table, accented author names, and eight
  bibliography entries are readable, without clipped content.
- The title is present in PDF metadata. The author list remains intentionally
  empty pending editorial confirmation.
- The upstream SBC style remains byte-identical. Documented adapter changes
  support Pandoc table widths and presentation metadata; they do not replace
  the supplied template.

The local Windows render used a workspace-local TeX runtime through a temporary
drive alias and a writable Quarto cache. Those runtime files are not publication
sources and are not committed. CI uses Ubuntu and TinyTeX instead.

These are document-integrity checks, not scientific validation. Final campaign
receipts, empirical figures, GitHub Actions results, repository Pages settings,
and a successful live-site deployment are not certified by this local record.
No research job was submitted or modified for this manuscript build.
