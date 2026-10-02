# CFL graph-learning manuscript

The manuscript source predates the final PR #57-#60 evidence reconciliation.
Its next editorial revision must replace the earlier 39-parent narrative with
the 54-parent training contract, validation-only guidance selection, frozen
six-parent held-out benchmark, censoring, and influence analysis. PR #61 updates
repository documentation but deliberately does not rewrite the article body;
that scientific revision remains a separately reviewed change.

Build the reviewed figures and static publication from the repository root:

```bash
python scripts/manuscript/check_manuscript.py
python -m unittest discover -s tests/manuscript -v
python scripts/manuscript/build_results_assets.py
quarto render manuscript --no-execute
python scripts/manuscript/check_manuscript.py --rendered
```

The supplied quarto-sbc extension is pinned and attributed in `template-provenance/`. Author ORCIDs use the LaTeX orcidlink package. The body is limited to 20 pages, excluding references. The publication workflow validates pull requests and deploys the static manuscript from develop; it never executes the research pipeline.

Original manuscript material is MIT licensed. Benchmark, solver, reference and template rights remain with their respective rights holders.
