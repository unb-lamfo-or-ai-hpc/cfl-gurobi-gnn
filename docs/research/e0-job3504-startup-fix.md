# E0 job3504: startup-path regression and recovery

## What happened and what is known

The downloaded return is preserved in `docs/evidence/e0/job3504-return.json`,
SHA256 `13089cf7db93175c6abd09fc6b52d5f204ea6b024cf4a6809be6459562df5deb`.
Slurm reports FAILED, exit 2:0, elapsed zero seconds. The return has no inference,
runtime or plan members. The download itself passed its SHA256 check.
The later `ValueError: members` was a receiver error for this incomplete return,
not the cause of the job's failure. No new predictive result is admitted.

The submitted E0 shell script unconditionally derived SOURCE from BASH_SOURCE.
Slurm executes a transferred batch script, not necessarily the original file:
[sbatch documentation](https://slurm.schedmd.com/sbatch.html).
For a spool copy, the derived STAGE is outside the allowlisted E0 directory and
the script exits 2 before the batch marker and Python invocation. This is a
confirmed code defect consistent with the observed early failure. The private
stderr and actual spool path of job3504 have not been collected, so the historical
failure location is not independently traced. The recovery preflight additionally
requires absence of both the old batch marker and run directory.

This repeats a problem already handled in `operate_pr80_integrated.sh`; the E0
adaptation omitted the existing source-export pattern. Syntax and Python tests
were insufficient because they did not exercise relocated script execution.

## Correction and verification

- Submit exports E0_SOURCE and E0_PYTHON; batch uses E0_SOURCE and fails closed
  if missing. `--export=ALL` makes the environment handoff explicit.
- A Linux regression executes the actual resolution block from a simulated
  spool copy, verifies the exported checkout, rejects a missing export and checks
  the normal direct status path. This adds no scheduler or inference execution.
- The unchanged job3504 receipt is a regression fixture. Incomplete returns now
  produce a structured diagnostic with exit code 3, not an unexplained traceback.
  The receiver preserves the download and explicitly warns that it is incomplete;
  it never prints the successful-inference marker for this case.
- The Windows sandbox cannot launch Git Bash here; actual Bash regression is
  required to pass on both Linux CI versions before the replacement handoff.

## Continuation, unchanged scientific scope

Keep the failed stage and return untouched. A fresh, commit-pinned stage may be
submitted manually once after the exact-head CI passes and the read-only recovery
preflight checks the old receipt and absent execution markers. No retry loop or
automatic resubmission is added. No diagnostic Slurm job is needed.

The plan SHA remains
`e13ce0dacfb7142ec0a5bacd61f3f31a2153ae8056c37ae7123ecb9108bc20ab`:
two frozen models, ten test parents, at most twenty forwards, one GPU, four CPU
cores requested, 32 GiB, forty minutes. No model, split, threshold, dependency,
training, root solve or Gurobi optimization changes. Status and collect remain
nonblocking. PR81 remains draft until the E0 results and scoped comparisons are
reviewed; this correction does not request or authorize a merge.
