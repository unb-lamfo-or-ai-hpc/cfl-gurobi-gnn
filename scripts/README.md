# Execution scripts

Scripts orchestrate package CLIs; scientific policy belongs in versioned
configuration and implementation modules. See the
[DaSCI launcher guide](slurm/dasci/README.md).

Only submit the stage whose upstream contracts have passed. A Slurm dependency
controls scheduling, not scientific acceptance. Do not modify the working
checkout or environment while jobs use it. This documentation branch does not
change active campaign launchers or submit any new jobs.

For PR #57-#59, keep plan creation, array execution, and audit submission
separate. The audit must depend on the complete array. PR #60 is a CPU-only
synthesis over accepted reports and must not invoke a solver. Every launcher
must use LF endings and resolve the repository explicitly rather than accepting
Slurm's spool directory as the project root.

