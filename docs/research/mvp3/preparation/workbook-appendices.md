# Workbook and appendix guide

The [English planning workbook](mvp3-preparation-workbook-EN.xlsx) complements, rather than replaces, scientific Appendices A-D in the approved plan. Its calculations use the approved decision register and its working tables distinguish planned records from observations.

| Appendix | Title | Location | Role |
| --- | --- | --- | --- |
| A | Mathematical and learning specification | Protocol Appendix A | Graph features, fixed parameter sharing, loss, gradient equivalence and dataset/predictor acceptance. |
| B | Root/Start decision procedures | Protocol Appendix B | Root vector capture, completion diagnosis and memory/interruption evidence. |
| C | Conditional Benders specification | Protocol Appendix C | Hard-only diagnosis, mathematical equivalence, numerical audit and separate release. |
| D | Scientific acceptance checklist | Protocol Appendix D | S1-S6 acceptance milestones and the decision/artifact required. |
| W1 | Planning workbook | mvp3-preparation-workbook-EN.xlsx | Sprints, budgets, hypotheses/design, acceptance, instance register and planned evaluation slots. |
| W2 | Machine-readable planning data | planning-registers.json | Canonical preparation data; no observed research results or frozen E/M split IDs. |

## Workbook use

Sprints presents planned packages and outcomes. Budget calculates the reservation, working-time, training and resource envelopes from labelled inputs. Hypotheses and design supplies the research propositions and experimental controls. Acceptance records the required evidence and leaves decision/evidence/date fields empty. Instances lists 66 original IDs with unfrozen E/M roles. Evaluation reserves 45 method slots without results or invented test-parent IDs. Appendices maps scientific and working appendices to their sources.

Editable planning drivers are distinguished from formula cells. Changing them is a sensitivity check, not approval of a new protocol: compare any proposed change with the approved decision register before release. Results are maintained by the later versioned analytical pipeline and immutable receipts, not entered into this planning workbook as substitute evidence.

## Machine-readable companions

planning-registers.json is the canonical preparation dataset for the workbook. CSV companions expose hypotheses, Sprints, instances and evaluation slots for GitHub review. Blank numeric fields mean no observation, not zero. E/M parent IDs in evaluation slots remain blank until S1 freezes the accepted split. The workbook builder performs documentary calculations and renders review ranges; it has no solver, training, network or Slurm call.
