"""Bounded Gurobi14 callback capture; no model-changing callback operations."""

import math

from .contract import require


def available(value, infinity=1e100):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or abs(value) >= infinity
    ):
        return {"value": None, "missing_reason": "native_unavailable_or_infinite"}
    return {"value": value, "missing_reason": None}


class NativeObserver:
    """One callback per explicitly invoked model, retaining bounded point evidence."""

    def __init__(self, api, matrix, store, stage):
        self.api, self.matrix, self.store, self.stage = api, matrix, store, stage
        self.root_ordinal = 0
        self.callback_ordinal = 0
        self.captured_root = None
        self.failure = None
        self.native_thread_lines = []
        self.start_messages = []
        self.presolve = {}

    def _get(self, model, name):
        code = getattr(self.api.GRB.Callback, name, None)
        if code is None:
            return {
                "value": None,
                "missing_reason": "callback_field_not_available_in_API",
            }
        return available(model.cbGet(code), self.api.GRB.INFINITY)

    def __call__(self, model, where):
        callback = self.api.GRB.Callback
        if (
            where == callback.POLLING
            or self.failure is not None
            or self.captured_root is not None
        ):
            return
        try:
            self._observe(model, where)
        except Exception as error:
            self.failure = {
                "type": type(error).__name__,
                "reason": "native_callback_or_capture_failure",
                "callback_ordinal": self.callback_ordinal,
            }
            # Preserve the error if the sink is healthy; never mask callback failure.
            try:
                self.store.append(
                    {"kind": "callback_failure", **self.failure}, critical=True
                )
            finally:
                model.terminate()

    def _observe(self, model, where):
        callback = self.api.GRB.Callback
        if where == callback.MESSAGE:
            message = model.cbGet(callback.MSG_STRING)
            if "Thread count" in message and len(self.native_thread_lines) < 16:
                self.native_thread_lines.append(message.rstrip("\r\n"))
            if ("MIP start" in message or "MIP Start" in message) and len(
                self.start_messages
            ) < 64:
                self.start_messages.append(message.rstrip("\r\n"))
            return
        names = {
            callback.PRESOLVE: "PRESOLVE",
            callback.MIP: "MIP",
            callback.MIPSOL: "MIPSOL",
            callback.MIPNODE: "MIPNODE",
        }
        optional = ("SIMPLEX", "BARRIER", "PDHG", "NLBAR")
        names.update(
            {
                getattr(callback, name): name
                for name in optional
                if hasattr(callback, name)
            }
        )
        if where not in names:
            return
        self.callback_ordinal += 1
        frame = {
            "kind": "native_callback",
            "callback_ordinal": self.callback_ordinal,
            "where": names[where],
            "native_runtime": self._get(model, "RUNTIME"),
            "native_Work": self._get(model, "WORK"),
            "native_memory_GB": self._get(model, "MEMUSED"),
            "native_peak_memory_GB": self._get(model, "MAXMEMUSED"),
        }
        if where == callback.PRESOLVE:
            for name in (
                "PRE_COLDEL",
                "PRE_ROWDEL",
                "PRE_SENCHG",
                "PRE_BNDCHG",
                "PRE_COECHG",
            ):
                self.presolve[name] = self._get(model, name)
            frame["presolve"] = dict(self.presolve)
        if where in (callback.MIP, callback.MIPSOL, callback.MIPNODE):
            prefix = names[where]
            frame.update(
                {
                    name: self._get(model, f"{prefix}_{name}")
                    for name in ("OBJBST", "OBJBND", "NODCNT", "SOLCNT", "PHASE")
                }
            )
        if where == callback.MIP:
            frame["ITRCNT"] = self._get(model, "MIP_ITRCNT")
            frame["CUTCNT"] = self._get(model, "MIP_CUTCNT")
        if where == callback.MIPSOL:
            # MIPSOL_OBJ may differ from OBJBST and need not improve it.
            frame["candidate_objective"] = self._get(model, "MIPSOL_OBJ")
            if self.stage != "root_relaxation":
                values = list(model.cbGetSolution(self.matrix.native_variables))
                require(
                    len(values) == len(self.matrix.variables),
                    "Incomplete original MIPSOL vector",
                )
                frame["candidate_vector"] = self.store.put_vector(values)
        if where == callback.MIPNODE:
            frame["node_status"] = self._get(model, "MIPNODE_STATUS")
            count = frame["NODCNT"]["value"]
            if count == 0:
                self.root_ordinal += 1
                frame["root_event"] = {
                    "ordinal": self.root_ordinal,
                    "cut_state": "pre_cut"
                    if self.root_ordinal == 1
                    else "later_cut_pass",
                    "cut_pass": self.root_ordinal - 1,
                }
                if (
                    self.stage == "root_relaxation"
                    and frame["node_status"]["value"] == self.api.GRB.OPTIMAL
                ):
                    values = list(model.cbGetNodeRel(self.matrix.native_variables))
                    require(
                        len(values) == len(self.matrix.variables),
                        "Incomplete original root vector",
                    )
                    descriptor = self.store.put_vector(values)
                    require(
                        descriptor["sha256"] is not None,
                        "Mandatory root capture exceeds declared storage envelope",
                    )
                    frame["root_vector"] = descriptor
                    self.captured_root = frame
        # Specific continuous progress is secondary to the native MIP trajectory.
        for prefix, fields in {
            "SIMPLEX": ("SPX_ITRCNT", "SPX_OBJVAL"),
            "BARRIER": ("BARRIER_ITRCNT", "BARRIER_PRIMOBJ", "BARRIER_DUALOBJ"),
            "PDHG": ("PDHG_ITRCNT", "PDHG_PRIMOBJ", "PDHG_DUALOBJ"),
        }.items():
            if names[where] == prefix:
                frame["phase_progress"] = {
                    name: self._get(model, name) for name in fields
                }
        critical = "candidate_vector" in frame or "root_vector" in frame
        stored = self.store.append(frame, critical=critical)
        if stored is None and critical:
            self.failure = {
                "type": "CaptureLimit",
                "reason": "mandatory_point_event_limit",
                "callback_ordinal": self.callback_ordinal,
            }
            model.terminate()
        elif self.captured_root is not None:
            model.terminate()

    def summary(self):
        return {
            "root_events": self.root_ordinal,
            "callback_events": self.callback_ordinal,
            "root_captured": self.captured_root is not None,
            "failure": self.failure,
            "native_thread_lines": self.native_thread_lines,
            "start_processing_messages": self.start_messages,
            "Start_incumbent_attribution": "native_messages_only_no_inference",
            "presolve": self.presolve,
        }
