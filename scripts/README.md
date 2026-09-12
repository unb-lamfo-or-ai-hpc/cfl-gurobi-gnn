# Execution scripts

Scripts orchestrate package CLIs; scientific policy belongs in versioned
configuration and implementation modules. See the
[DaSCI launcher guide](slurm/dasci/README.md).

Only submit the stage whose upstream contracts have passed. A Slurm dependency
controls scheduling, not scientific acceptance. Do not modify the working
checkout or environment while jobs use it. This documentation branch does not
change active campaign launchers or submit any new jobs.

