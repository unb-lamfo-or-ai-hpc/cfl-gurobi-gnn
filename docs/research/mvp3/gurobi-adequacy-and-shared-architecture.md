# Gurobi 14 methodological design note

This note supports the permanent [research protocol](coauthor-methodological-protocol.md). It specifies scientific responsibilities for solver features and proposed components. The separate operational transition dossier records environment and site evidence.

## Three distinct solver purposes

| Purpose | Principal profile | Evidence artifact |
| --- | --- | --- |
| Root-relaxation feature | Presolve=0, Heuristics=0, Method=-1, Threads=0, ConcurrentMIP=1, Seed=42 | Complete original-variable vector with root-event and cut-pass provenance |
| Incumbent reference | Native automatic presolve/method and default heuristics; MIPFocus=0 | Audited feasible incumbent, dual, gap and target trajectory |
| Main B/R/G comparison | Same native profile and resources for each parent; external Start varies | Paired target-time, quality and cost records |

Each primary call has a maximum28,800 s optimisation allowance and12 h job envelope. A complete feature capture ends its preparation run early. All effective parameters are recorded, including defaults.

Root-event ordering identifies the relevant continuous solution. Presolve and cutting-plane controls are distinct. The first root MIPNODE event and later root cut passes receive explicit ordinals; the first event with OPTIMAL status retains its actual position. The dataset identifies whether the vector represents the pre-cut relaxation or a later qualified root observation.

## Feasibility-oriented features in Gurobi 14

The new NoRel tree heuristic and PDHG-based MIP heuristic concern feasible solution discovery. MIPFocus=1 activates a feasibility-oriented strategy; SolutionLimit1 now acts as a limit rather than an implicit heuristic switch. The protocol assigns MIPFocus=1 to a separately identified conditional hard-instance preparation diagnostic. The primary root-feature and paired B/R/G contracts retain their specified profiles.

The diagnostic proposal records its trigger, instance, parameters and cost before release. It tests whether feasibility-oriented effort supplies a useful incumbent for qualification. Its observations retain their own provenance rather than becoming an additional main comparison arm.

## Component responsibilities for S1-S4

| Component | Responsibility |
| --- | --- |
| Native model adapter | Original-MILP identity, MINIMIZE, domains, bounds, fresh model state and effective parameters |
| Observational callbacks | Admissible event queries, candidate/root vectors, ordinals and bounded trajectories |
| Artifact layer | Complete variable order, hashes, provenance and immutable outcome records |
| Start adapter | B empty external Start; independent R; frozen G; undefined unselected values |
| Numerical audit | Objective, row, bound and integrality checks tied to exact vectors |
| Dispatcher/collector | Two-job/two-session ceiling, exclusive-node contract, attempt identities and terminal reconciliation |
| Analysis layer | Target-specific denominators, T_G/T_B orientation, quality, effort and cost scopes |

Historical executable sources and receipts remain preserved. S1 introduces the new versioned scientific contract and checks event/source semantics before any dataset release. Existing scientific workers with version-specific guards serve as design references; their historical invocations remain unchanged.

## Benders branch

Benders is conditional and restricted to the six hard instances. A design package gives the original-variable partition, recourse integrality, valid cuts, equivalence argument, numerical validation, memory rationale and budget. The researcher reviews it before implementation or execution. An audited incumbent receives BENDERS provenance, while root features retain their separately qualified original-MILP identity.

## References

The protocol provides the complete bibliography and versioned manual footnotes. Core technical sources are the Gurobi 14 parameter reference, callback codes, Start attribute and release notes; Gasse et al.(2019), Li et al.(2020) and Haq et al.(2025) supply the architectural, distributed-training and decomposition context.
