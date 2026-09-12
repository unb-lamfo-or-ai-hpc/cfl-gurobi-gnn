# Scientific manuscript

This is the independent, English-language manuscript draft for the CFL research
pipeline. It reuses `cvictorr2508/quarto-sbc` v0.2.0 at commit
`88eaa11eeee9f86cd8594466e4644b321c8d7b75`; the format was not rewritten.
The current article is a **development protocol, not a completed empirical study**.

## Local rendering

Requirements: Quarto 1.10.18, a working TeX distribution with the packages used
by the SBC extension, and Python 3.10 or later for the standard-library checks.
GitHub Actions installs TinyTeX and `orcidlink` (including its TikZ dependencies).
For an existing TeX Live installation, use `tlmgr install orcidlink` if needed.
No Gurobi, SCIP, Torch, GPU, or HPC access is
needed to render this article. Do not install the research runtime for this task.

From the repository root:

```bash
python scripts/manuscript/check_manuscript.py
python -m unittest discover -s tests/manuscript -v
quarto render manuscript --no-execute
python scripts/manuscript/check_manuscript.py --rendered
```

The rendered article is `manuscript/_manuscript/index.html`; the PDF is
`manuscript/_manuscript/index.pdf`. Review every PDF page visually as well as
checking citations, equations, and the shared HTML/PDF text. Build outputs are
ignored; source and provenance are committed. The only article is `index.qmd`.
No computational notebook, private result directory, or research code download
is included in the publication project.

## GitHub Pages

The `Manuscript` workflow validates and renders pull requests without deploying.
After an approved merge to **develop**, a manuscript-related push renders and
deploys the same isolated output directory to GitHub Pages. Manual dispatch also
requires the develop branch. Main is not a second publication source, avoiding
an older main checkout replacing a newer reviewed draft.

The repository owner reports public visibility and **Settings > Pages > Build
and deployment > Source: GitHub Actions** enabled. Permit deployments from develop
in the `github-pages` environment. The intended URL is
<https://unb-lamfo-or-ai-hpc.github.io/cfl-gurobi-gnn/>; this is not a claim that
the site is already live. Successful deployment and an HTTP check are required.
GitHub Pages availability for a private repository depends on the organization's
plan. Never change repository visibility to work around that limitation without
the owner's separate instruction. A publicly accessible website exposes the
rendered article, even if the source repository remains private.

The workflow adapts the supplied template's Actions deployment, rather than
requiring a local `quarto publish gh-pages` push. It grants Pages/OIDC permissions
only to the deployment job and uploads only `_manuscript`, never the repository
root, raw data, licence files, or model checkpoints. Bibliographic links lead to
public sources; code availability is described conditionally in the article.

Official guidance: [Quarto Manuscript publishing](https://quarto.org/docs/manuscripts/publishing.html),
[Quarto and GitHub Pages](https://quarto.org/docs/publishing/github-pages.html), and
[GitHub Pages availability](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

## Evidence integration after PR50

`evidence-status.json` freezes the current draft's evidence boundary. The check
fails if this protocol-only draft gains unreviewed empirical assets, executable
chunks, or a claim of scientific eligibility. It is intentionally not an
automatic import of whichever HPC run happens to be newest.

When acceptance receipts arrive, make a dedicated evidence update: verify cohort,
source/model/checkpoint/graph identities and all scientific gates; copy only
approved, sanitized tables and figures into this project; record relative paths,
source contract hashes, artifact hashes and sample counts; update the abstract,
results, limitations, captions, evidence ledger and its checks together. Render
again and inspect the figures and every PDF page. Do not reuse the earlier
rejected or zero-root-feature outputs as confirmation evidence. The full90
campaign and manuscript extension remain deferred.

The four authors, their order, affiliations, ORCIDs and email addresses are
user-approved and rendered in HTML and PDF. The supplied AI declaration appears
verbatim immediately before References. Funding, contributions, target venue,
data-access arrangements and remaining disclosures still require editorial review.
The [editorial plan](editorial-plan.md) caps the body at 20 pages plus references
and lists three Elsevier candidates. SBC remains the working layout, not a claim
of compliance with a selected Elsevier journal's submission format.

## Bibliography and template provenance

[Reference review](reference-review.md) records the cited subset, source checks,
exclusions, and the authorized fifteen-item Zotero collection. It is a targeted
relevance assessment, not a systematic literature review. Six existing items
were linked and two missing references imported without changing shared metadata.
The owner subsequently added seven items, all now cited with explicit scope
distinctions. The three L2O sources frame the study; four additional GNN sources
distinguish learning targets and expressivity. See the recorded
[Zotero JavaScript](zotero-developer-script.md) for the earlier membership update.

[Template provenance](template-provenance/README.md) records the exact upstream
revision and hashes. Its MIT notice applies to upstream original code; the SBC
third-party resources retain their distinct notices and are not relicensed.
