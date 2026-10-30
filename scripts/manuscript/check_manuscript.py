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
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_claim_evidence import check_claim_evidence
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
ACKNOWLEDGEMENTS = "The authors thank the University of Jaén (UJA) and the DaSCI Institute for providing access to the dgx-dasci high-performance computing infrastructure used in this study."
AI_DISCLOSURE = (
    "During the preparation of this work, the authors used Gurobot, Gemini 3.1 Pro, "
    "and ChatGPT Codex with models 5.6 Sol and 6.0 Astra, to assist with the codebase "
    "implementation and to support the preparation, structuring, language refinement, "
    "and data visualization of this manuscript. After using these tools/services, "
    "the authors reviewed and edited the content as needed and took full "
    "responsibility for the content of the published article."
)
TITLE = "Evaluating Graph Neural Network-Based Partial Warm Starts for Capacitated Facility Location Problems"
QUESTION = (
    "Can partial initial values predicted by a graph neural network (GNN) be used "
    "as warm starts for a deterministic MILP solver and improve its performance "
    "when solving Capacitated Facility Location (CFL) problems?"
)
INCLUDES = {"tables/principal_ratios.qmd", "tables/principal_costs.qmd"}
SUPPLEMENT_INCLUDES = {
    "../tables/current_predictive.qmd", "../tables/current_heldout.qmd",
    "../tables/current_influence.qmd", "../tables/current_timing.qmd",
    "../tables/principal_easy_times.qmd", "../tables/principal_medium_quality.qmd",
}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def safe_child(root: Path, name: str) -> Path | None:
    path = root / name
    return path if not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) else None


READER_TEXTS = (
    "index.qmd", "highlights.txt", "supplement/index.qmd",
    "supplement/README.md", "supplement/gnn-methods-audit.md",
    "supplement/configuration-reference.md", "supplement/extended-results.md",
)
READER_INTERNAL_NOTE = re.compile(
    r"\bco[- ]?authors?\b|\bPR\d+\b|\bMVP ?2\b|\bS1[–-]S6\b"
    r"|\bpending\b|\bin progress\b|\bfinal return\b|\bstill-running\b"
    r"|\bmerge approval\b|\bsubmission deadline\b|\bauthor-controlled\b"
    r"|\bbefore submission\b|\bworking material\b|\bnot an approved journal appendix\b",
    re.IGNORECASE,
)


def check_reader_material(root: Path) -> list[str]:
    """Keep editorial decisions and operational status outside journal prose."""
    failures = []
    allowed = {Path(name).name for name in READER_TEXTS if name.startswith("supplement/")}
    for path in (root / "supplement").glob("*.md"):
        if path.name not in allowed:
            failures.append("unregistered_supplement_text:" + path.name)
    for name in READER_TEXTS:
        path = root / name
        if not path.is_file():
            failures.append("reader_text_missing:" + name)
            continue
        text = path.read_text(encoding="utf-8")
        # Source URLs and cross-reference IDs can legitimately contain archive identifiers.
        prose = re.sub(r"(\[[^\]]+\])\([^\n)]+\)", r"\1", text)
        prose = re.sub(r"https?://[^\s)]+", "", prose)
        prose = re.sub(r"\{#[^}]*\}|@(?:sec|fig|tbl|eq)-[\w-]+", "", prose)
        if "<!--" in prose or READER_INTERNAL_NOTE.search(prose):
            failures.append("internal_note_in_reader_text:" + name)
    return failures


def check_source(root: Path = MANUSCRIPT) -> list[str]:
    failures = check_claim_evidence(root, ROOT)
    article = (root / "index.qmd").read_text(encoding="utf-8")
    bibliography = (root / "references.bib").read_text(encoding="utf-8")
    evidence = json.loads((root / "evidence-status.json").read_text(encoding="utf-8"))
    config = (root / "_quarto.yml").read_text(encoding="utf-8")
    adapter = (root / "_extensions/elsevier/template.tex").read_text(encoding="utf-8")
    readers = {name: (root / name).read_text(encoding="utf-8") for name in READER_TEXTS}
    reader_prose = "\n".join(readers.values())
    keys = {k for k in re.findall(r"(?<!\w)@([a-z][a-z0-9_-]+)", reader_prose)
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
    if not {"han2023", "scavuzzo2026survey"}.issubset(keys):
        failures.append("directed_primal_guidance_references_missing")
    if any(term not in article for term in (
        "150 seed42 observations", "numerical",
        "not an independent LP-only heuristic",
        "## Preliminary six-medium evidence",
    )):
        failures.append("mvp2_seed42_methodological_scope_missing")
    continuation = evidence.get("mvp2_continuation", {})
    if not isinstance(continuation, dict):
        continuation = {}
    principal = {
        "source": "docs/evidence/methodology-20261019", "seed": 42, "rows": 150,
        "easy_rows": 90, "medium_rows": 60, "exposed_test_parents": 10,
        "preserved_historical_rows": 210, "historical_only_seed43_44_rows": 60,
        "reported_terminal_targets": 97, "right_censored_targets": 53,
        "numerically_sensitive_rows": 30,
    }
    pending_cpu = {
        "source_commit": "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5",
        "protocol_id": "fresh_cpu12h_seed42_sixty_single_solve_jobs_v1",
        "execution_authorized_date": "2026-10-20", "jobs_already_submitted": 60,
        "execution_state": "in_progress_author_reported",
        "final_return_received": False, "scientific_results_included": False,
        "new_execution_authorized_by_this_revision": False,
    }
    if (evidence.get("current_protocol_scope")
            != "historical_six_medium_publication_archive_not_the_pr86_pr89_solver_cohort"
            or continuation.get("principal_analysis") != principal
            or continuation.get("method_aliases") != {"B": "M0", "R": "M1", "G": "M2"}
            or continuation.get("cpu_checkpoint_sha256")
            != "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"):
        failures.append("mvp2_principal_provenance_drift")
    if (continuation.get("governing_contract") != "CFL-GNN-SCI-2026-10-22-R3"
            or continuation.get("pr89") != pending_cpu
            or continuation.get("editorial_state")
            != "partial_integration_for_review_pr89_closeout_pending"
            or continuation.get("final_coauthor_approval") is not False
            or continuation.get("submission_authorized") is not False):
        failures.append("pending_cpu_campaign_misrepresented")
    if any(term in article for term in (
            "unapproved and unexecuted", "CPU extension is a proposal",
            "CPU proposal awaits separate resource approval",
    )):
        failures.append("obsolete_cpu_campaign_authority")
    failures += check_reader_material(root)
    if (f'title: "{TITLE}"' not in article
            or f'title: "{TITLE}"' not in readers["supplement/index.qmd"]
            or QUESTION not in article
            or "two empirical contributions" not in article
            or evidence.get("approved_scientific_communication") != {
                "date": "2026-10-30", "title": TITLE,
                "scientific_contributions": ["C2", "C3"],
                "C1_role": "methodological_obligation",
                "diagnostic_and_organization_approved": True,
                "new_experiments_authorized": False,
            }):
        failures.append("approved_scientific_communication_drift")
    if re.search(r"three (?:central |scientific |empirical )?contributions", article, re.I):
        failures.append("mechanism_promoted_to_independent_contribution")
    if r"\usepackage{orcidlink}" not in adapter or r"\providecommand{\orcidlink}" in adapter:
        failures.append("orcid_icon_package_missing_or_replaced")
    if "{elsarticle}" not in adapter or "elsarticle-harv" not in adapter or "cite-method: natbib" not in config:
        failures.append("elsevier_author_year_layout_missing")
    includes = re.findall(r"\{\{< include ([^>]+?) >\}\}", article)
    supplement = readers["supplement/extended-results.md"]
    supplement_includes = re.findall(r"\{\{< include ([^>]+?) >\}\}", supplement)
    entry_includes = re.findall(r"\{\{< include ([^>]+?) >\}\}",
                               readers["supplement/index.qmd"])
    if (set(includes) != INCLUDES or len(includes) != len(INCLUDES)
            or set(supplement_includes) != SUPPLEMENT_INCLUDES
            or len(supplement_includes) != len(SUPPLEMENT_INCLUDES)
            or entry_includes != ["gnn-methods-audit.md", "extended-results.md",
                                   "configuration-reference.md"]
            or re.search(r"```\s*\{", reader_prose)):
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
    if any(term in abstract for term in ("210 preserved", "3,400 updates", "PR89", "parents")):
        failures.append("internal_abstract_inventory")
    if not all(term in abstract for term in ("Capacitated Facility Location (CFL)",
                                            "Mixed-Integer Linear Programming (MILP)",
                                            "Graph Neural Network (GNN)")):
        failures.append("abstract_acronym_introduction_missing")
    if "**" in article or re.search(r"(?<!\w)__[^\n]+__", article):
        failures.append("bold_article_emphasis_not_permitted")
    if "# Conclusions and Future Research" not in article or "# Discussion and limitations" in article:
        failures.append("editorial_final_section_missing")
    before_results = article.split("# Computational Results", 1)[0]
    if not {"milpbench", "gneiting2007", "saito2015", "sklearnap", "brier1950", "guo2017"}.issubset(keys):
        failures.append("metric_or_dataset_references_missing")
    if any(term not in before_results for term in ("binary cross-entropy", "Average precision (AP)", "Brier score", "Expected calibration error (ECE)", "right-censored", "parent-macro")):
        failures.append("metrics_not_defined_before_results")
    figure_documents = {
        "index.qmd": ("fig-pipeline", "fig-principal-time", "fig-medium-gap", "fig-gpu-bce"),
        "supplement/extended-results.md": ("fig-loss", "fig-effects", "fig-target-time"),
    }
    for name, identities in figure_documents.items():
        text = readers[name]
        for identity in identities:
            match = re.search(r"!\[[^\n]+\]\([^\n]+\)\{#" + re.escape(identity) + r"\b[^\n]*\}", text)
            if not match or "@" + identity not in text[:match.start()]:
                failures.append("figure_not_introduced:" + identity)
    table_documents = {
        "index.qmd": (("principal_ratios", "tbl-principal-ratios"),
                      ("principal_costs", "tbl-principal-costs")),
        "supplement/extended-results.md": (
            ("current_predictive", "tbl-predictive"), ("current_heldout", "tbl-heldout"),
            ("current_influence", "tbl-influence"), ("current_timing", "tbl-times"),
            ("principal_easy_times", "tbl-easy-times"),
            ("principal_medium_quality", "tbl-medium-quality")),
    }
    for name, displays in table_documents.items():
        text = readers[name]
        prefix = "../" if name.startswith("supplement/") else ""
        for stem, identity in displays:
            marker = "{{< include " + prefix + "tables/" + stem + ".qmd >}}"
            if marker not in text or "@" + identity not in text.split(marker, 1)[0]:
                failures.append("table_not_introduced:" + identity)
    if any(re.search(r"(?m)^#{1,3} [^\n]+\n\n(?:!\[|\| |\{\{< include)", text)
           for name, text in readers.items() if name.endswith(".md") or name == "index.qmd"):
        failures.append("section_starts_with_display")
    keyword_count = front.split("keywords:", 1)[1].split("abstract:", 1)[0].count("  - ")
    if not 1 <= keyword_count <= 7:
        failures.append("keyword_budget_invalid")
    highlights = (root / "highlights.txt").read_text().splitlines()
    if not 3 <= len(highlights) <= 5 or any(len(line) > 85 or not line.strip() for line in highlights):
        failures.append("highlight_budget_invalid")
    tail = f"# {AI_HEADING}\n\n{AI_DISCLOSURE}\n\n# References"
    if not article.rstrip().endswith(tail):
        failures.append("ai_declaration_missing_changed_or_not_before_references")
    if f"# Acknowledgements\n\n{ACKNOWLEDGEMENTS}\n\n{tail}" not in article:
        failures.append("hpc_acknowledgements_missing_changed_or_misplaced")
    if r"\renewcommand{\bibsection}{\section{\refname}}" not in adapter:
        failures.append("numbered_bibliography_heading_missing")
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
    if AI_HEADING not in content or TITLE not in unescape(content):
        failures.append("rendered_scope_or_declaration_missing")
    if re.search(r"(?:Figure|Table|Section)\s*<a[^>]*class=\"quarto-xref\"[^>]*>(?:Figure|Table|Section)", content):
        failures.append("duplicated_crossreference_prefix")
    headings = "\n".join(unescape(re.sub(r"<[^>]+>", " ", match.group(2)))
                         for match in re.finditer(r"<h([1-6])\b[^>]*>(.*?)</h\1>", content, re.DOTALL))
    if not numbered_backmatter(headings):
        failures.append("html_backmatter_numbering_or_order_missing")
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
    supplement_html = output / "supplement/index.html"
    supplement_pdf = output / "supplement/index.pdf"
    if not supplement_html.is_file() or not supplement_pdf.is_file():
        failures.append("scientific_supplement_render_missing")
    else:
        content += supplement_html.read_text(encoding="utf-8")
        if not supplement_pdf.read_bytes().startswith(b"%PDF-"):
            failures.append("invalid_supplement_pdf_header")
        newest_supplement = max((root / name).stat().st_mtime_ns for name in READER_TEXTS
                                if name.startswith("supplement/"))
        if supplement_pdf.stat().st_mtime_ns < newest_supplement:
            failures.append("supplement_pdf_predates_sources")
    principal_receipt = output / "tables/principal_assets.json"
    if not principal_receipt.is_file():
        failures.append("principal_asset_receipt_missing")
    else:
        record = json.loads(principal_receipt.read_text())
        if (record.get("principal_rows") != 150 or record.get("experimental_units") != 10
                or record.get("research_execution_performed") is not False
                or record.get("scientific_reporting_eligible") is not False):
            failures.append("principal_asset_scope_drift")
        for name, expected in record.get("source_files", {}).items():
            path = ROOT / name
            if (not path.resolve().is_relative_to((ROOT / "docs/evidence").resolve())
                    or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
                failures.append("principal_source_hash_mismatch")
        for asset in record.get("outputs", []):
            path = safe_child(output, asset["relative_path"])
            if path is None or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
                failures.append("principal_output_hash_mismatch")
    for key in re.findall(r"^@\w+\{([^,]+),", (root / "references.bib").read_text(), re.MULTILINE):
        if f'id="ref-{key}"' not in content:
            failures.append("rendered_reference_missing:" + key)
    for path in output.rglob("*"):
        if path.is_symlink() or path.suffix.lower() in {".pt", ".parquet", ".pickle", ".gz", ".lic"}:
            failures.append("unexpected_research_artifact:" + path.name)
    return failures


def numbered_backmatter(text: str) -> bool:
    """Check sequential headings without depending on their current section IDs."""
    normalized = " ".join(text.split())
    titles = ("Acknowledgements", AI_HEADING, "References")
    matches = [re.search(r"\b(\d+)\.?\s+" + re.escape(title), normalized)
               for title in titles]
    if any(match is None for match in matches):
        return False
    numbers = [int(match.group(1)) for match in matches]
    return (matches[0].start() < matches[1].start() < matches[2].start()
            and numbers[1] == numbers[0] + 1 and numbers[2] == numbers[1] + 1)


def check_pdf_text(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    failures = []
    for word in ("Evaluating Graph Neural", "0.6993", "Gasse", "Goerigk", "References"):
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
    if not numbered_backmatter(text):
        failures.append("pdf_backmatter_numbering_or_order_missing")
    match = re.search(r"(?m)(?:^|[\n\f])[ \t]*(?:\d+\.[ \t]+)?(References)[ \t]*(?:\n|$)", text)
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
