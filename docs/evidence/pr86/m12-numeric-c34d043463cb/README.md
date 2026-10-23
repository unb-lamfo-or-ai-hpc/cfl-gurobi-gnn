# M12 read-only numerical audit

Original `numeric_audit.json` SHA256:
`c34d043463cb4f3e6ea389ac00b96b779b4a0b23e5c5cf62bda404b60047e7a2`.
No new solves, jobs, scheduler calls or raw-value/log export.

[Review, interpretation and explicit author decision](../../../research/pr86-m12-audit-final-nine.md).
Six stored vectors pass original tolerances. Four GNN vectors also pass the
rounded-copy diagnostic with zero observed row/integrality residuals; the two
controls fail original-unit rows in that copy. This is not the M4 outcome,
an exact certificate, a repair or permission to infer certified speedup.
The author separately approved the final nine original solves with explicit
M12 limitations; the original raw false admission/eligibility flags are unchanged.

Offline regeneration:

```text
python -B scripts/evidence/review_pr86_m12_numeric.py --output docs/evidence/pr86/m12-numeric-c34d043463cb
python -B -m unittest discover -s tests/evidence -p test_pr86_wave67.py -v
```
