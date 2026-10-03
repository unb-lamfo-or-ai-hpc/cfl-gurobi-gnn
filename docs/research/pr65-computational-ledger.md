# PR65: read-only computational reconciliation and class characterization

## Release boundary and purpose

This MVP 2.0 increment targets `develop`. Main, Pages, the private MVP 1.0
archive and the unpublished Zenodo draft remain unchanged. No manuscript
revision, optimizer run, new label, graph encoding or training is performed.
The engineering objective is to identify which historical observations can
support subsequent CPU, GPU and augmentation experiments.

## Two independent diagnostics

`scripts/evidence/collect_computational_ledger.py` discovers generated JSON
reports and incumbent Parquet tables in `analysis`, `intermediate` and `models`.
It excludes raw inputs, symlink traversal and operational directories. Each
observation has a content hash and a path-derived artifact identity; the
private inventory maps these identities to source paths. Public tables contain
allowlisted fields, not copied reports or exception messages. JSON larger than
32 MiB, malformed artifacts and unsupported canonical report schemas remain
explicitly unqualified. No pickle, checkpoint or solution vector is loaded.

The current solve adapter handles `gurobi_parent_solve_report.json` and
`scip_parent_solve_report.json`. These are report observations, not a universal
adapter for every legacy metadata format, paired worker outcome or failed
scheduler attempt. The recorded admission flag is the source's declaration,
not a new feasibility certificate. Sibling artifact hashes and parameter-map
hashes are checked independently. Repeated reports retain distinct identities;
event counts are not summed across aliases or experiments.

Training membership comes from each `gasse_training_plan.json` independently.
Conflicting roles within a plan are rejected. A plan does not prove that its
checkpoint was trained or that a derivative supplied optimizer updates. Such
execution and lineage joins remain subsequent evidence gates.

Parquet footer rows and columns are inventory observations. Solver attribution,
unique feasible vector counts and complete 54-parent solver totals remain
unavailable until variable orders, vectors, duplicates and feasibility are
qualified. Generation/labelling reports identify observed stages; they do not
certify independently labelled derivatives or actual training usage.

Slurm accounting preserves parent/task/step rows separately, including timeout
and failure states. Unknown GPU allocation or utilization is unavailable, not
zero. User-account jobs are not yet attributed to CFL attempts: these rows must
not be summed into a CFL research-cost claim.

`scripts/evidence/collect_class_statistics.py` separately reads the canonical
90 original LP paths. It uses only the authorized local Gurobi license, reads
one model at a time, records the input SHA256 and obtains original linear model
attributes without optimization or presolve. Objective sense is recorded and
set to MINIMIZE in memory only; source LPs are neither changed nor packaged.
Models with quadratic, SOS or general constraints are explicitly unsupported.

The per-parent table includes variable types, constraint senses, nonzeros,
matrix density, coefficient/objective/RHS ranges and mean bipartite degrees.
Class summaries report observed/missing counts, mean, median, minimum, maximum
and sample standard deviation. These are structural features, not predictive
positive prevalence or empirical difficulty guarantees. Full degree
distributions, graph visualization, PCA/UMAP and network-based methodology are
not computed in this increment.

Attribute definitions follow the official
[Gurobi model-attribute reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/model.html).
The installed reader version is recorded; no runtime upgrade is requested.

## Output and privacy contract

The ledger directory contains seven shareable artifacts and `SHA256SUMS.txt`:

- `parent_solver_ledger.csv`
- `training_membership.csv`
- `incumbent_table_inventory.csv`
- `augmentation_lineage.csv`
- `hardware_usage.csv`
- `missing_evidence.json`
- `ledger_report.json`

`source_inventory.private.json` stays on the HPC. Its digest is referenced by
the public report. The source Slurm accounting and raw diagnostic logs also
remain private. No source files are overwritten; existing output directories
are refused. Manifest verification never regenerates expected hashes to
approve altered output.

The class directory contains `class_instance_statistics.csv`,
`class_descriptive_statistics.csv`, `class_statistics_report.json` and its
own manifest. A report records whether all 90 models were read successfully.
A successful diagnostic with missing evidence is not scientific certification.

The packaging script uses an explicit allowlist of these ten artifacts, two
manifests and the source-commit receipt. It does not package raw LPs, binaries,
private inventories, license files or Slurm logs. No Zenodo action occurs.

## Execution on dgx-dasci

After publishing this feature branch to the canonical repository, use an
isolated worktree linked to the existing repository; leave the dirty primary
checkout and its data untouched. Run the qualified launcher from that worktree:

```bash
bash scripts/slurm/dasci/launch_pr65_evidence.sh
```

It first runs dependency, accounting and evidence-test checks, then submits two
independent diagnostics: one CPU/8G for the ledger and one CPU/64G for sequential
model reading, each with a two-hour scheduler limit and no GPU. All generated
outputs and logs reside in a fresh directory below
`/raid/vrcelestino/data/cfl-mvp2-evidence`, never directly in the home directory.
These initial reservations are safety budgets, not measured resource needs.

The first HPC preflight stopped in the deliberate Git ownership regression,
before either diagnostic was submitted. Older security-patched Git releases
do not recognize command-line `safe.directory`; see the official
[Git 2.35.5 configuration documentation](https://git-scm.com/docs/git-config/2.35.5.html).
The installed HPC Git version still needs to be recorded, so compatibility
is an explanation to qualify, not a confirmed version identification.
The binary evidence reader now supplies a subprocess-local temporary global
configuration containing only the exact resolved checkout. It clears inherited
trust, does not edit persistent global/system configuration, and removes the
temporary file on success or failure. Ownership tests remain enabled, including
linked-checkout isolation and the older command-line scope behavior. This is
locally qualified; the repaired HPC preflight is still pending.

Retain `LEDGER_JOB`, `CLASS_JOB`, `OUTPUT` and `EXEC` printed in the receipt. Do
not rerun the launcher to recover a forgotten path: read the existing receipt.
After both jobs terminate, inspect their status/error logs and the two reports.
To verify and package, from the same feature worktree:

```bash
bash scripts/slurm/dasci/package_pr65_evidence.sh "/exact/OUTPUT/from/submission"
```

Share the small package, its printed SHA256 and final `sacct` output. Do not
share the private inventory or raw logs without an additional privacy review.
The packager refuses to overwrite an existing package.

## Closure and next experimental gate

Review the collected reports, missingness and hashes before closing the PR.
Adapt legacy schemas and reconcile source/job/vector/derivative identities
where evidence is recoverable. If it is not, retain unavailable quantities.
Only then freeze a structural pilot subset and the CPU/thread experiment.
Qualification of serial/DDP 1/2/4/8-GPU training remains a separate sprint.
This diagnostic does not imply incumbent, scaling or warm-start improvements.
