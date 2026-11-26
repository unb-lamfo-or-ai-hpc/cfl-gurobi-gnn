# MVP 3.0 research protocol

S1-A implementation is documented in [the versioned contract and frozen parent identities](s1a-contract.md). It adds offline schemas, validation and planning manifests without scientific execution; the approved protocol and historical sources remain preserved.

The [English methodological protocol](coauthor-methodological-protocol.md) defines the scientific development programme S1-S6. It covers 66 instances, independent root-relaxation and incumbent preparation, equivalent-work serial/DDP training,45 paired B/R/G evaluation cells, numerical qualification and C2/C3 analysis.

The revised version incorporates the researcher's 62 PDF annotation records. Its coauthor-facing text contains the permanent scientific plan. Operational migration and runtime-compatibility records remain in the separate [NPAD transition dossier](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/102).

## Documents

- [Methodological protocol](coauthor-methodological-protocol.md): methods, population, parameter/resource tables, data collection, analysis, budget, schedule and self-contained appendices.
- [Decisions and budget](decisions-and-budget.json):177 primary optimisation calls, explicit working scenarios and coauthor-review proposals.
- [Evidence contract](evidence-contract.json): record identities, event/label/Start fields and metric-specific eligibility.
- [Gurobi methodological design note](gurobi-adequacy-and-shared-architecture.md): root features, feasible incumbents, Gurobi 14 heuristics and conditional Benders boundaries.
- [Editorial reconciliation](editorial-revision-plan.md) and [annotation disposition](annotation-disposition-EN.csv): implementation of the PDF review.
- [Development handover](development-handover.md): portable scientific context and release gates for the next development chat.
- [References](references.bib): bibliographic records used by the protocol.

The researcher approved the methodological plan on 23 November 2026 and requested this final GRBLogTools/configuration explanation. The coauthor packet retains its stated settings and budget. S1 will qualify secondary offline log extraction, and S5 will use reconciled summaries with explicit clock origins. PR99 was merged into develop at 22d5089f59f7306d97f7d5410f248d6b45ebdc0b following the researcher's specific approval; concrete HPC releases remain separate decisions.

## Rendering

Run render_review_pdfs.py with the protocol source and an output directory. It uses Pandoc, XeLaTeX, Pillow and PyMuPDF, generates the two diagrams and produces the PDF, self-contained HTML, page images and a build receipt. PANDOC and XELATEX environment variables can identify local executables. The renderer handles documentary work only.

The approved coauthor PDF is titled *CFL-GNN MVP3 Research Protocol EN, version 3*, dated 23 November 2026. GitHub retains the editable source and reproducible renderer; the approved PDF/HTML/LaTeX are versioned here, while the private machine handover stays local. This PR changes documentation and rendering assets, with zero new scientific calls.

## Standard time-ratio convention

Version 3 adopts T_B/T_G and T_R/T_G throughout method-time comparisons: values above one favour G. The same direction applies to comparable end-to-end and cumulative elapsed-time costs. See the [presentation reconciliation](presentation-reconciliation-20261123.md) for the 42-slide review and the resolved slide 34 convention. The experimental design and primary budget remain unchanged.


## Final development preparation

The [preparation dossier](preparation/README.md) consolidates the approved English plan and appendices, workbook, hypotheses, design, budgets and acceptance criteria for S1-S6. Download the [approved PDF](CFL-GNN-MVP3-Protocol-v3-EN.pdf), [HTML](CFL-GNN-MVP3-Protocol-v3-EN.html), [LaTeX](CFL-GNN-MVP3-Protocol-v3-EN.tex), or [planning workbook](preparation/mvp3-preparation-workbook-EN.xlsx). Exact approved file identities are recorded in approved-v3-manifest.json. This package prepares implementation in the next chat without new scientific execution.
