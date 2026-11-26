"""Pinned, secondary native-log interpretation with explicit unavailable fields."""

import math
import re
from importlib.metadata import version
from pathlib import Path

from .audit import quantity
from .contract import require
from .journal import durable_json, file_sha256
from .native import private_parameter

PARSER_VERSION = "4.0.1"
PARSER_WHEEL_SHA256 = "bc75fa6cc60fcfb37c42c95a8c97836ea158b2ae9105205ecb85e49d7fa92955"
SUMMARY_FIELDS = (
    "Version",
    "Status",
    "Runtime",
    "Work",
    "ObjVal",
    "ObjBound",
    "MIPGap",
    "SolCount",
    "NodeCount",
    "Threads",
    "PhysicalCores",
    "LogicalProcessors",
    "NumConstrs",
    "NumVars",
    "NumNZs",
    "PresolvedNumConstrs",
    "PresolvedNumVars",
    "PresolvedNumNZs",
    "PresolveTime",
    "NoRelTime",
    "NoRelBestBd",
    "NoRelBestSol",
)


def private_line(line):
    parameter = re.search(
        r"(?:Set parameter\s+)?([A-Za-z][A-Za-z0-9_]*)\s+(?:to value|=)", line
    )
    return bool(parameter and private_parameter(parameter.group(1))) or bool(
        re.search(
            r"(?i)license|licensed|username|user name|access.?id|secret|password|token|cloudpool|compute server|client log",
            line,
        )
    )


def observed(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return quantity(None, "not_emitted_or_not_supported_by_pinned_parser")
    if hasattr(value, "item"):
        value = value.item()
    require(type(value) in (int, float, str, bool), "Unsupported parser scalar")
    if isinstance(value, float) and not math.isfinite(value):
        return quantity(None, "not_emitted_or_not_supported_by_pinned_parser")
    return quantity(value)


def parse_native_log(path, output, *, source_kind, maximum_bytes=64 * 1024 * 1024):
    """Keep raw log private and immutable; publish only selected structured data.

    The released low-level per-log summaries avoid public summary()'s implicit
    default-parameter filling. No parser-supplied default is native evidence.
    """
    require(
        source_kind
        in ("synthetic_fixture", "author_cli_native_qualification", "primary_native"),
        "Explicit log provenance required",
    )
    require(version("gurobi-logtools") == PARSER_VERSION, "Unreviewed logtools version")
    import gurobi_logtools as glt

    path, output = Path(path), Path(output)
    require(
        type(maximum_bytes) is int and 0 < path.stat().st_size <= maximum_bytes,
        "Log outside the admitted byte envelope",
    )
    original = file_sha256(path)
    output.mkdir(parents=True, exist_ok=False)
    sanitized = output / "sanitized.log"
    removed = 0
    with (
        path.open("r", encoding="utf-8", errors="replace") as source,
        sanitized.open("x", encoding="utf-8", newline="\n") as target,
    ):
        for line in source:
            if private_line(line):
                removed += 1
                continue
            target.write(line)
    parsed = glt.parse(str(sanitized))
    summaries, progress = [], []
    for _, number, parser in parsed.parsers:
        raw = dict(parser.get_summary())
        # Merged summaries can carry root-LP OPTIMAL/Runtime into truncated MIP.
        tree = parser.nodelog_parser.get_summary()
        terminal = parser.termination_parser.get_summary()
        for name in ("Runtime", "Work", "ObjVal", "ObjBound", "MIPGap", "NodeCount"):
            raw[name] = tree.get(name)
        raw["Status"] = terminal.get("Status")
        continuous = parser.continuous_parser.get_summary()
        summaries.append(
            {
                "log_number": number,
                "fields": {name: observed(raw.get(name)) for name in SUMMARY_FIELDS},
                "continuous_phase": {
                    "clock_origin": "native_continuous_log_origin_unqualified",
                    "fields": {
                        name: observed(continuous.get(name))
                        for name in (
                            "Status",
                            "Runtime",
                            "Work",
                            "ObjVal",
                            "RelaxObj",
                            "RelaxTime",
                            "RelaxIterCount",
                            "IterCount",
                            "BarIterCount",
                        )
                    },
                },
            }
        )
        for section, reader, origin in (
            (
                "nodelog",
                parser.nodelog_parser,
                "optimize_entry_native_log_rounded_seconds",
            ),
            (
                "rootlp",
                parser.continuous_parser,
                "native_continuous_log_origin_unqualified",
            ),
            ("norel", parser.norel_parser, "NoRel_heuristic_entry_not_optimize_entry"),
        ):
            # Restrict output to numeric progress fields; paths/free text excluded.
            rows = []
            for row in reader.get_progress():
                rows.append(
                    {
                        name: observed(value)
                        for name, value in row.items()
                        if name
                        in {
                            "Time",
                            "Incumbent",
                            "BestBd",
                            "BestObj",
                            "Gap",
                            "CurrentNode",
                            "RemainingNodes",
                            "ItPerNode",
                            "Iteration",
                            "Objective",
                            "PInf",
                            "DInf",
                            "PObj",
                            "DObj",
                            "PRes",
                            "DRes",
                            "Compl",
                            "Obj",
                            "PrimalInf",
                            "DualInf",
                            "Depth",
                            "IntInf",
                        }
                    }
                )
            progress.append(
                {
                    "log_number": number,
                    "section": section,
                    "clock_origin": origin,
                    "rows": rows,
                    "missing_reason": None if rows else "no_supported_section_progress",
                }
            )
    require(file_sha256(path) == original, "Raw native log changed during parsing")
    result = {
        "schema_version": "mvp3-s1b-logparse-v1",
        "parser": {
            "distribution": "gurobi-logtools",
            "version": PARSER_VERSION,
            "official_wheel_sha256": PARSER_WHEEL_SHA256,
            "entry": "parse_then_pinned_per_log_summary_and_progress",
            "implicit_parameter_defaults_used": False,
        },
        "source_kind": source_kind,
        "raw_log_sha256": original,
        "sanitized_log_sha256": file_sha256(sanitized),
        "redacted_line_count": removed,
        "summaries": summaries,
        "progress": progress,
        "qualification": "secondary_log_evidence_only_native_API_and_independent_audits_required",
        "missing_status_means": "missing_or_truncated_or_unsupported_never_imputed_as_optimal",
        "native14_qualification": "synthetic_does_not_qualify_native14"
        if source_kind == "synthetic_fixture"
        else "requires_review_of_actual_native_return",
    }
    durable_json(output / "parsed.json", result)
    return result
