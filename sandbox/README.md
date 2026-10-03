# Toy bipartite experiment

[toy_bipartite.py](toy_bipartite.py) is the preserved compatibility experiment
for the Gasse and Liang model paths. It synthesizes small variable–constraint
graphs; it is not a CFL benchmark instance generator or a scientific dataset.

The focused numerical suite imports this generator. To run the original
standalone experiment in a qualified environment:

```bash
python3 sandbox/toy_bipartite.py
```

The script has its own training budget and writes to `sandbox/toy_outputs/`.
Running it is not equivalent to a single unit-test step. Keep the legacy source
and outputs distinguishable from corrected, versioned Gasse confirmation runs.

