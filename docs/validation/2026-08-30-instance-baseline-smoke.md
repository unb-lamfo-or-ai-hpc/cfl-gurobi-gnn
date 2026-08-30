# Gurobi parent-instance baseline: DaSCI smoke evidence

- Date: 2026-08-30
- Tested commit: `3c29403520dd7c6df7a362119a081185cdd53b41`
- Population status: development partial
- Result: provenance pipeline passed; one targeted corrective rerun remains

## Aggregate result

| Check | Result |
|---|---:|
| Planned parent instances | 90 |
| Artifact-available parents | 42 |
| Successfully generated graphs | 42 |
| Provenance sidecars | 42 |
| Failures | 0 |
| Easy parents | 30 |
| Medium parents | 12 |
| Hard parents | 0 |

All 42 results identified `MILPBench/CFL` as the raw structural dataset,
resolved the expected category/instance `.lp.gz`, loaded a root-node relaxation,
recorded the `MAXIMIZE` source directive and the corrected `MINIMIZE` override,
and persisted every required digest. No raw-path mismatch, missing digest, or
duplicate graph digest was found.

## Label audit

| Label artifact | Count |
|---|---:|
| `solutions.pickle.gz` | 33 |
| `incumbents.parquet` | 9 |

| MIP-gap band | Count |
|---|---:|
| Within optimality tolerance | 30 |
| Greater than 40% | 12 |

The label artifact supplies `variable.y` only; it does not supply graph
structure. Four high-gap labels came from the solution pool and eight came from
incumbents, so artifact name must not be used as a proxy for optimality.

## Findings and follow-up

- The previous non-writable NumPy-label warning did not recur.
- The CUDA initialization warning remained, but graph construction completed on
  CPU and is not blocked by it.
- Legacy incumbent timestamps used Unix-epoch scale while solution-pool times
  used Gurobi runtime seconds.
- Console output used the ambiguous key `source` for label provenance.
- The initial summary did not explain the candidate inventory behind selection.

The follow-up commit normalizes legacy timestamps, renames the log key to
`label_source`, and records evaluated/valid/invalid candidates plus the best
objective per artifact and the selection reason. A single-instance DaSCI rerun
with `--overwrite` is the remaining readiness gate.
