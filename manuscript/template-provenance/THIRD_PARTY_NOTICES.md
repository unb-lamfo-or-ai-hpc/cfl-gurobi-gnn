# Third-party notices

This repository contains original `quarto-sbc` code and documentation together with a historical LaTeX style resource derived from material distributed for events of the Sociedade Brasileira de Computação (SBC).

## Project license boundary

The MIT License in `LICENSE` applies to original `quarto-sbc` code and documentation authored for this repository, except for third-party material identified below.

The MIT License does **not** relicense third-party files or grant rights beyond those provided by their respective authors or upstream distributors.

## SBC LaTeX style resource

Path:

- `_extensions/sbc/sbc-template.sty`

Provenance:

- derived from the classic SBC LaTeX style supplied to this project;
- original header credits Jomi Hubner and Rafael Bordini (June 2001), with updates noted for March 2005 and December 2017;
- the repository copy preserves active LaTeX behavior while normalizing malformed comment characters to UTF-8 and translating repository-facing comments to English;
- the original project-supplied file is tracked by SHA-256 in `docs/SBC_TEMPLATE_PROVENANCE.md`.

This file is third-party material and is **not covered by the repository MIT License**. Users and redistributors are responsible for complying with any applicable upstream terms and venue-specific requirements.

## Historical SBC bibliography style

The project-supplied `sbc.bst` is **not vendored** in this repository. Its SHA-256 and compatibility analysis are recorded in `docs/SBC_TEMPLATE_PROVENANCE.md`. The executable adapter uses the standard `apalike` bibliography formatter with natbib punctuation configured to reproduce the documented SBC author-year citation behavior.

## Attribution and venue requirements

`quarto-sbc` is an independent research-oriented integration and is not an official SBC publication-rules authority. Authors should verify the current submission instructions and licensing requirements of the specific conference, journal, workshop, or event before publication.
