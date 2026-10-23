# Read-only execution registry after PR67

PR67 was merged into develop at
`f06374af9487515c5380ec974118a4f29b05406d`. Its outcome stays nine consistent
phase logs and one unqualified medium16 log. This increment advances Sprint A
identity/cost reconciliation; it changes no solver, label or learning policy.

## Three entities, three different questions

| Entity | What this increment establishes | What remains unknown |
| --- | --- | --- |
| Historical artifact observation | Original PR65 ledger row identity and report content hash; potential content aliases. | Distinct executions, explicit scheduler binding, full-vector feasibility/uniqueness. |
| Recorded pilot attempt | Original plan and execution-report edge bind a specific attempt report to job 3468. | Scientific eligibility or independently audited incumbent vectors. |
| Allocation observation | One reviewed accounting snapshot supplies job-level resources; three step rows are not extra allocations. | Globally unique allocation identity across job-ID reuse and complete historical accounting. |

PR65's column named `attempt_id` is path-derived. The new view calls it an
`observation_id`; it must not silently become a certified execution ID. Equal
report bytes group potential artifact aliases but neither collapse executions
nor establish new ones. Parent/solver/parameter equality alone cannot join jobs.

Explicit reviewed claims are classified `matched`, `ambiguous` or `unmatched`.
A match requires subject/report identity, declared cluster, concrete job ID and
the accounting-snapshot hash. Multiple candidate allocation observations remain
ambiguous. Missing bindings remain unmatched, with no allocation reference.
Hash-shaped strings alone are not proof: production callers verify the input
bytes first; the join primitive consumes already-reviewed projections.

## Inputs, outputs and provenance boundaries

The CLI accepts the already recovered PR65 package, pinned to SHA256
`51c82520d8c343d14cd15ebbc425846541f76224fa08bf7fb07941a8ed456286`, and the
already returned job3468 accounting bytes, pinned to
`420354974a6269891bc467529104227d8ba0715e54c767d7866cde10c313fa89`.
The existing recovery reader checks outer/member hashes and archive allowlists
without extraction. The original public PR66 manifest binds plan/execution/
attempt inputs. No legacy schema is guessed, no raw JSON report discovered and
no input artifact overwritten. No LP, private log, license, Parquet vector,
pickle or checkpoint is opened; no optimizer, Slurm query or training is used.

Public output is an allowlisted relational JSON view plus its SHA256 manifest,
in a two-member package. Paths, original arbitrary fields and private commands
are excluded. Source bytes remain in their original locations. Input archive
size checks use the existing 16-MiB reader; accounting reads are bounded and
rechecked. A fresh output directory outside public receipt sources is required.

The pilot join is limited to the reviewed snapshot. Cluster is declared by the
plan/operator context; the captured sacct text contains neither cluster nor
allocation start/end timestamps. Consequently this is not a globally unique
scheduler identity or a license to merge overlapping historical snapshots.
Hash provenance records observed bytes, not cryptographically signed execution.

## Actual read-only verification

Using already downloaded evidence locally, the view retains **87 historical
report observations** with unknown distinct-execution count and zero qualified
historical job bindings. The ten pilot attempts are explicitly bound to **one**
allocation observation, not ten additional reservations.

The parent snapshot yields allocated logical CPU-hours `32 * 1794 / 3600`
(15.946667), versus reported CPU-hours `2803.115 / 3600` (0.778643). These are
different measures, not speedup or phase utilization. No child CPU value is
added to the parent aggregate. The earlier 16-physical-core affinity measure
remains distinct from Slurm's 32 logical allocated CPUs.

Complete historical costs, complete 54-parent unique-incumbent totals and
per-phase costs remain null/unqualified. This does not certify the missing
historical executions or complete Sprint A. No new HPC run is needed to reproduce
the same projection from the retained downloads.

## Local CLI with already downloaded evidence

```powershell
python scripts/evidence/build_execution_registry.py `
  --pr65-package D:/Downloads/cfl-gurobi-gnn/pr65_recovered_evidence.tar.gz `
  --accounting /exact/local/download/sacct-final.txt `
  --output /fresh/local/output/execution-registry
```

For future HPC collection, freeze a separate input/scope receipt first and keep
all generated files below physical `/raid/vrcelestino/data/cfl-mvp2-evidence`.
Do not query account-wide jobs and add them to CFL totals. Preserve failed 3466,
completed 3468 and their original accounting/packages; no retry or cleanup is
authorized by a missing link. Historical adapters and job-ID reuse/time-window
corroboration are subsequent gates, followed by bounded full-vector/lineage audit.
Training contracts and resource budgets remain separately frozen before serial
or progressively qualified DDP execution. Main/Pages/Zenodo/MVP1 stay unchanged.
