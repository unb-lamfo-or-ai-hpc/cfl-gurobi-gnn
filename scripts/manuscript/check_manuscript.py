"""Check publication integrity; never certify research validity or execute solvers.

SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_pr60_evidence import ARCHIVE_SHA, ARTIFACTS, CONTRACT, MANIFEST, REPORT, UNSAFE, verify_payload

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
INCLUDES = {"tables/current_predictive.qmd", "tables/current_heldout.qmd",
            "tables/current_influence.qmd", "tables/current_timing.qmd"}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def safe_child(root: Path, name: str) -> Path | None:
    path = root / name
    return path if not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) else None


def check_source(root: Path = MANUSCRIPT) -> list[str]:
    failures = []
    article = (root / "index.qmd").read_text(encoding="utf-8")
    bibliography = (root / "references.bib").read_text(encoding="utf-8")
    evidence = json.loads((root / "evidence-status.json").read_text(encoding="utf-8"))
    config = (root / "_quarto.yml").read_text(encoding="utf-8")
    adapter = (root / "_extensions/elsevier/template.tex").read_text(encoding="utf-8")
    keys = {k for k in re.findall(r"(?<!\w)@([a-z][a-z0-9_-]+)", article)
            if not k.startswith(("fig-", "tbl-", "sec-", "eq-"))}
    entries = re.findall(r"^@\w+\{([^,]+),", bibliography, re.MULTILINE)
    if keys != set(entries) or len(entries) != len(set(entries)):
        failures.append("bibliography_not_exactly_cited_or_duplicate_keys")
    if not {"gasse2019", "bengio2021", "qu2026", "goerigk2025", "zhang2026"}.issubset(keys):
        failures.append("required_references_missing")
    if "1906.01629v3" not in bibliography or "10.48550/arXiv.1906.01629" not in bibliography:
        failures.append("mandatory_gasse_v3_reference_missing")
    if "## Learning to Optimize" not in article:
        failures.append("reviewed_l2o_context_missing")
    if r"\usepackage{orcidlink}" not in adapter or r"\providecommand{\orcidlink}" in adapter:
        failures.append("orcid_icon_package_missing_or_replaced")
    if "{elsarticle}" not in adapter or "elsarticle-harv" not in adapter or "cite-method: natbib" not in config:
        failures.append("elsevier_author_year_layout_missing")
    includes = re.findall(r"\{\{< include ([^>]+?) >\}\}", article)
    if set(includes) != INCLUDES or len(includes) != len(INCLUDES) or re.search(r"```\s*\{", article):
        failures.append("executable_or_unreviewed_included_content")
    if any(x not in config for x in ("enabled: false", "code-links: false", "meca-bundle: false")):
        failures.append("static_publication_boundary_missing")
    front = article.split("---", 2)[1]
    records = re.findall(r"  - name: (.+)\n    orcid: (.+)\n    email: (.+)", front)
    if tuple(records) != AUTHORS or evidence.get("authorship_confirmed") is not True:
        failures.append("confirmed_authorship_mismatch")
    abstract = front.split("abstract: |", 1)[1]
    if len(abstract.split()) > 250:
        failures.append("abstract_exceeds_250_words")
    if "class-aware" not in abstract.lower() or "value 1" not in abstract:
        failures.append("class_aware_abstract_explanation_missing")
    if "**" in article or re.search(r"(?<!\w)__[^\n]+__", article):
        failures.append("bold_article_emphasis_not_permitted")
    if "# Final considerations, limitations and future work" not in article or "# Discussion and limitations" in article:
        failures.append("editorial_final_section_missing")
    before_results = article.split("# Results", 1)[0]
    if not {"milpbench", "gneiting2007", "saito2015", "sklearnap", "brier1950", "guo2017"}.issubset(keys):
        failures.append("metric_or_dataset_references_missing")
    if any(term not in before_results for term in ("binary cross-entropy", "Average precision (AP)", "Brier score", "Expected calibration error (ECE)", "right-censored", "parent-macro")):
        failures.append("metrics_not_defined_before_results")
    for identity in ("fig-pipeline", "fig-loss", "fig-effects", "fig-target-time"):
        figure_match = re.search(r"!\[[^\n]+\]\([^\n]+\)\{#" + re.escape(identity) + r"\b[^\n]*\}", article)
        if not figure_match or "@" + identity not in article[:figure_match.start()]:
            failures.append("figure_not_introduced:" + identity)
    for name, identity in (("predictive", "tbl-predictive"), ("heldout", "tbl-heldout"), ("influence", "tbl-influence"), ("timing", "tbl-times")):
        marker = "{{< include tables/current_" + name + ".qmd >}}"
        if marker not in article or "@" + identity not in article.split(marker, 1)[0]:
            failures.append("table_not_introduced:" + identity)
    if re.search(r"(?m)^#{1,3} [^\n]+\n\n(?:!\[|\| |\{\{< include)", article):
        failures.append("section_starts_with_display")
    keyword_count = front.split("keywords:", 1)[1].split("abstract:", 1)[0].count("  - ")
    if not 1 <= keyword_count <= 7:
        failures.append("keyword_budget_invalid")
    highlights = (root / "highlights.txt").read_text().splitlines()
    if not 3 <= len(highlights) <= 5 or any(len(line) > 85 or not line.strip() for line in highlights):
        failures.append("highlight_budget_invalid")
    tail = f"# {AI_HEADING} {{.unnumbered}}\n\n{AI_DISCLOSURE}\n\n# References"
    if not article.rstrip().endswith(tail):
        failures.append("ai_declaration_missing_changed_or_not_before_references")
    if any(x not in article for x in ("not a runtime hardware probe", "6 Gb/s interface", "all eight GPUs")):
        failures.append("computational_environment_scope_missing")
    if evidence.get("schema_version") != 4 or evidence.get("source_contract_sha256") != CONTRACT:
        failures.append("unsupported_or_changed_evidence_contract")
    if evidence.get("development_only") is not True or evidence.get("scientific_reporting_eligible") is not False:
        failures.append("scientific_claim_without_review")
    protocol = {"parents": 54, "train": 34, "validation": 10, "predictive_test": 10,
                "optimization_validation": 6, "optimization_test": 6, "epochs": 100, "seed": 42,
                "maximum_label_gap_relative": 0.1}
    if evidence.get("current_protocol") != protocol:
        failures.append("current_cohort_drift")
    if evidence.get("editorial_plan", {}).get("maximum_body_pages_including_front_matter_and_declarations") != 20:
        failures.append("editorial_page_budget_changed")
    if evidence.get("license") != "MIT" or "license: MIT" not in config or not (root / "LICENSE").read_text().startswith("MIT License"):
        failures.append("mit_license_metadata_missing")
    current = root / "results/current"
    try:
        payload = {name: (current / name).read_bytes() for name in (*ARTIFACTS, MANIFEST, REPORT)}
        verify_payload(payload)
        receipt = json.loads((current / "import_receipt.json").read_text())
        hashes = {n: hashlib.sha256(v).hexdigest() for n, v in payload.items()}
        if receipt.get("archive_sha256") != ARCHIVE_SHA or receipt.get("files") != hashes:
            failures.append("import_receipt_mismatch")
    except (OSError, ValueError, KeyError, UnicodeError) as error:
        failures.append("source_evidence_invalid:" + str(error))
    history = csv_rows(current / "table_training_epoch_metrics.csv")
    if [int(r["epoch"]) for r in history] != list(range(1, 101)):
        failures.append("final_training_evidence_inconsistent")
    outcomes = csv_rows(current / "table_solver_outcomes.csv")
    test_parents = {"CFL_medium_instance_" + str(i) for i in (0, 4, 7, 9, 12, 20)}
    test = [r for r in outcomes if r["partition"] == "test"]
    if len(outcomes) != 36 or len(test) != 18 or {r["source_instance_id"] for r in test} != test_parents:
        failures.append("optimization_population_inconsistent")
    for name in ("index.qmd", "references.bib", "evidence-status.json", "_quarto.yml", "highlights.txt"):
        raw = (root / name).read_bytes()
        if b"\r" in raw:
            failures.append("non_lf_source:" + name)
        if UNSAFE.search(raw.decode("utf-8")):
            failures.append("private_content:" + name)
    provenance = json.loads((root / "template-provenance/elsevier.json").read_text())
    for entry in provenance["files"]:
        path = safe_child(root, entry["local_path"])
        if path is None or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            failures.append("template_hash_mismatch:" + entry["local_path"])
    return failures


def check_rendered(root: Path = MANUSCRIPT) -> list[str]:
    output = root / "_manuscript"
    html, pdf = output / "index.html", output / "index.pdf"
    if not html.is_file() or not pdf.is_file():
        return ["html_or_pdf_missing"]
    failures = []
    content = html.read_text(encoding="utf-8")
    for _, orcid, email in AUTHORS:
        if orcid not in content or email not in content:
            failures.append("rendered_author_identity_missing")
    if AI_HEADING not in content or "Class-aware graph neural warm starts" not in content:
        failures.append("rendered_scope_or_declaration_missing")
    if re.search(r"(?:Figure|Table|Section)\s*<a[^>]*class=\"quarto-xref\"[^>]*>(?:Figure|Table|Section)", content):
        failures.append("duplicated_crossreference_prefix")
    if not pdf.read_bytes().startswith(b"%PDF-"):
        failures.append("invalid_pdf_header")
    # An HTML-only refresh must not accidentally qualify a preceding draft PDF.
    newest_source = max((root / name).stat().st_mtime_ns for name in
                        ("index.qmd", "references.bib", "_extensions/elsevier/template.tex"))
    if pdf.stat().st_mtime_ns < newest_source:
        failures.append("pdf_predates_current_article_sources")
    receipt_path = output / "tables/rendered_assets.json"
    if not receipt_path.is_file():
        failures.append("rendered_asset_receipt_missing")
    else:
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("source_contract_sha256") != CONTRACT or receipt.get("training_epochs") != 100 or receipt.get("validation_minimum_epoch") != 34 or len(receipt.get("outputs", [])) != 16:
            failures.append("rendered_asset_source_or_count_mismatch")
        current = root / "results/current"
        for name, expected in receipt.get("source_files", {}).items():
            path = safe_child(current, name)
            if path is None or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                failures.append("rendered_source_hash_mismatch")
        for asset in receipt.get("outputs", []):
            path = safe_child(output, asset["relative_path"])
            if path is None or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
                failures.append("rendered_asset_hash_mismatch")
    for key in re.findall(r"^@\w+\{([^,]+),", (root / "references.bib").read_text(), re.MULTILINE):
        if f'id="ref-{key}"' not in content:
            failures.append("rendered_reference_missing:" + key)
    for path in output.rglob("*"):
        if path.is_symlink() or path.suffix.lower() in {".pt", ".parquet", ".pickle", ".gz", ".lic"}:
            failures.append("unexpected_research_artifact:" + path.name)
    return failures


def check_pdf_text(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    failures = []
    for word in ("Class-aware graph neural warm starts", "0.6993", "Gasse", "Goerigk", "References"):
        if word not in normalized:
            failures.append("pdf_text_missing:" + word)
    if "??" in text or "[?]" in text:
        failures.append("unresolved_pdf_reference")
    if any(orcid in text for _, orcid, _ in AUTHORS) or "ORCID:" in text:
        failures.append("orcid_identifier_printed_instead_of_icon")
    for _, _, email in AUTHORS:
        if email not in normalized:
            failures.append("pdf_author_email_missing:" + email)
    if "Gurobot, Gemini 3.1 Pro" not in normalized:
        failures.append("pdf_ai_declaration_missing")
    match = re.search(r"(?m)(?:^|[\n\f])[ \t]*(References)[ \t]*(?:\n|$)", text)
    if "\f" in text and match and text[:match.start(1)].count("\f") + 1 > 20:
        failures.append("manuscript_body_exceeds_twenty_pages")
    if UNSAFE.search(text):
        failures.append("private_pdf_content")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rendered", action="store_true")
    parser.add_argument("--pdf-text", type=Path)
    args = parser.parse_args()
    failures = check_source()
    if args.rendered:
        failures += check_rendered()
    if args.pdf_text:
        failures += check_pdf_text(args.pdf_text)
    print(json.dumps({"gate_status": "failed" if failures else "passed", "failures": failures,
                      "scientific_reporting_eligible": False, "scope": "publication_integrity_only"}, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
