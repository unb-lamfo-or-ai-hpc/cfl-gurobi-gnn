# S1-B native instrumentation and evidence capture

Status: implementation under review; **five tiny local Gurobi14.0.0 technical
cells qualified**, including independent point replay and actual log checks.
See the [qualification register](s1b-qualification-attempts-20261126.json).
The three earlier separately authorised admission failures remain preserved;
they made zero optimization calls. Production resources, the research parent
population, a learned predictor and the scientific Start policy remain pending.
This document and the code confer no scientific or HPC execution authority.

S1-A [PR104](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/104)
was integrated into `develop` at `edad5cc57f287d178706c2b91de8ba27e7878baa`
with explicit author approval and nine passing CI jobs. The merge tree equals
the approved head. See [receipt](s1a-integration-20261126.json). The sealed
`configs/mvp3/v1` bundle, approved protocol artifacts, historical worker/model/
trainer/solver sources and historical evidence remain unchanged. Main and the
installed HPC source are not updated by this implementation.

## Components and boundaries

| Component | Responsibility |
| --- | --- |
| `matrix` | Original MILP geometry, one row at a time; streaming S1-A signatures |
| `audit` | Full original-row, bound, integer-domain and objective checks |
| `journal` | Exclusive attempt directory, chained events, content-addressed vectors, fsync, one-call intent |
| `observer` | Context-valid Gurobi14 callbacks, root provenance, candidate and progress capture |
| `native` | Explicit injected API, fresh environment/model, default/effective parameter inventory, partial Starts, one optimize call |
| `resources` / `supervisor` | Owned process identities, sampled RSS, affinity/core mapping, exact job cgroup counters, bounded local child |
| `collection` | Read-only complete/partial return reconciliation and optional candidate audit replay |
| `logparse` | Pinned secondary log interpretation with explicit unsupported/missing fields |
| `qualification` | Prospective author CLI for five bounded tiny technical cells |

Imports do not initialise Gurobi or Torch, load a checkpoint, optimise, contact
HPC, submit/cancel jobs or retry. Gurobi is imported only in the explicit CLI
qualification worker. The low-level native session takes an injected API; its
permit records an external author approval reference, not a machine-generated
human signature. A future primary release must additionally admit the sealed
population/input/call plan, exact source, environment, hardware and measurement
envelope. This PR supplies no primary dispatcher or scientific release.

## Original model and numerical audit

The effective model is always MINIMIZE. Its original declared sense remains in
the identity. Original variable/row order, domains, bounds, sparse coefficients,
objective and constant are hashed compatibly with S1-A, without retaining the
full coefficient matrix twice. Unsupported quadratic/general/SOS representations
fail admission. Mathematical identity is reread from the native model after Start
installation and after return, including current variable metadata.

The separate [instrumentation policy](../../../configs/mvp3/instrumentation/v1.json)
uses absolute row/bound/objective tolerances `1e-6` and integrality tolerance
`1e-5`. This is an explicit floating-point numerical policy, not an exact
rational certificate. Activity/objective sums use `math.fsum`. All original
rows and variable bounds are checked, including implicit binary bounds.

Raw integer coordinates are snapped only within the integrality tolerance;
raw and canonical point hashes, changed-position digest and maximum raw integer
distance are retained. The entire canonical point is then audited again. A
rounding-induced row violation disqualifies it. Continuous coordinates are not
repaired or completed. Overflow/nonfinite evidence cannot qualify a point.

A root relaxation point is checked for continuous feasibility. Its objective
need not equal the native root bound (for example, integer-bound rounding can
separate them). A missing root candidate-objective residual therefore has an
explicit reason. Incumbent audits still require the actual candidate objective.
S1-A's continuous-audit validator now accepts that missing residual; its sealed
JSON schema did not change. An observed residual still must pass its tolerance.

## Native capture and default parameters

Each session starts a fresh environment and model, requires Gurobi14.0.0, no
prior solution/Start, and the approved stage profile. Complete documented
noncredential model parameter defaults and effective values are recorded; auth/
transport parameter names are excluded **before querying their values**. The
full retained effective map must equal defaults plus the declared profile.
Native parameter infinities use explicit `+Infinity`/`-Infinity` strings together
with retained API types and a versioned encoding label. Finite sentinels such as
`1e100` retain their observed values. NaN is rejected. These are valid parameter
settings, not missing measurements; the finite/missing measurement policy is
unchanged. S1-A already permits string parameter values, so its sealed schema
does not change. Parameter query/encoding failures expose only a noncredential
parameter name, operation and exception class/code, never a value or message.
`LogFile`/`LogToConsole` are not overridden: native stdout belongs to the owning
supervisor. Neither license files nor credential/environment-variable values
are read by the instrumentation.

POLLING performs no `cbGet`. Context-specific presolve, MIP, MIPSOL, MIPNODE and
continuous progress fields keep native Runtime, Work and native memory in GB.
MIPSOL candidate objective is distinct from OBJBST and does not assume an
improvement or a positive initial solution counter. Original-variable vectors
are retained before callback return. Root ordinals count nonoptimal root events
too; node-relaxation values are read only at an optimal root event. The actual
pre-cut/later-pass provenance is retained. Only the root-feature stage terminates
after successful capture; the incumbent/evaluation stage continues.

Callback errors and mandatory capture exhaustion are explicit and terminate
the owned model. Finite event/vector/storage limits and dropped counts remain
visible. A final raw/canonical point reserve is admitted before optimize; it is
not taken from earlier retained points. A dropped candidate does not acquire
a fabricated vector, audit or target time. Captured root events are not labelled
successful scientific records solely because optimize returned INTERRUPTED.

B writes no external Start attributes. R/G assign only the selected original
binaries, leave other variables UNDEFINED, enforce the independent 10% support
cap and bind the released root/policy/predictor hashes. R has no predictor.
No graph, root-rounding policy, training or inference is implemented here; the
qualification uses explicitly invented technical Start fixtures.

## Durable attempts, supervision and partial collection

Existing attempt directories/receipts are never overwritten. Before the sole
native call an exclusive fsynced intent reserves one budget slot. The intent
alone is not proof that a call completed. A separate marker records native
return. Terminal sealing includes attempt/receipt hashes, chained-journal hash,
complete frame count, dropped counts and artifact bytes. Collection checks
those links and vector byte identities. A torn unsealed final frame preserves
the complete prefix; mutation of a sealed prefix or receipt fails validation.
New attempts/retries require their own decisions; there is no resume-and-solve.

Collection distinguishes no intent, intent without return and native return.
Scheduler accounting is separate unavailable evidence until actually supplied.
Infrastructure failure is never silently converted into optimization censoring.
Optional replay audits retained candidate points against supplied original
geometry. Full S1-A run/resource/clock/target validation remains required before
any collected record becomes a scientific observation; collector output is a
capture/reconciliation envelope, not a qualified dataset or S5 estimate.

The supervisor launches one explicit argument vector, without a shell or retry.
It records PID creation times and signals only owned process identities, checks
wall time, sampled owned-tree RSS, observed stdout size and (when qualified) job
memory. Guards are sampled observations, not hard OS reservations; between-
sample overshoot is possible. RSS sum can double-count shared pages and is not
an exact continuous peak. Native GB, process bytes and cgroup job bytes remain
distinct. Missing coverage is explicit. Exact job cgroup-v2 paths must contain
the matching job ID; counters are read at the job scope, never reset/written.
OOM counters are preserved separately and do not establish scientific censoring.
Logical affinity and physical package/core sibling mapping are recorded where
available. This local implementation does not qualify the production Intel
32-physical/64-logical, exclusive 192/384GiB profiles or the two-job/session cap.

## Released parser scope

`gurobi-logtools==4.0.1` is pinned, including the official wheel SHA256 in the
policy; `psutil==7.2.2` and `jsonschema==4.26.0` are pinned separately. Parser
transitive dependencies are resolved by installation; the local environment
receipt records the direct installed versions. No unreleased/master parser
features are assumed. The wrapper uses released `parse` plus pinned per-log
summaries/progress, avoiding `summary()`'s implicit parameter-default filling.
Numeric/status fields absent or unsupported by this release remain null with
reasons; unknown/truncated terminal text is not inferred OPTIMAL. NoRel time
starts at the heuristic entry and is never relabelled global optimize Runtime.
Rounded textual times cannot replace point-specific native callback clocks.
Merged parser summaries can carry a root-LP status or Runtime into an incomplete
MIP log. The adapter therefore takes MIP final values only from the tree/final
termination sections and retains continuous-phase summaries separately. A
continuous OPTIMAL status never becomes a MIP terminal status by inheritance.

Raw stdout is private, retained unchanged and hashed. A separate sanitized copy
removes credential/license/transport lines before parsing; structured output is
restricted to named fields. Raw logs, usernames, license values and native
error text are not committed to Git. The offline Gurobi14-shaped log tests are
invented fixtures, not execution evidence. The earlier Dell native license probe
did not save raw logs, so it cannot qualify this parser or callback API.

## Local CLI qualification (separate approval per invocation)

Entry: `scripts/mvp3/qualify_local.py`. The reviewed command must name the exact
40-character commit, a new private output directory outside the clean checkout,
the existing isolated Python environment and the concrete author approval
reference. It checks the clean exact source and direct dependency versions before
calls. Its worker accepts only the exact generated 20-binary, one-row LP bytes,
uses `QUAL_TINY20` identities and cannot run a primary campaign.

The maximum is five fresh sequential native calls: root, incumbent, B/R/G
wiring. Each uses one thread, Seed42, at most ten native seconds and thirty
worker wall seconds, observed memory guard 1GiB, observed stdout guard16MiB,
8MiB vector storage, sixteen candidate vectors and1,000 events. Final-point
storage is reserved. The synthetic LP's root can have objective10.5 versus
integer bound11, exercising the explicit objective/bound distinction. R/G
guidance/predictor names are invented fixtures; there is no learned model.

Each failure stops the sequence and preserves partial files; no automatic retry.
The resulting private report requires actual native14 API returns, audited tiny
points and actual native14 log headers. It does not qualify the research parent
population, production hardware, a trained predictor or a scientific Start policy.
Review the return before any production release. The qualified invocation is
recorded below. Every further invocation still needs its own concrete author
CLI decision. It is local.

### First attempt and reviewed correction

The author explicitly approved one invocation of source
`f6cf5fa8ef640ee55fa2828d0b362971986b0cc1`, conditional on all nine CI jobs.
Both exact-source CI runs succeeded before that invocation. The first worker
returned GurobiError before measurement admission/optimize intent, with zero
optimization calls. The sequence stopped and preserved every private artifact;
the remaining four cells were not started. The original worker recorded only
the exception class, so the precise native error code/admission phase is unknown.
This is an admission failure, not optimization censoring or a scientific result.

The received earlier Dell license qualification had routed the existing local
Gurobi14 license explicitly in the child. Default discovery in the first worker
did not reproduce that configuration. The corrected CLI requires `--license-file`
with that already qualified local path, checks existence without opening or
hashing its contents, and sets `GRB_LICENSE_FILE` only inside the worker before
the native import/environment start. It does not inspect the parent variable,
change profiles or modify a license file. This routing difference is a likely
cause; it is not retrospectively asserted as a verified native error code.

Failed workers now retain a sealed `worker-error.json` with the fixed phase,
exception class and numeric native error code when present, excluding exception
message text. Parent collection reconciles failed workers as well as successful
returns. Offline tests cover child routing without license-content reads,
safe diagnostics, environment-start failure before intent and single-attempt
parent behavior. The corrected source requires a new specific CLI decision,
its own passing CI and a new output directory. The failed attempt is never
overwritten or automatically retried. This correction does not authorise a call.

### Subsequent admission findings

Source d258258 passed all nine CI jobs. Its first specifically approved
invocation initialized the existing local licence but failed at native model
read (GurobiError0) from the non-ASCII workspace path. A separately approved
invocation of the **same source** in an ASCII temporary directory read the LP,
applied parameters and extracted the original geometry, then stopped in the
parameter inventory with ValueError. It also wrote no optimize intent. All14
files from that temporary attempt were copied into private workspace preservation
storage and their hashes matched; the original temporary folder remains intact.

The native parameter inventory's strict JSON handling could not represent IEEE
infinity; an API double reproduces ValueError with unbounded defaults. The
official parameter reference defines several defaults as Infinity. The current
correction records typed infinities explicitly, models them in the API double,
and adds per-parameter safe diagnostic context. The observed failure phase is
confirmed; the old attempt did not record the individual parameter/operation,
so infinity serialization remains a working diagnosis until native qualification.

Windows model paths are now admitted as ASCII before native initialization; a
non-ASCII path fails locally with an explicit staging instruction. Byte-preserving
staging retains the input SHA and mathematical identity. Each new qualification
invocation has its own UUID and distinct attempt keys; the two old d258258
bindings were identical across separate preserved directories because their
original technical attempt tokens were reused. The old files are not rewritten.
Original geometry identity is persisted before parameter inventory, improving
partial admission evidence. These are prospective technical corrections.

### Qualified local return and documentary closeout

The author specifically approved one invocation of source
`dab3b99ef8172d320223d05f74155eeeac063768` after its nine CI jobs passed
(runs 45862135727/45862136240). Its five sequential native calls completed:
one root capture and incumbent/B/R/G wiring. Offline independent replay checked
the original 20-binary/one-row geometry, retained vectors, audits, source/input/
parameter bindings, journal seals, actual 14.0.0 log headers and terminal values.
All five passed. The root event was ordinal 1/pre-cut/pass 0; its point objective
was 10.5 and its native bound 11. Four main calls ended OPTIMAL with objective and
bound 11. B/R/G synthetic Start sizes were 0/2/2; these are wiring fixtures.

The actual factory snapshot contained 18 infinite parameter defaults. Typed
serialization and the complete effective-map checks passed. All five used one
thread, Seed42 and the declared ten-second technical limit. Their original-model
hash and default-map hash agreed. There is no speedup or predictor-quality claim.
The 86 private return files were preserved in the workspace with every file hash
matching the original ASCII temporary directory. Earlier failed attempts remain
unchanged. The sanitized register includes the result and independent-review
hashes, code-tree IDs, call accounting and qualification limits.

This final closeout changes documentation/receipts only. The qualified source
remains pinned to dab3b99; package, entry, test and configuration tree IDs are
recorded so that equivalence of later documentary commits is reviewable. No
additional native execution accompanies the closeout. S2 requires a separately
reviewed production environment/resource envelope and author-controlled release
before any of the 177 planned primary calls. Hardware qualification and actual
scientific collection are not implied by the local return.

## Offline verification

The four Linux/Windows Python3.10/3.13 CI cells install only validation/parser/
supervision/lint dependencies, not Gurobi/Torch. Native behavior uses API doubles;
the only child-process test launches a tiny Python sleep/print fixture and checks
its owned wall guard. Tests cover audit rounding, streaming identity, credential
query tripwires, callback contexts/provenance, Start semantics, model drift,
one-call intent, caps, torn/sealed journals, PID reuse, cgroup scoping, parser
version drift/missingness and prospective qualification guards. Historical CI
continues separately. No offline pass is described as native or scientific
qualification.

Local verification on 26 November 2026: **110 offline tests passed** (55 S1-A
contracts and55 instrumentation/resource/parser/release-guard tests), Python3.13
in a separate tooling environment. Scoped Ruff checks and formatting pass. CI
results belong to the exact PR head and are recorded in its description; this
local statement does not claim a CI or actual native qualification result.

Official references: [Gurobi14 callbacks](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html),
[Python model API](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html),
[gurobi-logtools4.0.1 release](https://pypi.org/project/gurobi-logtools/4.0.1/),
[Linux cgroup-v2 memory](https://docs.kernel.org/admin-guide/cgroup-v2.html).
