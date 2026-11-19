# PR94 final reconciliation — 5 November 2026

This record describes the completed recovery evaluation, jobs 3833–3880. Its frozen source and original design are in [PR #94](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/94) and the [versioned 144-cell plan](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/81c829b66f6dacf703da388e34501d9df0980f45/docs/research/solver-seed-extension-v2/README.md). The original entry failure and cancelled jobs stay in the operational history.

Both ZIP SHA-256 values, member inventories, CRCs and member manifests were independently verified after transfer. The terminal accounting query was 2026-11-05 20:34:25 UTC (17:34:25 in Fortaleza). All 48 jobs and their 96 batch/extern steps ended COMPLETED/0:0. The 144 rows match the planned instance/method/seed identities and their job bindings. All 16 parent bindings agree across the two exports. The reconciliation reruns the installed result validator and cost arithmetic, and checks the serialized child, raw, start-of-execution, supervision and cost receipts against their seals. It matches the reported solution hashes against the seal index. The vectors, logs and original model bytes are held separately. The original eligibility flags remain intact.

| Export | Bytes | SHA-256 |
| --- | ---: | --- |
| Terminal ZIP | 396640 | `99ba525f7977389342c2a09b58c363464c4e33b22e9ed565c1746097e4718dc0` |
| Recovery installation ZIP | 7496 | `703609030229554ba663242fdc183d788d43a7555ba35b0270357dc84e0a977d` |
| Installed plan | | `92ac169c5ccb69962628dc0b91aab6afff183538da87f14e3ebf080b8cfe53fb` |

## Derived outputs

- [Cell-level CSV](cells.csv) contains all 144 records, including observed target times, censoring and follow-up at each threshold, primal and dual values, gaps, runtime, costs and numerical scope. Gaps are fractions unless named as percentages. `target_001` denotes 0.01%. For an observed target the follow-up column is its observed event time. For a censored target it is the lesser of the terminal observation time and 3,600 seconds. Empty target times indicate censored observations. `target_status` is solver status code 2, interpreted with solver tolerances.
- [Summary JSON](summary.json) aggregates first observed crossings within 3,600 s and fixed-horizon outcomes. Its contrast key denotes numerator/comparison method over denominator/reference method. The `left_only` count refers to the reference method, and `right_only` to the comparison method. At 3,600 s use the last observation within budget, including the terminal record for an early finish. Time ratios require two observed crossings and exclude M4/M12. For the fixed-horizon contrasts, take the median of paired seed differences within each instance and then the median across instances. Report medium with all ten instances descriptively and separately as a sensitivity view outside M4/M12.
- The one-hour results support scoped comparisons of solver-reported outcomes. The cross-bound excess on M12 seed 42 and the previously documented M4/M12 qualifications limit interpretation. The eight-medium sensitivity retains M7. Solver and supervised times have separate meanings from preparation, allocated logical CPU time and elapsed campaign time. R/G preparation costs remain unavailable in the evaluation receipts.

Reproduce these files locally using the original two ZIPs and a read-only source snapshot at the executed commit:

```sh
python -B docs/research/runbooks/pr94_offline_reconcile.py \
  --source /path/to/81c829b6 --terminal /path/to/terminal.zip \
  --installation /path/to/installation.zip --out /path/to/output
```

The script performs offline verification and arithmetic. Keep the private archives in their authorized storage. The article and appendices use the derived, allowlisted outputs.
