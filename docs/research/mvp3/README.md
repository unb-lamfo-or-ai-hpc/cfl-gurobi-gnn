# MVP3 methodological review packet

Prepared 19 November 2026 under the approved consolidated mandate. This packet is a scientific proposal for the coauthors, not a request to execute a historical launcher and not an execution authorization. No materials were sent to coauthors.

Start with [the detailed protocol](coauthor-methodological-protocol.md), then [the Gurobi adequacy/shared architecture note](gurobi-adequacy-and-shared-architecture.md). [Decisions and budget](decisions-and-budget.json) identify adopted directions and eight unresolved decisions; [the evidence contract](evidence-contract.json) specifies proposed normalized records without implementing a new pipeline.

## Deliverable coverage

| Mandate deliverables | Location |
|---|---|
|E1: MVP2 closeout|PR97/98 integration records and PR98 retirement receipt|
|E2/E3/E4/E7: scientific question, Gurobi/HPC, 90-instance characterization and 39-parent B/R/G|Protocol sections 1–4 and 7–11; evidence contract|
|E5/E6: dataset/labels/split and serial/DDP|Protocol sections 5–6; decisions D1–D5|
|E8/E9: shared architecture and independent Benders|Technical Note A–F, component inventory and exactness conditions|
|E10: full mathematical foundation|[Appendix A.8](../../../manuscript/supplement/gnn-mathematical-foundations.md), [Portuguese original](source/fundamentacao-matematica-pt-20261119.txt) and [reconciliation](foundation-reconciliation.json)|
|E11: consolidated English coauthor protocol|Detailed protocol plus explicitly linked specifications above|

## Boundaries

The 990 matrix and the 66/18 alternatives are discontinued. Preserve the technical pilots and artifacts as historical evidence. The new principal design is 90 characterization baselines and 39 test parents x B/R/G, with a conservative 207-solve budget. Two 20-core jobs are a candidate, not demonstrated capacity. Extra seeds, hints, parameter sensitivities, shared-core code and Benders implementation are not authorized.

The existing approved Sprint sequence is retained; this packet does not repeat or expand it. Protocol milestone 3 December 2026, pause 19 December–10 January, target journal submission 18 March2027. Resource/schedule risk and required coauthor decisions are visible in the protocol. No main/Pages/Zenodo publication is implied by a develop documentation PR.
