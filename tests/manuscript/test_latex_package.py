"""Verify retained Quarto source selection without compiling TeX."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/manuscript"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("latex_package", SCRIPTS / "package_latex_project.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class RetainedSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_manuscript_export_takes_precedence_over_old_root_source(self):
        (self.root / "index.tex").write_text("old")
        exported = self.root / "_manuscript/_tex/index.tex"
        exported.parent.mkdir(parents=True)
        exported.write_text("current")
        self.assertEqual(PACKAGE.generated_tex(self.root), exported)

    def test_root_level_retained_source_is_supported(self):
        source = self.root / "index.tex"
        source.write_text("current")
        self.assertEqual(PACKAGE.generated_tex(self.root), source)

    def test_missing_source_fails_with_render_instruction(self):
        with self.assertRaisesRegex(ValueError, "render the manuscript first"):
            PACKAGE.generated_tex(self.root)


if __name__ == "__main__":
    unittest.main()
