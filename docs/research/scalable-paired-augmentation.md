# Scalable paired augmentation and graph campaign

## Purpose

This stage scales the validated local-branching prototype without changing its
scientific semantics. It consumes the paired-parent eligibility contract from
the parent collection campaign and prepares four comparable data views:
Gurobi-original, Gurobi-augmented, SCIP-original, and SCIP-augmented.

Gurobi remains the priority solver and the sole graph-construction authority.
PySCIPOpt provides a matched source of incumbents and independent labels. It is
not used to encode graph features. An incumbent vector is provenance and a
local-branching centre; it is never represented as a graph by itself.

## Inclusion and leakage controls

Only parents satisfying all of the following conditions are admitted:

1. the parent role is `train` for the frozen rotation;
2. both solver artifacts and their hashes passed the parent audit;
3. both terminal labels satisfy the precommitted maximum relative MIP gap;
4. both incumbent artifacts are eligible augmentation sources.

Validation and test parents are never augmented. Every derived MILP inherits
its parent fold and remains train-only. Original validation/test graphs are
retained for the later held-out evaluation stage.

## Execution contract

For each admitted parent, exactly one task is planned for each solver. Both
tasks use the same binary-variable local-branching operator and the same radius
fractions. Each derived MILP is solved independently in a fresh process, with
no parent incumbent, warm start, or hidden solver state supplied. The default
per-candidate budget is 3,600 seconds; 14,400 seconds is reserved for an
explicit rescue campaign. Because a solver-parent task resolves three radii
serially, its Slurm wall-time accommodates three 14,400-second candidate
budgets plus bounded orchestration overhead. Terminal MIP gap and solver wall
time remain the primary label-quality measurements.

The task array is resumable only when the generation report, independent solve
report, and referenced artifacts still match their SHA-256 contracts. The
campaign audit verifies paired radii and emits a path-neutral source index for
the graph stage.

The path-neutral generation package is self-contained: a byte-identical,
SHA-256-bound copy of the source incumbent is stored beside the generation
plan. Membership audits resolve that local file name, while legacy absolute
references remain readable only for backward compatibility. This prevents
execution-host paths from entering reports and allows completed independent
solves to be re-audited without re-optimisation.

## Graph and descriptive-analysis contract

The graph stage accepts multiple independently audited source directories per
solver. Every original parent MIP and every derived local-branching MIP receives
one graph. Gurobi captures the first optimal root `MIPNODE` relaxation for the
seventh variable feature; zero and continuous-relaxation fallbacks remain
prohibited.

The four arm manifests may contain two label views of the same original graph.
Before descriptive analysis, these views are deduplicated by mathematical-MIP
SHA-256. Conflicting graph hashes for one MIP fail closed. `graph_statistics`
and `graph_clustering` then run over this structural manifest, producing
hash-bound CSV, JSON, and SVG artifacts.

## Current acceptance boundary

The PR is validated with a bounded development smoke, not the complete
90-parent scientific campaign. Consequently all results remain
`development_only=true` and `scientific_reporting_eligible=false`. The later
strict campaign must repeat the accepted code over all 30 easy, 30 medium, and
30 hard parents and all precommitted rotations.
