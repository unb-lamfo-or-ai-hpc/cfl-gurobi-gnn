# Approved-source checkout and package admission — 23 November 2026

The existing NPAD checkout and the CFL-only package installation are accepted within their recorded scopes. The [sanitized receipt](checkout-package-admission-20261123.json) binds the approved source, current 66-input catalogue and environment inventories. This operational admission does not start scientific MVP 3.0 development.

## Source and input identity

The author diagnostic confirms a clean checkout of `61ba422c147c3a3d9ae04b49f1607ed5fca4d0e1`, tree `e79ed1222649d04fea4739585981833685ca7dc6`. Exact local reconstructions reproduce checkout receipt `c283023b588ca1b3ba44520372b63a1b9093f74412df9c4cae24f144f79e6018` and the 66-file path-map hash `5415ac847e182d5f748e59a7c026d828cde2386cc723e3a0affdd0f5f241aaaf`. All 12 project/build requirements are satisfied. The later exclusive-stage error refused a duplicate invocation; no replacement clone is needed.

All 66 current NPAD inputs are present. The researcher explicitly confirms that the DGX and NPAD LPs are the same MILPBench instances and accepts decoded-LP equivalence on that provenance basis. Different stored gzip hashes remain separate identities. No independent decoded-byte comparison, gzip integrity test or full Gurobi model-read test is claimed; no additional decompression or identity test is required. The [input inventory](current-input-inventory-20261123.md) retains the compressed-file provenance and preservation classification.

## Package installation

One offline editable install added only `cfl-gurobi-gnn 0.1.0`, without dependencies, build isolation or extras. The author receipt's exact canonical reconstruction reproduces SHA256 `bcda9426e8e0f449b8fb9b911b1cbc4d0545bb619c94520dcc1061a6a92e1ab1`; the CLI exited 0. Table 1 separates the current target inventory from its preserved qualification baseline.

**Table 1. Environment admission identities.**

| Record | Before installation | After installation |
| --- | --- | --- |
| Original environment inventory | `94e163438088c2e35743c3858e35c60dbfd3b1c8fd05ec1b7ff6a54dce3bc750` | Unchanged |
| Target distribution records | 106 | 107 |
| Target inventory SHA256 | `dafe3bf6020249096a4b8f31574b7a192cb3f3d45175f893e916aedd605dd82d` | `1fa27e7b9e2dce69eb2d13d48cfe8dcf32991765c49efa550a3ab7220508f839` |
| Added distribution | None | CFL 0.1.0 only |

The checked receipt reports preservation of every preexisting distribution version and the original environment. The full remote inventory and pip log were not transferred; this review independently verifies the receipt hash and its internal/source bindings. Earlier successful GPU/training/license receipts retain their original target inventory and executed source. Do not rewrite them or repeat their tests solely because the project distribution was subsequently added.

The inert package root imports successfully from the approved editable source. The resolved scratch filesystem mount alias explains the reported module path. Neither Torch nor Gurobi was imported by this check. This is package discovery admission, not qualification of the training driver, real graphs, historical checkpoints, DDP or performance.

## Historical installation boundary and subsequent home binding

At this installation snapshot, the installer reports unchanged tracked source and metadata for all 66 inputs, with zero model-payload reads, solves, neural forwards, optimizer steps, training calls or Slurm submissions. The project's ignored private secrets directory is prepared, but its license file is absent. No license was read, copied or initialized.

A subsequent [home-checkout binding](home-checkout-binding-20261123.md) now supersedes this source-location and license-placement boundary. The installation was rebound to the approved home clone; both source checkouts remain preserved. The earlier scratch-source binding and absent-license fields in the immutable installation receipt remain historical.

TR-04 completed source checkout, input path binding and package admission in this snapshot; the later home-binding return also confirms the author-provisioned project-local license path. Any later technical test with real CFL data requires an explicit bounded scope; it is not automatically authorized by this record. TR-05 continues through the English protocol in Draft PR #99 before scientific implementation. PRs #99, #101 and #102 remain Draft; merges require separate approval.
