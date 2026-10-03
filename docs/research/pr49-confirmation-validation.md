# PR49: mathematical validation and confirmation campaign

## Status and scope

This PR implements the audit-driven repairs and native guidance executors.
It does **not** certify that the 42-parent experiment has been trained or that
guidance improves optimization. Hardware execution and admissible medium labels
remain acceptance gates. A passing software inventory is not a feasibility proof.

The frozen confirmation population contains easy IDs 0--29 and medium IDs 0--6,
15--19: 42 parents, no hard instances. Canonical rotation 0 assigns 24 training,
10 validation, and 8 test parents. Seed 42 and 100 epochs are fixed. Historical
graphs and solutions are preserved; the 90-parent campaign is not submitted.

All CFL input models are forced to MINIMIZE. The erroneous original MAXIMIZE
sense is retained as provenance, never used as the effective research model.
Gurobi is the graph and independent mathematical audit authority; SCIP is a
comparison solver. Neither Pyomo nor one-graph-per-incumbent training is introduced.

## Implemented corrections

1. `validation.mathematical` independently checks named-variable coverage,
   finiteness, variable domains, integrality, linear rows, and the objective
   including its constant. The strict Gurobi graph builder invokes this audit.
2. Strict graph construction requires explicit constraint/variable edge order
   and an aligned, finite root-relaxation vector. No zero fallback is permitted
   on this route. Clipped/infinite raw-feature counts are recorded. Historical
   permissive builders remain readable for legacy reproduction, not confirmation.
3. A shared binary-target contract rejects general integer and fractional labels;
   it does not clamp arbitrary discrete values into BCE targets.
4. The legacy `gasse.py` blob remains unchanged. The opt-in
   `gasse_v2_alternating_prenorm` model fits variable-side normalization from
   updated constraint messages. Streaming moments use all training graphs,
   never validation or test; DDP ranks use the same complete reference population.
   Corrected checkpoints must be retrained and their model version retained.
5. Exact validation-threshold search is sorted/cumulative rather than quadratic.
   Training and validation losses share one figure. Partial engineering runs do
   not fabricate a validation curve. Optimizer-step training loss and validation
   loss have different measurement contexts and are labelled accordingly.
6. Graph EDA reports binary-target prevalence, parent counts and distributions.
   Structural projections use 17 outcome-free encoded descriptors, report
   effective rank/clusters, and explicitly reject degenerate structure. These
   are descriptive graph summaries, not learned GNN embeddings. Optional UMAP
   requires `umap-learn`; PCA remains available without it. Labels and solve
   outcomes are not projection inputs. Projections do not define the data split.
7. Held-out Gasse evaluation adds tie-aware average precision, Brier score, ECE,
   unweighted BCE, parent-macro metrics, constant-zero and root-LP diagnostics.
   Weighted-BCE scores are not claimed to be calibrated probabilities. Prediction
   bundles contain named predictions and checkpoint/MIP hashes, not target labels.

## Sprint A: execution gates

The inventory CLI creates `confirmation_inventory.json` and structural EDA.
`gate_status=passed` here means the expected graph files were found; inspect
`counts.gap_admissible`, `repair_parent_ids` and `training_ready` separately.
The inventory deliberately leaves `training_ready=false` until source labels and
strict Gurobi graphs have independent validation. A gap below 10% alone is not enough.

Before rescue, reuse a better existing solution only after checking its parent
MIP hash, full variable-name mapping, objective sense, feasibility and gap
provenance. The inventory does not automatically import arbitrary historical
solutions. Prepared repair plans are a fallback, not an instruction to discard
valid earlier work. The repair runner uses existing collectors, hash-validated
resume and isolated 3600/14400-second directories; it escalates only if the first
budget does not yield an admissible label. Solver errors remain errors.

After repair/migration, compose the strict 42-parent Gurobi graph/label manifest
with the existing builders and use `configs/training/gasse_confirmation_v2.json`
with the reconnected trainer. This protocol refuses a smaller or augmented
cohort. Do not remove missing medium parents, change the ceiling, or use test
labels to select a checkpoint. If any medium remains inadmissible, report the
campaign as incomplete and retain its censored evidence.

## Sprint B: execution semantics

The common paired four-arm intersection is distinct from the broad Gurobi
confirmation cohort. `paired_four_arm_confirmation_v2.json` selects the corrected
model while retaining common parent folds, original-only validation/test,
equal parent mass, and equal optimizer-step budgets. Missing SCIP coverage must
be disclosed; it does not justify calling a smaller paired experiment a
42-parent experiment. Existing augmentation limits remain three per train parent.

`run_native_neural_guidance` implements:

- Gurobi unguided control and native nonbinding `VarHintVal`/`VarHintPri`;
- partial MIP starts on Gurobi and SCIP;
- exploratory partial fixing and full-support local-branching neighborhoods;
- a fresh original-model recovery phase after every restrictive intervention,
  with only a primal start transferred and restricted dual bounds discarded.

Restricted optimization receives 20% of the budget; full-model recovery receives
the remaining optimization time. Coverage/radius values remain precommitted.
Reports retain the four time regions, native and common relative gaps, feasibility,
censoring, and first *observed* times to gap targets. Callback observation times
are not exact continuous-time crossing estimates. Phase-local restricted gaps
are not full-model certificates. Prediction inference is reported separately;
graph construction costs are not included, so end-to-end speedup claims are disabled.

The CLI requires original held-out MIP and checkpoint identities. These identities
support reproducibility, not a security signature or proof that a caller did not
manually alter a prediction bundle. Paired campaign assembly and aggregate
acceptance must also verify the source evaluation ledger before execution.

## Single DaSCI-DGX validation submission

From the repository root, with `tfm_env` active and a valid Gurobi licence:

```bash
git fetch origin
git switch feature/literature-backed-neural-guidance-policy
git pull --ff-only origin feature/literature-backed-neural-guidance-policy
sbatch scripts/slurm/dasci/submit_confirmation_validation.sbs
```

The launcher runs the full smoke suite with solver tests mandatory, then the
42-graph inventory, EDA and repair-plan preparation. It does not run the repair
array, train a network, evaluate test performance, or submit 90-parent jobs.
Its log is `slurm_cfl_confirmation_<job-id>.out`; the default result directory is
`data/analysis/confirmation/pr49_<job-id>`. An existing output directory is not
overwritten. Do not publish raw licence logs or machine-specific paths.

## Local verification and remaining evidence

CPU Torch/PyG numerical tests exercise the original toy generator, updated-message
prenorm, all-training streaming replay, finite gradients, toy overfitting,
checkpoint replay, and permutation/disjoint-union behavior. A native SCIP toy
checks restrictive and fresh-model recovery optima. Full native cross-solver tests
are marked pending when no working local Gurobi licence is available; the DGX
launcher makes that condition fail rather than silently skip.

No claim of GPU/DDP parity, 42-parent training, empirical solver superiority,
generalization to hard instances, or TRL 6 follows solely from these unit tests.

## PR50 acceptance plan

1. Consume the DGX validation inventory, reuse compatible labels, and execute
   only necessary medium-label rescue. Consolidate source/graph/label hashes.
2. Complete strict graph migration and audit the 42-parent split. Run exactly
   100 epochs with seed 42; collect joint loss curves and held-out diagnostics.
3. Assemble the separately reported paired intersection, train its four arms,
   and bind prediction bundles to the evaluation ledger. Execute primary native
   hint/control comparisons first; keep starts/recovery methods separate.
4. Produce audited descriptive tables and figures, native/common gap and timing
   comparisons, failure/censoring counts, and cohort/label-quality disclosures.

English-only repository documentation and dependency consolidation follow, then
the manuscript using the user-supplied Quarto template. The full 90-parent
campaign and manuscript extension remain last. PR readiness is a code-review
state; scientific acceptance still requires the runtime gates above.
