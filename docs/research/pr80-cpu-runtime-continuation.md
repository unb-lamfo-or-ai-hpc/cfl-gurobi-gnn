# PR80: isolated CPU runtime after job 3500

## What, how and why

The operator's metadata inventory reports Python 3.10.20, x86_64, glibc 2.35,
torch 2.1.2+cu121, PyG 2.7.0, NumPy 1.26.4, SciPy 1.15.3, gurobipy 13.0.1,
and packaging 26.0. It is a current metadata observation, not historical
environment attestation or an import test. Job 3500 remains preserved as
[one runtime-blocked parent and 53 unattempted parents](pr80-job3500-runtime-diagnosis.md).

Use a **new, isolated Python venv for CPU numerical auditing only**, without
system site packages. Do not upgrade `tfm_env`, retrain a model, regenerate a
graph/label, or repeat Sprint B. This is a manually initiated technical
continuation after an identified environment defect, not automatic retry.

### Version choice

The new audit runtime pins torch **2.10.0+cpu**, PyG 2.7.0, NumPy 1.26.4,
SciPy 1.15.3, gurobipy 13.0.1 and packaging 26.0. Python remains 3.10.
PyTorch's second restricted-unpickler advisory,
[GHSA-63cw-57p8-fm3p](https://github.com/pytorch/pytorch/security/advisories/GHSA-63cw-57p8-fm3p),
affects versions through 2.9.1 and is patched in 2.10.0. Thus merely upgrading
to 2.6 is insufficient for the current documented loader policy. The auditor
minimum is raised to 2.10; there is no `weights_only=False` fallback.
This choice addresses those published advisories, not a universal safety claim.

The pinned CPython-3.10/Linux-x86_64/manylinux-2.28 CPU wheel is listed in the
[official PyTorch CPU index](https://download.pytorch.org/whl/cpu/torch/), with
SHA256 `a280ffaea7b9c828e0c1b9b3bd502d9b6a649dc9416997b69b84544bd469f215`.
glibc 2.35 exceeds that wheel's platform minimum. No CUDA wheel, optional PyG
compiled extension, torchvision or torchaudio is required by this auditor.
[PyG's installation guide](https://pytorch-geometric.readthedocs.io/en/2.7.0/install/installation.html)
documents the minimal installation without optional compiled extensions.
Actual installed compatibility is still tested, not inferred from these pages.

Top-level versions are pinned. Transitive dependencies are resolved from PyPI
as binary wheels and retained in `environment.freeze.txt` and the private pip
installation report with artifact URLs/hashes. This is **not** a fully locked
transitive specification before installation. The return binds the freeze hash;
the files remain on HPC for reproduction and later review. No hidden package
installation occurs during a job. Failure to obtain a wheel stops preparation.

## Sequence and conditions

1. Require all four exact-source CI arms (Ubuntu/Windows, Python 3.10/3.12).
2. Create a fresh stage under `/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/`.
   Fetch the published immutable source SHA, not a moving branch. Preserve
   `numeric-13bcc3ef50f8` and `tfm_env` unchanged.
3. Run offline tests, then `operate_pr80_numeric.sh prepare`. It creates only
   `STAGE/venv` and local preparation evidence; package/temp files stay under
   the stage. pip uses official indexes, no source compilation, no download
   retries, and bounded timeouts. Existing partial preparation is not reused.
4. Preparation tests exact versions, real imports, NumPy/SciPy interoperability,
   CPU-only torch, and restricted roundtrip of a tiny **synthetic** PyG graph.
   It does not read research graphs or start a Gurobi environment/license.
5. `submit` repeats that preflight using the exact `STAGE/venv/bin/python3`
   **before** creating a submission claim or calling Slurm. Any failure means
   no submission. The command returns immediately after one `sbatch`.
6. The single technical job retains one node, one CPU, 16 GiB and 16 minutes,
   no GPU/requeue/retry. A 30-second batch preflight precedes the existing
   900-second audit, inside the scheduler ceiling. Children retain their
   90-second/16-GiB bounds. Numerical tolerances and the 54 unique parents are
   unchanged. The license path is still the existing authorized file; no
   license copying or credential export.
7. `status` is one-shot. After a terminal state, `collect` produces one
   `audit-return.json` containing the numerical receipt and three sanitized
   runtime checks, plus the job ID and environment-freeze hash. Partial numeric
   results remain partial. Repeated collection is read-only when bytes match;
   differing existing export bytes are rejected, not overwritten.
8. Download that one file using one SCP connection. Verify its SHA256 against
   `AUDIT_RETURN_SHA256`, then independently review cohort/parent states and
   runtime identity. Do not interpret Slurm completion or a smoke test as
   scientific/numerical admission. Training, E0 and merge remain gated.

## Operator commands after installing the exact-source worktree

The chat handoff supplies the immutable source SHA and the initial worktree
creation. All following commands are also versioned here. The chosen stage is
`/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-cpu-v2`.

```bash
OP=/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-cpu-v2/source/scripts/evidence/operate_pr80_numeric.sh
bash "$OP" prepare && bash "$OP" submit
```

If preparation or preflight fails, preserve the stage and return the sanitized
runtime JSON/error. Do not rerun prepare or submit. If a job ID was printed,
only query or collect it:

```bash
OP=/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-cpu-v2/source/scripts/evidence/operate_pr80_numeric.sh
bash "$OP" status
# Run only after terminal state:
bash "$OP" collect
```

Single-connection Windows download, without raw logs or pip reports:

```powershell
$Expected = (Read-Host 'Cole AUDIT_RETURN_SHA256 (64 caracteres)').Trim().ToLowerInvariant()
if ($Expected -notmatch '^[0-9a-f]{64}$') { throw 'SHA256 invalido' }
$Destination = Join-Path $PWD ('pr80-cpu-' + $Expected.Substring(0,12))
if (Test-Path -LiteralPath $Destination) { throw 'Destino existente: preservar' }
New-Item -ItemType Directory -Path $Destination -ErrorAction Stop | Out-Null
$File = Join-Path $Destination 'audit-return.json'
scp 'vrcelestino@dgx-dasci.ujaen.es:/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/numeric-cpu-v2/audit-return.json' $File
if ($LASTEXITCODE -ne 0) { throw 'Transferencia falhou: preservar, sem retry' }
if ((Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected) { throw 'Hash divergente' }
$Result = Get-Content -LiteralPath $File -Raw | ConvertFrom-Json
if ($Result.protocol_id -ne 'sprint_c_cpu_audit_return_v1' -or $Result.training_admitted -cne $false -or $Result.raw_logs_included -cne $false) { throw 'Escopo inesperado' }
$Result.numeric.cohorts | ConvertTo-Json -Depth 5
Write-Host "PR80_CPU_TRANSFER_HASH_OK: $Destination"
```

This transfer check is not independent numerical admission. Return the
directory, hash and accounting; no repeat submission, E0 or merge is implied.
