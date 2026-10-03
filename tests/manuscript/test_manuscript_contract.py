"""Regression tests for current evidence, static rendering, and editorial bounds."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("manuscript_check", ROOT / "scripts/manuscript/check_manuscript.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class ManuscriptContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "manuscript"
        shutil.copytree(ROOT / "manuscript", self.root,
                        ignore=shutil.ignore_patterns("_manuscript", ".quarto", "figures", "tables", "index.tex"))

    def change(self, name, old, new):
        path = self.root / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def test_sources_pass_without_generated_assets(self):
        self.assertEqual(CHECK.check_source(self.root), [])

    def test_changed_source_csv_fails(self):
        path = self.root / "results/current/table_predictive_metrics.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertTrue(any(x.startswith("source_evidence_invalid:") for x in CHECK.check_source(self.root)))

    def test_changed_report_fails_even_with_same_contract(self):
        path = self.root / "results/current/pr60_scientific_evidence_report.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertTrue(any(x.startswith("source_evidence_invalid:") for x in CHECK.check_source(self.root)))

    def test_changed_manifest_fails(self):
        path = self.root / "results/current/pr60_scientific_evidence_manifest.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertTrue(any(x.startswith("source_evidence_invalid:") for x in CHECK.check_source(self.root)))

    def test_wrong_archive_receipt_fails(self):
        path = self.root / "results/current/import_receipt.json"
        data = json.loads(path.read_text())
        data["archive_sha256"] = "0" * 64
        path.write_text(json.dumps(data))
        self.assertIn("import_receipt_mismatch", CHECK.check_source(self.root))

    def test_final_epoch_budget_is_verified(self):
        path = self.root / "results/current/table_training_epoch_metrics.csv"
        path.write_text("\n".join(path.read_text().splitlines()[:-1]) + "\n")
        self.assertIn("final_training_evidence_inconsistent", CHECK.check_source(self.root))

    def test_historical_cohort_cannot_replace_current(self):
        path = self.root / "evidence-status.json"
        data = json.loads(path.read_text())
        data["current_protocol"]["parents"] = 39
        path.write_text(json.dumps(data))
        self.assertIn("current_cohort_drift", CHECK.check_source(self.root))

    def test_scientific_certification_is_not_inferred(self):
        path = self.root / "evidence-status.json"
        data = json.loads(path.read_text())
        data["scientific_reporting_eligible"] = True
        path.write_text(json.dumps(data))
        self.assertIn("scientific_claim_without_review", CHECK.check_source(self.root))

    def test_author_order_and_orcid_are_frozen(self):
        self.change("index.qmd", "0000-0001-5913-2997", "0000-0000-0000-0000")
        self.assertIn("confirmed_authorship_mismatch", CHECK.check_source(self.root))

    def test_orcid_icons_required(self):
        self.change("_extensions/elsevier/template.tex", r"\usepackage{orcidlink}", "")
        self.assertIn("orcid_icon_package_missing_or_replaced", CHECK.check_source(self.root))

    def test_author_year_journal_class_required(self):
        self.change("_extensions/elsevier/template.tex", "{elsarticle}", "{article}")
        self.assertIn("elsevier_author_year_layout_missing", CHECK.check_source(self.root))

    def test_four_new_references_are_required(self):
        self.change("index.qmd", "@qu2026", "Qu et al.")
        self.assertIn("required_references_missing", CHECK.check_source(self.root))

    def test_unknown_citation_fails(self):
        self.change("index.qmd", "# Introduction", "# Introduction\n\n@invented2026")
        self.assertIn("bibliography_not_exactly_cited_or_duplicate_keys", CHECK.check_source(self.root))

    def test_class_aware_abstract_must_explain_positive_values(self):
        self.change("index.qmd", "value 1, which are rare", "the rare class")
        self.assertIn("class_aware_abstract_explanation_missing", CHECK.check_source(self.root))

    def test_article_has_no_bold_emphasis(self):
        self.change("index.qmd", "# Introduction", "# Introduction\n\n**Emphasis**")
        self.assertIn("bold_article_emphasis_not_permitted", CHECK.check_source(self.root))

    def test_metrics_are_defined_before_results(self):
        self.change("index.qmd", "Expected calibration error (ECE)", "ECE")
        self.assertIn("metrics_not_defined_before_results", CHECK.check_source(self.root))

    def test_final_section_uses_reviewed_structure(self):
        self.change("index.qmd", "# Final considerations, limitations and future work", "# Conclusions")
        self.assertIn("editorial_final_section_missing", CHECK.check_source(self.root))

    def test_pipeline_is_announced_before_its_display(self):
        self.change("index.qmd", "@fig-pipeline summarizes", "The pipeline summarizes")
        self.assertIn("figure_not_introduced:fig-pipeline", CHECK.check_source(self.root))

    def test_predictive_table_is_announced_before_its_display(self):
        self.change("index.qmd", "@tbl-predictive reports", "The table reports")
        self.assertIn("table_not_introduced:tbl-predictive", CHECK.check_source(self.root))

    def test_sections_cannot_start_with_a_table(self):
        self.change("index.qmd", "{{< include tables/current_influence.qmd >}}", "## Empty lead\n\n{{< include tables/current_influence.qmd >}}")
        self.assertIn("section_starts_with_display", CHECK.check_source(self.root))

    def test_l2o_context_required(self):
        self.change("index.qmd", "## Learning to Optimize", "## Other topic")
        self.assertIn("reviewed_l2o_context_missing", CHECK.check_source(self.root))

    def test_unapproved_include_fails(self):
        self.change("index.qmd", "tables/current_predictive.qmd", "../../private.qmd")
        self.assertIn("executable_or_unreviewed_included_content", CHECK.check_source(self.root))

    def test_executable_chunk_fails(self):
        self.change("index.qmd", "# Introduction", "# Introduction\n```{python}\nprint(42)\n```\n")
        self.assertIn("executable_or_unreviewed_included_content", CHECK.check_source(self.root))

    def test_declaration_is_exact_and_before_references(self):
        self.change("index.qmd", "# References", "# Other section\n\n# References")
        self.assertIn("ai_declaration_missing_changed_or_not_before_references", CHECK.check_source(self.root))

    def test_highlights_length_is_bounded(self):
        (self.root / "highlights.txt").write_text("A" * 86 + "\n")
        self.assertIn("highlight_budget_invalid", CHECK.check_source(self.root))

    def test_upstream_class_is_hash_bound_not_relicensed(self):
        path = self.root / "elsarticle.cls"
        path.write_bytes(path.read_bytes() + b"% changed\n")
        self.assertIn("template_hash_mismatch:elsarticle.cls", CHECK.check_source(self.root))

    def test_hardware_inventory_is_not_allocation(self):
        self.change("index.qmd", "not a runtime hardware probe", "verified allocation")
        self.assertIn("computational_environment_scope_missing", CHECK.check_source(self.root))

    def test_sata_interface_is_bits_not_bytes(self):
        self.change("index.qmd", "6 Gb/s interface", "6 GB/s interface")
        self.assertIn("computational_environment_scope_missing", CHECK.check_source(self.root))

    def test_private_path_fails_but_https_passes(self):
        self.assertEqual(CHECK.check_source(self.root), [])
        self.change("index.qmd", "# Introduction", "# Introduction\n\n/raid/private/output")
        self.assertIn("private_content:index.qmd", CHECK.check_source(self.root))

    def test_windows_private_path_fails(self):
        self.change("index.qmd", "# Introduction", "# Introduction\n\nC:\\Users\\private")
        self.assertIn("private_content:index.qmd", CHECK.check_source(self.root))

    def test_missing_render_is_not_success(self):
        self.assertEqual(CHECK.check_rendered(self.root), ["html_or_pdf_missing"])

    def test_html_refresh_cannot_qualify_a_stale_pdf(self):
        output = self.root / "_manuscript"
        output.mkdir()
        (output / "index.html").write_text("<html></html>")
        pdf = output / "index.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        os.utime(pdf, (1, 1))
        self.assertIn("pdf_predates_current_article_sources", CHECK.check_rendered(self.root))

    def test_pdf_twenty_page_limit(self):
        path = self.root / "text.txt"
        path.write_text("Body\f" * 20 + "References\n")
        self.assertIn("manuscript_body_exceeds_twenty_pages", CHECK.check_pdf_text(path))

    def test_pdf_orcid_identifier_not_printed(self):
        path = self.root / "text.txt"
        path.write_text("ORCID: 0000-0001-5913-2997")
        self.assertIn("orcid_identifier_printed_instead_of_icon", CHECK.check_pdf_text(path))

    def test_pdf_unresolved_citation_fails(self):
        path = self.root / "text.txt"
        path.write_text("References [?]")
        self.assertIn("unresolved_pdf_reference", CHECK.check_pdf_text(path))

    def test_references_heading_is_not_suppressed_in_the_adapter(self):
        adapter = (ROOT / "manuscript/_extensions/elsevier/template.tex").read_text()
        self.assertNotIn(r"\renewcommand{\bibsection}{}", adapter)

    def test_pdf_uses_vector_fonts_and_unicode_text_mapping(self):
        adapter = (ROOT / "manuscript/_extensions/elsevier/template.tex").read_text()
        self.assertIn(r"\usepackage{lmodern}", adapter)
        self.assertIn(r"\pdfgentounicode=1", adapter)

    def test_workflow_does_not_deploy_pull_requests_or_execute_research(self):
        workflow = (ROOT / ".github/workflows/manuscript.yml").read_text()
        self.assertIn("github.event_name != 'pull_request'", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertNotIn("github.ref == 'refs/heads/develop'", workflow)
        self.assertIn("path: manuscript/_manuscript", workflow)
        self.assertIn("quarto render manuscript --no-execute", workflow)
        self.assertNotIn("pull_request_target", workflow)

    def test_article_displays_have_no_repetitive_source_sentences(self):
        self.assertNotIn("Source:", (self.root / "index.qmd").read_text(encoding="utf-8"))
        generator = (ROOT / "scripts/manuscript/build_cor_assets.py").read_text(encoding="utf-8")
        self.assertNotIn("Source:", generator)


if __name__ == "__main__":
    unittest.main()
