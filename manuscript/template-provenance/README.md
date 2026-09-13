# Pinned upstream template

Source: https://github.com/cvictorr2508/quarto-sbc

Revision: `88eaa11eeee9f86cd8594466e4644b321c8d7b75` (v0.2.0).
The style and extension metadata are vendored without modifications. The
Quarto/Pandoc adapter `template.tex` adds `\usepackage{calc}` because Pandoc
3.10 emits proportional table widths with `\real`. This compatibility import
does not change the SBC style and is not described as an official SBC change.
The adapter additionally hides coloured hyperlink boxes, sets PDF title metadata,
and suppresses the style's otherwise orphaned institution marker when no
affiliations are supplied. It renders user-approved authors with the maintained
`orcidlink` package's clickable icon and an `\institution{}` wrapper inside SBC
`\address{}`, retaining `\author{}` and `\email{}`. Identifiers remain in author
metadata and link targets, but are not printed in the PDF. The package is a TeX
runtime dependency, not vendored article code; see
[CTAN](https://ctan.org/pkg/orcidlink) and its LPPL 1.3 licence. These are adapter
changes, not modifications to the original SBC style.
The adapter also imports `float` so the three interim result figures can remain
beside their evidence paragraphs (`fig-pos: H`) instead of floating ahead of
the Results heading. This is an editorial placement change only.
The upstream MIT licence, third-party notice and style-provenance document are
preserved here. `upstream.json` records SHA-256 identities for these six files.
The cited original SBC archive hashes are upstream statements, not a claim that
this manuscript independently retrieved and verified that original archive.

The project configuration and article are adapted from the upstream Manuscript
scaffold. The publication workflow uses the upstream Actions/Pages approach,
scoped to this subproject with static-source checks and no code execution.
Authorship metadata is supplied explicitly by the user. English-only text
omits the optional Portuguese resumo; venue-specific requirements must
still be checked before submission. No SBC layout command has been rewritten.

The upstream canonical example's PDF checker tests its own example text and
authorship. It is not applied unchanged to this different article. This project
instead checks its own citations/evidence boundaries, renders both formats,
and requires visual review of the article's PDF pages. That distinction does
not imply new official SBC requirements or independent venue certification.
