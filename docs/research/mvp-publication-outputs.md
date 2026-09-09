# Reproducible MVP tables and figures

## Scope

This stage converts the contract-bound development evidence into deterministic
CSV tables and SVG vector figures. It consumes only artifacts listed by the
end-to-end reproducibility ledger and verifies every input SHA-256 digest before
reading any numerical result.

The output layer covers:

- epoch-wise training and validation loss for all four GNN arms;
- held-out BCE, accuracy, precision, recall, and F1;
- terminal MIP gap and exact solver outcomes;
- total, data-read, model-build, and `model.optimize()` wall time;
- paired descriptive effects and right-censoring annotations; and
- sensitivity at relative MIP-gap thresholds of 1%, 5%, and 10%.

## Reproducibility design

Tables use UTF-8 RFC 4180 CSV. Figures use deterministic SVG generated with
the Python standard library, avoiding a new plotting-runtime dependency. The
timing figure uses `log10(1 + seconds)` because data reading and model
construction are several orders of magnitude shorter than optimization; exact
untransformed measurements remain available in the corresponding CSV table.

Each output receives a SHA-256 identity in a path-sanitized manifest. The
manifest binds the output contract to the accepted PR #39 reproducibility
contract and to the immutable training, evaluation, and comparison inputs.

## Interpretation boundary

These are publication-quality *assets* for review, not yet publication-eligible
scientific results. The current parent population remains partial. The figures
therefore contain a development-only notice, retain right-censored runs, and do
not rank or select a GNN arm. Inferential claims remain prohibited.

## Next gate

After the table and figure audit passes, the repository will undergo a
comprehensive academic-scientific English review. That review will cover the
README, code comments, reproducibility instructions, and complete dependency
declarations in `pyproject.toml`. The later manuscript will reuse the external
Quarto Manuscript template selected by the research team.
