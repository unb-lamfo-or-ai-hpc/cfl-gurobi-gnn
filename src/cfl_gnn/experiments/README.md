# Methodological experiment contracts

These modules specify eligibility, sampling, budgets, and intervention semantics.
They do not establish runtime success by themselves.

[neural_guidance_policy.py](neural_guidance_policy.py) distinguishes the primary
Gurobi hint/control comparison from partial starts and exploratory recovery
methods. [mvp_contract.py](mvp_contract.py) preserves four-arm and augmentation
controls. Historical vertical-slice contracts remain identifiable.

Keep seed, parent population, coverage/radius sensitivity, and model-selection
rules fixed before inspecting held-out outcomes. A change requires a new
identified protocol, not an edited old report.

[pr58_guidance.py](pr58_guidance.py) defines the three-method validation policy
used by the current route: unguided control, root-LP partial start, and GNN
partial start. Its qualification result freezes the subsequent PR #59 test;
held-out outcomes cannot be used to retune the policy.

