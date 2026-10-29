# Supplementary methods and evidence guide

This supplement explains how neural predictions enter the facility-location
solver and how the reported evidence is interpreted. It provides background
for readers familiar with optimization or machine learning who may not
specialize in both.

## Reading the supplement

The [methods explanation](gnn-methods-audit.md) follows the information path
from coefficients and a root-relaxation vector to neural scores and a partial
Start. It introduces the terminology before the equations and uses a schematic
example to explain why R matches G's assignment counts without copying its
variable choices.

The [configuration reference](configuration-reference.md) identifies the
data inputs, graph encoding, fixed hyperparameters, validation-selected settings,
Gurobi parameter map and separate GPU configuration. Fixed-revision GitHub
links identify the files behind the values; unexported effective settings
remain distinct from documented defaults.

The [sensitivity discussion](sensitivity-review-plan.md) distinguishes
unmeasured search variability, neural configuration sensitivity and mechanism
ablations. These are directions for further study, not completed experiments.

## Populations and evidence chains

| Evidence chain | Unit and scope | Public source | Interpretation boundary |
| --- | --- | --- | --- |
| Historical optimization archive | Six medium optimization-test parents; separate predictive cohort | [Imported manifest](../results/current/pr60_scientific_evidence_manifest.json) | Original populations, budgets and influence diagnostics are retained |
| Principal CPU analysis | Ten exposed parents, seed42, 150 method/cap rows | [Summary](../../docs/evidence/methodology-20261019/summary.json) and [rows](../../docs/evidence/methodology-20261019/seed42_main.csv) | 97 reported terminal targets and 53 censures; the 30 sensitive M4/M12 rows are a subset |
| Matched GPU training | One seed42 serial1/DDP4 pair; ten predictive-test parents | [Timing records](../../docs/evidence/pr87/jobs3673-3674/timings.csv) and [predictive metrics](../../docs/evidence/pr87/jobs3673-3674/aggregates.csv) | Training speed, selected quality and assigned resources have separate meanings |

B/R/G denote historical methods M0/M1/M2. Parent identifiers occupy a separate
field: instance M0 and method M0 are different objects. Method/cap rows,
binary variables and repeated seeds do not enlarge the independent parent
count. The admitted learning cohort contains 54 parents with 34/10/10
training/validation/test roles. Historical test exposure limits independent
generalization.

## Interpreting prediction and optimization evidence

| Observation | Supported interpretation | Unsupported substitution |
| --- | --- | --- |
| Validation-selected checkpoint and threshold | The stated validation rule chose the retained model and decision threshold | Evidence that every fixed hyperparameter is optimal |
| Matched R/G support and one count | Equal supplied-value budget and class composition | An independent LP-only baseline or a causal selector ablation |
| Loaded Start message | Solver acceptance under its numerical conventions | Exact feasibility, optimality or a later performance gain |
| Recorded 10% crossing | The descriptive threshold was observed by that callback time | Attainment of the much tighter terminal stopping criterion |
| Terminal time limit | The solver's observation budget ended | A successful time-to-target or evidence that every earlier threshold was missed |
| Lower selected F1 with faster training | A speed-quality trade-off within the matched training comparison | Preserved predictive quality or downstream solver improvement |

The [metric definitions](../../docs/research/mvp2-r3-metrics-and-reproducibility.md)
distinguish terminal status, threshold-specific censoring, unavailable values
and numerical restrictions. An observed crossing is not an exact continuous
hitting time. Horizon brackets retain their actual timestamps and staleness;
terminated trajectories are not extended to later horizons.

M4/M12 remain visible with metric-specific limitations. Solver acceptance
of original floating-point vectors does not certify feasibility of rounded
copies or exact optimality. A longer runtime does not itself resolve numerical
sensitivity.

## Numerical provenance

A displayed value has a defined population, metric, checkpoint, averaging
rule and clock. A training-loop speedup cannot replace whole-job speedup;
a selected-model F1 cannot be replaced by a terminal-epoch F1.
[claim-evidence.json](claim-evidence.json) binds 17 principal CPU/GPU claim
groups to four versioned public source files.

The records identify source revisions and file-content hashes, named JSON
fields or unique CSV selections, sign conventions, percent conversion and
displayed rounding. Historical tables and figures retain their separate
import manifest. Automated source checks support traceability of recorded
values; they do not independently rescore predictions or establish scientific
validity. The map is not an exhaustive verification of every sentence.

## Clocks and computational costs

Solver Runtime, dispatch follow-up, scheduler elapsed time, queueing,
preparation and training measure different intervals. Assigned GPU-hours
equal allocated GPUs multiplied by job elapsed time; they are neither measured
active GPU time nor energy use. R shares G-dependent preparation, so reused
or amortized cost scenarios differ from cold application measurements.

Threshold fractions 0.10/0.05/0.01/0.0001 correspond to 10/5/1/0.01%.
The one-hour archive and the twelve-hour protocol retain separate stopping
rules and observation definitions. Parameter specifications in the configuration
reference are not outcome measurements and do not extend the evidence scope
of the reported comparisons.
