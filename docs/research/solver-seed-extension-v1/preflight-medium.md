# Six-medium read-only preflight

This is an author-run byte/structure inventory for M5/M6/M9/M13/M20/M26.
It does not prepare a root, load the GNN, generate labels, run inference,
instantiate Gurobi or change any scientific parameter. Planning approval
already exists; this CLI step only resolves existing-file facts.

## Reuse before new reading

The existing E0 inventory already records M13/M26 original-file hashes:
- M13: f219560e7ee07013152d4069af8585848e853d6d8bc213b248ba2ebcd0d8dde5
- M26: 568bbff8df060b2de1df4d9bf3815d77e2e18ac73158fe676ba121182add70c8

Those are historical digests, not current-byte confirmations. The previous
inspection did not admit their root caches for inference; caches are not
rescanned or deserialized. The four remaining source digests were not
identified in the reviewed records. The parent table's six blank hashes
must not be mistaken for proof that originals are absent.

## What the code reads

[preflight_medium_readonly.py](preflight_medium_readonly.py) checks only
.lp.gz/.lp filenames for the six canonical parents, in two documented data
layouts below the existing RAID data root. There is no recursive scan,
pickle/tensor loading, solver/GPU import or package upgrade. Missing and
ambiguous originals remain explicit; no replacement is generated or chosen.

The text reader records declared variables/domains, rows, lexical nonzero
terms and coefficient ranges. It is a deliberately restricted linear LP
inventory, not Gurobi's parser or a new formulation/feasibility certificate.
Unsupported syntax is reported rather than treated as a valid complete
model. Bounds are counted, not independently validated. The original
MAXIMIZE declaration is observed; the future MINIMIZE contract is retained
without rewriting the file.

Hashes and file size/mtime are checked around reading. Historical M13/M26
hash mismatches block their source binding. Package versions are obtained
from distribution metadata, without importing the model-execution libraries.
A read-only Git HEAD query confirms the existing PR89 source identity.

## Resource and storage boundaries

Only this metadata process is lowered to nice19 and limited to at most1GiB
address space. Reading is serial, with a300-second budget and bounded
compressed/decoded bytes, line lengths and variable indices. This still
uses CPU and I/O on a shared host; its start/end and elapsed times are
recorded and must not be described as zero overhead.

No scheduler query/mutation or PR89 result-file access occurs. The script
creates one UUID-named private ZIP directly in the existing evidence root,
outside the PR89 stage; it creates no directory and writes nothing to home
or installed source. The ZIP contains a sanitized preflight report, a private
input-path map and member hashes. Raw LP data is not exported.

## Author CLI and transfer

The Codex temporary workspace contains pr94-preflight-medium-six.sh with
the exact tested Python wrapped by python -B - <<'PY'. Paste the entire
block in the existing tfm_env Bash session, including the final standalone
PY. It prints ARQUIVO_HPC, SHA256, INSTANCIAS_LOCALIZADAS,
PREFLIGHTS_LEITURA_COMPLETOS, PENDENCIAS, OTIMIZACOES_NOVAS=0 and BYTES_ZIP.

Then use the delivered pr94-transferir-preflight-medium.ps1 in local
PowerShell. It accepts only the expected output prefix, creates a new
local UUID filename, uses terminal-password SCP and compares SHA256.
Send the seven HPC lines and local hash/path. Passwords stay in the terminal.

Keep a partial report and errors for diagnosis. A completed read-only
preflight does not admit optimization, resource allocation or new training.
The source package, Start bindings, budget and executor checks remain
separate release gates. Fourteen synthetic tests cover successful reading,
unchanged inputs, missing/ambiguous files, historical mismatch, unsupported
or corrupt input, bounds on reading, path scope, exclusive output and the
absence of solver/ML/mutating APIs.

## Received return — 1 November 2026

The author-run preflight completed on dgx-dasci from23:06:06 to23:08:12 UTC (20:06:06–20:08:12 Fortaleza). All six originals were uniquely located and the bounded text inventory completed without reported issues. The private ZIP has2582 bytes and SHA256 c8c709a0f495baa0b1e060364544397c6d6c47f60421904b2f696212a304c8df. The receiver independently verified that digest, the archive CRCs and both member seals. Only the [sanitized receipt](preflight-return-20261101.json) is public; the private path map and archive are not uploaded.

M13/M26 match their historical original-file hashes. M5/M6/M9/M20 now also have observed source hashes, propagated to the cohort and54 new-cell candidates. These are identities of the original compressed inputs, not a completed root/graph/Start or solver-model binding. The preflight took125.837 seconds and read356,780,406 bytes for hashing plus618,538,568 decoded bytes. This is observed metadata-process work, not optimizer time, active CPU utilization or a budget for future inference.

| Parent | Variables observed | Declared binary variables | Continuous by difference | Rows observed | Matrix nonzero terms |
| --- | ---: | ---: | ---: | ---: | ---: |
| M5 | 1281600 | 1172800 | 108800 | 2400 | 2561600 |
| M6 | 1281600 | 1184000 | 97600 | 2400 | 2561600 |
| M9 | 1281600 | 1166400 | 115200 | 2400 | 2561600 |
| M13 | 1281600 | 1155200 | 126400 | 2400 | 2561600 |
| M20 | 1281600 | 1169600 | 112000 | 2400 | 2561600 |
| M26 | 1281600 | 1148800 | 132800 | 2400 | 2561600 |

All six share the observed total dimensions, but their binary/continuous composition and coefficient ranges differ. These structural observations do not establish a computational-difficulty ranking. Matrix terms are lexical counts; bounds and model feasibility were not independently validated by this text reader. All originals declare MAXIMIZE; the accepted runtime MINIMIZE correction remains unchanged. No new formulation certification is requested.

The input-identity subgate is now closed. Preparation source, root/graph/Start bindings, inference device, complete resources and executor admission remain open. There were zero new optimization, inference or training calls and zero scheduler mutations. PR89's source head was observed unchanged; no claim about its current jobs or new result receipt follows.
