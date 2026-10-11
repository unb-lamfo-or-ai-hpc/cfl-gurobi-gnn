"""Bounded, read-only LP structure and historical report audit; no solver imports."""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
import re
from pathlib import Path

from verify_sprint_c_artifacts import AuditStop, Reader

PROTOCOL = "pr85_existing_lp_and_training_context_v1"
NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
NAME = r"[A-Za-z_][A-Za-z0-9_.,()\[\]{}]*"
TOKEN = re.compile(rf"{NUMBER}|{NAME}|<=|>=|[+\-=<>]")
HEADERS = {
    "maximize": "objective",
    "maximum": "objective",
    "max": "objective",
    "minimize": "objective",
    "minimum": "objective",
    "min": "objective",
    "subject to": "rows",
    "such that": "rows",
    "st": "rows",
    "s.t.": "rows",
    "bounds": "bounds",
    "binaries": "binary",
    "binary": "binary",
    "bin": "binary",
    "generals": "integer",
    "general": "integer",
    "gen": "integer",
    "integers": "integer",
    "end": "end",
}


def require(condition, code):
    if not condition:
        raise AuditStop(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def tokens(text):
    result, end = [], 0
    for match in TOKEN.finditer(text):
        require(not text[end : match.start()].strip(), "unsupported_lp_syntax")
        result.append(match.group())
        end = match.end()
    require(not text[end:].strip(), "unsupported_lp_syntax")
    return result


def family(name):
    # No original identifiers, indices, file paths or matrix rows are exported.
    stem = re.match(r"[A-Za-z_]+", name).group().strip("_")
    require(len(stem) <= 32, "lp_family_name_limit")
    return stem or "anonymous"


def linear(text):
    pieces, index, sign = tokens(text), 0, 1
    terms, constant = [], 0.0
    while index < len(pieces):
        if pieces[index] in ("+", "-"):
            sign = -1 if pieces[index] == "-" else 1
            index += 1
        require(index < len(pieces), "incomplete_lp_expression")
        value = 1.0
        explicit = re.fullmatch(NUMBER, pieces[index]) is not None
        if explicit:
            value = float(pieces[index])
            index += 1
        value *= sign
        require(math.isfinite(value), "nonfinite_lp_coefficient")
        if index < len(pieces) and re.fullmatch(NAME, pieces[index]):
            terms.append((pieces[index], value))
            index += 1
        else:
            require(explicit, "unsupported_lp_term")
            constant += value
        sign = 1
    require(math.isfinite(constant), "nonfinite_lp_constant")
    return terms, constant


def aggregates(terms):
    groups = {}
    for name, value in terms:
        group = groups.setdefault(family(name), [])
        group.append(value)
    require(len(groups) <= 64, "lp_family_count_limit")
    return {
        key: {
            "terms": len(values),
            "minimum": min(values),
            "maximum": max(values),
            "negative": sum(v < 0 for v in values),
            "zero": sum(v == 0 for v in values),
        }
        for key, values in sorted(groups.items())
    }


def lp_summary(lines, tick=lambda: None):
    """Restricted linear-LP lexical summary, not a replacement solver parser."""
    section, buffer, expanded = None, [], 0
    variables, domains = set(), {"binary": set(), "integer": set()}
    rows, samples, bounds = collections.Counter(), [], collections.Counter()
    sample_groups = collections.Counter()
    structures = {}
    objective, sense = None, None

    def flush():
        nonlocal buffer, objective
        if not buffer:
            return
        text = " ".join(buffer)
        buffer = []
        if ":" in text:
            text = text.split(":", 1)[1]
        if section == "objective":
            require(objective is None, "multiple_lp_objectives")
            terms, constant = linear(text)
            variables.update(name for name, _ in terms)
            objective = {"constant": constant, "families": aggregates(terms)}
        elif section == "rows":
            parts = re.split(r"(<=|>=|=)", text)
            require(len(parts) == 3, "unsupported_lp_row")
            terms, constant = linear(parts[0])
            rhs_terms, rhs = linear(parts[2])
            require(not rhs_terms, "nonconstant_lp_rhs")
            variables.update(name for name, _ in terms)
            rows[parts[1]] += 1
            description = {
                "sense": parts[1],
                "rhs_minus_lhs_constant": rhs - constant,
                "families": aggregates(terms),
            }
            require(math.isfinite(rhs - constant), "nonfinite_lp_rhs")
            key = json.dumps(
                [
                    parts[1],
                    [
                        (name, value["minimum"] < 0, value["maximum"] > 0)
                        for name, value in description["families"].items()
                    ],
                ]
            )
            group = structures.setdefault(
                key,
                {
                    "rows": 0,
                    "sense": parts[1],
                    "families": list(description["families"]),
                    "rhs_minimum": rhs - constant,
                    "rhs_maximum": rhs - constant,
                },
            )
            require(len(structures) <= 128, "lp_row_structure_limit")
            group["rows"] += 1
            group["rhs_minimum"] = min(group["rhs_minimum"], rhs - constant)
            group["rhs_maximum"] = max(group["rhs_maximum"], rhs - constant)
            # Representative summaries only; do not export the full matrix.
            if (
                len(samples) < 12
                and sample_groups[key] < 3
                and description not in samples
            ):
                samples.append(description)
                sample_groups[key] += 1

    for raw in lines:
        tick()
        expanded += len(raw)
        require(expanded <= 256 * 1024**2 and len(raw) <= 1024**2, "lp_expansion_limit")
        text = raw.decode("ascii").strip()
        if not text or text.startswith("\\"):
            continue
        header = HEADERS.get(text.lower())
        if header:
            flush()
            section = header
            if header == "objective":
                sense = "MAXIMIZE" if text.lower().startswith("max") else "MINIMIZE"
            continue
        require(section not in (None, "end"), "unexpected_lp_section")
        if section in ("objective", "rows"):
            if section == "rows" and ":" in text:
                flush()
            buffer.append(text)
        elif section in domains:
            names = tokens(text)
            require(
                all(re.fullmatch(NAME, name) for name in names), "invalid_lp_domain"
            )
            domains[section].update(names)
            variables.update(names)
        elif section == "bounds":
            pieces = tokens(text)
            names = [
                p
                for p in pieces
                if re.fullmatch(NAME, p)
                and p.lower() not in ("free", "inf", "infinity")
            ]
            variables.update(names)
            shape = " ".join(
                "N" if re.fullmatch(NUMBER, p) else "V" if p in names else p.lower()
                for p in pieces
            )
            require(len(shape) < 100, "unsupported_lp_bound")
            bounds[shape] += 1
    flush()
    require(
        section == "end" and objective is not None and sum(rows.values()) > 0,
        "incomplete_lp_file",
    )
    require(
        not domains["binary"].intersection(domains["integer"]), "overlapping_lp_domains"
    )
    return {
        "source_sense": sense,
        "required_effective_sense": "MINIMIZE",
        "objective": objective,
        "row_senses": dict(rows),
        "row_structure_groups": list(structures.values()),
        "representative_row_summaries": samples,
        "variables_observed": len(variables),
        "explicit_domain_families": {
            k: dict(collections.Counter(family(n) for n in v))
            for k, v in domains.items()
        },
        "explicit_binary_variables": len(domains["binary"]),
        "explicit_general_variables": len(domains["integer"]),
        "remaining_continuous_by_linear_lp_default": len(
            variables - domains["binary"] - domains["integer"]
        ),
        "bound_syntax_counts": dict(bounds),
        "expanded_bytes": expanded,
        "economic_units": "not_encoded_or_inferred",
        "full_semantics_qualified": False,
        "coverage": "representative_parent_only_not_all_54",
    }


def bounded_lines(stream):
    while True:
        line = stream.readline(1024**2 + 1)
        if not line:
            return
        require(len(line) <= 1024**2, "lp_line_limit")
        yield line


def report_summary(plan, report, model, cohort):
    require(
        report.get("training_contract_sha256") == plan.get("contract_sha256"),
        "training_contract_mismatch",
    )
    require(
        report.get("outputs", {}).get("checkpoint", {}).get("sha256")
        == model["checkpoint_sha256"],
        "checkpoint_report_mismatch",
    )
    require(
        report.get("gate_status") == "passed" and report.get("test_graphs_loaded") == 0,
        "historical_report_gate",
    )
    require(
        report.get("checkpoint_selection") == model["checkpoint_selection"]
        and report.get("threshold_source") == model["threshold_source"],
        "historical_selection_mismatch",
    )
    require(
        report.get("selected_probability_threshold") == model["threshold"],
        "historical_threshold_mismatch",
    )
    prenorm = report.get("prenorm_audit", {})
    expected_train = sum(r["role"] == "train" for r in plan["records"])
    checked = (
        prenorm.get("validation_or_test_used") is False
        and prenorm.get("training_graphs") == expected_train
        and prenorm.get("method") == "streaming_population_moments_all_training_graphs"
    )
    weight, epochs = report.get("pos_weight"), report.get("epochs_completed")
    require(
        type(weight) in (int, float) and math.isfinite(weight) and weight > 0,
        "invalid_historical_pos_weight",
    )
    require(type(epochs) is int and 0 < epochs <= 100, "invalid_historical_epoch_count")
    return {
        "cohort": cohort,
        "plan_sha256": model["plan_sha256"],
        "report_sha256": model["report_sha256"],
        "checkpoint_sha256": model["checkpoint_sha256"],
        "train_parents": expected_train,
        "prenorm_training_graphs": prenorm.get("training_graphs")
        if type(prenorm.get("training_graphs")) is int
        else None,
        "train_only_prenorm_attested_by_hashed_report": checked,
        "pos_weight": weight,
        "epochs_completed": epochs,
        "threshold": model["threshold"],
        "test_graphs_loaded": 0,
        "historical_fit_replayed": False,
        "pos_weight_train_only_scope": "code_path_review_not_consumed_sample_replay",
    }


def prepare():
    import audit_pr85_scientific as audit

    selected = audit.numeric.selected_parents(audit.numeric.source_receipt())
    parents = ("CFL_easy_instance_0", "CFL_medium_instance_0")
    return {
        "protocol_id": PROTOCOL,
        "models": audit.inference.plan()["models"],
        "parents": {p: selected[p]["mip_sha256_declared"] for p in parents},
        "source_sha256_lf": {
            p.name: digest(p.read_bytes().replace(b"\r\n", b"\n"))
            for p in (
                Path(__file__),
                Path(__file__).with_name("verify_sprint_c_artifacts.py"),
                Path(__file__).with_name("audit_sprint_c_inputs.py"),
            )
        },
    }


def collect(root, request):
    require(request.get("protocol_id") == PROTOCOL, "request_protocol")
    require(
        set(request["source_sha256_lf"])
        == {
            Path(__file__).name,
            "verify_sprint_c_artifacts.py",
            "audit_sprint_c_inputs.py",
        },
        "request_dependency_set",
    )
    require(set(request["models"]) == {"easy", "mixed"}, "request_cohorts")
    require(
        set(request["parents"]) == {"CFL_easy_instance_0", "CFL_medium_instance_0"},
        "request_parents",
    )
    for name, sha in request["source_sha256_lf"].items():
        require(
            name
            in (
                Path(__file__).name,
                "verify_sprint_c_artifacts.py",
                "audit_sprint_c_inputs.py",
            ),
            "request_dependency",
        )
        require(
            digest(Path(__file__).with_name(name).read_bytes().replace(b"\r\n", b"\n"))
            == sha,
            "dependency_hash",
        )
    reader = Reader(root, seconds=180, max_bytes=512 * 1024**2)
    reader.scan()
    found = {}
    for path in reader.files:
        if path.name in ("gasse_training_plan.json", "gasse_training_report.json"):
            raw = reader.read(path, content=True)
            found.setdefault(digest(raw), raw)
    training, models = {}, {}
    for cohort, model in request["models"].items():
        try:
            require(
                model["plan_sha256"] in found and model["report_sha256"] in found,
                "frozen_training_documents_missing",
            )
            training[cohort] = report_summary(
                json.loads(found[model["plan_sha256"]]),
                json.loads(found[model["report_sha256"]]),
                model,
                cohort,
            )
        except AuditStop as error:
            training[cohort] = {"state": str(error), "qualified": False}
    for parent, sha in request["parents"].items():
        try:
            require(
                parent in ("CFL_easy_instance_0", "CFL_medium_instance_0"),
                "unexpected_representative_parent",
            )
            difficulty = parent.split("_")[1]
            base = (
                reader.root
                / "raw/MILPBench/CFL"
                / ("CFL_" + difficulty + "_instance")
                / "LP"
            )
            paths = [
                p
                for p in (base / (parent + ".lp.gz"), base / (parent + ".lp"))
                if p.is_file()
            ]
            require(len(paths) == 1, "representative_lp_missing_or_ambiguous")
            path = reader.safe(paths[0])
            reader.verify(path, sha)
            before = path.stat()
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rb") as stream:
                result = lp_summary(bounded_lines(stream), reader.tick)
            require(
                before.st_size == path.stat().st_size
                and before.st_mtime_ns == path.stat().st_mtime_ns,
                "lp_changed_during_read",
            )
            result["source_sha256"] = sha
            models[parent] = result
        except AuditStop as error:
            models[parent] = {"state": str(error), "qualified": False}
        except (OSError, UnicodeError, ValueError):
            models[parent] = {"state": "lp_read_or_grammar_failure", "qualified": False}
    return {
        "protocol_id": PROTOCOL,
        "request_sha256": digest(json.dumps(request, sort_keys=True).encode()),
        "training_reports": training,
        "representative_models": models,
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "submissions_added": 0,
        "raw_model_text_included": False,
        "private_paths_included": False,
        "new_comparison_admitted": False,
        "scientific_reporting_eligible": False,
    }


def review(raw, expected_sha, request):
    require(
        re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None, "invalid_receipt_sha"
    )
    require(digest(raw) == expected_sha, "receipt_hash")
    result = json.loads(raw)
    require(result.get("protocol_id") == PROTOCOL, "receipt_protocol")
    require(
        result.get("request_sha256")
        == digest(json.dumps(request, sort_keys=True).encode()),
        "receipt_request_binding",
    )
    require(
        set(result["training_reports"]) == set(request["models"]), "receipt_cohorts"
    )
    require(
        set(result["representative_models"]) == set(request["parents"]),
        "receipt_parents",
    )
    for key in ("optimization_runs_added", "training_runs_added", "submissions_added"):
        require(
            type(result.get(key)) is int and result[key] == 0, "receipt_operation_scope"
        )
    for key in (
        "raw_model_text_included",
        "private_paths_included",
        "new_comparison_admitted",
        "scientific_reporting_eligible",
    ):
        require(result.get(key) is False, "receipt_scope")
    for parent, item in result["representative_models"].items():
        if "source_sha256" in item:
            require(
                item["source_sha256"] == request["parents"][parent],
                "receipt_lp_identity",
            )
    for cohort, item in result["training_reports"].items():
        if "report_sha256" in item:
            for key in ("plan_sha256", "report_sha256", "checkpoint_sha256"):
                require(
                    item[key] == request["models"][cohort][key],
                    "receipt_training_identity",
                )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "collect", "review"))
    parser.add_argument("--request", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.action == "review":
        result = review(
            args.receipt.read_bytes(),
            args.expected_sha256,
            json.loads(args.request.read_bytes()),
        )
        print(
            json.dumps(
                {
                    "transfer_and_request_binding_verified": True,
                    "training_states": {
                        k: v.get("state", "hashed_report_reconciled")
                        for k, v in result["training_reports"].items()
                    },
                    "lp_states": {
                        k: v.get("state", "representative_structure_collected")
                        for k, v in result["representative_models"].items()
                    },
                    "new_comparison_admitted": False,
                }
            )
        )
        return
    require(args.output is not None, "output_required")
    require(not args.output.exists(), "output_already_exists")
    if args.action == "collect":
        require(
            args.data_root is not None and args.request is not None,
            "collection_arguments",
        )
        require(
            not args.output.resolve().is_relative_to(args.data_root.resolve()),
            "output_inside_input_data",
        )
    result = (
        prepare()
        if args.action == "prepare"
        else collect(args.data_root, json.loads(args.request.read_bytes()))
    )
    raw = json.dumps(result, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    with args.output.open("xb") as stream:
        stream.write(raw)
    print(
        json.dumps(
            {
                "receipt_sha256": digest(raw),
                "output": str(args.output),
                "optimization_runs_added": 0,
                "submissions_added": 0,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "PR85_READ_ONLY_AUDIT_STOPPED_NO_PRIVATE_EXCEPTION_TEXT"
        ) from None
