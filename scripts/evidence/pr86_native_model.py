"""Exception-safe ownership for PR86, reusing the frozen mathematical adapter.

The historical adapter is hash-bound to job3506. Do not rewrite it to repair
new execution: specialize only resource ownership, not model construction.
"""

from cfl_gnn.solvers.neural_guidance import NativeModel as HistoricalModel


class NativeModel(HistoricalModel):
    def __init__(self, path, solver, budget):
        if solver != "gurobi":
            raise ValueError("pr86_gurobi_only")
        self.model = self.env = None
        try:
            super().__init__(path, solver, budget)
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    def close(self):
        model, env = self.model, self.env
        self.model = self.env = None
        try:
            if model is not None:
                model.dispose()
        finally:
            if env is not None:
                env.dispose()
