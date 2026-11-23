# Current 66-input inventory — 23 November 2026

The [sanitized receipt](current-cohort66-receipt-20261123.json) closes **stored-file inventory reception** for the current NPAD inputs: **30 easy, 30 medium and six hard**, all named .lp.gz, with no missing original. It does not certify decoded model content, gzip integrity or the full CFL runtime.

The author's complete JSON reproduces SHA256 `048b823a865af4988088b9f80388e759a7d227ef1f45e8e796a653077170d83c`. Reconstructing the 66-line SHA256SUMS file from its rows reproduces `6dc39f36376813e2c06b1db63a21c2f3b77d5b606344204364ffe0ad9f5f8728`. The reviewed checker reported fresh hashes, valid gzip magic, stable input metadata, no errors and 1,810,985,584 stored bytes read in 10.27 seconds. The raw file-stat payload and source files were not independently downloaded. The [current compressed-file identities](current-input-hashes-20261123.json) contain only relative benchmark paths and hashes, not private locations or raw MILP data.

## Interpretation

All 66 compressed hashes differ from the DGX representations; all 66 stored lengths agree. Seven hashes are unchanged from the earlier NPAD catalogue. The researcher reports extracting the TAR containers and gzip-compressing the LPs. These observations support a new NPAD compressed-file identity baseline; they do not prove that gzip headers alone explain the differences or establish decoded LP equivalence. Honor the researcher's no-decompression decision. No further input transfer or repeated hashing is required for the next **read-only checkout inspection**.

The earlier six-file private-stage verifier returned exit 2 because it targeted another location/representation. That result remains historical. It does not make the now-complete shared cohort missing. Preserve the unused private incoming stage; no cleanup or deletion follows automatically.

## Remaining historical artifacts

The verified job 3930 index has a disjoint 299-file classification:

| Group | Files | Stored logical bytes | Current disposition |
| --- | ---: | ---: | --- |
| Original model inputs | 66 | 1,810,985,584 | Current NPAD cohort inventoried; no additional original copy needed |
| Original family ZIPs | 3 | 5,580,158,205 | Preserve on DGX; avoid duplicate transfer |
| Historical graph/root/label/prediction/Start assets | 226 | 6,838,697,772 | Preserve; select a reproduction subset only when needed |
| Canonical historical checkpoint | 1 | 124,450 | Preserve; no load, training use or model replacement |
| Migration metadata ZIPs | 2 | 1,608,848 | Preserve provenance |
| Uncommitted editorial file | 1 | 163 | Preserve; do not apply to the approved source automatically |

These are snapshot member sizes, not new NPAD consumption or RAM requirements. Existing NPAD presence of non-model artifacts is not established by an instance catalogue. No historical label, root or Start becomes an MVP 3.0 observation. The complete 168 GB historical dataset and active DGX interpreter dependencies remain in place; this classification is not a deletion approval.

## Next bounded handoff

TR-03 has received the current input inventory and preservation index. TR-04 proceeds with preparation of an **isolated checkout of the approved develop revision**, plus read-only checks of pyproject requirements, both environment inventories and current data metadata. Do not install the project or any dependency automatically, import Gurobi/Torch, invoke project entry points, copy a license, train or solve.

A full real-data technical qualification, if required later, needs a separate concrete scope and resource decision. Scientific MVP 3.0 implementation remains behind the reviewed English protocol and budget in Draft PR #99. The original environment, historical evidence, main/develop refs and publication remain unchanged.
