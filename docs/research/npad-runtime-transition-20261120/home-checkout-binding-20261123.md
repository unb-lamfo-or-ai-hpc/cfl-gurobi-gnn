# Stable CFL checkout binding — 23 November 2026

The author cloned the approved develop revision into the intended home checkout, manually placed the project license in its ignored secrets directory, and completed the bounded editable-package rebinding. The exact reconstructed author receipt reproduces SHA256 `fee7f455ca186a09153a279723bfb2f658064a9e74e627d14ab828ff07ea1c36`, with CLI exit0. The [sanitized receipt](home-checkout-binding-20261123.json) links this return to the [earlier package admission](checkout-package-admission-20261123.md).

The source remains `61ba422c147c3a3d9ae04b49f1607ed5fca4d0e1`, tree `e79ed1222649d04fea4739585981833685ca7dc6`. Both the imported module and editable direct-URL metadata now point to the approved home clone. The scratch checkout is preserved as evidence and is no longer the active editable source. No tracked source was changed.

Table 1 summarizes the operational checks. These checks establish package binding and license-path readiness; they do not establish a new solver or full-driver qualification.

**Table 1. Home-checkout admission.**

| Check | Received result |
| --- | --- |
| CFL package and inert root import | 0.1.0; approved home source |
| Target distribution records | 107 before and after |
| Target Name/Version inventory SHA256 | Unchanged: `1fa27e7b9e2dce69eb2d13d48cfe8dcf32991765c49efa550a3ab7220508f839` |
| Original environment inventory SHA256 | Unchanged: `94e163438088c2e35743c3858e35c60dbfd3b1c8fd05ec1b7ff6a54dce3bc750` |
| Project-local license path | Present, readable and ignored by Git |
| Torch/Gurobi imports during rebinding | None |
| New solves, training, forwards or Slurm jobs | None |

One offline, no-dependency editable install changed the source binding while preserving all distribution versions. The version inventory digest correctly remains unchanged: it identifies sorted package names and versions, not source URLs. The separate receipt records the new source binding. The inventory JSON file digest differs from the earlier installation because the reviewed workers serialize different enclosing fields; neither full remote inventory file was transferred for independent replay.

The license check used filesystem metadata and Git ignore/tracking checks only. The author uploaded the file; the rebinding worker did not read or copy its contents or initialize Gurobi. Future explicitly authorized commands must select the CFL project's own `secrets/gurobi.lic` through `GRB_LICENSE_FILE`, replacing the temporary Agrologistic test path. This update does not edit shell profiles or activate a license automatically.

TR-04 operational admission is complete for the current source, data path map, package discovery and project-license path. The current66 input catalogue and researcher-confirmed MILPBench equivalence remain unchanged. Prior technical GPU/synthetic-training/license receipts retain their original executed source and environment baseline. No repeat of those tests is required solely for this documentary or path-binding update.

Full CFL driver operation with real data, historical-checkpoint loading, DDP, hard-instance memory use and performance remain outside the qualified scope. They require a separately approved bounded test or scientific protocol. The English methodological plan remains under author review in Draft PR #99. Preserve both checkouts and all receipts; no cleanup, bulk artifact migration, merge or publication follows automatically.
