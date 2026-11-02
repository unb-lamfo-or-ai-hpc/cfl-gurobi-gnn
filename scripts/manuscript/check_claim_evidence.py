"""Bind existing article numbers to public evidence; never execute research."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import string
from pathlib import Path, PurePosixPath

REQUIRED_CLAIMS = {
    "cpu_preserved_rows", "cpu_principal_rows", "cpu_historical_rows",
    "cpu_easy_rows", "cpu_medium_rows", "cpu_reported_targets",
    "cpu_censored_targets", "cpu_sensitive_rows", "gpu_loop_speedup",
    "gpu_job_speedup", "gpu_loop_efficiency", "gpu_f1_loss", "gpu_auc_loss",
    "gpu_selected_f1", "gpu_selected_auc", "gpu_loop_seconds", "gpu_job_seconds",
}
REQUIRED_SOURCES = {"cpu_main", "gpu_review", "gpu_timings", "gpu_metrics"}


def _source_path(repository: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (relative.is_absolute() or relative.parts[:2] != ("docs", "evidence")
            or ".." in relative.parts or "\\" in name or ":" in name):
        raise ValueError("unsafe_source_path")
    path = repository.joinpath(*relative.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(repository.resolve()):
        raise ValueError("unsafe_source_path")
    return path


def _section(article: str, identity: str) -> str:
    heading = re.search(r"(?m)^#{1,6} [^\n]*\{#" + re.escape(identity) + r"\}", article)
    if heading is None:
        raise ValueError("article_section_missing")
    end = re.search(r"(?m)^#{1,6} ", article[heading.end():])
    return article[heading.end():heading.end() + end.start()] if end else article[heading.end():]


def _value(metric: dict, sources: dict) -> str:
    source = sources[metric["source"]]
    if "json_pointer" in metric and "row" not in metric:
        value = source
        pointer = metric["json_pointer"]
        if not pointer.startswith("/"):
            raise ValueError("invalid_json_pointer")
        for part in pointer[1:].split("/"):
            value = value[part.replace("~1", "/").replace("~0", "~")]
    elif "row" in metric and "json_pointer" not in metric:
        if not isinstance(source, list):
            raise ValueError("csv_source_required")
        rows = [row for row in source
                if all(row.get(key) == expected for key, expected in metric["row"].items())]
        if len(rows) != 1:
            raise ValueError("source_row_not_unique")
        value = rows[0][metric["column"]]
    else:
        raise ValueError("ambiguous_metric_selector")
    if isinstance(value, bool):
        raise ValueError("boolean_is_not_a_measurement")
    value = float(value)
    scale, spec = metric.get("scale", 1), metric["format"]
    if not math.isfinite(value) or scale not in (-1, 1, 100) or spec not in {
        ".0f", ".2f", ".3f", ".6f",
    }:
        raise ValueError("invalid_numeric_format")
    return format(value * scale, spec)


def check_claim_evidence(manuscript: Path, repository: Path) -> list[str]:
    """Check coverage, source bytes, unambiguous selectors and scoped prose."""
    failures = []
    try:
        manifest = json.loads((manuscript / "supplement/claim-evidence.json").read_text(encoding="utf-8"))
        claims, records = manifest["claims"], manifest["sources"]
        ids, source_ids = [claim["id"] for claim in claims], [record["id"] for record in records]
        if (manifest["schema_version"] != 1
                or manifest["kind"] != "editorial_claim_evidence_not_scientific_certification"
                or manifest["governing_contract"] != "CFL-GNN-SCI-2026-10-22-R3"
                or set(ids) != REQUIRED_CLAIMS or len(ids) != len(REQUIRED_CLAIMS)
                or set(source_ids) != REQUIRED_SOURCES or len(source_ids) != len(REQUIRED_SOURCES)):
            return ["claim_evidence_coverage_invalid"]
        pending = manifest["pending_cpu"]
        if (pending["source_commit"] != "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5"
                or pending["final_return_received"] is not False
                or pending["result_claims"] != []):
            failures.append("claim_evidence_pending_cpu_promoted")
        article = (manuscript / "index.qmd").read_text(encoding="utf-8")
        sources = {}
        for record in records:
            path = _source_path(repository, record["path"])
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                failures.append("claim_source_hash_mismatch:" + record["id"])
                continue
            if record["format"] == "json":
                sources[record["id"]] = json.loads(raw)
            elif record["format"] == "csv":
                sources[record["id"]] = list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))
            else:
                raise ValueError("unsupported_source_format")
        for claim in claims:
            try:
                metrics, template = claim["metrics"], claim["article_template"]
                fields = list(string.Formatter().parse(template))
                names = {name for _, name, _, _ in fields if name is not None}
                if (names != set(metrics)
                        or any(name is not None and (not re.fullmatch(r"[a-z_][a-z0-9_]*", name) or spec or conversion)
                               for _, name, spec, conversion in fields)):
                    raise ValueError("invalid_article_template")
                statement = template.format(**{key: _value(metric, sources)
                                               for key, metric in metrics.items()})
                section = _section(article, claim["section"])
                if " ".join(statement.split()) not in " ".join(section.split()):
                    failures.append("claim_value_mismatch:" + claim["id"])
            except (KeyError, TypeError, ValueError, IndexError):
                failures.append("claim_selector_invalid:" + claim["id"])
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, IndexError):
        failures.append("claim_evidence_invalid")
    return failures
