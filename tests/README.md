# Verification suite

The [smoke suite](smoke) includes schema and contract checks, numerical
Torch/PyG regressions, and native solver tests. It is not entirely dependency-free.
Test counts vary with installed optional dependencies and license availability.

From a qualified environment at the repository root:

```bash
PYTHONPATH=src python3 -m pytest tests/smoke -q -rs
PYTHONPATH=src python3 -m pytest tests/smoke/test_gasse_numerical.py -q -rs
```

The numerical tests retain the [toy bipartite generator](../sandbox/toy_bipartite.py)
as a compatibility input and exercise corrected prenormalization. They do not
substitute for a 100-epoch real-instance train/validation run.

For the native guidance tests in a licensed environment:

```bash
CFL_REQUIRE_SOLVER_TESTS=1 PYTHONPATH=src python3 -m pytest \
  tests/smoke/test_native_guidance_execution.py -q -rs
```

That flag makes missing Gurobi support fail in the tests that honor it; inspect
the full skip report because not every optional test uses that flag. CPU tests
do not establish CUDA or DDP parity. Record warnings, skips, software versions,
and the exact commit.

The documentation checks protect download URLs, internal README links, and
methodological distinctions. Editorial-only changes do not authorize rewriting
artifact hashes or claiming fresh native solver validation.

