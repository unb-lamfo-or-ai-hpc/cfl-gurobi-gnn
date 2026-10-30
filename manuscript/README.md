# Class-aware GNN partial-start manuscript

## Approved scientific/editorial revision — 30 October 2026

The author approved the detailed diagnostic and its implementation in PR93.
The approved title is **Evaluating Graph Neural Network-Based Partial Warm Starts for Capacitated Facility Location Problems**.
Only C2 (conditional optimization effects) and C3 (computational economics)
are scientific contribution claims; C1 is a methodological obligation.
Earlier candidate C1–C3 framing below is superseded in this respect, without
changing historical evidence or the installed experimental contract.
See the [revision record](../docs/research/pr93-editorial-revision-20261030.md) for the approved diagnostic, locations,
implementation and validation boundaries.

S1/S2/S4/S5 advance with existing evidence. PR89, its source, settings,
resources and sequence remain intact; S3 requires its reconciled 60-cell
return and metric-specific qualification. Further seeds, methods, models,
training and ablations remain future work. The final audit, merge,
publication and editorial submission retain their human gates.
No coauthor communication or new experimental execution is authorized here.


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
[coauthor brief](../docs/research/coauthor-review-brief.md) contains the scientific argument,
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

The principal 150-row CPU comparison is interpreted across six easy and four medium instances, three methods and five thread caps. Time ratios change with the resource cap; primal improvement need not coincide with a smaller gap, and adding measured preparation can reverse a solver-level advantage. The separate historical six-medium study improves five of six learned-start terminal gaps, with a mean sensitive to two instances. Its original timing table omits upstream preparation/inference and is not a complete cold-application measurement. The studies are not pooled.

Regressions, censoring, numerical restrictions, historical exposure and the negative earlier pilot are retained. Predictive AP is not PR-AUC; an accepted Start is not evidence of speedup. Cost scenarios retain their individual measurement boundaries, and unavailable measurements are never substituted with zero.

Publication-integrity tests do not certify scientific validity, publication
eligibility, statistical significance, or submission readiness. The internal
body budget is 20 pages, excluding references. The authors must complete
the declarations and data-release decisions in `submission-checklist.md`.

Original manuscript material and scripts are MIT licensed. Upstream
templates, benchmarks, and solvers retain their own rights.

## Scientific supplement build

The reader supplement is assembled as A (methods), B (extended results) and C (computational settings/reproducibility). After building the static figures, render the article and then its separate supplement project:

    quarto render manuscript --no-execute
    quarto render manuscript/supplement --no-execute

The second command writes beneath manuscript/_manuscript/supplement. It executes no solver, inference or training. Internal plans and coauthor material remain outside the supplement entry point. The final integral scientific audit still follows CPU12h qualification.
