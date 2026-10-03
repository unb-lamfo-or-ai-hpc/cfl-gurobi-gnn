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
90 original LP paths, accepting either `.lp` or `.lp.gz` per identity. It uses
only the authorized local Gurobi license, reads
one model at a time, records the input SHA256 and obtains original linear model
attributes without optimization or presolve. Objective sense is recorded and
set to MINIMIZE in memory only; source LPs are neither changed nor packaged.
Models with quadratic, SOS or general constraints are explicitly unsupported.
Compressed LPs are passed directly to the reader; no decompressed copy is saved.
Input hashes identify the original stored bytes, including compression. Two
stored formats for the same identity are ambiguous and require reconciliation;
the collector does not silently choose one. Missing/unsafe/ambiguous sources are
distinct from model-read errors. The launcher requires all 90 unambiguous inputs
before submission. A collection with any missing/failed models retains its
diagnostic artifacts but exits nonzero.

Compressed I/O is documented in the official
[Gurobi file-format reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/fileformats.html).

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
locally qualified and the author-confirmed repaired HPC preflight passed all
54 tests. Diagnostic jobs 3463 and 3464 subsequently completed.

The first package was independently verified against SHA256
`9028296e9574593d2a62be6e20f8ac976dd9519458b8401a87085270a1ded07c`,
including all 13 members, two manifests and both collector source hashes.
Its coverage receipt is `docs/evidence/pr65/first_collection_verification.json`.
The original class collector recognized only `.lp`, whereas existing pipeline
contracts use `.lp.gz`: all 90 records were `missing_lp`, not read/license errors.
The compressed-path correction was subsequently qualified by recovery job 3465,
as recorded below. The first-attempt receipt retains its original failed coverage.
The ledger's one issue has the exact path-identity hash of the previously
archived invalid `models/run_01/experiment_summary.json`; historical bytes are
preserved, not repaired to conceal this record.

To retry only class reading after publishing the correction, from the same
isolated checkout run:

```bash
bash scripts/slurm/dasci/retry_pr65_classes.sh "/exact/original/OUTPUT"
```

This verifies the previous manifests and discovery, creates a fresh
`classes-recovery-*` directory, and submits one model-reading job. On complete
reading it automatically packages the unchanged original ledger with the new
class artifacts. The original files/package remain intact. A public
`recovery_receipt.json` records separate ledger/class source commits and the
reused/superseded report hashes. The new package path and digest appear in the
recovery job's log; do not replace the original local package when downloading it.

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

## Verified recovery and class structure

Job 3465 completed with author-reported ExitCode 0:0 in 529 seconds. The received
recovery package has SHA256
`51c82520d8c343d14cd15ebbc425846541f76224fa08bf7fb07941a8ed456286`.
Independent verification checked all 14 regular members, both manifests, the
ten declared artifact hashes, text-marker sanitization, collector hashes and
split-source provenance. All eight ledger members are byte-identical to the
first package. The 90 unique canonical parents were successfully read from
compressed originals using Gurobi 13.0.1. Arithmetic recomputation independently
confirmed 60 class-feature rows and all 300 descriptive statistic values.

The public receipts and compact structural projection are versioned in
`docs/evidence/pr65/recovered_collection_verification.json` and
`docs/evidence/pr65/structural_class_summary.json`. They do not redistribute
benchmark LPs or deserialize model/checkpoint binaries. To reproduce verification
locally with both downloaded packages:

```powershell
python scripts/evidence/verify_pr65_recovery.py `
  --first-package D:/Downloads/pr65_evidence.tar.gz `
  --recovered-package D:/Downloads/pr65_recovered_evidence.tar.gz
```

The table summarizes model dimensions, which are constant within each class.
Variable-type composition and numerical coefficient ranges vary across parents.

| Original class | Parents | Variables | Constraints | Matrix nonzeros | Density (%) |
| --- | ---: | ---: | ---: | ---: | ---: |
| easy | 30 | 160,400 | 800 | 320,400 | 0.249688 |
| medium | 30 | 1,281,600 | 2,400 | 2,561,600 | 0.083281 |
| hard | 30 | 5,123,200 | 4,800 | 10,243,200 | 0.041654 |

Medium has approximately eight times the variables and nonzeros of easy; hard
has approximately four times those of medium. Density decreases with class
size, while the mean variable degree remains approximately two and the mean
constraint degree rises from 400.5 to 1,067.33 and 2,134. Lower density therefore
does not imply a smaller matrix or lower memory demand. These attributes help
design memory and thread experiments, but do not measure scaling or prove
that a specific thread count improves solve time.

All 90 stored models declare MAXIMIZE. The diagnostic records this explicitly
and sets MINIMIZE in memory only, following existing CFL experiment contracts.
The successful read does not independently establish why the stored objective
sense differs or certify historical solver configuration. Original stored bytes
remain unchanged. Binary-variable counts describe variable domains, not the
prevalence of positive solution labels.

## Closure and next experimental gate

Close PR65 as a verified read-only engineering diagnostic after the final
published commit passes CI and review on `develop`. Structural collection and
recovery are complete; full computational reconciliation is not. The unchanged
ledger contains 87 supported reports (45 Gurobi, 42 SCIP) across 36 parents:
four easy, all 30 medium and two hard. Unsupported legacy observations are
missing evidence, not evidence that the other easy parents were never solved.
The one invalid historical JSON remains preserved and reported.

Next qualify legacy schemas and attempt aliases, join Slurm jobs to actual CFL
attempts, audit variable order and unique feasible vectors, and verify actual
derivative training usage. Preserve unavailable totals when sources cannot
support them. Full 54-parent unique-incumbent totals and complete historical
compute cost remain unavailable; report counts and footer rows must not replace
them.

The next CPU experiment can use the qualified structural cohort to select a
predeclared representative easy/medium pilot, testing 1/2/4/8/16 solver threads
with matched budgets, measured memory, allocated CPU-hours, measured CPU use and identical
solver parameters apart from the planned thread intervention. No hard-label
campaign is authorized here. Serial versus DDP 1/2/4/8-GPU training qualification
remains separate, with matched effective global batch and data membership before
claims about speed or predictive quality. This diagnostic does not imply
incumbent, scaling or warm-start improvements. Main/Pages and Zenodo remain
unchanged.
