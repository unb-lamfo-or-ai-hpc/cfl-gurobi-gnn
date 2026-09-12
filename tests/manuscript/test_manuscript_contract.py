"""Standard-library regression tests for the isolated manuscript boundary."""

import importlib.util
import json
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
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "manuscript"
        shutil.copytree(ROOT / "manuscript", self.root,
                        ignore=shutil.ignore_patterns("_manuscript", ".quarto", "*.tex", "*.pdf"))
        # The extension TeX adapter is source, not a generated article.
        shutil.copy2(ROOT / "manuscript/_extensions/sbc/template.tex", self.root / "_extensions/sbc/template.tex")

    def test_source_passes(self):
        self.assertEqual(CHECK.check_source(self.root), [])

    def test_unknown_citation_fails(self):
        with (self.root / "index.qmd").open("a", encoding="utf-8") as stream:
            stream.write("\n@invented2026\n")
        self.assertIn("bibliography_not_exactly_cited_or_duplicate_keys", CHECK.check_source(self.root))

    def test_author_order_and_orcid_are_frozen(self):
        path = self.root / "index.qmd"
        path.write_text(path.read_text(encoding="utf-8").replace("0000-0001-5913-2997", "0000-0000-0000-0000"), encoding="utf-8")
        self.assertIn("confirmed_authorship_mismatch", CHECK.check_source(self.root))

    def test_text_orcid_fallback_is_rejected(self):
        path = self.root / "_extensions/sbc/template.tex"
        path.write_text(path.read_text(encoding="utf-8").replace(r"\usepackage{orcidlink}", ""), encoding="utf-8")
        self.assertIn("orcid_icon_package_missing_or_replaced", CHECK.check_source(self.root))

    def test_pdf_does_not_print_orcid_identifiers(self):
        path = self.root / "text.txt"
        path.write_text("ORCID: 0000-0001-5913-2997", encoding="utf-8")
        self.assertIn("orcid_identifier_printed_instead_of_icon", CHECK.check_pdf_text(path))

    def test_l2o_context_is_required(self):
        path = self.root / "index.qmd"
        path.write_text(path.read_text(encoding="utf-8").replace("## Learning to Optimize", "## Other topic"), encoding="utf-8")
        self.assertIn("reviewed_l2o_context_missing", CHECK.check_source(self.root))

    def test_declaration_is_exact_and_immediately_before_references(self):
        path = self.root / "index.qmd"
        path.write_text(path.read_text(encoding="utf-8").replace("# References", "# Additional section\n\n# References"), encoding="utf-8")
        self.assertIn("ai_declaration_missing_changed_or_not_before_references", CHECK.check_source(self.root))

    def test_twenty_page_body_limit(self):
        path = self.root / "text.txt"
        path.write_text(("Body\f" * 20) + "References\n", encoding="utf-8")
        self.assertIn("manuscript_body_exceeds_twenty_pages", CHECK.check_pdf_text(path))

    def test_empirical_claim_fails(self):
        path = self.root / "evidence-status.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["scientific_reporting_eligible"] = True
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("scientific_claim_without_review", CHECK.check_source(self.root))

    def test_executable_chunk_fails(self):
        with (self.root / "index.qmd").open("a", encoding="utf-8") as stream:
            stream.write("\n```{python}\nprint(42)\n```\n")
        self.assertIn("executable_or_unreviewed_included_content", CHECK.check_source(self.root))

    def test_template_edit_requires_provenance(self):
        with (self.root / "_extensions/sbc/template.tex").open("a", encoding="utf-8") as stream:
            stream.write("% changed\n")
        self.assertTrue(any(x.startswith("template_hash_mismatch:") for x in CHECK.check_source(self.root)))

    def test_missing_render_is_not_success(self):
        self.assertEqual(CHECK.check_rendered(self.root), ["html_or_pdf_missing"])

    def test_private_path_fails(self):
        with (self.root / "index.qmd").open("a", encoding="utf-8") as stream:
            stream.write("\n/raid/private/results\n")
        self.assertIn("private_content:index.qmd", CHECK.check_source(self.root))

    def test_windows_path_fails_without_rejecting_https_or_math(self):
        self.assertEqual(CHECK.check_source(self.root), [])
        with (self.root / "index.qmd").open("a", encoding="utf-8") as stream:
            stream.write("\nC:\\Users\\private\\results\n")
        self.assertIn("private_content:index.qmd", CHECK.check_source(self.root))

    def test_unresolved_pdf_citation_fails(self):
        path = self.root / "text.txt"
        path.write_text("Graph Neural Guidance empirical confirmation pending Gasse Fischetti Nair References [?]", encoding="utf-8")
        self.assertIn("unresolved_pdf_reference", CHECK.check_pdf_text(path))

    def test_publication_is_scoped_and_not_a_pull_request_deploy(self):
        workflow = (ROOT / ".github/workflows/manuscript.yml").read_text(encoding="utf-8")
        self.assertIn("github.event_name != 'pull_request'", workflow)
        self.assertIn("github.ref == 'refs/heads/develop'", workflow)
        self.assertIn("path: manuscript/_manuscript", workflow)
        self.assertIn("quarto render manuscript --no-execute", workflow)
        self.assertNotIn("pull_request_target", workflow)


if __name__ == "__main__":
    unittest.main()
