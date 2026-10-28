# Class-aware GNN partial-start manuscript

## PR93 continuation

PR92 is merged into develop at `ac2dccb8bd56af6b03b866db5199d19944b7a28b`.
PR93 now targets develop and continues that independent-stage baseline.
See the [working R2-D8 assessment](../docs/research/mvp2-integrated-assessment.md)
and [editorial completion criteria](editorial-plan.md). PR93 remains gated
by qualified CPU evidence, final synthesis and the complete audit; none is
inferred from a passing preview.


## Delivered PR92 scope — 28 October 2026

PR92 delivers the independent R3 methods, provenance and preliminary review
stage while the authorized CPU campaign continues. Its
[coauthor brief](coauthor-review-brief.md) contains the scientific argument,
known limitations and a first-pass audit register. The
[editorial plan](editorial-plan.md) defines this PR's completion criteria;
the [Sprint/PR plan](../docs/research/mvp2-closeout-plan.md) separates it from
the final article integration.

A subsequent draft PR carries synthesis, the qualified CPU return, R2-D8,
the final scientific supplement and complete audit. PR92 can therefore be
ready for review without claiming that the article is submission-ready.
No final CPU results, coauthor approval or publication authorization are asserted.

B/R/G remain presentation aliases for archived M0/M1/M2. The historical
six-medium archive, principal 150-row seed42 view and pending CPU12h campaign
retain separate populations and provenance in evidence-status.json.
The [working supplement](supplement/README.md) includes the numerical
claim map; missing pending results are not filled with synthetic values.

The existing Manuscript workflow checks sources, regressions and HTML/PDF.
It does not execute research or deploy a pull request to Pages. Additional
experiments remain limitations/future work outside the current Sprints.

## Earlier build and archive instructions


The current article targets **Computers & Operations Research**. It reports
the 54-parent, 100-epoch predictor; six-parent validation qualification; and
a distinct six-parent frozen optimization benchmark. The earlier 39-parent
evidence remains under `results/` for historical reproducibility. Only
`results/current/` supplies the current loss curves and result tables.

## Evidence and reproducible rendering

The author-supplied archive is bound by SHA256 in
`results/current/import_receipt.json`. Its 13 original publication files
are preserved byte-for-byte. The PR88 GPU subsection separately uses the reviewed
PR87 jobs3673/3674 archive; it does not replace those historical article assets.
`docs/evidence/pr88/gpu/manifest.json` binds the new English BCE figure and its
Spanish companion. `python scripts/evidence/plot_pr88_gpu_bce.py` regenerates
them from audited histories, without model loading or HPC. Its recorded rendering
runtime is Matplotlib3.9.2; data/hashes are checked independently of rendering.
No graph, label, checkpoint, raw solver log,
or license file is required for publication rendering. Derived vector
figures and tables have a separate source/output receipt.

From the repository root, with Python and Matplotlib installed:

```bash
python scripts/manuscript/check_manuscript.py
python -m unittest discover -s tests/manuscript -v
python scripts/manuscript/build_results_assets.py
quarto render manuscript --no-execute -M latex-auto-install:true
pdftotext -layout manuscript/_manuscript/index.pdf manuscript-pdf-text.txt
python scripts/manuscript/check_manuscript.py --rendered --pdf-text manuscript-pdf-text.txt
python scripts/manuscript/package_latex_project.py --output cfl-cor-latex-project.zip
```

Quarto 1.10.18 and Matplotlib 3.10.9 are selected in the publication workflow.
The PDF requires an existing TeX distribution with the packages used by the
adapter, including `orcidlink` and `lmodern`. Missing packages may be installed
into that distribution. GitHub Actions provides TinyTeX for rendering.
The workflow runs no research code and publishes only `manuscript/_manuscript`
from `main`; `develop` and pull requests produce previews without deploying Pages.
The workflow also packages `cfl-cor-latex-project.zip` alongside the preview.

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
