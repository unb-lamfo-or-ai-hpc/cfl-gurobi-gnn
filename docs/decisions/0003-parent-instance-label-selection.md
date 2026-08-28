# ADR 0003: Best-available label for each parent instance

- Status: proposed — requires DaSCI smoke validation
- Date: 2026-08-28

## Context

The instance baseline defined by ADR 0002 requires one graph and one target
vector per original MILPBench CFL instance. Collected artifacts may contain a
final Gurobi solution pool, multiple true branch-and-bound incumbents, or both.
The legacy incumbent-conditioned ETL must remain available unchanged.

## Decision

Create a separate Gurobi parent-instance ETL. For each available instance:

1. require the corrected persisted objective sense to be minimization;
2. enumerate valid candidates from `solutions.pickle.gz` and
   `incumbents.parquet`;
3. reject candidates with non-finite objectives, non-finite labels, or a label
   length different from the persisted number of variables;
4. choose the minimum objective;
5. resolve objective ties by lower MIP gap, final solution-pool provenance,
   lower recorded time, lower node, and source index;
6. attach `source_instance_id` and its canonical fold to the graph.

Outputs use stable instance-named `.pt` files under a dedicated
`instance_baseline` root. They never overwrite the incumbent-conditioned PyG
dataset. Missing or invalid instances are recorded in a JSON summary.

## Partial-inventory policy

The builder processes every currently eligible instance without changing the
90-instance fold plan. Its summary is marked `development_partial` until the
complete canonical population is available and valid. `--strict_inventory`
provides the final completeness gate.

## Consequences

- Current easy/medium artifacts can exercise the builder before all solves are
  complete.
- Partial outputs are engineering artifacts, not final scientific results.
- Training and evaluation do not consume this new dataset yet; that integration
  is a subsequent PR after the DaSCI smoke test.
- The existing incumbent collector and incumbent-conditioned ETL are unchanged.
