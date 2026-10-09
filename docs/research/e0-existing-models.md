# E0: evaluate existing models before new training

Current continuation: [installed coverage review and twenty frozen-model test forwards](e0-coverage-review-and-test-inference.md).
The original metadata collection below is complete; do not repeat it.

9 October 2026. Base: PR80 merged into `develop` at
`15e6d3494f6fedc6d61e6dbc14eaddc895b5e4e2`.

## What, how and why

**Question:** how much useful solver guidance do the existing frozen GNN models
provide, and at what end-to-end computational cost? Reuse models and compatible
results before paying for new training, DDP or augmented data.

PR80 completed numerical verification of **all 54 learning parents**, not 39.
Its four forwards used two known validation parents, not the full test set.
E0 does not repeat either audit. It first reconciles historical method coverage;
new optimization is not yet admitted by this implementation.

The versioned collector reads only recognized JSON result/plan names under the
existing dataset's `analysis`, `intermediate`, and `models` directories. It emits
allowlisted metadata, hashes and candidate results, never logs, credentials,
paths, checkpoint binaries or predictions. Limits: 50,000 entries, 128 MiB total
JSON, 8 MiB per JSON, and a checked 120-second traversal budget. This is an
elapsed check between filesystem operations, not a hard timeout for stalled I/O.
No Torch/Gurobi import, scheduler query/submission or dependency installation.

Recognized files: the three method-named JSONs, `per_method_outcomes.json`, and
PR58/PR59 guidance plans. This is **not** a universal scan of every historical
format or evidence directory. Missing, skipped or unsupported evidence cannot
establish non-existence. Malformed recognized files are counted; copies with
identical method bytes are not independent observations. Aggregate rows do not
substitute for method, solution and preparation provenance.

## Population, without retrospective relabeling

The inherited table contains 16 parents x 3 methods = 48 cells:

| Stratum | Parents | Meaning |
| --- | ---: | --- |
| Predictive test | 10 | Six easy and four admitted medium, original split unchanged |
| Label-excluded medium | 6 | Historical exposure disclosed; not an untouched test set |

The published table contains 24 method rows and lacks 24: F0, F3, F6, F14,
F27, F29, M13 and M26. Canonical M13/M26 role is `train`, but they were not
admitted to the 54-parent learning sample. Keep canonical role, learning
admission and evaluation stratum separate. Do not pool these strata into a
single generalization claim. F/M are display aliases; retain stable source IDs.

## Three methods and frozen-model comparison

1. Gurobi with no external start.
2. Partial binary start selected from a root LP solved by Gurobi, matched to
   the GNN start's support size and positive-assignment count. Continuous values
   are not submitted as the start; Gurobi completes unspecified variables.
3. Partial binary start selected from frozen GNN probabilities.

The root LP is a source of scores, not an alternative solver. The historical
policy caps support at 10% and 20,000 binaries, selects positive assignments
first and abstains without a positive GNN prediction. Do not tune thresholds
from test outcomes. Reusing cached root features must record their original
cost; otherwise guidance appears artificially free.

PR80 binds easy-only and mixed checkpoints and thresholds. This first receipt
locates historical method/plan metadata; it does **not** reverify checkpoint or
solution bytes or claim that both models have already been compared by Gurobi.
Before new runs, bind checkpoint, training population, representation, parent
MILP, seed, threshold, support policy, full effective solver parameter map,
Gurobi version, root provenance and preparation cost. Compare guided runs only
with a compatible parent/seed/thread/budget control. Keep unmatched historical
results descriptive; do not silently treat them as new matched controls.

The provisional 24-main-solve/8-root ceiling inherited from PR80 describes one
three-method completion of the eight missing parents. It is **not** sufficient
authority to multiply runs across two models and five CPU caps. Model-specific
guidance arms and their shared controls must be enumerated before execution.
Five caps (1,2,4,8,16) remain required for E1/E2; no repeat of Sprint B now.

## Two immediate outputs and continuation

`collect` produces one sanitized `coverage.json`. After one SCP transfer,
`review` produces `coverage.csv` (48 rows) and `proposal.json`, linked to the
receipt hash. These are reconciliation outputs, not statistical result tables
and not an executable approval manifest. `reuse_admitted` and execution flags
remain false until the evidence review is complete.

After the installed return, continue **this delivery**, not a separate PR per
helper: review candidates, inspect only missing provenance, freeze the minimal
missing-run manifest and give a single nonblocking operator flow. Preserve
historical failures; no automatic retry, training, package update or promotion.

E0 closure outputs: per-parent/method/model CSV; gaps, censoring and observed
target times; start acceptance; preparation/root/inference/main-solve/full cost;
paired effect tables and SVG/PDF/PNG figures with source hashes and Spanish
captions. Missing times remain missing. Inference-only GPU timing is not GPU
training speedup. The accepted C2/C3/D/E1-E2/F plan remains in
[the full delivery plan](mvp2-results-plan-20261009.md).

## Operator runbook (read-only, no Slurm job)

Use the exact published E0 commit from the handoff, after its four evidence CI
checks pass. Set `E0_SHA` to that commit. The block makes a fresh source snapshot
on `/raid` and leaves the working checkout and previous receipts untouched.

```bash
conda activate tfm_env
(
  set -euo pipefail
  test "${#E0_SHA}" -eq 40
  E0_REPO=/raid/vrcelestino/data/cfl-gurobi-gnn
  git -C "$E0_REPO" fetch origin feature/e0-existing-evidence
  test "$(git -C "$E0_REPO" rev-parse FETCH_HEAD)" = "$E0_SHA"
  mkdir -p /raid/vrcelestino/data/cfl-mvp2-evidence/e0
  E0_STAGE=$(mktemp -d /raid/vrcelestino/data/cfl-mvp2-evidence/e0/coverage-XXXXXXXX)
  mkdir "$E0_STAGE/source"
  git -C "$E0_REPO" archive "$E0_SHA" | tar -x -C "$E0_STAGE/source"
  python3 -B "$E0_STAGE/source/scripts/evidence/reconcile_e0_coverage.py" collect \
    --data-root "$E0_REPO/data" --output "$E0_STAGE/coverage.json"
  sha256sum "$E0_STAGE/coverage.json"
  printf 'E0_OUTPUT=%s\n' "$E0_STAGE"
)
```

Then run `scripts/evidence/receive_e0_coverage.ps1` locally with `-RemoteDirectory`
equal to `E0_OUTPUT` and `-ExpectedSha256` equal to the printed 64-character
receipt SHA256 (not the 40-character Git commit). One SCP connection downloads
one file. Share the output directory and receipt for independent review.
If collection stops, preserve the directory and share the error; do not repeat
automatically. There is no solver submission or resource-approval phrase.

## Exit checklist

- [x] Implement read-only candidate collection, local table generation and one-transfer receiver.
- [x] Add offline tests for coverage, sanitization, deduplication, role conflicts and preservation.
- [ ] Four exact-head CI checks and installed collection receipt.
- [ ] Independently review compatibility and freeze minimal missing runs.
- [ ] Execute only admitted missing coverage, then produce comparison figures/tables.
- [ ] Ready for review, followed by separate human merge authorization.

## PR63 red X: diagnosis, not a failed merge

PR63 merged into `main` at `c8297139aaeed78c7951c91379983c414b181860`.
The automatic [Manuscript run 37121174278](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/37121174278)
was cancelled. Its render annotation identifies a higher-priority waiting
request for `manuscript-refs/heads/main`. At that commit, the workflow uses
`concurrency.group: manuscript-${{ github.ref }}` and `cancel-in-progress: true`.
The later manual [run 37121179282](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/37121179282)
completed both render and deploy successfully **at the same commit**. The red X
therefore does not establish a merge/content failure. Do not repeat the merge
or disable concurrency. The separate Node20/Node24 deprecation warning was not
the cancellation cause. Verified against public GitHub API on 9 October 2026.
