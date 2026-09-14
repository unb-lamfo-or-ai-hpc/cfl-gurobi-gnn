"""Validate the static manuscript and explicitly scoped interim evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = ROOT / "manuscript"
AUTHORS = (
    ("Victor Rafael Rezende Celestino", "0000-0001-5913-2997", "vrcelestino@unb.br"),
    ("Víctor Alejandro Vargas-Pérez", "0000-0001-6803-3608", "victorvp@go.ugr.es"),
    ("Óscar Cordón García", "0000-0001-5112-5629", "ocordon@decsai.ugr.es"),
    ("Pedro González García", "0000-0002-6733-3868", "pglez@ujaen.es"),
)
AI_HEADING = "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process"
AI_DISCLOSURE = (
    "During the preparation of this work, the authors used Gurobot, Gemini 3.1 Pro, "
    "and ChatGPT Codex with models 5.6 Sol and 6.0 Astra, to assist with the codebase "
    "implementation and to support the preparation, structuring, language refinement, "
    "and data visualization of this manuscript. After using these tools/services, "
    "the authors reviewed and edited the content as needed and took full "
    "responsibility for the content of the published article."
)


def check_source(root: Path = MANUSCRIPT) -> list[str]:
    """Check document integrity, not scientific validity or remote artifact truth."""
    failures: list[str] = []
    article = (root / "index.qmd").read_text(encoding="utf-8")
    bibliography = (root / "references.bib").read_text(encoding="utf-8")
    evidence = json.loads((root / "evidence-status.json").read_text(encoding="utf-8"))
    config = (root / "_quarto.yml").read_text(encoding="utf-8")
    citation_keys = {key for key in re.findall(r"(?<!\w)@([a-z][a-z0-9_-]+)", article)
                     if not key.startswith(("fig-", "tbl-"))}
    entries = re.findall(r"^@\w+\{([^,]+),", bibliography, re.MULTILINE)
    if citation_keys != set(entries) or len(entries) != len(set(entries)):
        failures.append("bibliography_not_exactly_cited_or_duplicate_keys")
    if "gasse2019" not in citation_keys or "1906.01629v3" not in bibliography:
        failures.append("mandatory_gasse_v3_reference_missing")
    if "10.48550/arXiv.1906.01629" not in bibliography:
        failures.append("mandatory_gasse_doi_missing")
    l2o_keys = {"chen2022primer", "chen2024tutorial", "tang2024l2o"}
    if not l2o_keys.issubset(citation_keys) or "## Learning to Optimize" not in article:
        failures.append("reviewed_l2o_context_missing")
    adapter = (root / "_extensions/sbc/template.tex").read_text(encoding="utf-8")
    if r"\usepackage{orcidlink}" not in adapter or r"\providecommand{\orcidlink}" in adapter:
        failures.append("orcid_icon_package_missing_or_replaced")
    if re.search(r"```\s*\{", article) or "{{< include" in article:
        failures.append("executable_or_unreviewed_included_content")
    if any(setting not in config for setting in ("enabled: false", "code-links: false", "meca-bundle: false")):
        failures.append("static_publication_boundary_missing")
    if "An Audited Original-Instance Study" not in article or "No matched four-arm learning comparison" not in article:
        failures.append("completed_study_scope_missing")
    environment_boundaries = (
        "## Computational environment",
        "{#tbl-computational-environment}",
        "not a runtime hardware probe",
        "does not establish that a training run uses all eight",
        "missing values will remain explicitly unavailable",
        "6 Gb/s interface",
    )
    if any(text not in article for text in environment_boundaries):
        failures.append("computational_environment_scope_missing")
    if evidence.get("schema_version") != 3:
        failures.append("unsupported_evidence_schema")
    if evidence.get("development_only") is not True:
        failures.append("development_boundary_missing")
    if evidence.get("scientific_reporting_eligible") is not False:
        failures.append("scientific_claim_without_review")
    assets = evidence.get("empirical_assets", [])
    allowed_assets = {"source_evidence.json", "confirmation_final.json", "graph_clustering_report.json",
                      "training_epoch_metrics.csv", "per_parent_metrics.csv", "per_difficulty_metrics.csv",
                      "calibration_curve.csv", "graph_statistics.csv", "graph_clustering.csv"}
    if evidence.get("empirical_results_included") is not True or {a.get("relative_path") for a in assets} != {"results/" + name for name in allowed_assets}:
        failures.append("unreviewed_empirical_asset_scope")
    for asset in assets:
        if asset.get("relative_path") not in {"results/" + name for name in allowed_assets}:
            failures.append("unreviewed_empirical_asset_scope")
            continue
        path = root / asset["relative_path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset.get("sha256"):
            failures.append("source_evidence_hash_mismatch")
    if evidence.get("license") != "MIT" or "license: MIT" not in config:
        failures.append("mit_license_metadata_missing")
    if not (root / "LICENSE").read_text().startswith("MIT License"):
        failures.append("mit_manuscript_notice_missing")
    front = article.split("---", 2)[1]
    author_records = re.findall(r"  - name: (.+)\n    orcid: (.+)\n    email: (.+)", front)
    if evidence.get("authorship_confirmed") is not True or tuple(author_records) != AUTHORS:
        failures.append("confirmed_authorship_mismatch")
    for affiliation in ("University of Brasilia", "Data Science and Computer Intelligence Institute, University of Granada",
                        "Data Science and Computer Intelligence Institute, University of Jaén"):
        if affiliation not in front:
            failures.append("confirmed_affiliation_missing")
    expected_tail = f"# {AI_HEADING} {{.unnumbered}}\n\n{AI_DISCLOSURE}\n\n# References"
    if not article.rstrip().endswith(expected_tail):
        failures.append("ai_declaration_missing_changed_or_not_before_references")
    if evidence.get("editorial_plan", {}).get("maximum_body_pages_including_front_matter_and_declarations") != 20:
        failures.append("editorial_page_budget_changed")
    expected = {"parents": 42, "easy": 30, "medium": 12, "hard": 0,
                "train": 24, "validation": 10, "test": 8, "seed": 42, "epochs": 100,
                "maximum_label_gap_relative": 0.1}
    protocol = evidence.get("confirmation_protocol", {})
    if any(protocol.get(key) != value for key, value in expected.items()):
        failures.append("confirmation_protocol_drift")
    acceptance = evidence.get("acceptance", {})
    if acceptance.get("held_out_confirmation_evaluation") != "completed_receipt_and_classification_consistency_verified" or acceptance.get("paired_four_arm_comparison") != "not_executed_future_work":
        failures.append("acceptance_claim_requires_evidence_update")
    if acceptance.get("full_90_parent_campaign") != "deferred":
        failures.append("full_population_scope_changed")
    boundary = {"complete_source_label_bundle": "incomplete_39_of_42_admitted",
                "strict_42_graph_bundle": "not_achieved",
                "revised_39_graph_bundle": "receipt_audited_raw_artifacts_not_transferred",
                "confirmation_training_100_epochs": "completed_100_epochs_receipt_and_history_verified"}
    if any(acceptance.get(k) != v for k, v in boundary.items()):
        failures.append("unsupported_completion_claim")
    revision = evidence.get("revised_confirmation_protocol", {})
    revised_expected = {"parents": 39, "easy": 30, "medium": 9, "hard": 0,
                        "train": 23, "validation": 8, "test": 8, "seed": 42,
                        "epochs": 100, "maximum_label_gap_relative": 0.1}
    if any(revision.get(k) != v for k, v in revised_expected.items()):
        failures.append("revised_cohort_drift")
    source = json.loads((root / "results/source_evidence.json").read_text())
    if source.get("campaign_contract_sha256") != protocol.get("execution_contract_sha256"):
        failures.append("source_campaign_mismatch")
    if source.get("training", {}).get("epochs_completed") is not None or source.get("training", {}).get("test_metrics") is not None:
        failures.append("historical_source_extract_changed")
    final = json.loads((root / "results/confirmation_final.json").read_text())
    with (root / "results/training_epoch_metrics.csv").open(newline="", encoding="utf-8") as stream:
        epochs = list(csv.DictReader(stream))
    if final.get("gate_status") != "passed" or final["training"]["epochs"] != 100 or [int(r["epoch"]) for r in epochs] != list(range(1, 101)):
        failures.append("final_training_evidence_inconsistent")
    if final["cohort"] != {"parents": 39, "easy": 30, "medium": 9, "hard": 0, "train": 23, "validation": 8, "test": 8}:
        failures.append("final_cohort_inconsistent")
    with (root / "results/per_parent_metrics.csv").open(newline="", encoding="utf-8") as stream:
        parents = list(csv.DictReader(stream))
    aggregate = final["evaluation"]["aggregate_metrics"]
    if len(parents) != 8 or any(sum(int(r[k]) for r in parents) != aggregate[k] for k in ("tp", "tn", "fp", "fn", "n_targets", "n_positive")):
        failures.append("final_classification_totals_inconsistent")
    if abs(2 * aggregate["tp"] / (2 * aggregate["tp"] + aggregate["fp"] + aggregate["fn"]) - aggregate["f1_score"]) > 1e-12:
        failures.append("final_f1_inconsistent")
    if final["evaluation"]["score_diagnostics"]["probability_calibration_claimed"] is not False:
        failures.append("unsupported_calibration_claim")
    for parent in source.get("rejected", []):
        for run in parent["repairs"]:
            expected_gap = abs(run["solution_objective"] - run["best_bound"]) / abs(run["solution_objective"])
            if abs(expected_gap - run["mip_gap_relative"]) > 1e-10 or run["mip_gap_relative"] <= .1:
                failures.append("rejection_gap_inconsistent")
            if run["right_censored"] is not True or run["solve_status"] != "timelimit":
                failures.append("rejection_censoring_missing")
    private_pattern = re.compile(r"/raid/|/home/|(?<![\w{])[A-Za-z]:[\\/]|WLSSecret|LicenseID|gurobi\.lic")
    for name in ("index.qmd", "references.bib", "evidence-status.json", "_quarto.yml", *("results/" + name for name in allowed_assets)):
        payload = (root / name).read_bytes()
        if b"\r" in payload and not name.endswith(".csv"):
            failures.append(f"non_lf_source:{name}")
        if private_pattern.search(payload.decode("utf-8")):
            failures.append(f"private_content:{name}")
    provenance = json.loads((root / "template-provenance" / "upstream.json").read_text(encoding="utf-8"))
    for entry in provenance["files"]:
        path = root / entry["local_path"]
        if not path.resolve().is_relative_to(root.resolve()):
            failures.append("unsafe_template_path")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            failures.append(f"template_hash_mismatch:{entry['local_path']}")
    return failures


def check_rendered(root: Path = MANUSCRIPT) -> list[str]:
    """Check required outputs and bounded publication paths, not scientific truth."""
    output = root / "_manuscript"
    failures: list[str] = []
    html = output / "index.html"
    pdf = output / "index.pdf"
    if not html.is_file() or not pdf.is_file():
        return ["html_or_pdf_missing"]
    content = html.read_text(encoding="utf-8")
    if "An Audited Original-Instance Study" not in content:
        failures.append("rendered_status_missing")
    for _, orcid, email in AUTHORS:
        if orcid not in content or email not in content:
            failures.append("rendered_author_identity_missing")
    if AI_HEADING not in content:
        failures.append("rendered_ai_declaration_missing")
    if not pdf.read_bytes().startswith(b"%PDF-"):
        failures.append("invalid_pdf_header")
    receipt_path = output / "tables/rendered_assets.json"
    if not receipt_path.is_file():
        failures.append("rendered_asset_receipt_missing")
    else:
        receipt = json.loads(receipt_path.read_text())
        source_hash = hashlib.sha256((root / "results/source_evidence.json").read_bytes()).hexdigest()
        final_hash = hashlib.sha256((root / "results/confirmation_final.json").read_bytes()).hexdigest()
        if receipt.get("source_sha256") != source_hash or receipt.get("final_evidence_sha256") != final_hash or len(receipt.get("outputs", [])) != 13:
            failures.append("rendered_asset_source_or_count_mismatch")
        for asset in receipt.get("outputs", []):
            path = output / asset["relative_path"]
            if not path.resolve().is_relative_to(output.resolve()) or not path.is_file():
                failures.append("missing_or_unsafe_rendered_asset")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
                failures.append("rendered_asset_hash_mismatch")
    bibliography = (root / "references.bib").read_text(encoding="utf-8")
    for key in re.findall(r"^@\w+\{([^,]+),", bibliography, re.MULTILINE):
        if f'id="ref-{key}"' not in content:
            failures.append(f"rendered_reference_missing:{key}")
    for path in output.rglob("*"):
        if path.is_symlink():
            failures.append("publication_symlink")
        if path.is_file() and (path.suffix.lower() in {".pt", ".parquet", ".pickle", ".gz", ".lic"}
                               or path.name in {"PROJECT_STATE.md", "parent_solution.json"}):
            failures.append(f"unexpected_research_artifact:{path.name}")
    return failures


def check_pdf_text(path: Path) -> list[str]:
    """Inspect extracted text as a supplement to mandatory visual page review."""
    text = path.read_text(encoding="utf-8")
    failures = []
    for expected in ("Graph Neural Prediction", "0.5825",
                     "Gasse", "Fischetti", "Nair", "References"):
        if expected not in text:
            failures.append(f"pdf_text_missing:{expected}")
    if "??" in text or "[?]" in text:
        failures.append("unresolved_pdf_reference")
    normalized = " ".join(text.split())
    if any(orcid in text for _, orcid, _ in AUTHORS) or "ORCID:" in text:
        failures.append("orcid_identifier_printed_instead_of_icon")
    for _, _, email in AUTHORS:
        if email not in normalized:
            failures.append(f"pdf_author_email_missing:{email}")
    if "Gurobot, Gemini 3.1 Pro" not in normalized:
        failures.append("pdf_ai_declaration_missing")
    # pdftotext separates pages with form feeds. Count conservatively, including
    # the page on which References begins, when it also contains manuscript text.
    references = re.search(r"(?m)(?:^|[\n\f])[ \t]*(References)[ \t]*(?:\n|$)", text)
    if "\f" in text and references and text[:references.start(1)].count("\f") + 1 > 20:
        failures.append("manuscript_body_exceeds_twenty_pages")
    if re.search(r"/raid/|/home/|[A-Za-z]:\\|WLSSecret|LicenseID", text):
        failures.append("private_pdf_content")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rendered", action="store_true")
    parser.add_argument("--pdf-text", type=Path)
    args = parser.parse_args()
    failures = check_source()
    if args.rendered:
        failures.extend(check_rendered())
    if args.pdf_text:
        failures.extend(check_pdf_text(args.pdf_text))
    print(json.dumps({"gate_status": "failed" if failures else "passed", "failures": failures,
                      "scientific_reporting_eligible": False,
                      "scope": "static_manuscript_integrity_only"}, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
