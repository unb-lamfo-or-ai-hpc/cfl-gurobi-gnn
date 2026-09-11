# Literature-backed neural-guidance policy

## Methodological boundary

Neural Diving predicts partial integer assignments and asks a MIP solver to
complete the unassigned variables. Assignment coverage is therefore an
experimental parameter, and fixing a variable is not equivalent to suggesting
its value. A bound equality removes every solution that disagrees with the
prediction; a native hint does not.

Nair et al. formulate Neural Diving through multiple partial assignments and
smaller residual MIPs. Yoon et al. subsequently show that assignment coverage
materially affects primal solution quality. These results rule out treating one
arbitrary deterministic hard-fixing fraction as a neutral baseline.

Primary research references:

- Vinod Nair et al., *Solving Mixed Integer Programs Using Neural Networks*,
  <https://arxiv.org/abs/2012.13349>.
- Taehyun Yoon et al., *Threshold-aware Learning to Generate Feasible Solutions
  for Mixed Integer Programs*, <https://arxiv.org/abs/2308.00327>.
- Matteo Fischetti and Andrea Lodi, *Local Branching*, Mathematical
  Programming 98 (2003), <https://doi.org/10.1007/s10107-003-0395-5>.

## Native interventions

Gurobi variable hints use `VarHintVal` and `VarHintPri`. The values influence
heuristics and branching throughout the search but do not fix a variable.
Gurobi MIP starts instead ask the solver to construct an initial feasible
solution from a complete or partial assignment. These mechanisms answer
different questions and are reported separately.

Official Gurobi references:

- <https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html>
- <https://docs.gurobi.com/projects/optimizer/en/current/reference/fileformats/otherformats.html>

PySCIPOpt supports partial primal solutions and submission through SCIP's
solution interfaces. This supplies a matched partial-start comparison, not a
claim that SCIP exposes an exact equivalent of Gurobi variable hints.

Official SCIP/PySCIPOpt references:

- <https://pyscipopt.readthedocs.io/en/latest/api/model.html>
- <https://www.scipopt.org/doc/html/FAQ.php>

## Precommitted hierarchy

1. Compare Gurobi variable hints with an unguided Gurobi control.
2. Compare deterministic partial starts within Gurobi and SCIP.
3. Treat confidence-based partial fixing and local branching as exploratory
   restricted phases followed by mandatory recovery on the original model.
4. Preserve 1, 5, and 10 percent coverage sensitivity and 0.1, 0.5, and
   1 percent local-branching radius sensitivity without test-based selection.
5. Use 3,600 seconds for the development screen and reserve 14,400 seconds for
   the precommitted confirmation, never to rescue a method selectively after
   observing its test performance.

The primary outcomes are terminal relative MIP gap and wall time spent inside
the native optimization call. Total, input-read, model-build, and optimization
times remain separate. Time-limited runs are right-censored evidence rather
than failures or missing observations.

PR #49 freezes and audits these semantics. It intentionally performs no solver
run. PR #50 is responsible for native Gurobi and PySCIPOpt adapters, fresh
process isolation, paired execution, recovery, and result aggregation.

