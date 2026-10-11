"""Disjoint timing and cost accounting; unknown preparation is never zero."""

import math
import time
from contextlib import contextmanager

PREPARATION = ("root", "features", "inference", "assembly_lp", "assembly_gnn")
EXECUTION = ("input_hash", "model_build", "optimize", "audit", "export", "other")


def seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid_duration")
    return float(value)


class StageClock:
    """Non-overlapping monotonic intervals; caller supplies GPU synchronization."""

    def __init__(self, clock=time.perf_counter):
        self.clock, self.active, self.records = clock, False, {}

    @contextmanager
    def measure(self, name, synchronize=None):
        if name not in PREPARATION + EXECUTION or self.active or name in self.records:
            raise ValueError("timing_region")
        self.active = True
        started, finished = None, False
        try:
            if synchronize:
                synchronize()
            started = self.clock()
            yield
            if synchronize:
                synchronize()
            elapsed = seconds(self.clock() - started)
            finished = True
        finally:
            self.active = False
            self.records[name] = {
                "seconds": elapsed if finished else None,
                "state": "complete" if finished else "failed_or_incomplete",
            }


def execution_costs(timing):
    """Map the existing solver's timing, whose 'other' INCLUDES export."""
    names = {
        "input_hash": "data_read_wall_time_seconds",
        "model_build": "model_build_wall_time_seconds",
        "optimize": "model_optimize_wall_time_seconds",
        "audit": "independent_audit_wall_time_seconds",
        "export": "solution_export_wall_time_seconds",
    }
    result = {name: seconds(timing[key]) for name, key in names.items()}
    total = seconds(timing["total_wall_time_seconds"])
    legacy_other = seconds(timing["other_wall_time_seconds"])
    residual = legacy_other - result["export"]
    if residual < -1e-6:
        raise ValueError("export_exceeds_other")
    result["other"] = max(0.0, residual)
    if not math.isclose(sum(result.values()), total, rel_tol=1e-8, abs_tol=1e-6):
        raise ValueError("timing_not_disjoint")
    return result


def end_to_end(method, preparation, execution, uses=7, worker_overhead=None):
    if method not in ("M0", "M1", "M2") or type(uses) is not int or uses <= 0:
        raise ValueError("cost_scenario")
    if set(execution) != set(EXECUTION):
        raise ValueError("execution_regions")
    base = sum(seconds(v) for v in execution.values())
    required = (
        ()
        if method == "M0"
        else (
            "root",
            "features",
            "inference",
            "assembly_lp" if method == "M1" else "assembly_gnn",
        )
    )
    missing = [k for k in required if preparation.get(k) is None]
    for key in required:
        if preparation.get(key) is not None:
            seconds(preparation[key])
    prep = None if missing else sum(seconds(preparation[k]) for k in required)
    overhead = None if worker_overhead is None else seconds(worker_overhead)
    complete_base = None if overhead is None else base + overhead
    complete = prep is not None and complete_base is not None
    return {
        "method": method,
        "execution_seconds": base,
        "worker_overhead_seconds": overhead,
        "full_execution_seconds": complete_base,
        "preparation_seconds": prep,
        "missing_preparation_regions": missing,
        "cold_end_to_end_seconds": complete_base + prep if complete else None,
        "amortized_end_to_end_seconds": complete_base + prep / uses
        if complete
        else None,
        "amortization_uses": uses,
        "counterfactual_method_cost_not_campaign_consumption": True,
    }


def campaign_preparation(preparation):
    """Count shared root/features/inference once, plus both start assemblies."""
    missing = [k for k in PREPARATION if preparation.get(k) is None]
    for key in PREPARATION:
        if preparation.get(key) is not None:
            seconds(preparation[key])
    return {
        "seconds": None
        if missing
        else sum(seconds(preparation[k]) for k in PREPARATION),
        "missing_regions": missing,
        "shared_dependencies_charged_once": True,
    }
