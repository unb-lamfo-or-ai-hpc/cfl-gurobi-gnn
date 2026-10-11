# Experiment protocol

## Required record for every run

Record the following before execution:

- protocol ID and source commit;
- parent IDs, cohort, role, and partition;
- method arm and whether the start is none, relaxation-derived, or GNN-derived;
- model/checkpoint and normalization hashes;
- Gurobi version, Python version, parameters, seed, objective sense, gap and
  time limits;
- physical CPU cores, thread cap, GPU count/type, memory limit, partition,
  wall limit, and requeue policy;
- input, receipt, and public-output SHA256 values.

## Data separation

Partitioning is performed at the parent-instance level. Derived samples never
cross from validation or test into training. Labels are generated only for
authorized training parents and are never used to select a test start.

The easy and medium strata are reported separately. A table must state the
number of parents, number of derived artifacts, number of attempted runs,
number of qualified runs, and number excluded, with the exclusion reason.

## Solver comparison

For each eligible parent and each thread cap in `{1, 2, 4, 8, 16}`, compare
the three arms under matched instance, seed, stopping rule, and resource
contract. Report preparation cost separately from solver cost. A partial start
must be checked for variable-order identity, bounds, integrality policy,
feasibility, and the exact number of values supplied.

The root-relaxation arm is a control: its values come from the verified LP
relaxation and are not predictions from the GNN. The GNN arm is a separate
control: its values come from the frozen model and must be evaluated without
using the target labels.

## Reporting

Report primal objective, best bound, relative gap, time to first incumbent,
time to termination, preparation time, memory, CPU allocation, GPU allocation,
and solver status. Include paired differences and confidence/dispersion
summaries where the number of qualified pairs permits them. Never infer a
performance result from a receipt that is marked partial, unqualified, or
scientifically ineligible.
