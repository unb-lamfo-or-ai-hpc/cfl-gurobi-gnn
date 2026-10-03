# Diagnostic utilities

The [diagnostics](diagnostics) directory contains source-recovery and artifact
inspection helpers. [audit_legacy_pipeline_recovery.py](diagnostics/audit_legacy_pipeline_recovery.py)
supports the recorded legacy-to-current comparison; it is not a substitute for
runtime model validation.

Pickle inspection must be restricted to trusted research artifacts: loading
pickle can execute code. Do not inspect arbitrary downloaded objects in a
credential-bearing environment. Preserve source files and report findings
without overwriting historical evidence.

