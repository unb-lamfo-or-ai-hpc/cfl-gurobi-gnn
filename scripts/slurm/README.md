# Slurm execution

Site-specific launchers live under [dasci](dasci/README.md). Resource requests,
job-array concurrency, solver threads, GPU allocation, and optimization time
limits are distinct controls. Record all of them.

A scheduler memory-quota wait is not a solver failure. A successful scheduler
exit is not sufficient acceptance: verify the report gate, eligibility, hashes,
and expected task population. Preserve failed and censored task records.

