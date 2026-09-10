# Scalable paired parent collection campaign

## Purpose

This campaign scales the recovered original-parent solve contract without
changing its scientific boundary. Gurobi is the priority solver and
PySCIPOpt is a matched comparison. Each Slurm array task processes one parent
sequentially with Gurobi followed by SCIP, so a failed Gurobi solve cannot be
silently paired with an unrelated SCIP result.

The current campaign is a development MVP over the available inventory. The
strict 30 easy, 30 medium, and 30 hard execution is intentionally deferred.

## Reproducibility contract

- Raw parent paths and SHA-256 hashes come from the canonical 90-parent fold
  manifest.
- CFL files record their original objective sense and are solved with the
  effective `MINIMIZE` sense.
- Accepted time limits are 3,600 and 14,400 seconds. Their run directories are
  disjoint, preventing a rescue run from overwriting shorter-budget evidence.
- Solver threads, seed, node limit, solver profile, parent fold, and parent role
  are contract fields.
- Reuse requires matching solve contracts, parent hashes, report checks, and
  hashes for every declared artifact.
- At most four parent pairs run concurrently by default. This is an operational
  resource control, not a statistical parameter.

## Progress, missingness, and censoring

The progress audit always distinguishes a valid audit from a complete
campaign. Missing or invalid tasks produce solver-specific rescue manifests.
A valid right-censored result is retained. If its label exceeds the maximum
10% relative MIP gap and a larger precommitted budget exists, the record is
recommended for the 14,400-second rescue campaign. Results that remain
ineligible at the maximum budget are explicit terminal exclusions.

Paired eligibility is computed at the parent level. The output reports:

- valid, invalid, and missing solver tasks;
- right-censored tasks;
- Gurobi-only, SCIP-only, paired, and neither-eligible missingness classes;
- paired eligibility at relative MIP gaps of 1%, 5%, 6%, and 10%;
- eligibility to supply an incumbent for symmetric Local Branching;
- the four wall-time regions: total, data read, model build, and optimize.

No incomplete inventory is eligible for scientific reporting.

## Execution sequence

First write a plan for the files that currently exist:

```bash
python3 -m cfl_gnn.cli.plan_parent_collection \
  --base_source_dir /raid/.../data/raw/MILPBench/CFL \
  --output_dir /raid/.../data/analysis/parent_collection/<campaign>-plan \
  --time_limit 3600
```

Then export the plan, run, progress, raw-data, and license paths and launch the
bounded paired array:

```bash
export MAX_PARALLEL_PARENTS=4
bash scripts/slurm/dasci/launch_paired_parent_collection.sh
```

The progress job uses `afterany`, not `afterok`, so failed array tasks remain
observable and generate rescue records. It never converts missing evidence
into an eligible label.

For a 14,400-second rescue, create a new plan containing only the parent IDs
listed in the rescue manifests. The budget-specific task paths preserve the
original 3,600-second evidence.
