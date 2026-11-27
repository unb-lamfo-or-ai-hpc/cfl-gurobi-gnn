"""Portable author entry, inert until an explicit stage is selected."""
# ruff: noqa: E402 -- bootstrap exact checkout or verified portable package

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from cfl_gnn.mvp3.production.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
