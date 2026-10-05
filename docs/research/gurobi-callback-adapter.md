# Sprint B: Gurobi callback binding and no-optimization installed preflight

## Capability and authority

This increment follows the author's approved PR69 merge into develop at
`4b8d9b65b18bc5f130a687cdfdc09608657ec772`. It supplies the actual Python callback
binding for the bounded telemetry contract and an installed-runtime preflight.
It is not the fresh-process licensed worker, a scheduler launcher, an approved
experiment or a new solve result. Its CLI has only a `preflight` action and calls
neither `optimize()` nor a scheduler. The immutable PR69 proposal, original
collectors/tolerances and job3468 evidence remain unchanged; medium16 is still
unqualified. Merge authorization never substitutes for resource-budget approval.

## Callback observation policy

The future worker passes `GurobiCallbackAdapter` to its one fresh model's
optimization call. The adapter observes only MIP and MIPSOL callbacks. Other
phases, including POLLING, are ignored without queries. MIP regular observations
are separated by at least one solver-runtime second; every MIPSOL event is
observed, including repeated events at the same timestamp. The adapter queries
only Runtime, best-known objective/bound and node count, with the callback-specific
codes. It neither requests candidate vectors/node relaxations nor changes
algorithm parameters, adds cuts, injects starts or terminates for a gap target.

MIPSOL_OBJ describes a presented solution and is not necessarily an improvement.
MIPSOL_SOLCNT counts callback presentations and may temporarily lag; it is not
proof that an incumbent has been accepted. Therefore neither quantity is used
to manufacture an incumbent. MIPSOL_OBJBST is the solver's current best-known
objective. If that value is unavailable during a first presentation, the target
remains unobserved until a later qualified callback or terminal attribute.

Infinity and Gurobi's numeric bound sentinel become null. NaN, booleans,
nonnumeric values or backwards runtime observations fail. For finite nonzero
incumbents, callback gap is `abs(primal-dual)/abs(primal)`, without a floor or
assuming monotonicity for mixed-sign objectives. All zero-incumbent-objective
gaps remain conservatively unqualified: parameter and attribute documentation
use different zero-objective wording. Do not invent a zero gap or first crossing
from this unresolved edge case. The original CFL objective convention remains
in-memory MINIMIZE, with stored MAXIMIZE sources unchanged.

Terminal Runtime, status, solution count, ObjVal, ObjBound and MIPGap are read
outside optimization. Final finite MIPGap is checked against its model-bound
formula, not against a raw callback bound. Its original normalized attribute is
also retained separately, including the zero-objective qualification boundary.
Preserve overshoot, late target flags, right-censored timeouts and distinct
resource/planned-gap/other stops. A failed callback requests `model.terminate()`;
failure of that request is recorded. No exception text is exported. The future
supervisor must pause the remaining matrix and enforce the independent watchdog
even if termination cannot be requested; there is no such supervisor here yet.

Callback wall/current-process CPU costs are accumulated separately and never
subtracted from solver runtime. Storage is bounded by the PR69 library; first
sampled target tracking continues after storage fills. This does not bound the
number of callbacks or establish negligible overhead. Installed execution and
overhead qualification still require a separately approved licensed test.
No continuous first-crossing time, primal integral, vector feasibility,
root/tree cost, scheduler accounting or population-level scaling is certified.

## No-optimization preflight

On canonical dgx-dasci, in tfm_env, pinned clean source must reside below physical
`/raid/vrcelestino/data`; all fresh outputs stay below physical cfl-mvp2-evidence.
Only the canonical license already specified in the PR66 runbook is allowed.
The preflight reuses the checked version/license guard, reads the original
easy17/medium1 once each and checks all ten proposed parameter configurations.
It checks Gurobi13.0.1, callback symbol availability/uniqueness, model callback
methods, original source hashes, single-objective linear-MIP structure and the
established objective-sense override. Each environment/model is closed; source
hashes are checked afterwards. Defaults, including unbounded NodeLimit, remain
strict-JSON serializable. No callback is installed or called on a live solve.

The output is a hash-bound allowlisted `preflight_receipt.json` plus SHA256SUMS.
It includes source/dependency/proposal identity and zero optimization/training,
but not paths, license identifiers, raw LPs or private text. Runtime errors are
recorded as a fixed failure code without exception details. Keep whole-process
console output private because the solver may otherwise print license details.
The CLI safety gate fails closed for the wrong host/source/output or dirty
tracked source. It never resumes an existing directory; repeated execution is
not an implicit remedy. Retain failed qualification evidence.

Passing means only that installed API/model-reading/parameter checks passed.
It **does not** qualify callback execution, cost overhead, hour-long memory,
Slurm walltime, physical-core affinity or scientific eligibility. These fields
remain explicitly false. It also does not make the PR69 proposal executable.

## Operator hand-off and next work

After exact-head four-arm CI and raw/Git blob review, the task supplies a pinned
one-shot helper to create a fresh source worktree/output on RAID, run only this
preflight and display the sanitized receipt with its hash. No sbatch, optimizer,
training, deletion, environment installation or accounting wait loop occurs.
Return the receipt/hash, not the private console log or license contents.
On failure, retain the output, stop and return the sanitized failure marker;
do not retry, loosen limits or send private logs without a scoped diagnostic.

The source CLI is deliberately not a submission workflow:

```bash
python -B scripts/evidence/gurobi_callback_adapter.py preflight \
  --source-sha EXACT_REVIEWED_COMMIT \
  --output FRESH_PHYSICAL_RAID_DIRECTORY
```

The helper handles exact source/hash/CI guards and console privacy before this
command; placeholders above must not be executed literally. No optimization
budget is requested by the installed no-optimization preflight.

Next implement the fresh-process worker, close/seal/private-log binding, full
result/export validator, atomic persistent submission locks and sequential
nonblocking submit/status/collect/receive workflow. Do not submit until the
installed preflight has been independently reviewed, callback fault/overhead
qualification and higher-budget resource safety are accepted, and the author
explicitly approves the exact versioned solve budget. Licensed qualification
solves themselves need a declared budget; their costs cannot be hidden as
"preflight". After approved comparison, independently review accounting/target
coverage before separately budgeting replication and resource-curve synthesis.

Primary references: [Gurobi callback codes](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html),
[MIPGap parameter](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html#mipgap),
and [model attributes](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/model.html).
They support observation semantics, not proof of installed callback execution
or an explanation of historical job3468's footer/API timing mismatch.
