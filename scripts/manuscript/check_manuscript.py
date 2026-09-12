"""Validate the static, evidence-pending manuscript without a research runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = ROOT / "manuscript"


def check_source(root: Path = MANUSCRIPT) -> list[str]:
    """Return failures; this gate intentionally supports only the protocol draft."""
    failures: list[str] = []
    article = (root / "index.qmd").read_text(encoding="utf-8")
    bibliography = (root / "references.bib").read_text(encoding="utf-8")
    evidence = json.loads((root / "evidence-status.json").read_text(encoding="utf-8"))
    config = (root / "_quarto.yml").read_text(encoding="utf-8")
    citation_keys = set(re.findall(r"(?<!\w)@([a-z][a-z0-9_-]+)", article))
    entries = re.findall(r"^@\w+\{([^,]+),", bibliography, re.MULTILINE)
    if citation_keys != set(entries) or len(entries) != len(set(entries)):
        failures.append("bibliography_not_exactly_cited_or_duplicate_keys")
    if "gasse2019" not in citation_keys or "1906.01629v3" not in bibliography:
        failures.append("mandatory_gasse_v3_reference_missing")
    if "10.48550/arXiv.1906.01629" not in bibliography:
        failures.append("mandatory_gasse_doi_missing")
    if re.search(r"```\s*\{", article) or "{{< include" in article:
        failures.append("executable_or_unreviewed_included_content")
    if any(setting not in config for setting in ("enabled: false", "code-links: false", "meca-bundle: false")):
        failures.append("static_publication_boundary_missing")
    if "empirical confirmation pending" not in article:
        failures.append("visible_pending_status_missing")
    if evidence.get("schema_version") != 1:
        failures.append("unsupported_evidence_schema")
    if evidence.get("development_only") is not True:
        failures.append("development_boundary_missing")
    if evidence.get("scientific_reporting_eligible") is not False:
        failures.append("scientific_claim_without_review")
    if evidence.get("empirical_results_included") is not False or evidence.get("empirical_assets") != []:
        failures.append("empirical_assets_require_dedicated_review")
    if evidence.get("authorship_confirmed") is not False or "author: []" not in article:
        failures.append("authorship_requires_editorial_confirmation")
    expected = {"parents": 42, "easy": 30, "medium": 12, "hard": 0,
                "train": 24, "validation": 10, "test": 8, "seed": 42, "epochs": 100,
                "maximum_label_gap_relative": 0.1}
    protocol = evidence.get("confirmation_protocol", {})
    if any(protocol.get(key) != value for key, value in expected.items()):
        failures.append("confirmation_protocol_drift")
    acceptance = evidence.get("acceptance", {})
    required_pending = ("complete_source_label_bundle", "strict_42_graph_bundle",
                        "confirmation_training_100_epochs", "held_out_confirmation_evaluation",
                        "paired_four_arm_comparison")
    if any(acceptance.get(key) != "pending" for key in required_pending):
        failures.append("acceptance_claim_requires_evidence_update")
    if acceptance.get("full_90_parent_campaign") != "deferred":
        failures.append("full_population_scope_changed")
    private_pattern = re.compile(r"/raid/|/home/|(?<![\w{])[A-Za-z]:[\\/]|WLSSecret|LicenseID|gurobi\.lic")
    for name in ("index.qmd", "references.bib", "evidence-status.json", "_quarto.yml"):
        payload = (root / name).read_bytes()
        if b"\r" in payload:
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
    if "empirical confirmation pending" not in content:
        failures.append("rendered_status_missing")
    if not pdf.read_bytes().startswith(b"%PDF-"):
        failures.append("invalid_pdf_header")
    for key in ("gasse2019", "cappart2021", "ding2020", "khalil2022", "canturk2024",
                "fischetti2003", "nair2020", "gurobi2026"):
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
    for expected in ("Graph Neural Guidance", "empirical confirmation pending",
                     "Gasse", "Fischetti", "Nair", "References"):
        if expected not in text:
            failures.append(f"pdf_text_missing:{expected}")
    if "??" in text or "[?]" in text:
        failures.append("unresolved_pdf_reference")
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
