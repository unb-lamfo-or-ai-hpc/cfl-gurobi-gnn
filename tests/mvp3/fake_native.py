"""Invented API double. Never imports gurobipy or acquires a license."""

from types import SimpleNamespace as NS

from cfl_gnn.mvp3.contract import approved_contract
from cfl_gnn.mvp3.native import private_parameter

CALLBACKS = "POLLING MESSAGE MSG_STRING PRESOLVE MIP MIPSOL MIPNODE SIMPLEX BARRIER PDHG RUNTIME WORK MEMUSED MAXMEMUSED PRE_COLDEL PRE_ROWDEL PRE_SENCHG PRE_BNDCHG PRE_COECHG MIP_OBJBST MIP_OBJBND MIP_NODCNT MIP_SOLCNT MIP_PHASE MIP_ITRCNT MIP_CUTCNT MIPSOL_OBJ MIPSOL_OBJBST MIPSOL_OBJBND MIPSOL_NODCNT MIPSOL_SOLCNT MIPSOL_PHASE MIPNODE_OBJBST MIPNODE_OBJBND MIPNODE_NODCNT MIPNODE_SOLCNT MIPNODE_PHASE MIPNODE_STATUS SPX_ITRCNT SPX_OBJVAL BARRIER_ITRCNT BARRIER_PRIMOBJ BARRIER_DUALOBJ PDHG_ITRCNT PDHG_PRIMOBJ PDHG_DUALOBJ".split()


class FakeModel:
    def __init__(self):
        self.ModelSense = -1
        self.NumQNZs = self.NumQConstrs = self.NumGenConstrs = self.NumSOS = 0
        self.ObjCon = 0.0
        self.variables = [
            NS(VarName=f"x{i}", VType="B", LB=0.0, UB=1.0, Obj=1.0, index=i, X=1.0)
            for i in range(20)
        ]
        self.constraints = [NS(ConstrName="capacity", Sense=">", RHS=20.0)]
        self.SolCount = self.NumStart = self.calls = 0
        self.defaults = {
            **approved_contract()["solver"]["profiles"]["incumbent"],
            "Cuts": -1,
        }
        self.parameters = dict(self.defaults)
        self.closed = self.terminated = False
        self.values = {name: 0.0 for name in CALLBACKS}
        self.values.update(
            RUNTIME=0.01,
            WORK=0.001,
            MEMUSED=0.001,
            MAXMEMUSED=0.001,
            MIPSOL_OBJ=20.0,
            MIPSOL_OBJBST=21.0,
            MIPSOL_OBJBND=18.0,
            MIPNODE_OBJBND=18.0,
            MIPNODE_STATUS=2.0,
        )
        self.solution = [1.0] * 20

    def getVars(self):
        return self.variables

    def getConstrs(self):
        return self.constraints

    def getRow(self, constraint):
        return NS(
            size=lambda: 20, getVar=lambda i: self.variables[i], getCoeff=lambda i: 1.0
        )

    def update(self):
        pass

    def setParam(self, name, value):
        self.parameters[name] = value

    def getParamInfo(self, name):
        if private_parameter(name):
            raise AssertionError("Credential metadata must never be queried")
        return (
            name,
            type(self.defaults[name]),
            self.parameters[name],
            -1,
            1e100,
            self.defaults[name],
        )

    def cbGet(self, code):
        return self.values[code]

    def cbGetSolution(self, variables):
        return list(self.solution)

    def cbGetNodeRel(self, variables):
        return list(self.solution)

    def terminate(self):
        self.terminated = True

    def optimize(self, observer):
        self.calls += 1
        observer(self, "POLLING")
        observer(self, "PRESOLVE")
        observer(self, "MIPNODE" if self.parameters["Presolve"] == 0 else "MIPSOL")
        self.SolCount = 1
        self.Status = 11 if self.terminated else 2
        self.Runtime, self.Work = 0.02, 0.002
        self.ObjVal = self.ObjBound = 20.0
        self.MIPGap = 0.0

    def dispose(self):
        self.closed = True


def fake_api(model=None):
    model = model or FakeModel()
    names = list(model.defaults) + [
        "WLSAccessID",
        "WLSSecret",
        "CSManager",
        "ServerPassword",
        "CloudAccessID",
        "TokenServer",
        "LicenseID",
    ]
    environment = NS(started=False, closed=False)

    def start():
        environment.started = True

    def close():
        environment.closed = True

    environment.start, environment.dispose = start, close
    api = NS(
        GRB=NS(
            Callback=NS(**{name: name for name in CALLBACKS}),
            Param=NS(**{name: name for name in names}),
            MINIMIZE=1,
            OPTIMAL=2,
            INFINITY=1e100,
            UNDEFINED=1e101,
        ),
        gurobi=NS(version=lambda: (14, 0, 0)),
        Env=lambda empty: environment,
        read=lambda path, env: model,
    )
    return api, model, environment
