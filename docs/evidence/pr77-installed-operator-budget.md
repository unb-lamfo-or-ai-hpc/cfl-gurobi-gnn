# PR77 — installed operator receipt and explicit budget recording

## Evidence and unchanged execution source

The installed PR76 operator receipt is preserved byte-identically at
`pr76/operator-ad4800505bae/pr76_operator_preparation.json`, SHA256
`0249a1de5cb6d06422932d7ffa5568a2077ceb0c6f51099a5675a6f33fdeca14`.
It records 28 tests with zero skips, errors or failures; no scheduler query,
submission, optimization, raw-log export or scientific promotion.

Independent review recomputed all thirteen dependencies and both frozen plans:

- Operator: `c7f5aa69c775088e7d383a942d9ee66f2b053dfe656e5d123e80e546692f70a2`.
- Matrix: `b24dbe0924a2c6f03f7f162cf2f85bfd327f4a0bd99048b98200b6f22e5a575b`.
- Original installed source: `ad4800505bae78032e8fdbaa449a7afd2f12a080`.

PR77 adds the receipt archive, its read-only verifier, an explicit authorization
recorder and offline tests. It does not change any PR75/PR76 execution bytes or
reprepare the installed flow. A PR76 merge does not change the original head
bound to the existing plans. PR77 merge approval and matrix-budget approval
are distinct. All tests use explicitly authorized synthetic fixtures only.

## Recording is not approval inference or execution

`review` validates the archived exact schema, bytes and dependencies on
Windows or Linux. `preview` qualifies the original installed, untouched flow
and prints an authorization template with all three approval gates false.
It performs only two local Git reads; no scheduler query or license access.

`record` is unavailable without an independently supplied, canonical
authorization file and its exact SHA256. The file must state separate human
approval of the frozen resource budget, exact-head four-arm CI review and
installed no-solver probes review. It binds the original source, both plans,
receipt and physical flow directory. Unknown fields, numeric substitutes for
booleans, increased limits, GPU, exclusive allocation, requeue, retry,
scientific promotion or invented installed memory qualification are rejected.
Neither receipt review nor a merged PR constitutes that explicit approval.

Before recording, the helper checks the actual original checkout's clean Git
head and all thirteen dependency bytes, both installed plan files, the
installed receipt and the original false approval files. It refuses a started
flow or any preexisting submission/execution claim. Recording consumes a
durable exclusive authorization claim and retains the original false files.
Each approval replacement is atomic, but the pair is **not a transaction**:
interruption can leave one or both files updated without an acknowledgment.
Claims and partial state are preserved for manual reconciliation. There is
no automatic rollback, resume, clearing of locks or repeat recording.

Recording never submits a job. Its completion receipt reports zero new
submissions, optimizations and scheduler queries. Actual-allocation RAM,
swap, affinity and process-group interruption remain mandatory before model
access; memory safety is not qualified by this engineering receipt.

## Bounds and operational sequence

The prospective budget remains two sequential CPU-only parent jobs, 16
physical cores, 64 GiB, at most 330 minutes per parent; five serial attempts
per parent with at most one 3,600-second optimize call each. The original
instances, seed 42, thread order, defaults and memory policies are unchanged.
Medium still requires independent easy review. No retry or extension exists.

```bash
# Read-only receipt review. No HPC or budget authority is implied.
python3 -B scripts/evidence/paired_budget_authorization.py review

# Safe installed preflight only: request template stays false.
python3 -B scripts/evidence/paired_budget_authorization.py preview \
  --directory /raid/vrcelestino/data/cfl-mvp2-evidence/pr76/operator-ad4800505bae/flow

# NOT AUTHORIZED by this PR. Only after separate exact budget approval:
python3 -B scripts/evidence/paired_budget_authorization.py record \
  --directory /raid/vrcelestino/data/cfl-mvp2-evidence/pr76/operator-ad4800505bae/flow \
  --authorization "$EXPLICIT_AUTHORIZATION_FILE" \
  --authorization-sha "$EXPLICIT_AUTHORIZATION_SHA256"
```

After a successful, separately authorized recording, use the unchanged PR76
source's submit/status/collect commands. Do not execute the matrix from the
PR77 checkout: the installed flow binds the original PR76 source commit.
Queries are one-shot, collection is terminal-only, and returned evidence
still requires independent review. No optimizer or Slurm command is included
in PR77's merge/publication or no-solver handoff.

Next gates remain: PR77 four-arm CI and review, installed no-solver preview,
separate exact budget, actual resource qualification, easy execution and
independent review, medium execution and independent review, then paired
censoring/target/cost analysis. Sprint B is not complete.

## Verification and publication checkpoint

The candidate passed pinned Ruff 0.16.8 check and formatting, `git diff --check`,
and the complete offline evidence suite: 389 tests, four platform-specific
skips. Eighteen new tests exercise receipt/source/dependency checks, explicit
authorization, durable claims, replay rejection and interrupted recordings.
An injected failure before replacement leaves both original false files;
failure between replacements retains partial state; failure writing the final
acknowledgment retains both updated files without claiming successful recording.
These are synthetic offline fixtures, not installed memory qualification.

At preparation, GitHub publicly confirmed PR76 open/ready at the exact approved
head and all four evidence jobs successful in run `37391947798`. The user
authorized its merge into `develop`. The previous sanitized receipt-review
comment was not posted: browser automation could not verify the active URL.
The current local GitHub CLI credential is invalid, so no authenticated
publication or merge is claimed by this checkpoint. The operator handoff
validates authentication and exact heads, posts that review, performs only
the approved PR76 merge, and publishes this separate candidate as a draft.
PR77 CI, ready status and merge authorization remain distinct later gates.
No HPC preparation, budget recording, scheduler operation or optimization is
part of that GitHub publication handoff.
