# S1-A: versioned scientific contracts and frozen parent identities

26 November 2026. The researcher authorised autonomous S1-A implementation,
offline tests and a Draft PR targeting develop. This implementation translates
the approved English protocol v3 and final preparation into executable contracts.
It preserves the historical workers, architecture, checkpoints, partitions and
receipts. It adds no scientific observation and grants no execution authority.

## Files and responsibilities

| Artifact | Responsibility |
| --- | --- |
| `configs/mvp3/v1/contract.json` | Approved population, solver/resource profiles, learning work, guidance template, clocks, budgets and scientific boundaries |
| `input-catalogue.json` in the same directory | Sanitized identity of 66 NPAD stored gzip files, bound to the previously checked private receipt |
| `parent-manifest.json` | Frozen 42/9/9 easy/medium partition and six hard transfer parents |
| `primary-plan.json` | 66 root-relaxation, 66 incumbent and 45 fresh evaluation slots; every slot remains PLANNED |
| `evidence.schema.json` | JSON Schema 2020-12 for run, root, label, Start, event, target and unavailable-outcome records |
| `bundle-manifest.json` | Exact byte counts and SHA256 for the five bundle members |
| `src/cfl_gnn/mvp3/` | Offline generation, integrity checks, mathematical signatures, record linkage and individual paired-time eligibility |
| `tests/mvp3/` | Invented small-model evidence, failure cases and deterministic export/import checks |

`contract.py` independently checks the approved constants and exact sanitized
catalogue digest. Recomputing a file seal does not permit changing the scientific
contract, catalogue, split or evidence schema. The seal is an integrity register,
not a digital author signature. Digests bind bytes/objects; they do not attest to
the truth of a measurement or grant permission to execute it.

## Deterministic split

The input population is the 66 original IDs in the approved preparation register:
30 easy, 30 medium and H0/H5/H10/H15/H20/H25. The splitter never reads a label,
solver outcome, historical performance, graph or checkpoint.

Within each easy/medium family, rank original IDs by the hexadecimal SHA256 of
the following UTF-8 string, with literal NUL separators:

```text
cfl-gnn/mvp3/split/v1<NUL>42<NUL><family><NUL><original_id>
```

Ascending hash order, followed by the original ID in the event of a tie, fixes
the ranks. The first 21 parents per family train the model. The next five easy
and four medium parents form validation; the remaining four easy and five medium
parents form the test set. This seed-42 stratified procedure is independent of
Python/NumPy RNG implementations and catalogue iteration order.

| Role | Frozen aliases |
| --- | --- |
| Training: easy | E0, E3, E4, E5, E7, E8, E9, E11, E12, E13, E15, E16, E19, E20, E21, E22, E23, E24, E25, E26, E28 |
| Training: medium | M2, M3, M5, M6, M7, M8, M9, M11, M12, M13, M14, M15, M16, M17, M19, M20, M23, M24, M25, M27, M28 |
| Validation | E1, E2, E6, E10, E18, M0, M1, M4, M29 |
| Held-out easy/medium test | E14, E17, E27, E29, M10, M18, M21, M22, M26 |
| Hard transfer | H0, H5, H10, H15, H20, H25 |

These are MVP3 learning roles. Historical exposure remains documented in the
preserved MVP2 records; the new split does not make previously studied parents
an unseen external population. An S2 feature/label failure retains the parent's
role and receives an explicit disposition. It does not trigger reshuffling,
replacement, broader label admission or an invented observation. Dataset coverage
is accepted before training under the approved milestone.

The 15 evaluation parents use their canonical manifest order, with the cyclic
orders B/R/G, R/G/B and G/B/R over successive parent blocks. Each method occupies
each position five times. These are logical blocks, not a dispatcher or queued
jobs. The fresh evaluation B is separate from incumbent preparation. One original
parent remains the analysis unit; four targets are nested views of one trajectory.

## Stored identity and mathematical identity

The catalogue strips operational paths and retains original ID, alias, family,
stored-file SHA256 and bytes. Its 66 entries total 1,810,985,584 stored bytes.
The source receipt SHA256 is
`048b823a865af4988088b9f80388e759a7d227ef1f45e8e796a653077170d83c`.
It records NPAD compressed identities only. DGX compressed identities stay in
their separate preserved receipts. Decoded equivalence rests on the researcher's
accepted MILPBench provenance; no decoded digest or decompression verification is
invented or imposed by S1-A.

`model_identity()` accepts an already extracted, ordered model description. It
retains variable names/domains/bounds, objective coefficients and constant, row
names/senses/RHS and sparse coefficients. Effective sense must be MINIMIZE;
declared MAXIMIZE/MINIMIZE remains separate metadata. The effective mathematical
signature excludes the erroneous declared-sense flag, while the run binding
preserves both. Null lower/upper bounds explicitly denote negative/positive
infinity. Nonfinite coefficients, duplicate names or coordinates, invalid sparse
indices and reversed finite bounds are rejected.

Numeric normalization preserves the full decimal spelling of input integers and
finite floats, equates 1 with 1.0 and -0 with 0, and sorts sparse coordinates
within each original row. Row and variable order remain identity-bearing. The
function does not load an LP, mutate a model, certify formulation correctness or
prove feasibility. S1-B will bind extracted native model data to these identities.

## Evidence and qualification boundaries

Every observation has an original-parent/stage/method/seed/attempt key. Preparation
uses a null method; B/R/G is reserved for evaluation on the frozen test/transfer
parents. Source commit, environment inventory, input bytes, native-default
inventory/receipt, mathematical identity, effective parameters, audit policy and
resource profile bind a run. All effective parameters must equal its recorded
native defaults plus the approved stage overrides. A default-inventory digest
alone does not authenticate its claimed origin; S1-B must qualify and retain the
corresponding native Gurobi 14.0.0 receipt.

Root records require complete original-variable coverage, MIPNODE/OPTIMAL at zero
processed nodes and actual root-event/cut-pass provenance. A later valid root
observation cannot be relabelled pre-cut. A successful early capture has its own
outcome, even if the solver subsequently reports INTERRUPTED. Unavailable roots
use reasoned dispositions rather than partial fabricated features.

Labels refer to the exact retained, audited final incumbent and generating gap.
Terminal-target labels have gap <=0.0001. Intermediate or unqualified labels
remain explicit and cannot silently enter the primary learning tier. Hard labels
remain transfer-only. The reserved BENDERS provenance requires a hard parent,
separate release reference and equivalence-audit reference; it neither implements
nor authorises a decomposition or adds a primary call.

Start records preserve the original model and undefined unselected coordinates.
B has empty external guidance; R has no predictor dependency; G references a
predictor. Unique original positions/names, binary values, bounds, ones count,
assignment digest and the floor(10% of binaries) cap are checked. R/G support
counts need not match. These contracts do not generate Starts or freeze the
production policies prematurely; predictor/policy selection remains S3.

Audit records name the exact mathematical model and vector, measured row/bound/
integrality/objective residuals and explicit tolerances. The tolerance-map digest
must match the run's audit policy and participates in pairing. S1-A checks these
assertions and links; it does not recompute residuals from retained real vectors
or approve a new numerical tolerance policy. S1-B supplies and qualifies the
independent numerical auditor and its frozen policy.

An attained target must point to a retained event with the same run, clock, time,
gap, candidate vector and qualified point-specific audit. A final-solution audit
does not qualify a different intermediate vector. Events and follow-up cannot
exceed the recorded endpoint for that clock. A native report of zero gap is not,
by itself, an independently qualified target event.

## Clocks, missingness and individual factors

| Clock | Origin | Unit |
| --- | --- | --- |
| native_runtime | optimize_entry | seconds |
| worker_elapsed | worker_entry | seconds |
| end_to_end | pipeline_entry | seconds |
| reuse_elapsed | scenario_entry | seconds |

Native Work, memory bytes, logical allocation, physical topology and observed
activity retain distinct fields/units. Timings are overlapping scopes, not an
implicitly additive cost table. A missing numeric measurement is null with a
nonblank reason; an observed zero is retained as zero. Native infinite gap with
zero primal/unequal dual is represented by null and its explicit reason.

`paired_time_factor()` first validates its supplied runs/events and both target
records. It computes T_B/T_G or T_R/T_G only for a common qualified target, parent,
positive observed times, identical clocks/origins and a common comparison binding.
It also returns comparator-minus-G seconds. Censoring has no observed attainment
time; a target at zero remains attained but has no numeric factor. Infrastructure,
memory, callback and numerical failures retain separate outcomes. An infrastructure
interruption cannot be recast as valid time-limit censoring.

This is an individual-factor eligibility check for the contract tests, not the
S5 analysis pipeline. S5 will reconcile all planned cells and attempts, freeze
metric-specific cohorts, aggregate per-parent factors, and develop the cost/reuse
tables without summing nested clocks or substituting censoring endpoints.

## Local verification

Use an existing Python environment with jsonschema 4.26.0. The package exposes an
optional `mvp3-contract` dependency; no environment is reinstalled by this change.
From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -B -m cfl_gnn.mvp3 --bundle configs/mvp3/v1
python -B -m unittest discover -s tests/mvp3 -v
python -m ruff check --config configs/quality/pr64-ruff.toml src/cfl_gnn/mvp3 tests/mvp3
python -m ruff format --check --config configs/quality/pr64-ruff.toml src/cfl_gnn/mvp3 tests/mvp3
```

Add `--records <local-json-array>` to validate observations and their relational
bindings. Add `--export <new-directory>` to reproduce the frozen bundle in a new
directory; export fails if the directory already exists. Validation is read-only.
All committed test observations are invented in `tests/mvp3/fixtures.py` and are
not campaign records. No Gurobi/Torch import, license initialisation, solver,
training, inference, Slurm, SSH or SCP operation is required.

The dedicated CI checks Linux/Windows with Python 3.10/3.13, pinned jsonschema
4.26.0 and the repository's ruff 0.16.8. Existing evidence CI remains unchanged.
Local verification and exact-head CI results belong in the PR/checkpoint, not in
the planning workbook as scientific observations.

## Next boundary: S1-B

Native callbacks, LP extraction, independent residual computation, native-default
qualification, memory/process sampling, durable attempt claims, terminal
collection and release-pinned GRBLogTools adopted-field validation remain S1-B.
Real-data feature/label generation is S2. This PR contains no HPC launcher, remote
checkout update, experiment release, automatic retry, merge or publication.
