# Resource budgets and acceptance criteria

## Primary reservation envelope

| Stage | Calls | Maximum solver-hours | Reserved job-hours |
| --- | ---: | ---: | ---: |
| Root-relaxation feature | 66 | 528 | 792 |
| Incumbents and labels | 66 | 528 | 792 |
| B/R/G evaluation | 45 | 360 | 540 |
| Primary total | 177 | 1416 | 2124 |
| Conditional diagnosed-hard feasibility work | up to 6 | up to 48 | up to 72 |

Every primary call has at most 28800 native optimisation seconds and a 12-hour Slurm envelope. The ceiling is two jobs and two Gurobi sessions. Stage barriers give 33 + 33 + 23 = 89 two-slot waves: 44.5 days if every slot uses 12 hours. This is a reservation scenario before queues and additional work, not an observed runtime prediction.

The historically informed working scenario is 72 easy calls x 1 hour plus 105 medium/hard calls x 8 hours = 912 optimisation-hours. Adding 0.25 job-hours per call gives 956.25 job-hours; dividing by two slots and 24 hours gives a 19.92-day lower bound before stage barriers and scheduling. It is separate from the 44.5-day reservation scenario.

## Hardware and training scopes

The planned Intel allocation is one exclusive node, one task and 64 logical Slurm CPUs (32 physical cores). Easy/medium calls request 192 GiB on intel-256 and hard calls request 384 GiB on intel-512. Native Threads=0 is retained; allocation, native thread count and observed activity remain distinct. These requested envelopes are not assertions of guaranteed user quotas.

Serial learning uses one V100 and DDP uses four V100s, with six-hour job caps per arm. Model-requested use is at most 30 GPU-hours, and exclusive GPU-node occupancy is at most 12 node-hours. On an eight-device node, whole-node device-slot occupancy is a different quantity, at most 96 slot-hours. Artifact-processing allowances are 12 hours for graph/dataset assembly, 8 for inference/Starts and 4 for reconciliation, totalling 24 CPU job-hours. The primary 2124 job-hours plus those 24 and 12 GPU-node hours sum to 2160 job/node occupancy-hours only under those explicit accounting scopes; they are not CPU core-hours or model GPU-hours. The conditional hard diagnostic adds at most 72 job-hours if separately released. Benders has no standing execution budget in this dossier.

## Acceptance by Sprint

### S1. Scientific contract and instrumentation

Required artifact: Versioned contracts, 42/9/9 parent manifest, event/clock definitions and audit/collection design.

Acceptance: All approved parameters, mathematical identities and accounting scopes are represented; synthetic/offline checks establish callback and missingness semantics.

Dependency: Approved protocol v3. Next decision: Release only a concrete reviewed preparation batch through the author CLI.

### S2. Root features and qualified labels

Required artifact: 66 feature and 66 label dispositions; accepted learning dataset.

Acceptance: Every planned parent has a reconciled disposition. Only complete audited features and admissible incumbent labels enter the accepted dataset; incomplete coverage receives an explicit author decision before training.

Dependency: Accepted S1 contracts and author release. Next decision: Accept dataset coverage and freeze its exact identities.

### S3. Equivalent-work learning and policy freeze

Required artifact: Two matched-work training returns; frozen predictor and independent guidance policies.

Acceptance: Serial 1 V100 and DDP 4 V100 share initialisation, transformations and 4200 global updates; validation alone selects the predictor. R/G thresholds, ranking, support and ties are frozen before evaluation.

Dependency: Accepted S2 dataset and author training release. Next decision: Seal predictor, transforms and Start policies.

### S4. Paired B/R/G evaluation

Required artifact: 45 planned cells on 15 original parents, including explicit failed/censored dispositions.

Acceptance: Each parent has B/R/G under common mathematical, hardware and solver contracts; hashes, completion status, audit eligibility and target-specific follow-up reconcile to the 45-cell plan.

Dependency: Frozen S3 artifacts and reviewed author evaluation release. Next decision: Freeze qualified trajectories and metric-specific eligible cohorts.

### S5. Comparative analysis and computational economics

Required artifact: Paired time factors, attainment, primal/dual effort, training quality and cost/reuse analyses.

Acceptance: T_B/T_G and T_R/T_G use comparable clocks and positive qualified times; censoring and denominators remain visible. Preparation and recurring costs are separated; claims trace to eligible instance-level observations.

Dependency: Reconciled S4 data and training/preparation records. Next decision: Freeze derived datasets, scripts and scoped interpretations.

### S6. Scientific synthesis and dissemination

Required artifact: Coauthor-reviewed article and appendices, reproducibility package and submission materials.

Acceptance: All methods, figures and claims trace to approved contracts and qualified evidence. Scientific limitations, data rights and reproducibility are reviewed; merge/publication/submission receive their specific approvals.

Dependency: Accepted S5 synthesis and coauthor review. Next decision: Researcher-authorised dissemination; target submission 18 March 2027.

## Release and scientific success

Accepting an implementation requires the stated artifacts, traceability and appropriate checks. Accepting a dataset requires explicit eligibility and coverage, not an assumed count of successful solves. An observed lack of G benefit is a valid scientific result. Concrete HPC releases fix source, inputs, environment, resources, attempt identity and collection procedure. Failure/retry, a new arm, resource expansion, Benders, merge and publication retain their applicable specific decisions.
