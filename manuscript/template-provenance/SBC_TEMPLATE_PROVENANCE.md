# SBC template provenance

The PDF format in `quarto-sbc` is derived from the classic LaTeX template distributed for events of the Sociedade Brasileira de Computação (SBC).

## Project-supplied reference package

The implementation was checked against the archive supplied by the project owner:

- archive: `sbc-template-latex.zip`
- SHA-256: `4f9afbf2428d8403de56c3ecbae2bb4e17ec5efe35debbc07184f24ee0d8430b`

Reference files inside that archive:

| File | SHA-256 | Integration status |
|---|---|---|
| `sbc-template.sty` | `dbe513d56dde32bedc53dcf7b9efba052ff1b3b747037ed2f284f7095a91e895` | Integrated as the normative layout resource. Malformed characters occurring only in comments were normalized to UTF-8 and repository-facing comments were translated to English; active LaTeX behavior was preserved. |
| `sbc.bst` | `d884c6793e4ea54d13f5c751b3d6f4ea529a62d0906cd9774f2ec350b394691f` | Inspected and tracked by hash. The file states that it is a copy of `apalike` for SBC whose documented change is removal of the comma before the year in citation labels. The adapter therefore uses the standard `apalike` formatter with natbib configured to reproduce that SBC author-year punctuation. Literal vendoring of the historical `.bst` remains optional and must preserve its original copying notice. |
| `sbc-template.tex` | `7b1c4682b13c523968cea1ea367eda4477952e49628b1527312e040a6f3b776b` | Used as the behavioral reference for title, authors, affiliations, Abstract, Resumo, and page layout. |

The hashes above identify the original project-supplied reference files. They are not hashes of the adapted repository copies.

## Encoding policy

The historical `sbc-template.tex` supplied with the project contains both

```tex
\usepackage[utf8]{inputenc}
```

and

```tex
\usepackage[latin1]{inputenc}
```

in the same document. `quarto-sbc` intentionally does **not** reproduce that conflict. The Quarto adapter uses UTF-8 consistently.

## Comment-language policy

Repository-facing code comments and engineering documentation are maintained in English so the project can be reviewed and reused internationally.

This policy does not translate or rename LaTeX commands, SBC interface terms such as `Resumo`, proper nouns, bibliographic titles, or verbatim upstream identifiers. Translating comments in the imported `.sty` is treated as a non-executable adaptation and is recorded here explicitly.

## Bibliography compatibility policy

The supplied `sbc.bst` begins by identifying itself as a copy of `apalike` for SBC with no comma before the year in the citation label. The executable Quarto adapter keeps `apalike` as the bibliography formatter and sets natbib author-year punctuation explicitly so that citation behavior reproduces this documented SBC difference.

The historical SBC style also contains a `hyperref` end-preamble hook that redefines `\@lbibitem`. In the Quarto adapter, the already integrated natbib/hyperref definition is restored after `\begin{document}` so author-year citation labels remain correct without changing the active historical style code responsible for layout.

This avoids silently modifying or partially copying the historical `.bst` while retaining a reproducible bibliography path. A bibliography fixture derived from the supplied SBC example is rendered and checked in CI.

## Adaptation policy

The project keeps the following distinction explicit:

1. **Normative SBC behavior** — page geometry, typography, title block, sections, captions, Abstract/Resumo, and related LaTeX behavior come from `sbc-template.sty`.
2. **Quarto/Pandoc adapter** — `_extensions/sbc/template.tex` maps normalized Quarto metadata and Pandoc output into the commands expected by the SBC style and contains compatibility fixes required by current Quarto/natbib/hyperref behavior.
3. **Web representation** — HTML is a companion scholarly representation and is not claimed to reproduce the SBC PDF layout pixel-for-pixel.

Any future modification to an imported SBC resource should be documented here and should not be described as an official SBC change unless supported by an authoritative upstream source.
