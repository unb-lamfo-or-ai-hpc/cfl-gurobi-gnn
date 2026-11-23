# MVP 3.0 research protocol

The [English methodological protocol](coauthor-methodological-protocol.md) defines the scientific development programme S1-S6. It covers 66 instances, independent root-relaxation and incumbent preparation, equivalent-work serial/DDP training,45 paired B/R/G evaluation cells, numerical qualification and C2/C3 analysis.

The revised version incorporates the researcher's 62 PDF annotation records. Its coauthor-facing text contains the permanent scientific plan. Operational migration and runtime-compatibility records remain in the separate [NPAD transition dossier](../npad-runtime-transition-20261120/README.md).

## Documents

- [Methodological protocol](coauthor-methodological-protocol.md): methods, population, parameter/resource tables, data collection, analysis, budget, schedule and self-contained appendices.
- [Decisions and budget](decisions-and-budget.json):177 primary optimisation calls, explicit working scenarios and coauthor-review proposals.
- [Evidence contract](evidence-contract.json): record identities, event/label/Start fields and metric-specific eligibility.
- [Gurobi methodological design note](gurobi-adequacy-and-shared-architecture.md): root features, feasible incumbents, Gurobi 14 heuristics and conditional Benders boundaries.
- [Editorial reconciliation](editorial-revision-plan.md) and [annotation disposition](annotation-disposition-EN.csv): implementation of the PDF review.
- [Development handover](development-handover.md): portable scientific context and release gates for the next development chat.
- [References](references.bib): bibliographic records used by the protocol.

The proposed split allocation, label-admission tier, independent R/G support settings, training schedule and conditional diagnostic profiles are visible review choices. The PR remains Draft. Approval of the protocol and a concrete resource release precede scientific execution; merges require the researcher's specific decision.

## Rendering

Run render_review_pdfs.py with the protocol source and an output directory. It uses Pandoc, XeLaTeX, Pillow and PyMuPDF, generates the two diagrams and produces the PDF, self-contained HTML, page images and a build receipt. PANDOC and XELATEX environment variables can identify local executables. The renderer handles documentary work only.

The local coauthor PDF is titled *CFL-GNN MVP3 Research Protocol EN*, dated23 November 2026. GitHub retains the editable source and reproducible renderer; the delivered PDF and detailed machine handover are local review artifacts. This PR changes documentation and rendering assets, with zero new scientific calls.
