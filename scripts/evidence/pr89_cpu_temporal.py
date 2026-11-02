"""Prospective CPU12h observations. No solver import, scheduler or admission.

Actual callback timestamps bracket horizons; no interpolation or claim of
continuous exact hitting times. This adapter does not change the old recorder.
"""

import math

from pr86_attempt_instrumentation import require

PROTOCOL = "cpu12h_observed_thresholds_and_horizons_v1"
THRESHOLDS = (0.10, 0.05, 0.01, 0.0001)
HORIZONS = (3600, 14400, 28800, 43200)


def finite(value):
    return (
        float(value)
        if type(value) in (int, float) and math.isfinite(value) and abs(value) < 1e100
        else None
    )


def gap(primal, dual):
    if primal is None or dual is None:
        return None
    if primal == 0:
        return 0.0 if dual == 0 else None
    return abs(primal - dual) / abs(primal)


class Recorder:
    def __init__(self):
        self.previous = self.terminal = None
        self.crossings = {str(t): None for t in THRESHOLDS}
        self.brackets = {str(h): {"before": None, "after": None} for h in HORIZONS}
        self.count = 0

    def observe(self, seconds, primal, dual, event):
        require(finite(seconds) is not None and seconds >= 0, "observation_clock")
        require(self.terminal is None, "observation_after_terminal")
        require(event in {"MIP", "MIPSOL", "terminal"}, "observation_event")
        require(
            self.previous is None or seconds >= self.previous["seconds"],
            "nonmonotonic_observation",
        )
        primal, dual = finite(primal), finite(dual)
        relative = gap(primal, dual)
        point = {
            "seconds": seconds,
            "primal": primal,
            "dual": dual,
            "gap_fraction": relative,
            "event": event,
            "state": "no_incumbent"
            if primal is None
            else "unavailable_bound_or_infinite_gap"
            if relative is None
            else "solver_reported",
        }
        for threshold in THRESHOLDS:
            key = str(threshold)
            if (
                relative is not None
                and relative <= threshold
                and self.crossings[key] is None
            ):
                self.crossings[key] = {
                    "first_observed": point,
                    "previous_observation": self.previous,
                    "exact_continuous_crossing_claimed": False,
                }
        for horizon in HORIZONS:
            bracket = self.brackets[str(horizon)]
            if seconds <= horizon:
                bracket["before"] = point
            if seconds >= horizon and bracket["after"] is None:
                bracket["after"] = point
        self.previous = point
        self.count += 1
        if event == "terminal":
            self.terminal = point

    def finish(self):
        require(self.terminal is not None, "terminal_observation_missing")
        horizons = {}
        for h in HORIZONS:
            before, after = self.brackets[str(h)].values()
            horizons[str(h)] = {
                "state": "terminated_before_horizon"
                if self.terminal["seconds"] < h
                else "exact_observation"
                if before is not None and before["seconds"] == h
                else "bracketed"
                if before is not None and after is not None
                else "unavailable",
                "before": before,
                "after": after,
                "staleness_seconds": None if before is None else h - before["seconds"],
                "terminal_if_earlier": self.terminal
                if self.terminal["seconds"] < h
                else None,
                "interpolated": False,
            }
        return {
            "protocol_id": PROTOCOL,
            "clock": "monotonic_wall_since_optimize_dispatch",
            "observation_count": self.count,
            "first_observed_thresholds": {
                str(t): {
                    "state": "observed"
                    if self.crossings[str(t)] is not None
                    else "right_censored"
                    if self.terminal["primal"] is not None
                    else "unavailable",
                    "crossing": self.crossings[str(t)],
                    "followup_seconds": self.terminal["seconds"],
                }
                for t in THRESHOLDS
            },
            "horizons": horizons,
            "terminal": self.terminal,
            "numerical_eligibility": "requires_separate_scoped_review",
        }


def validate(value):
    require(value["protocol_id"] == PROTOCOL, "temporal_protocol")
    require(
        value["clock"] == "monotonic_wall_since_optimize_dispatch", "temporal_clock"
    )
    require(
        value["numerical_eligibility"] == "requires_separate_scoped_review",
        "temporal_not_certificate",
    )
    require(
        type(value["observation_count"]) is int and value["observation_count"] > 0,
        "observation_count",
    )
    terminal = value["terminal"]

    def point(p):
        require(
            finite(p["seconds"]) is not None
            and 0 <= p["seconds"] <= terminal["seconds"],
            "point_seconds",
        )
        for key in ("primal", "dual"):
            require(p[key] is None or finite(p[key]) == p[key], "point_finite")
        require(p["gap_fraction"] == gap(p["primal"], p["dual"]), "point_gap")
        require(p["event"] in {"MIP", "MIPSOL", "terminal"}, "point_event")
        expected = (
            "no_incumbent"
            if p["primal"] is None
            else "unavailable_bound_or_infinite_gap"
            if p["gap_fraction"] is None
            else "solver_reported"
        )
        require(p["state"] == expected, "point_state")

    point(terminal)
    require(terminal["event"] == "terminal", "terminal_event")
    require(set(value["horizons"]) == {str(h) for h in HORIZONS}, "horizon_keys")
    require(
        set(value["first_observed_thresholds"]) == {str(t) for t in THRESHOLDS},
        "threshold_keys",
    )
    for key, entry in value["first_observed_thresholds"].items():
        require(entry["followup_seconds"] == terminal["seconds"], "followup")
        crossing = entry["crossing"]
        if crossing is None:
            require(
                entry["state"]
                == ("unavailable" if terminal["primal"] is None else "right_censored"),
                "censoring",
            )
        else:
            require(
                entry["state"] == "observed"
                and crossing["exact_continuous_crossing_claimed"] is False,
                "crossing_scope",
            )
            p = crossing["first_observed"]
            point(p)
            require(
                p["gap_fraction"] is not None and p["gap_fraction"] <= float(key),
                "crossing_threshold",
            )
            prior = crossing["previous_observation"]
            if prior is not None:
                point(prior)
                require(
                    prior["seconds"] <= p["seconds"]
                    and (
                        prior["gap_fraction"] is None
                        or prior["gap_fraction"] > float(key)
                    ),
                    "crossing_bracket",
                )
    for key, entry in value["horizons"].items():
        h = int(key)
        before, after = entry["before"], entry["after"]
        require(entry["interpolated"] is False, "interpolation_forbidden")
        for p in (before, after):
            if p is not None:
                point(p)
        require(before is None or before["seconds"] <= h, "horizon_before")
        require(after is None or after["seconds"] >= h, "horizon_after")
        expected = (
            "terminated_before_horizon"
            if terminal["seconds"] < h
            else "exact_observation"
            if before is not None and before["seconds"] == h
            else "bracketed"
            if before is not None and after is not None
            else "unavailable"
        )
        require(entry["state"] == expected, "horizon_state")
        require(
            entry["staleness_seconds"]
            == (None if before is None else h - before["seconds"]),
            "staleness",
        )
        require(
            entry["terminal_if_earlier"]
            == (terminal if terminal["seconds"] < h else None),
            "early_terminal",
        )
    return value
