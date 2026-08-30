# ADR 0003: Best-available label for each parent instance

- Status: proposed — initial DaSCI smoke passed; provenance rerun required
- Date: 2026-08-28

## Context

The instance baseline defined by ADR 0002 requires one graph and one target
vector per original MILPBench CFL instance. Collected artifacts may contain a
final Gurobi solution pool, multiple true branch-and-bound incumbents, or both.
The legacy incumbent-conditioned ETL must remain available unchanged.

## Decision

Create a separate Gurobi parent-instance ETL. For each available instance:

1. resolve the original `MILPBench/CFL/<category>/LP/*.lp.gz` parent and require
   that it matches the manifest identifier;
2. require the corrected persisted objective sense to be minimization;
3. build graph structure and static features from
   `original_features.pickle.gz`, which the collector extracted from that raw
   parent;
4. add the root-LP-relaxation context from `node_relaxations.parquet`, or an
   explicit zero fallback when no valid root vector is available;
5. enumerate label candidates from `solutions.pickle.gz` and
   `incumbents.parquet`;
6. reject candidates with non-finite objectives, non-finite labels, or a label
   length different from the persisted number of variables;
7. choose the minimum objective;
8. resolve objective ties by lower MIP gap, final solution-pool provenance,
   lower recorded time, lower node, and source index;
9. attach `source_instance_id` and its canonical fold to the graph.

The solution artifact is the source of `variable.y` only. It does not define
the constraint matrix, rows, columns, nonzeros, or node features and therefore
does not turn an incumbent into a new instance in this baseline.

Outputs use stable instance-named `.pt` files under a dedicated
`instance_baseline` root. They never overwrite the incumbent-conditioned PyG
dataset. Missing or invalid instances are recorded in a JSON summary.

Each graph has a `.provenance.json` sidecar. It records the raw parent path and
SHA-256; structural-feature, collection-metadata, and root-context provenance;
separate label artifact, path, SHA-256, objective, MIP gap, quality band, time,
node, and source index; the candidate counts and best objective per artifact;
the deterministic selection reason; and the graph SHA-256. Legacy Unix-epoch
incumbent timestamps are normalized relative to the first recorded incumbent,
while native Gurobi runtime seconds are preserved. Both recorded and normalized
times and the normalization method remain auditable. The run summary aggregates
label counts by artifact and MIP-gap band. Existing graphs are reused only when
the sidecar is present and all recorded hashes still match.

## Partial-inventory policy

The builder processes every currently eligible instance without changing the
90-instance fold plan. Its summary is marked `development_partial` until the
complete canonical population is available and valid. `--strict_inventory`
provides the final completeness gate.

## Consequences

- Current easy/medium artifacts can exercise the builder before all solves are
  complete.
- Partial outputs are engineering artifacts, not final scientific results.
- Feasible labels with nonzero MIP gaps remain explicitly distinguishable from
  labels within optimality tolerance and require a reviewed training policy.
- Training and evaluation do not consume this new dataset yet; that integration
  is a subsequent PR after the DaSCI smoke test.
- The existing incumbent collector and incumbent-conditioned ETL are unchanged.
