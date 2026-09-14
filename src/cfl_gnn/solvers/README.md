# Native solver integration

Gurobi is the priority solver and graph/mathematical audit authority.
[pyscipopt_solution.py](pyscipopt_solution.py) supports direct SCIP comparison;
there is no Pyomo reformulation.

[neural_guidance.py](neural_guidance.py) separates native variable hints,
partial starts, and exploratory restrictive methods. Restricted phases cannot
supply full-model dual certificates; recovery uses the original model.
[gurobi](gurobi) preserves hint and benchmark compatibility utilities.

Record the actual solver version, seed, threads, status, objective, bound, gap,
timing regions, and censoring. Never expose license credentials in publication
artifacts. A callback observation is not an exact serialization of a search node.

