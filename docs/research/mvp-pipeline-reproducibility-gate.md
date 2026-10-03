# MVP pipeline reproducibility gate

## Purpose

This gate closes the executable, development-only MVP pipeline before any
publication table or figure is produced. It binds the dataset, four-arm GNN
training, common held-out evaluation, equal-budget Neural Diving benchmark,
and descriptive comparison through recomputed contracts and SHA-256 digests.

The audit is intentionally fail-closed. A changed plan, report, checkpoint,
training history, hint file, solver result, or comparison table invalidates
the chain. The generated ledger contains only stage-relative paths, digests,
and byte sizes; it does not retain host-specific filesystem locations.

## Scientific boundary

Passing this gate means that the tested MVP execution can be reproduced from
the recorded artifacts. It does not convert the partial experiment into a
scientifically reportable result, select a GNN arm, or authorize inferential
claims. Every upstream stage must remain marked `development_only`, and the
final report keeps `scientific_reporting_eligible` set to `false`.

## Audited chain

The audit verifies the following links:

1. dataset plan to dataset report;
2. dataset contract to training plan;
3. training plan to training report;
4. training contract to evaluation plan and report;
5. dataset contract to evaluation plan;
6. evaluation plan to evaluation report;
7. evaluation contract to Neural Diving plan;
8. Neural Diving plan to benchmark report;
9. benchmark contract to descriptive comparison plan; and
10. comparison plan to comparison report.

It also verifies the explicit file digests crossing training, evaluation,
benchmark, and comparison boundaries. The ledger inventories the core plans,
reports, arm manifests, GNN checkpoints, epoch histories, hint artifacts,
solver task results, and descriptive tables.

## DaSCI-DGX execution

Normalize the launcher before submission if a Windows checkout introduced
CRLF line endings:

```bash
sed -i 's/\r$//' \
  scripts/slurm/dasci/submit_mvp_pipeline_reproducibility.sbs
```

Export the five approved run directories and submit the gate:

```bash
export EXPERIMENT_NAME="mvp_repro_pr39_$(date -u +%Y%m%dT%H%M%SZ)"

JOB_ID=$(sbatch --parsable \
  --export=ALL \
  scripts/slurm/dasci/submit_mvp_pipeline_reproducibility.sbs)
JOB_ID=${JOB_ID%%;*}
echo "JOB_ID=${JOB_ID}"
```

The expected result is `gate_status=passed`, all common controls equal to
`true`, a nonempty artifact ledger, and
`next_gate=mvp_publication_tables_and_figures`.
