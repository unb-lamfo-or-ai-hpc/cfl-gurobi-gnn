"""Author CLI entry; --help is inert and execution requires the concrete release."""
# ruff: noqa: E402 -- run from a checkout without installing historical extras

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from cfl_gnn.mvp3.qualification import main

if __name__ == "__main__":
    raise SystemExit(main())
