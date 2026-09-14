# CFL graph-learning manuscript

The article reports a completed 39-parent original-instance study: 100 training epochs, seed 42 and eight held-out parents. It reports exclusions, graph structure, validation-selected classification and probability diagnostics. Augmentation comparisons and native solver-guidance outcomes remain future work.

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
