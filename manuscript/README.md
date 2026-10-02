# Class-aware GNN partial-start manuscript

The current article targets **Computers & Operations Research**. It reports
the 54-parent, 100-epoch predictor; six-parent validation qualification; and
a distinct six-parent frozen optimization benchmark. The earlier 39-parent
evidence remains under `results/` for historical reproducibility. Only
`results/current/` supplies the current loss curves and result tables.

## Evidence and reproducible rendering

The author-supplied archive is bound by SHA256 in
`results/current/import_receipt.json`. Its 13 original publication files
are preserved byte-for-byte. No graph, label, checkpoint, raw solver log,
or license file is required for publication rendering. Derived vector
figures and tables have a separate source/output receipt.

From the repository root, with Python and Matplotlib installed:

```bash
python scripts/manuscript/check_manuscript.py
python -m unittest discover -s tests/manuscript -v
python scripts/manuscript/build_results_assets.py
quarto render manuscript --no-execute
pdftotext -layout manuscript/_manuscript/index.pdf manuscript-pdf-text.txt
python scripts/manuscript/check_manuscript.py --rendered --pdf-text manuscript-pdf-text.txt
python scripts/manuscript/package_latex_project.py --output cfl-cor-latex-project.zip
```

Quarto 1.10.18 and Matplotlib 3.10.9 are selected in the publication workflow.
The PDF requires an existing TeX distribution with the packages used by the
adapter, including `orcidlink`. GitHub Actions provides TinyTeX for rendering.
The workflow runs no research code and publishes only `manuscript/_manuscript`
from `develop`; pull requests produce previews without deploying Pages.

The PDF uses the unmodified Elsevier `elsarticle` class and Harvard
author-year style. Provenance and LPPL rights are in `template-provenance/`.
The previous quarto-sbc template is retained, but no longer typesets the
current article. Author ORCIDs appear through `orcidlink`, not printed IDs.

## Interpretation and submission boundary

Five of six learned-start terminal gaps improve, but the mean is sensitive
to two parents. Regressions, censored events, population overlap rules, and
the negative earlier pilot are retained. Predictive AP is not PR-AUC;
accepted starts are not evidence of speedup. The transferred tables do not
include preparation/inference or all four timing-region measurements, so
they do not quantify cold end-to-end acceleration. No missing measurement
is substituted with zero.

Publication-integrity tests do not certify scientific validity, publication
eligibility, statistical significance, or submission readiness. The internal
body budget is 20 pages, excluding references. The authors must complete
the declarations and data-release decisions in `submission-checklist.md`.

Original manuscript material and scripts are MIT licensed. Upstream
templates, benchmarks, and solvers retain their own rights.
