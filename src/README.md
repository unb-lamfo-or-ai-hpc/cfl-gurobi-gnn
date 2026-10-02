# Source layout

The installable Python package is [cfl_gnn](cfl_gnn/README.md). The repository
uses the standard `src` layout so imports resolve from an installed package or
from `PYTHONPATH=src` during tests. Invoke command modules as
`python3 -m cfl_gnn.cli.<module>`; `src` is not part of the import name.
