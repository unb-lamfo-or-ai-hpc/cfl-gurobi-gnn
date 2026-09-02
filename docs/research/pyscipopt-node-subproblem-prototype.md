# PySCIPOpt node-subproblem prototype protocol

## Research question

Can PySCIPOpt expose and serialize enough node-local state to reconstruct an
independently readable MILP that represents a specific pruned or active
branch-and-bound region?

The null result is acceptable: inability to prove exactness ends the
node-derived-instance strategy without contaminating existing datasets.

## Scope of the implementation PR after this design

The implementation must add only an optional CLI, a solver-isolated analysis
module, dependency-free tests with fakes, a toy MILP, and one CPU-only Slurm
launcher. It must not modify Gurobi collectors, PyG builders, trainers,
evaluators, canonical folds, or artifact directories.

Pyomo is prohibited. The only SCIP Python interface is PySCIPOpt.

## Experimental phases

### Phase A: environment contract

Record Python, SCIP, and PySCIPOpt versions and bind the run to the SHA-256 of
the input model. Confirm that the selected PySCIPOpt/SCIP versions are mutually
compatible. Do not add PySCIPOpt to the package's mandatory dependencies.

### Phase B: controlled toy tree

Use a small MILP with known binary branch alternatives. With one thread and a
fixed randomization configuration, capture at least the root and two non-root
focused nodes. Validate node number, parent, depth, parent branchings, domain
changes, local bounds, and added constraints against the known construction.

### Phase C: candidate serialization

Identify bounded non-root samples at `NODEFOCUSED`, but recapture their state
and defer serialization until the node LP has completed at `LPSOLVED`. Attempt
both:

- `Model.writeMIP()`, documented as writing the MIP relaxation of the current
  branch-and-bound node;
- `Model.writeProblem(trans=True)`, retained only as a transformed-problem
  control; its readability is not evidence that node-local branch bounds were
  materialized.

The event handler must remain observational. Serialization errors, invalid
solver stages, unsupported formats, or missing local state are reportable
results rather than reasons to mutate the solve.

### Phase D: independent round trip

Open each candidate in a fresh PySCIPOpt model. Compare:

- minimization objective and objective coefficients;
- variable names/types and original, global, and local bounds;
- every normalized lower/upper branching bound along the complete ancestral
  path, including branchings that no longer differ from a reported global
  bound;
- active and node-added constraints;
- rows, columns, nonzeros, and handler-specific constraint counts;
- source, semantic-node, and artifact SHA-256 values.

Solve the reloaded candidate only after structural validation. Feasibility or
an objective value alone does not prove that it represents the sampled node.
Only a `writeMIP()` artifact can pass the node-candidate mechanical gate;
transformed-problem artifacts remain controls.

### Phase E: one CFL smoke

Only after the toy gate passes, run one easy CFL parent with explicit time,
node, depth, and sample limits. Preserve the original MILPBench file as the
source of structure and force `MINIMIZE`. Compare presolve disabled and default
presolve in separate reports.

### Phase F: root-relative identity audit

Serialize `root_mip_baseline.lp` with `writeMIP()` after the root LP is solved.
Compare every node MIP with that baseline using separate canonical hashes for
matrix, objective, domains, and the complete formulation. Report dimensional
deltas independently: equal rows, columns, nonzeros, or file size do not imply
equal formulations when branching changes variable domains.

Classify each mechanically valid node MIP according to ADR 0009 and report
unique semantic nodes, artifacts, formulations, duplicates, and storage. The
transformed-problem writer remains a control and may be disabled with
`--skip_transformed_controls` (or `WRITE_TRANSFORMED_CONTROLS=0` in Slurm) after
its behavior has been replicated.

## Planned artifacts

All reports are path-sanitized and written under a research-only output root:

- `pyscipopt_node_probe_plan.json`;
- `pyscipopt_node_capability_report.json`;
- `candidates/root_mip_baseline.lp` as the comparison baseline;
- `node_manifest.jsonl` with bounded node metadata;
- candidate `.cip` or `.mps` files only when the writer succeeds;
- `roundtrip_audit.jsonl` for candidate-versus-source comparisons.

The manifest must label every candidate as `experimental_ineligible` until all
eligibility gates in ADR 0008 pass.

## Stop conditions

Stop without dataset integration when any of the following holds:

- local bounds or ancestry cannot be captured consistently;
- written candidates omit local branching restrictions;
- round-trip models lose integrality or local constraints;
- serialization changes across repeated captures of the same semantic node;
- node identity depends only on a run-local numeric id;
- memory, storage, or callback overhead is unbounded;
- the full report cannot be sanitized.

## Review checklist

- [ ] PySCIPOpt and SCIP version pair selected for DaSCI;
- [ ] toy MILP and expected branch semantics reviewed;
- [ ] callback/event stage supports passive node capture;
- [ ] serialization is attempted after LP completion, separately from focus;
- [ ] `writeMIP()` behavior tested independently;
- [ ] transformed-problem writer behavior tested independently;
- [ ] all ancestral branching bounds are verified after a fresh-process read;
- [ ] semantic and structural signatures compared separately;
- [ ] every node MIP is compared with the mechanically valid root MIP baseline;
- [ ] matrix, objective, domain, and formulation fingerprints are reported;
- [ ] dimensional deltas and storage projections are reported separately;
- [ ] fresh-model round trip passes or fails with an explicit reason;
- [ ] no Gurobi, graph, training, or evaluation artifact is modified;
- [ ] no Pyomo import, dependency, documentation path, or fallback exists.
