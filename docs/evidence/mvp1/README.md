# Experimental MVP 1.0 closure baseline

Source and publication were promoted through PRs 62 and 63. This record closes
the private evidence freeze without publishing the archive or altering the
54-parent model and frozen solver outcomes.

## Traceable summaries

The reproducible publisher creates `closure_verification.json`,
`incumbent_inventory.json`, `hardware_allocations.json`, `parent_coverage.json`
and their `SHA256SUMS.txt`. The private package is not committed. Source SHA256:
`f5cc52a20f69ebae0af8aecff5ac7c2981de85118d09a4d5406c3877a4cef156`.

```bash
python scripts/evidence/publish_mvp2_baseline.py \
  --receipts /path/to/private/mvp1-closure-receipts.tar.gz \
  --output /path/to/fresh/public-summary-directory
```

The verifier reads small tar members without extracting them or loading pickles
and tensors. Large archives were hashed on the HPC; local checks verify receipts
and declarations, not 181 GB of original data. The seven discovery exclusions
are operational tools/bootstrap/queue paths. One invalid historical JSON remains
preserved and flagged in the private archive. The freeze contains 8,790 files in
26 parts with 26,481,802,784 compressed bytes and no transformed source bytes.

If replaying older commits on Windows introduces CRLF-only checkout drift, run
`python scripts/evidence/verify_public_checkout.py --repair-line-endings`.
The verifier compares the five allowlisted public files with committed bytes
and the existing hashes before repair. It refuses changes beyond line endings;
it does not rewrite research contents or replace the expected checksums.

## Interpretation

The cohort contains 30 easy and 24 medium parents. Slurm records allocate one
GPU to training jobs 3307, 3361 and 3422, not eight-GPU DDP. Allocation does not
establish device utilization. The 77 observed Parquet tables span repeated
attempts, historical pilots and derived models. Path-attributed Gurobi tables
contain 7,860 footer rows; SCIP tables contain 119; unattributed tables contain
284. These are not unique feasible incumbent totals for the 54-parent cohort.
Missing tables are not proof of zero incumbents or mathematical infeasibility.

Zenodo remains unpublished. The private archive is not upload-ready. This is an
engineering freeze, not journal readiness or scientific certification.
