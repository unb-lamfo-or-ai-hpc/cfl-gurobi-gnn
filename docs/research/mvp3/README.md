# MVP3 methodological review packet

**Editorial status:** narrative reorganization requested by the author; see [the revision plan](editorial-revision-plan.md). PR99 remains Draft. Locally generated PDFs are working previews until the integrated rewrite and final visual review are complete.

Prepared 19 November 2026 under the approved consolidated mandate. This packet is a scientific proposal for the coauthors, not a request to execute a historical launcher and not an execution authorization. No materials were sent to coauthors.

Start with [the detailed protocol](coauthor-methodological-protocol.md), then [the Gurobi adequacy/shared architecture note](gurobi-adequacy-and-shared-architecture.md). [Decisions and budget](decisions-and-budget.json) identify adopted directions and eight unresolved decisions; [the evidence contract](evidence-contract.json) specifies proposed normalized records without implementing a new pipeline.

## Deliverable coverage

| Mandate deliverables | Location |
| --- | --- |
| E1: MVP2 closeout | [PR97](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/97), [PR98](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/98) and [retirement receipt](../../evidence/pr98/closure-20261119/retirement.json) |
| E2/E3/E4/E7: scientific question, Gurobi/HPC, 90-instance characterization and 39-parent B/R/G | Protocol sections 1–4 and 7–11; evidence contract |
| E5/E6: dataset/labels/split and serial/DDP | Protocol sections 5–6; decisions D1–D5 |
| E8/E9: shared architecture and independent Benders | Technical Note A–F, component inventory and exactness conditions |
| E10: full mathematical foundation | [Appendix A.8](../../../manuscript/supplement/gnn-mathematical-foundations.md), [Portuguese original](source/fundamentacao-matematica-pt-20261119.txt) and [reconciliation](foundation-reconciliation.json) |
| E11: consolidated English coauthor protocol | Detailed protocol plus explicitly linked specifications above |

## Boundaries

The 990 matrix and the 66/18 alternatives are discontinued. Preserve the technical pilots and artifacts as historical evidence. The new principal design is 90 characterization baselines and 39 test parents x B/R/G, with a conservative budget of 207 principal solves; root preparation and learning are budgeted separately. Two 20-core jobs are a candidate, not demonstrated capacity. Extra seeds, hints, parameter sensitivities, shared-core code and Benders implementation are not authorized.

The existing approved Sprint sequence is retained; this packet does not repeat or expand it. Protocol milestone 3 December 2026, pause 19 December–10 January, target journal submission 18 March 2027. Resource/schedule risk and required coauthor decisions are visible in the protocol. No main/Pages/Zenodo publication is implied by a develop documentation PR.

## Local PDF review builds

The two documents are rendered by [`render_review_pdfs.py`](render_review_pdfs.py), an editorial helper that does not import the scientific pipeline. Requirements: Python with ReportLab, Quarto/Pandoc, a native LaTeX installation with `amsmath`/`amssymb`, Poppler and Times/Arial/Courier fonts (the font directory is configurable). Run from this directory, using an output directory below the approved local temporary workspace:

```text
python -B render_review_pdfs.py --output-dir <local-output-directory> --revision <exact-commit-sha> --pdflatex <path-to-pdflatex>
```

Optional `--quarto`, `--pdftoppm` and `--font-dir` arguments select local tools. The build receipt records source and PDF SHA256 hashes; the exact source revision appears in each PDF footer. Render every final page with Poppler and inspect equations, table continuations and pagination before delivery. PDFs and intermediate formula images remain local; this PR versions only the sources and the rendering helper.
