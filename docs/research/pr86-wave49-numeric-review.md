# PR86 — M4 return: structural success, numerical qualification pending

Updated: 16 October 2026. This is a read-only review, not authorization to retry
or to change the mathematical formulation, tolerances or experimental design.

## What was received and checked

Jobs3609–3614 completed with scheduler exit0:0. Their original public return is
preserved at `../evidence/pr86/jobs3609-3614/public_return.json`, SHA256
`ed87d2e280a1941228c7662ff234c24dd31a5906d8f0fe1d98962938fcdfdbe6`.
Source596c87bf004405f6148d381d2ba1764c650ca60c and plan SHA256
84bda69a51876564e09f22351d26be79d0e29d433e81085499b7308a7d6a23f9
match the released M4 positions49–54. The unmodified source-tree validator
passed before this continuation. Eighteen cells, twelve accepted starts,
MINIMIZE, original model identity and individual tolerance-feasibility checks
reconcile; no memory/callback stop was observed. The six jobs sum65,856s
(18h17min36s) of scheduler elapsed, excluding queues, not measured solver CPU.

There are now **165 collected cells**, but only the prior **147 cells** retain
their previous scoped review. These18 M4 cells are held for numerical review.
Forty-five planned main solves/15 groups remain unexecuted. No next wave is
released by this document. Raw receipt flags are unchanged.

## Why the wave is not promoted

M4/M2/8threads/seed42 reports status2, primal=dual4.905362657205728,
gapzero and terminal runtime3367.821671962738s. Seventeen other cells are
time-limited, not exact completed times to the target. Three returned
incumbents, individually feasible **within the recorded tolerances**, lie
below the purported terminal lower bound:

| Candidate M4 cell | Objective | Bound excess | Max integrality residual |
| --- | ---: | ---: | ---: |
| M2 /1thread /seed43 | 4.904654739916017 | 0.000707917289711 | 3.1710e-7 |
| M2 /2threads /seed42 | 4.900766815427447 | 0.004595841778281 | 8.9105e-6 |
| M0 /4threads /seed42 | 4.902162841678935 | 0.003199815526793 | 9.9713e-6 |

All18 children report the same model SHA2569673147c6b0ca81086134a595d980d8eb5a462731a8f0336ae7a9a2dbefbe3c1,
fingerprint1649844212 and mathematical signature
5d55c833cb154f695825d4ef87a649d7e106f77d87b2f6ee1c6f40502b40d09a.
The largest discrepancy is0.09378% of the candidate objective, above the0.01%
gap target. This is a **cross-run consistency warning**, not proof of a solver
bug or an exactly feasible counterexample. An integrality residual below1e-5
does not prove exact integer feasibility; original-unit row residuals below1e-6
can be sensitive to scaling. The old per-run checker does not test consistency
of a bound with other runs or reevaluate rounded integer coordinates.

The independent read-only check found no substantive analogous terminal
bound/incumbent conflict in the prior147-row CSV at absolute tolerance1e-6.
That is a screen of recorded values, not a new solution/bound certification.

Gurobi documents finite-precision feasibility and integrality tolerances and
the possible effect of scaling and near-integral values. These mechanisms are
**hypotheses here**, not an established explanation:
[tolerances and scaling](https://docs.gurobi.com/projects/optimizer/en/current/concepts/numericguide/tolerances_scaling.html),
[integrality and rounding](https://support.gurobi.com/hc/en-us/articles/360012237872-Why-does-Gurobi-sometimes-return-non-integral-values-for-integer-variables).
Do not silently tighten tolerances, repair/reoptimize a solution, change starts,
relabel a timeout or claim a GNN speedup to resolve this warning.

## How the next diagnostic works

`scripts/evidence/audit_pr86_wave49_numeric.py` has two modes:

1. Offline: verify the pinned original return/plan/manifest and nested members;
   produce18 observed rows, a three-conflict numerical screen and output hashes.
   It keeps the distinction between165 collected and147 previously reviewed.
2. Installed, explicitly executed by the author on dgx-dasci: read the same
   model and the four stored private solution vectors implicated above. Verify
   model/child/bundle identity and sealed solver logs; recompute original and
   diagnostically rounded-in-memory objectives and residuals. Report normalized
   row residuals and extended-precision arithmetic as diagnostics, not new
   acceptance rules or exact arithmetic certificates. Export only hashes,
   counts, numeric summaries and allowlisted log flags, never paths/names/vectors
   or raw logs. No optimizer, inference, training, scheduler query or job.

The installed audit reads four vectors sequentially, caps decompressed solution
reads at512MiB and sets a16GiB virtual-address-space process ceiling. The proposed
author-run invocation below enforces a900s external timeout. Those are diagnostic bounds, not a new Slurm
allocation or evidence of historical memory safety. Partial diagnostic files
are preserved on failure; no automatic repeat. Original solution hashes were
not exported by the old worker: hashes observed now cannot be misrepresented
as historical seals. Child and solver-log hashes were already sealed and are
checked. Original model, solutions, parameters and receipts remain untouched.

After installing the reviewed, source-pinned audit into a separate worktree,
with SOURCE pointing to that worktree and OUTPUT a new direct child of the
PR86 evidence directory, execute only:

```bash
timeout 900s env PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  GRB_LICENSE_FILE="${GRB_LICENSE_FILE:?Set the existing license path privately}" \
  python3 -B "$SOURCE/scripts/evidence/audit_pr86_wave49_numeric.py" \
  --installed-output "$OUTPUT"
```

Historical bundle digests are checked against the pinned group-start receipt,
not just the current request file. Canonical filenames, complete cells/contexts,
regular nonsymlink input containment, and sealed child/log identities are
required. The output records the collector Git commit/source hash separately
from the historical worker commit. Standard output contains no private input
paths or exception text; the caller already knows its chosen output directory.

## Acceptance and continuation

The next return must bind all four audits to the stored model/cells and explain
what survives rounding and row-normalized checks. If the discrepancy remains,
report that limitation and decide the smallest scientifically justified action
before further optimization. Failed rounding alone proves neither the proposed
mechanism nor the reported optimum. Do not discard or replace the18 runs.

The PR remains draft; fixes stay in this PR. Following resolution, resume the
unchanged manifest at55: M4/16/seed42, then M7/1/seeds42,43,44 and2/4/seed42.
That future six-job wave is inside210/70, but **not yet released**. PR87 mandatory
1-GPU serial/4-GPU DDP requires its exact budget; PR88 manuscript work remains
parallel. Final develop/main synchronization follows article revision.
