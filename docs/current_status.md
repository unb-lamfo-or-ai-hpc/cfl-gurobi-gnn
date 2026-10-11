# Current status

Updated: 2026-10-09

## Integrated baseline

`develop` contains the merged MVP 2.0 baseline through PR #82 at commit
`91630762bf0b86ec153e2882c42dc83161eebe4a`. The baseline includes the E0
easy three-method executor evidence for job 3506, the bounded numerical and
resource audits, and the published CPU comparison tables and figures.

The evidence is scientific input, not a blanket claim that every method or
parent has been qualified. Results remain stratified by parent, method,
threads, and resource allocation.

## Active work

PR #83 is a separate draft branch for the installed M13/M26 medium-artifact
continuation. Its first inventory is preserved with SHA256
`9e73c05c776b12dc2b8132c8904cc462b9ce90735e4ebea74101d15537ad08b9`.
It contains two original MILP byte objects and eight metadata candidates. The
inventory does not prove that ten valid graphs or ten solver runs exist.

The follow-up inspection is intentionally read-only and scoped to the pinned
JSON files plus known sibling names. It does not rescan the dataset, deserialize
graphs, use labels to select starts, execute Gurobi, submit Slurm jobs, or train.

## Open gates

- Complete the bounded semantic inspection of M13/M26 and classify available
  root/graph/checkpoint artifacts.
- Keep any partial or inconsistent receipt and explain the limitation; never
  convert missing data into zero-cost or zero-runtime evidence.
- Only after a qualified preparation artifact exists, publish a minimal
  three-method manifest and a separately reviewed resource budget.
- Maintain the five Gurobi thread caps (1, 2, 4, 8, 16) in future paired
  comparisons, without silently repeating already qualified runs.
- Prepare the final E0/C/D/E evidence tables and figures before release review.

## Not yet claimed

No statement here admits M13/M26 to training, test performance, scientific
promotion, or a new solver allocation. Main synchronization remains a later
release decision and is not part of this context PR.
