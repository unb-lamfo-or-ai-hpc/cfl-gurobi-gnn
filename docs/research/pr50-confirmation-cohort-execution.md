# PR #50: frozen confirmation-cohort execution

## Evidence and scope

PR #49 was squash-merged into `develop` at
`a86ab1088d0948e6d1f6c98d571c411bcd8e94fb` after the maintainer supplied
387 passing DGX tests and the 42-parent confirmation inventory. The inventory
contains 30 easy and 12 medium parents, with no hard parents. All graph hashes
match their sidecars. However, the medium labels have relative gaps between
0.4329146386 and 0.8472560275. These are not admissible under the fixed 0.10
ceiling. A deprecation warning about TypedStorage is not a training failure.

The inventory contract is
`b3bc28d3cc0a1c33d0f02f9ec9817b1bc3bf54f20f743e09b30689e984b8455c`.
It is an inventory gate, not independent mathematical or training validation.

This increment implements the **source-admission gate** of PR #50. It does not
claim that 42-parent training, strict graph migration, or a guided benchmark
has already run. Keep this PR draft until the execution evidence and the
remaining integration stages below have been reviewed.

## Source admission

1. Freeze the exact inventory, graph and sidecar hashes, original MIP hashes,
   canonical roles, implementation hashes, and repair-plan hashes.
2. Index existing `gurobi_parent_solve_report.json` files below
   `DATA_ROOT/intermediate`. Only matching original-parent identity and MIP
   hashes can supply a reusable named label. A derived MIP is not an original.
3. Alternatively, import the exact selected historical pool/incumbent record.
   This requires matching artifact hashes, corrected MINIMIZE metadata, and
   historical column/row/matrix features matching the original Gurobi model at
   the historical writer's float32 precision. Check the full-precision solution
   independently against original bounds, integrality, rows and objective.
   Never import `graph.y` as full-precision evidence. Never assign the terminal
   best-pool gap to a different pool member. Intermediate incumbent gaps retain
   callback semantics, and terminal runtime is not an epoch timestamp.
4. Select deterministically among independently admissible sources. When none
   qualifies and `--repair` is explicit, solve that parent with Gurobi for 3600
   seconds, then 14400 seconds only if the first outcome remains inadmissible.
   Each budget is a fresh independent solve, not continuation or warm start.
   Maximum optimization budget is 18000 seconds per repaired parent. There is
   no automatic full-90 campaign or SCIP rerun in this source-admission step.
5. Reaudit newly solved labels against the original model. Save named solutions,
   gap and execution-time provenance to a separate campaign, preserving source
   files. Resume verifies solution/source hashes and original-MIP feasibility.
   Legacy missing time-region fields remain null rather than fabricated zeros.
6. Aggregate with an `afterany` dependency so missing or unsuccessful tasks
   remain visible. Exactly 42 admitted parents are required for the label gate.
   Even then, `training_ready` remains false pending strict graph consolidation.

Invalid inputs and inadmissible gaps are distinct. Historical records are not
deleted or rewritten. Prior inconclusive task reports are retained by content
hash when the same campaign is retried. Inspect `source_errors` if expected
legacy reuse is rejected. Trusted local legacy pickle files are deserialized
only after checking their frozen hashes; do not point this importer at untrusted
downloaded pickle artifacts.

The imported label identifies its origin as
`independently_audited_gurobi_confirmation_label`. It is deliberately not
silently presented to old graph/training loaders as a newly executed solve.
The strict graph consolidation adapter is the next integration gate.

## DGX execution

Run these commands on **dgx-dasci**, inside the repository and `tfm_env`.
Do not run them on `service0` or from a different project. Values ending in
`_DIR` below denote directories, not JSON filenames.

The shortest supported route, after updating the branch, is:

```bash
export DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
bash scripts/slurm/dasci/launch_confirmation_execution.sh \
  "${DATA_ROOT}/analysis/confirmation/pr49_20260911T224543Z/confirmation_inventory.json"
```

This child script runs the complete licensed test gate, prepares the frozen
campaign, and submits source/recovery tasks plus an `afterany` audit. It stops
before submission on a failed preflight, without closing the interactive shell.
It prints the campaign directory and saves submitted job IDs there as text files.
Selective repair is enabled by default. The expanded equivalent is below;
do not run both routes for the same experiment.

```bash
git fetch origin
git switch feature/confirmation-cohort-execution
git pull --ff-only origin feature/confirmation-cohort-execution
python3 -m pip install -e . --no-deps
CFL_REQUIRE_SOLVER_TESTS=1 PYTHONPATH=src python3 -m pytest tests/smoke -q

export EXEC_DIR="$PWD"
export DATA_ROOT=/raid/vrcelestino/data/cfl-gurobi-gnn/data
export GRB_LICENSE_FILE="${EXEC_DIR}/secrets/gurobi.lic"
export CONFIRMATION_EXECUTION_DIR="${DATA_ROOT}/analysis/confirmation_execution/pr50_$(date -u +%Y%m%dT%H%M%SZ)"

python3 -m cfl_gnn.cli.run_confirmation_cohort prepare \
  --inventory "${DATA_ROOT}/analysis/confirmation/pr49_20260911T224543Z/confirmation_inventory.json" \
  --data_root "${DATA_ROOT}" \
  --campaign_dir "${CONFIRMATION_EXECUTION_DIR}"
```

Stop before submission if preparation fails. No solver has run at this point.
To perform only read-only source admission, set `REPAIR_LABELS=0`; the execution
below explicitly enables selective repair, not unconditional re-solving.

```bash
export REPAIR_LABELS=1
SOURCE_JOB_ID=$(sbatch --parsable --array=0-41%4 --export=ALL \
  scripts/slurm/dasci/submit_confirmation_sources.sbs)
SOURCE_JOB_ID=${SOURCE_JOB_ID%%;*}
if [[ "$SOURCE_JOB_ID" =~ ^[0-9]+$ ]]; then
  AUDIT_JOB_ID=$(sbatch --parsable --dependency="afterany:${SOURCE_JOB_ID}" --export=ALL \
    scripts/slurm/dasci/submit_confirmation_sources_audit.sbs)
  AUDIT_JOB_ID=${AUDIT_JOB_ID%%;*}
  printf 'SOURCE_JOB_ID=%s\nAUDIT_JOB_ID=%s\nCAMPAIGN=%s\n' \
    "$SOURCE_JOB_ID" "$AUDIT_JOB_ID" "$CONFIRMATION_EXECUTION_DIR"
else
  echo "SUBMISSION_FAILED; no dependent job submitted"
fi
```

After completion:

```bash
sacct -j "${SOURCE_JOB_ID},${AUDIT_JOB_ID}" --format=JobID,State,ExitCode,Elapsed,MaxRSS
jq '{gate_status,planned_parents,independently_admissible_parents,
     label_inventory_ready,training_ready,next_gate,
     pending:[.records[]|select(.label_eligible != true)]}' \
  "${CONFIRMATION_EXECUTION_DIR}/confirmation_execution_report.json"

python3 - "$CONFIRMATION_EXECUTION_DIR" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
report = json.loads((root / 'confirmation_execution_report.json').read_text())
item = report['label_index']
path = (root / item['relative_path']).resolve()
assert path.is_relative_to(root)
assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
for row in rows:
    for name in ('solution', 'report'):
        item = row[name]
        target = (root / item['relative_path']).resolve()
        assert target.is_relative_to(root)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']
assert len(rows) == report['independently_admissible_parents']
print('PR50_SOURCE_HASHES_OK', len(rows))
PY
```

Published source reports contain no absolute paths. Raw `repair_runs` collector
artifacts are private operational evidence; do not upload them indiscriminately.
Share the aggregate report and failed task diagnostics, never a license file.
An incomplete aggregate is not authority to increase the gap ceiling or remove
medium parents. It is evidence for the next targeted intervention.

## Remaining PR #50 gates and subsequent work

- Complete strict Gurobi-authoritative graph consolidation from the admitted
  label index, with real MIPNODE root vectors, exact variable identity and
  original-only graph identities. Do not use zero root-feature fallback.
- Bind the 42-parent dataset to rotation 0: 24 train, 10 validation, 8 test.
  Run the versioned Gasse model and toy test, seed 42, 100 full epochs. Calibrate
  prenorm on training only, select checkpoint/threshold on validation only, and
  export training and validation loss on the **same figure**. Test remains held out.
- Run held-out quality evaluation and verified prediction export. Then execute
  the precommitted primary native Gurobi hints/control benchmark with MIP gap,
  four time regions and censoring retained. Do not label a single-arm 42-parent
  run as a completed matched four-arm augmentation comparison.
- Complete the matched four-arm dataset where paired solver labels exist, then
  compare on identical parent partitions and budgets. Publish descriptive tables,
  graph statistics/clustering and verified figures without arm-selection claims
  based on the small development cohort.
- Keep English-only documentation/comments and dependency reproducibility work,
  followed by the Quarto Manuscript draft using the maintainer's future template.
  The full-90 execution and extended scientific results remain postponed until
  after that draft. No TRL or generalization claim follows from unit-test counts.
