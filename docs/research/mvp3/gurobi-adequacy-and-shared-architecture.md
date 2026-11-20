# Technical Gurobi Adequacy Note — MVP 3.0

Prepared 19 November 2026 for methodological review. This is the documentary response to Technical Gurobi Addendum 2026-02, not an implementation or execution release. Read with the [coauthor protocol](coauthor-methodological-protocol.md).

Evidence labels used below:

- **DOC:** confirmed in official versioned documentation.
- **CODE:** present in the inspected repository source, not necessarily site-qualified.
- **OBS:** previously returned experimental/technical evidence.
- **DEC:** methodological direction approved in the mandate.
- **OPEN:** unresolved technical/scientific decision.
- **FUTURE:** separate development or experiment requiring authorization.

## A. Recommendations accepted

### A.1. Internal and external parallelism

**DEC:** `Threads=0` and `ConcurrentMIP=1` for the principal CFL-GNN design; two externally concurrent jobs are a candidate, not a measured capacity. **DOC:** conventional parallel MIP and independent concurrent MIP searches are distinct. **OBS:** historical H25 logs identify 40 physical cores and 80 logical CPUs and Gurobi 13.0.1. This is not a live site inventory.

**OBS:** the H25 pilot log showed concurrent LP activity at the root under conventional MIP. `ConcurrentMIP=1` does not imply that every root-LP algorithm is single-threaded or nonconcurrent.

The qualification specification must bind physical-core identities and SMT siblings, cpuset/affinity, NUMA policy, per-job memory, environment `ThreadLimit`, solver ceiling, process native-thread count and sampled CPU utilization. These observations have different meanings. Two jobs can contend for caches and memory bandwidth despite disjoint CPU affinity. No performance improvement is presumed.

### A.2. MIP `Start` semantics

**DEC:** retain B/R/G only. G and R submit partial values via `Start`; no domain fixing or new hint arm. **CODE:** `paired_partial_start.py` and `pr94_evaluation_solver.py` check fresh models, assignment support, original bounds and mathematical signatures; undefined entries remain undefined. R is cardinality/positive-count matched to G, not independent of its preparation.

`Start` submitted, processing observed, completed/repaired, accepted incumbent and subsequent primal/dual trajectory are separate events. A message indicating that a `Start` did not produce a new incumbent does not alone establish infeasibility. The new evidence contract must permit “unobserved” and record the scope of each message.

Table 1 lists the version 13 controls in the parameter inventory. Defaults are reference values, not a decision to tune them.

**Table 1. Gurobi control inventory.**

| Official control | Reference default | Mechanism and scope |
| --- | --- | --- |
| `Start` (attribute) | Undefined for an unassigned entry | MIP initial values |
| `StartNodeLimit` | -1 | Partial-`Start` node budget; inherits `SubMIPNodes` |
| `SubMIPNodes` | 500 | Sub-MIP heuristics/node allowance |
| `StartTimeLimit` | Infinity | Partial-`Start` time budget |
| `StartWorkLimit` | Infinity | Partial-`Start` work budget |
| `MIPFocus` | 0 | Search emphasis |
| `Heuristics` | 0.05 | Heuristic effort |
| `ImproveStartGap` | 0 | Gap-triggered improvement strategy |
| `ImproveStartNodes`, `ImproveStartTime`, `ImproveStartWork` | Infinity | Improvement-strategy triggers |
| `VarHintVal` / `VarHintPri` | Unspecified value / priority 0 | Search hints, not Starts |
| `LPWarmStart` | -1 | Continuous-LP warm starts |

**DOC:** `StartTimeLimit`/`StartWorkLimit` are version 13 additions, present in the version family observed. A time-based `Start` limit can add timing variability. **OPEN:** exact installed patch, effective parameter/attribute values and any API/environment limits are to be captured before future execution. Do not treat `heuristicEmphasis` or `warmstart` as official Gurobi parameter names or assume a one-to-one translation from another interface.

### A.3. Variability and computational work

**DEC:** `Seed` 42 remains principal; no automatic multi-seed requirement. **DOC:** `Runtime` is elapsed solver time; `Work` is a separate hardware/configuration-conditioned measure with arbitrary units. Do not convert work to seconds, replace `TimeLimit` with `WorkLimit` or equate deterministic work with identical outcomes under wall-time cutoffs.

**CODE:** the existing callback adapter records runtime, incumbent, dual, gap and nodes. **OPEN:** native `Work` at each observation, full phase provenance and a documented OS sampling contract are incomplete relative to the new specification. Existing historical data must not be retroactively populated with invented fields.

### A.4. Infeasibility certificates for Benders

**DEC:** initial Benders is external/iterative. **DOC:** `FarkasDual`/`FarkasProof` require the relevant LP infeasibility information; `InfUnbdInfo=1` is part of the certification specification. Resolve `INF_OR_UNBD` separately, with `DualReductions=0` when necessary or under an approved certification policy. IIS is diagnostic, not the dual certificate defining a cut.

Before any implementation, document primal/dual equations, row senses, objective sense, variable bounds, master-dependent right-hand sides/coefficient terms and sign conventions. Validate the resulting inequality and residuals against the actual formulation. No certificate of an LP relaxation is an automatic exact value for integer recourse.

## B. Recommendations accepted with qualifications

### B.1. Safe callbacks and isolated environments

**DOC:** the user callback is serialized during conventional parallel optimization. This does not make arbitrary nested optimization safe, remove callback overhead or make a shared Gurobi environment safe for external worker threads. **DEC:** no Benders callback implementation in this phase.

Specify isolated models/environments for external workers, cleanup/lifetime rules, license limits, interruption handling and durable evidence on exceptions. Keep solver API queries on the supported callback/optimization thread. OS telemetry can sample externally without invoking Gurobi. The initial Benders coordinator remains external to the master optimization; branch-and-Benders-cut is later work.

### B.2. Lazy constraints and strengthening cuts

**DOC:** `cbLazy` and `cbCut` have different correctness roles. A callback Benders design would require `LazyConstraints=1` for necessary omitted constraints and sufficient `MIPSOL` checking to reject invalid integer candidates; `MIPNODE`-only checking is insufficient. User cuts must be globally valid for integer-feasible solutions of the full model, and `PreCrush` is considered only for that appropriately justified path.

**OPEN:** exact separation proof and event policy depend on the chosen decomposition. No blanket conversion of all Benders cuts to user cuts is accepted.

### B.3. Persistent LP reoptimization

**DEC:** consider persistent subproblem models and native simplex basis reuse before manual `VBasis`/`CBasis` management. Changes in RHS, bounds, coefficients and structure are distinct. **DOC:** `LPWarmStart` concerns continuous optimization, not the neural MIP `Start` treatment. **OPEN:** availability/use of a basis and actual reoptimization savings must later be observed, not presumed. No benefit or memory reduction is claimed in this specification.

### B.4. Observability of phases and resources

Record source and resolution: direct native attribute, callback observation, parsed log, OS/cgroup sample or unavailable. A callback's occurrence is not a complete timestamped boundary for every solver-internal activity. Barrier, crossover, root processing, cut passes and heuristics can overlap in what the logs expose. Do not force them into additive phase durations.

A process thread count is not the count of continuously active solver threads. A sampled cgroup peak, process RSS sum, native environment memory and Slurm MaxRSS are not interchangeable. Specify bytes/GiB and scope explicitly.

## C. Recommendations not incorporated now

No `ConcurrentMIP>=2` factorial, new solver/interface, hint policy, extra seeds, tuning campaign, architecture search or PaScal work. No shared-core implementation, automatic extraction/refactoring, manual basis manager or Benders callback code. No scientific execution or benchmark from this document. A correctness proof or a qualified resource envelope cannot be replaced by CI success.

## D. Existing contracts and component correspondence

CFL-GNN inspected at `3700d90`; hard preparation at `0bb77ee8`. Agrologistic develop inspected at `245bb3894a3bb0adc34275e8f3eaff6fe3378455`. Later integration commits preserve these sources as historical authorities.

Table 2 maps candidate responsibilities to the inspected implementation sources.

**Table 2. Existing component correspondence.**

| Candidate responsibility | CFL-GNN inspected source | Agrologistic inspected source | Assessment |
| --- | --- | --- | --- |
| Configuration/session | `solvers/neural_guidance.py`; evidence executors | `src/logic/model_config.py`; `optimization_gurobipy.py` | CODE: existing native lifecycle/parameter application; common contract still to specify |
| Model identity | `paired_partial_start.mathematical_signature`; model hashes | `model_validation.py` and input contracts | CODE: reusable concept; signatures and domain adapters differ |
| Root capture | `gurobi_graph_artifact.py`; `pr94_preparation_science.py` | Native extensive-form optimization | CODE: CFL capture exists; no equivalent reusable root contract established in this review |
| Incumbent/gap events | `gurobi_callback_adapter.py`; `pr94_evaluation_solver.py` | `resource_telemetry.gurobi_message`; optimizer callbacks | CODE: partial coverage; `Work` and event eligibility need harmonization |
| Resource telemetry | pr86 allocation/supervision and cost records | `src/logic/resource_telemetry.py` | CODE: OS/cgroup infrastructure exists; no claim of literal interchangeability |
| Independent solution audit | `solvers/gurobi_solution.py` | `src/logic/solution_validation.py` | CODE: audit contracts can align; mathematical checks remain domain-specific |
| Benders | No qualified implementation found in inspected components | `manuscript/benders_extension_audit.md` | OPEN: mathematical design, not implemented evidence |

The Agrologistic configuration includes Python syntax requiring a newer interpreter than CFL's historical Python 3.10 environment. A common-core proposal therefore needs an explicit compatibility target; copying a whole domain module is not a valid shortcut. Do not upgrade either environment merely to force sharing.

Candidate module names are gurobi_config, gurobi_session, model_identity, relaxation_capture, incumbent_recorder, gap_recorder, resource_telemetry, solution_validator, evidence_schema, benders_coordinator and benders_cuts. They are proposed responsibilities, not files to create now. Mathematical opening/allocation logic and agricultural multi-period/scenario logic stay in separate adapters.

## E. Required scientific and architectural contracts

### E.1. Versioned result and event contracts

Specify input mathematical/byte identity, effective objective sense, fresh-model state, parameter map, environment, resource allocation and source commit. Results carry incumbent availability, recalculated objective and audit scope, dual bound, gap convention, nodes, `Runtime`/`Work`, status and terminal cause.

An event carries where/what semantics, timestamp origin, observation time/work, candidate/best-incumbent distinction, numeric eligibility and native/log/sample provenance. Each target has attained/censored/unavailable/ineligible status. Bound and gap qualifiers must survive table generation.

Keep a canonical row per instance and normalized per-execution/per-event records; this avoids embedding repeated event histories in a single table cell. Schemas should bind immutable artifact hashes, not rely on filenames alone.

### E.2. Generic/domain boundary and versioning

A common core can handle immutable records, clocks, units, config validation, environment lifecycle and I/O/provenance. It cannot interpret agricultural flows or CFL binary assignments without an adapter. Public interfaces can be shared without operational dependencies between repositories.

Only literally generic, compatible modules may later use identical relative paths, contents, tests and SHA256. A manifest should state common-module version, copied-from commit, file hashes, interpreter range and adapter versions. Divergence must be explicit. This phase creates no cross-repository package dependency and changes no Agrologistic implementation.

### E.3. Benders exactness and bound accounting

Partition the actual original variables into master variables $y$ and recourse variables $x$ only after confirming their domains. For continuous recourse with a fixed matrix, consider the canonical value function

$$
Q(y)=\min_{x\geq0}\{q^\top x:Wx\geq h-Ty\}.
$$

A dual-feasible multiplier satisfies

$$
\pi\geq0,\qquad W^\top\pi\leq q.
$$

For the master variable $\theta$ representing recourse cost, the corresponding optimality cut is

$$
\theta\geq\pi^\top(h-Ty).
$$

Feasibility rays and finite variable bounds require the corresponding full derivation, not mechanical use of this simplified notation.

For integer recourse, these LP cuts can bound a relaxation but do not by themselves describe the integer value function. Consider an appropriate exact integer/logic-based decomposition only after formulation analysis. If all relevant integer variables remain in the master, its size can still dominate memory.

Use a certified solver best bound from a time-limited master for the global lower bound, not its incumbent objective. A global upper bound needs a feasible original-model completion and original-objective recomputation. Stop only under the approved valid global-gap criterion; retain cut counts, certificate residuals and subproblem dispositions.

The initial external design is: solve master; evaluate recourse; validate dual certificate or feasible completion; construct/prove a cut; update valid bounds; repeat. Reuse persistent LP models where mathematically justified. Establish equivalence on analytically checkable cases before any large-instance authorization. Those checks are future implementation requirements, not tests executed here.

#### E.3.1. Conditional validity of the canonical cuts

For the continuous fixed-recourse form above, take any dual-feasible $\pi$. For any feasible $x$ at any master point $y$, weak duality gives

$$
q^\top x\geq\pi^\top Wx\geq\pi^\top(h-Ty).
$$

Thus $\theta\geq\pi^\top(h-Ty)$ is a lower supporting inequality for $Q(y)$. An optimal dual solution makes it tight at the current point when LP strong duality applies. This proves the canonical cut only under the stated continuous, fixed-matrix assumptions.

For an infeasibility ray $r\geq0$ with $W^\top r\leq0$, feasibility of $x\geq0$ and $Wx\geq h-Ty$ would imply

$$
r^\top(h-Ty)\leq r^\top Wx\leq0.
$$

Therefore

$$
r^\top(h-Ty)\leq0
$$

is a necessary feasibility cut. A certified strictly positive value at the current $y$ separates that point. Finite lower/upper bounds must be included in the actual canonical transformation and its certificate. A general Gurobi `FarkasDual` vector has its own row-sense convention; it must be transformed and validated before being substituted for this $r$.

If the recourse matrix depends on $y$, the displayed dual-feasible set need not be common to all $y$; the simple fixed-recourse argument cannot be imported unchanged. If recourse is integer, LP cuts remain relaxation bounds and are not an exact integer value-function representation. No claimed exact CFL decomposition is established until the actual domain/matrix mapping and global-bound proof are completed.

### E.4. Domain-specific Benders risks

CFL: verify all binary opening/allocation variables, master size and whether any alleged continuous resource actually retains integer variables. Do not relax them to obtain a convenient LP.

Agrologistic: preserve current scenario weights, investments, nonanticipativity, time/capacity structure, emergency slacks and flow equalities. The existing Benders audit already documents differences from supplied working formulations. Do not import those formulations as an approved replacement. No extra solver comparison is introduced.

Memory, faster bounds and improved incumbents are hypotheses. Persistent subproblems, saved bases, cut pools and worker environments can increase memory. Benders gets a separate resource plan.

## F. Pending scientific authorization and acceptance

The coauthor decision register covers label quality, split, deployment, `Start` policy, reuse of characterization B and site resource envelope. Benders partition/certificate policy and any later callback/parallel-subproblem stage also need explicit approval. Additional seed robustness and parameter sensitivity remain future proposals.

Acceptance of this note means the specification is coherent and traceable; it does not mean that 20 cores per job and two simultaneous jobs, exact decomposition or low-overhead instrumentation are empirically qualified. Before execution, future implementation PRs require proportionate tests and exact-source/site gates. The author operates all HPC CLI/SCP. No experiment, inference, training, scheduler query or queue mutation was performed for this note.

## Primary sources

- [Gurobi 13 parameters](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/parameters.html).
- [Model attributes](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/attributes/model.html).
- [Variable `Start`/hint attributes](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/attributes/variable.html).
- [Callback codes](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/numericcodes/callbacks.html).
- [Serialized callbacks](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/c/logging.html).
- [Python `cbLazy`/`cbCut`](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/python/model.html).
- [Farkas attributes](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/attributes/constraintlinear.html).
- [Existing Agrologistic Benders audit](https://github.com/unb-lamfo-or-ai-hpc/model-agrologistic/blob/245bb3894a3bb0adc34275e8f3eaff6fe3378455/manuscript/benders_extension_audit.md).
