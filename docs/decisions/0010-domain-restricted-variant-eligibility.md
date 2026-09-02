# ADR 0010: treat domain-only node MIPs as derived variants, not new instances

## Status

Proposed for methodological review.

## Context

The schema-v3 PySCIPOpt audit serialized four mechanically valid node MIPs from
one easy CFL parent. Each artifact was distinct from the root and from the
other candidates because hundreds of variable bounds changed. Nevertheless,
all candidates retained the parent's objective, constraint matrix, rows,
columns, and nonzeros.

The project originally sought node-derived MILPs with new structural counts.
The observed `writeMIP()` artifacts do not satisfy that definition. Conversely,
discarding them solely because their dimensions are equal would ignore a real
change in the feasible region. A formal distinction is therefore required
between a benchmark instance and a derived learning sample.

## Decision

A `domain_distinct_same_matrix` artifact is not a new independent MILP instance
and must not increase the number of parent instances reported by an experiment.
It may be studied later as a **domain-restricted variant** of exactly one parent
instance, in a separate experimental dataset variant.

The following terminology is normative:

- **parent instance**: an original MILPBench CFL file and the unit of population,
  splitting, and primary inference;
- **structurally distinct formulation**: a formulation whose canonical matrix,
  objective, rows, columns, or nonzeros differ for a mathematically relevant
  reason;
- **domain-restricted variant**: a child formulation with the same matrix and
  objective as its parent but a distinct canonical variable-domain fingerprint;
- **node observation**: solver metadata captured at a focused node; it is not
  itself an instance;
- **transformed control**: a `writeProblem(trans=True)` artifact used only for
  diagnostics and never admitted to a dataset.

The terms “new instance”, “independent instance”, “pruned subtree”, and “exact
node subproblem” must not be used for a domain-restricted variant unless a later
experiment establishes the additional claim. The current probe observes
focused nodes, not an ex-post serialization of every pruned subtree.

## Statistical unit and leakage boundary

The parent instance is the indivisible grouping key. Every root graph, variant,
label, checkpoint input, and evaluation record derived from the same parent
must remain in the same fold and role. A variant may never cross train,
validation, or test boundaries relative to its parent or siblings.

Reports must expose both counts separately:

- `n_parent_instances`;
- `n_domain_restricted_variants`.

Metrics over variants are secondary, clustered by parent, and cannot be used to
claim an increased independent sample size. Comparisons should give each parent
equal aggregate weight and estimate uncertainty with parent-clustered methods.

## Eligibility gates for a future derived dataset

Domain-restricted variants remain `dataset_eligible=false` until every gate
below passes:

1. **Serialization**: fresh-process readability, integrality, ancestral branch
   bounds, local constraints, objective sense, and root-relative fingerprints
   pass for every admitted artifact.
2. **Graph observability**: the graph schema encodes the local lower and upper
   bounds responsible for variant identity, and graph fingerprints distinguish
   the admitted variants. If bounds are absent or normalized away, the variant
   cannot be used.
3. **Label validity**: labels are produced by solving or validating the derived
   MIP itself. Parent incumbents are not inherited unless feasibility under the
   child domains is demonstrated.
4. **Parent-grouped split**: one auditable contract assigns all descendants of a
   parent to the parent's canonical fold and partition.
5. **Deduplication**: semantic-node, formulation, graph, and label hashes are
   audited; exact duplicates are removed or explicitly weighted once.
6. **Sampling policy**: depth strata, maximum variants per parent, seeds,
   presolve regime, termination limits, and selection rules are precommitted.
7. **Dependence-aware reporting**: parent and variant counts, per-parent weights,
   and clustered uncertainty are reported; variants do not inflate the nominal
   benchmark population.
8. **Resource budget**: storage and solve costs are bounded. Transformed controls
   are disabled after validation and are never retained at dataset scale.
9. **Replication**: the complete contract is replicated across multiple parents
   and available difficulty levels before training integration.

## Consequences

The current 90-instance plan remains defined exclusively by original parent
instances. The Gurobi instance baseline and its canonical folds remain
unchanged. No node-derived artifact enters training, validation, or test data as
a result of this ADR.

A future positive gate may create a separately named experimental variant, for
example `scip_parent_grouped_domain_variants`. It must reuse parent folds and
must never be pooled with the parent-instance baseline without an explicit
comparison design.

If graph observability or label validity fails, the strategy stops without a
dataset implementation. If all gates pass, a later implementation PR may add a
research-only builder and audit CLI; eligibility will still require an explicit
review decision.
