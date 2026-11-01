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
