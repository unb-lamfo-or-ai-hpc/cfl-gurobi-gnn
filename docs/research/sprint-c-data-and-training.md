# Sprint C: data, representation, and matched training

## Entry checkpoint and operator decision

PR79 was merged into develop at `461f72580f9bae4d5c2daadcf22e0490594e4188`.
Sprint B is closed by the preserved paired analysis, not by a new solve.
Jobs 3489 and 3494 already contain caps 1, 2, 4, 8 and 16 for
`CFL_easy_instance_17` and `CFL_medium_instance_1`, respectively. Medium caps
4/8/16 are time-limited outcomes, not failed executions or target attainments.
Job3490 remains a separately accounted interruption.

The operator explicitly selected **retain all five thread caps for comparison
with and without warm-start**, not repeat the unguided matrix now. The
conservative one-thread development default does not remove any comparison arm.
These two previously inspected parents are development examples, not untouched
test data. Their split roles must not be relabelled to claim generalization.

## Three integrated deliveries

| Delivery | Implementation and evidence | Completion criterion |
| --- | --- | --- |
| C1 (this PR, initially draft) | Historical metadata audit, exact graph/label admission, representation specification and leakage checks | Selected input bytes, model/variable identity, mathematical label feasibility, gap and parent roles verified; explicit unavailable history; frozen baseline representation |
| C2 | Matched easy-only and mixed training with baseline Gasse-v2, two layers, hidden dimension 32; at least 100 epochs | Frozen eligible cohorts/roles, validation-only checkpoint/threshold selection, per-parent predictions, AP/F1/precision-recall/calibration and preparation/training/inference cost receipts |
| C3 | Serial/1-GPU versus 2-GPU DDP, conditional 4/8 only if justified | Equal global batch, sampling mass and optimizer updates; measured wall time, utilization, communication and peak memory; predictive quality reported separately |

These are deliverables, not a quota of tiny PRs. Continue implementation and
installed evidence within C1; do not create one PR per diagnostic helper.
No training, solver run, GPU campaign or budget expansion is authorized by this
planning document. Freeze each execution budget before its CLI handoff.

## C1 implemented entry audit

### Installed return reviewed: 2026-10-07

The original v1 receipt SHA256 is
`1183e69f817a62ae249e2d41a110de941084b19cfbfa4c641d03248a3796781e`.
Its exact bytes are preserved in `docs/evidence/pr80-inputs-receipt.zip`.
Independent local hashing matched the operator's receipt. It reports 9,391
entries, 330,824 metadata bytes, 17 plan files, 13 distinct plan digests, no
unreadable metadata and no symlinks. This is metadata coverage, not a count of
training executions or eligible datasets.

Selected candidates (pinned by original bytes, not by file modification date):

| Cohort | Plan SHA256 | Distinct parents | Train / validation / test |
| --- | --- | --- | --- |
| Easy-only | `cbf0fe92b07aa79de97b9ac616a64178534156b58224fd43ae8494b9d54839ae` | 30 easy; two identical plan copies | 18 / 6 / 6 |
| Mixed | `07c3377c20ef49c0ad3ae33a6b57d9dd70f92fc48a32f5f80c25b5cb32aa5da4` | 30 easy + 24 medium | 34 / 10 / 10 |

**Collector correction, not data repair:** v1 incorrectly required the legacy
`parent_ids_by_role` and `graph_manifest_sha256` fields for every plan variant.
The actual builders in `easy_transfer_training.py`, `pr57_training.py` and
`confirmation_training.py` deliberately use `graph_report_sha256` and derive
roles from records. The two corresponding v1 issue codes therefore do not
prove damaged labels, split leakage or missing graph artifacts. v2 recognizes
those explicit variants, still validates the canonical contract and checks any
present role declaration. It requires the proper graph-report hash and never
silently admits unknown variants. Original receipts and plans are unchanged.
Historical smoke/augmentation plans remain unsuitable for the complete
original-only comparison; that does not invalidate their original smoke use.

### Next installed step: selected artifact bytes and canonical split

`verify_sprint_c_artifacts.py` uses the two reviewed plan digests above. It
deduplicates exact plan copies, resolves the referenced graph report by digest,
checks its manifest bytes and exact selected rows, and verifies each selected
graph/root/label SHA256. It also checks parent identity, fold and role against
the repository's canonical split. It does not infer paths from a guessed run
name; missing or ambiguous references stop that cohort with a public reason.

Bounds: 20,000 directory entries, 8 MiB per metadata file, 2 GiB per referenced
artifact, 8 GiB total reads and a 180-second cooperative deadline. Hashing is
streamed in 1 MiB blocks; there is no binary deserialization, network query,
solver import, training or Slurm submission. Cache hits check file identity and
size/mtime; private paths and raw exception text are not exported. Each cohort
has its own outcome, so success for easy cannot hide an unresolved mixed cohort.
The focused tests exercise both report-backed variants, byte tampering,
duplicate copies, ambiguous reports, canonical splits, unsafe paths, limits,
cache mutation and real CLI no-overwrite/hash behavior.

**Still not training admission:** this verifies declared artifact identities,
not current mathematical feasibility, variable-order agreement, numerical
features, normalization or historical training consumption. Those checks and
the representation decision remain C1 work in this same PR. Do not repeat the
first inventory or any Sprint B solve. Run the new exact-head handoff once,
return its one sanitized JSON, and preserve any incomplete result.

`scripts/evidence/audit_sprint_c_inputs.py` uses only the Python standard library.
It discovers `gasse_training_plan.json` and `gurobi_graph_manifest.jsonl` under
analysis/models/bipartite_graphs/intermediate. It skips symlinks and secret/tool
directories; it never reads a licence, log, pickle, PyG tensor or model file.
The limits are 20,000 entries, 8 MiB per metadata file, 64 MiB of metadata and a
45-second cooperative deadline (not an OS hard I/O timeout). Exceeding traversal
limits stops; invalid/unreadable files yield explicit incomplete coverage.

For each training plan, verify its canonical contract hash using the existing
Gasse contract's excluded derived fields. Check declared source hashes, gap
eligibility (0--10%), sample uniqueness, role counts, parent separation and
same-MIP role/graph consistency. Compare its declared graph-manifest digest
with observed manifest bytes. Summaries are per plan, never pooled across
different protocols or historical runs; duplicated plans do not add parents.

The public receipt contains allowlisted identities, counts, issue codes and
hashes, not raw paths or arbitrary source strings. A successful CLI means that
the bounded collection completed; inspect `failures`, `issues` and coverage.
`training_admitted=false` remains unconditional: matching metadata hashes does
not establish feasibility, graph feature validity or actual training usage.

### Remaining work in this same PR after the installed receipt

1. Select exact easy-only and mixed graph/label roots from observed contracts.
   The historical 30 easy (18/6/6) and 54 mixed (34/10/10) are candidate cohorts,
   not admission inferred from an aggregate count.
2. Reuse existing strict graph/label auditors to bind original model hashes,
   named variable order, independent feasible labels and label gap to roles.
   Hash/check only the selected artifacts under a bounded audited operation.
   Missing labels stay excluded; do not automatically generate new labels.
3. Freeze the baseline 7-variable-feature / 5-constraint-feature / 1-edge-feature
   bipartite representation. Audit feature finiteness/scaling, graph identity,
   label-independent structure and train-only fitting of learned transforms.
4. Specify dimensionality reduction as an ablation, not a silent baseline
   replacement. Separate exploratory plots from input transformations;
   transformations require an out-of-sample rule and fitting-parent-only fit.
   Verify the exact Vargas-Perez reference and applicability before choosing a
   method. No claim that PCA/UMAP or that paper has already been implemented.
5. Close with selected coverage, exclusions and unresolved historical costs.
   Obtain no new execution merely to reconstruct unavailable historical telemetry.

## Future solver comparison retained in full

For each eligible easy/medium parent, compare unguided, root-LP-guided and
GNN-guided starts at **1, 2, 4, 8, 16 threads**, paired by parent/seed/cap.
Freeze order, target, resource limits and start coverage before runs. Retain
timeouts, memory/worker failures and no-start/failed-start outcomes distinctly.
Keep cold preparation/inference/relaxation costs as well as solver time.
Use Sprint B observations as historical development evidence; do not silently
reuse them as matched contemporaneous controls under a changed protocol.
This comparison belongs to E1/E2 after qualified models exist; C1 records its
requirements and C2/C3 produce the models. No new Gurobi matrix is submitted now.

## Operator workflow

Fetch the exact reviewed PR head into a fresh directory under
`/raid/vrcelestino/data/cfl-mvp2-evidence/`. Run the audit against
`/raid/vrcelestino/data/cfl-gurobi-gnn/data`; write the receipt outside that tree.
The handoff supplies the exact commit, collection and single-file SCP return.
There is no Slurm submission, polling loop, approval phrase or retry. Preserve
the original metadata and this receipt. Review the return locally before
changing admission or preparing a training command. Merge requires the operator.
