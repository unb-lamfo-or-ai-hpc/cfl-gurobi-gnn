"""Reconcile a supervised attempt with disjoint solver-function timings.

This module performs arithmetic only. The interval excludes scheduler queueing,
parent orchestration outside supervise(), and preparation in other processes.
"""

import math

import pr86_cost_accounting as costs


def reconcile(supervision, result, method, preparation=None, uses=7):
    wall = costs.seconds(supervision["supervisor_wall_seconds"])
    exit_code = supervision["child_exit_code"]
    if type(exit_code) is not int:
        raise ValueError("child_exit_code")
    successful = (
        exit_code == 0
        and supervision["guard_stop"] is None
        and result is not None
        and result.get("gate_status") == "passed"
    )
    value = {
        "scope": "supervised_attempt_including_process_start_and_log_flush",
        "supervisor_wall_seconds": wall,
        "complete_attempt": successful,
        "solver_function_seconds": None,
        "outside_solver_function_seconds": None,
        "execution_regions_seconds": None,
        "preparation_seconds": None,
        "cold_attempt_seconds": None,
        "amortized_attempt_seconds": None,
        "whole_job_end_to_end_qualified": False,
        "preparation_costs_qualified": False,
    }
    # Validate the cost scenario even for failed attempts; never turn a stopped
    # process into a successful zero-cost observation or discard its wall time.
    if method not in ("M0", "M1", "M2") or type(uses) is not int or uses <= 0:
        raise ValueError("cost_scenario")
    if not successful:
        return value
    regions = costs.execution_costs(result["timing"])
    function_seconds = sum(regions.values())
    overhead = wall - function_seconds
    if overhead < 0:
        raise ValueError("supervisor_shorter_than_solver_function")
    estimate = costs.end_to_end(
        method, preparation or {}, regions, uses=uses, worker_overhead=overhead
    )
    if not math.isclose(estimate["full_execution_seconds"], wall, abs_tol=1e-6):
        raise ValueError("attempt_cost_reconciliation")
    value.update(
        solver_function_seconds=function_seconds,
        outside_solver_function_seconds=overhead,
        execution_regions_seconds=regions,
        preparation_seconds=estimate["preparation_seconds"],
        cold_attempt_seconds=estimate["cold_end_to_end_seconds"],
        amortized_attempt_seconds=estimate["amortized_end_to_end_seconds"],
        preparation_costs_qualified=not estimate["missing_preparation_regions"],
    )
    return value
