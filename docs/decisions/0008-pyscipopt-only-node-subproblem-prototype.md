# ADR 0008: PySCIPOpt-only node-subproblem prototype

- Status: proposed
- Date: 2026-09-01

## Context

The Gurobi feasibility audit observed node relaxations but confirmed that the
documented callback API does not expose the local bounds, branch path, node
identity, parent relationship, or exact node model needed to serialize a
branch-and-bound subproblem. The validated DaSCI run therefore rejected Gurobi
node relaxations and incumbents as new MILP instances.

PySCIPOpt exposes a richer solver-native tree surface. Its documented node API
includes node number, parent, depth, node domain changes, parent branchings,
and constraints added at the node. Variables expose local and global bounds.
The model API also provides `writeMIP()`, documented as writing the MIP
relaxation of the current branch-and-bound node, and `writeProblem(trans=True)`
for the transformed problem valid at the current node.

These capabilities make an empirical prototype justified, but do not by
themselves prove that a written file is an exact, independently solvable node
subproblem.

## Decision

Use PySCIPOpt directly for the SCIP experiment. Pyomo is not a dependency,
modeling layer, migration target, or fallback.

The first SCIP change will be an isolated, bounded research prototype. It will
not alter Gurobi collection, parent-instance training, incumbent-conditioned
training, graph schemas, or evaluation.

The prototype will:

1. read one original CFL LP/MPS instance and apply the established `MINIMIZE`
   correction;
2. register a passive PySCIPOpt event handler for focused nodes;
3. record a bounded sample of node number, parent number, depth, type, lower
   bound, domain-change counts, parent branchings, added constraints, and local
   variable bounds;
4. construct a deterministic semantic fingerprint from the source-instance
   SHA-256, ancestry, local bound vector, and local-constraint metadata;
5. compare `writeMIP()` with `writeProblem(trans=True)` as candidate
   serializations, without assuming either is exact;
6. read each candidate into a fresh SCIP model and audit objective sense,
   variable types, bounds, constraints, rows, columns, nonzeros, and file hash;
7. keep every output separate from production dataset roots.

`writeLP()` is not evidence of a new MILP because it writes the current LP.
Neither an LP relaxation nor a solution vector may be promoted to a MILP.

## Instance identity

Two complementary signatures are required:

- **structural signature**: rows, columns, nonzeros, variable-type counts, and
  constraint-handler counts;
- **semantic node signature**: source hash, node ancestry, parent branchings,
  local-domain hash, local-constraint hash, objective sense, and serialized
  artifact hash.

A child created only by variable bounds can be a semantically distinct node
subproblem while retaining the parent's row, column, and nonzero counts.
Therefore count changes are reported, but are not required for identity.

## Eligibility gate

A candidate becomes eligible for later dataset design only if all conditions
hold:

- it comes from a non-root node with an unambiguous parent chain;
- at least one local domain restriction or local constraint distinguishes it
  from the parent;
- the serialized artifact can be read by a fresh SCIP process;
- the round trip preserves integrality, objective sense, local bounds, and
  relevant local constraints within explicit tolerances;
- repeated exports of the same sampled node have identical semantic hashes;
- different semantic hashes are not duplicate serialized models;
- the report contains no absolute paths, credentials, or solver-private data.

Failure of any condition is recorded as evidence and fails closed. It does not
trigger graph generation or training.

## Consequences

- PySCIPOpt remains an optional, isolated research dependency until the DaSCI
  capability gate passes.
- The controlled toy MILP is tested before any CFL instance.
- Presolve-on and presolve-off runs are separate experimental conditions,
  because transformed rows, columns, and nonzeros need not match the original
  formulation.
- Node numbers are treated as run-local identifiers. Stable identity comes
  from the semantic fingerprint, not from the number alone.
- The production SCIP-only and SCIP-incumbent variants remain future work.
  This ADR does not authorize their implementation.

## Official references

- [PySCIPOpt event handlers](https://pyscipopt.readthedocs.io/en/latest/tutorials/eventhandler.html)
- [PySCIPOpt Node API](https://pyscipopt.readthedocs.io/en/latest/api/node.html)
- [PySCIPOpt Variable API](https://pyscipopt.readthedocs.io/en/latest/api/variable.html)
- [PySCIPOpt Model API](https://pyscipopt.readthedocs.io/en/latest/api/model.html)
- [SCIP transformed-problem writer](https://www.scipopt.org/scip/doc/html/group__GlobalProblemMethods.php)
- [PySCIPOpt installation guide](https://pyscipopt.readthedocs.io/en/stable/install.html)
