# Collect jobs3729–3734 after the campaign becomes terminal

Prepared1November2026 for the author's CLI intervention. This is collection
of existing approved jobs, not execution authority for a new experiment.
PR89 source9ab7823c, starts, resources, parameters and order remain frozen.

## Scope and timing

The author's latest undated accounting snapshot reports3729COMPLETED,
3730RUNNING and3731–3734PENDING. Its elapsed times are not query timestamps.
There are still54 received/reconciled result cells. A completed job does not
become a received result until its artifacts have been transferred and checked.

| Job | Parent | Physical thread cap | Historical method | Presentation |
| --- | --- | ---: | --- | --- |
| 3729 | M12 | 8 | M0 | B |
| 3730 | M12 | 8 | M1 | R |
| 3731 | M12 | 8 | M2 | G |
| 3732 | M12 | 16 | M1 | R |
| 3733 | M12 | 16 | M2 | G |
| 3734 | M12 | 16 | M0 | B |

This table follows the frozen plan, not an assumed B/R/G submission order.
The collector reads every existing submission identity and verifies the
job-to-index binding across all60 jobs3675–3734.

Wait until the remaining jobs have finished. Run the prepared Bash block
once in the existing `tfm_env` session on `dgx-dasci`. It issues one read-only
`sacct` query for all60 IDs, preserving root/step accounting and UTC query
start/end. If a root or a reported step of the final six is still active,
it exits with `AGUARDE_ESTADOS_NAO_TERMINAIS` **before creating a ZIP**.
There is no polling loop or automatic subsequent action.

Terminal failures, cancellations, timeouts and nonzero exit codes are
preserved, not relabelled as success. Missing optional result/debug files
are listed. Their collection does not authorize repair, rerun or retry.
An ambiguous identity, changed seal or size-cap breach stops the export.

## What is exported

The [stdlib-only exporter](pr89_terminal_tail_export.py) verifies host,
account, environment, Git HEAD/tree, plan/preflight/authorization hashes,
all submission bindings, and present tail child/nested/log seals. It copies
only whitelisted files for indices54–59: submission and result receipts,
supervision/costs/checks, launch/intent/held profiles, original compressed
solution vectors, closed solver logs and private batch output. It also
includes the original controls, complete job/cell map, accounting response
and a new manifest.

The first54 result bundles are reused from the two previously reconciled
archives; they are not duplicated or re-audited. The manifest explicitly
references their hashes. M12's original model was already transferred in
the forensic archive with SHA256
`bf5f13a9d6e34de77312c10e613f8b677e7b2548eec97e2a3c03cb9cae4105c2`;
its bytes are not copied again. All six tail cells must bind that same model.

Solution-file hashes are observed at collection; closed-log hashes are
verified historical seals when present in the child. The collector does
not decompress, score, round or otherwise change any solution vector.
No solver/campaign library is imported and no installed source is written.

The sole new HPC file is
`terminal-tail-jobs3729-3734.private.zip` in the existing CPU12h stage.
Creation is exclusive: a prior or partial file cannot be overwritten.
No new directory or home file is created. Input size caps are8MiB per JSON,
32MiB per log/batch output,64MiB per compressed vector and768MiB in total.
Copying/hashing uses CPU and disk I/O; it is intentionally deferred until
the campaign is terminal. All copied bytes are checked again inside the ZIP.

Success prints `ARQUIVO_HPC`, `SHA256`, `JOBS_TERMINAIS=6`, the six
`JOBS_COLETADOS`, `JOBS_CAMPANHA_TERMINAIS=60`, `ARQUIVOS_AUSENTES`,
`OTIMIZACOES_NOVAS=0` and `BYTES_ZIP`. Preserve all eight lines.
The archive is private local evidence, not a GitHub/publication artifact.

## Copy/paste and transfer

The local Codex delivery provides a ready-to-paste
`pr89-coletar-restantes-3729-3734.sh`: it wraps the exact Python source in
`python -B - <<'PY'`. Paste the entire file, including the final standalone
`PY`, in the existing Bash session. `-B` suppresses bytecode writes. There
is no need to install the collector into the HPC source tree.

After successful export, use the delivered local PowerShell block
`pr89-transferir-restantes-3729-3734.ps1`. It asks for the printed hash,
uses SCP with the author's terminal password, writes a new UUID-named file
in the existing Codex temporary directory and compares SHA256 before
printing `ARQUIVO_LOCAL`. It does not overwrite earlier local files.
Send the eight HPC lines and the local hash/path for independent review.

On any error, preserve the output and any partial ZIP. Do not delete or
overwrite it, alter the queue or invoke prepare/authorize/submit/solve.
The earlier data and this tail form the inputs to60-cell reconciliation;
the manifest's false final/scientific flags prevent collection alone from
being mistaken for scientific closeout. They do not redefine the agreed
reception/reconciliation gate or erase failed/missing cells.

## Validation

Eighteen synthetic tests pass: complete six-job export/all60 accounting,
root/step active-state refusal, missing/duplicate/foreign accounting,
failed-terminal capture, absent-file disclosure, control/submission/nested
and log identity rejection, exclusive creation, size cap, concurrent
mutation, path scope, and absence of solver/polling/mutating calls.
The PowerShell block passes parser validation. These checks do not assert
that the final six jobs have finished or that their results are qualified.
