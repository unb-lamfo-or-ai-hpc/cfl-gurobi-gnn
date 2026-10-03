# Experimental evidence archiving

These scripts read generated evidence without modifying source files, executing
a solver, loading pickle/PyTorch objects, or uploading/publishing a deposit.
Raw benchmark inputs and credential-named directories/files are excluded.

`prepare_cfl_zenodo.py inventory` creates an inventory; `package` creates
independent tar.gz parts; `verify` checks archive SHA256 values, every recorded
member, missing/unexpected members, and recorded sidecars. Default packaging
redacts text and withholds malformed JSON or suspicious content. Text validation
occurs before the long compression pass.

For the private MVP 1.0 freeze, `--private-archive` retains original evidence
bytes, including invalid structured artifacts and host paths, with matching
source/member hashes. Credential-marked small text is withheld. Opaque binaries
are not comprehensively privacy-certified. This mode is not upload-ready and
does not validate malformed scientific records.

Use a fresh output directory outside source data and the repository. Completed
parts receive an atomic journal. `--resume` requires the same inventory,
collector hash, quota, part size and privacy mode; completed archives are hash
checked and unfinished archives renamed/preserved. Old failed jobs without this
journal cannot be certified as resumable.

`collect_mvp_computational_inventory.py` inventories reported counters and
Parquet metadata. It does not equate event rows with distinct feasible solutions
or silently invent solver-specific totals for the 54-parent population. PyArrow
is optional; unavailable/unreadable metadata remains explicitly missing.

Run synthetic tests with `python -m unittest discover -s tests/archive -v`.
The [release gates](../../docs/releases/mvp-1.0.md) separate archive integrity,
repository promotion, manuscript rendering and public deposition.
