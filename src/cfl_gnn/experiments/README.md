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

