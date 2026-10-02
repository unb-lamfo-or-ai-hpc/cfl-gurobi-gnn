"""Package the generated article and its dependencies, never research binaries.

SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from check_manuscript import MANUSCRIPT, check_source
from import_pr60_evidence import UNSAFE


def package(output: Path, root: Path = MANUSCRIPT) -> None:
    failures = check_source(root)
    if failures:
        raise ValueError("source checks failed: " + str(failures))
    names = ["index.tex", "references.bib", "elsarticle.cls", "elsarticle-harv.bst",
             "LICENSE", "highlights.txt", "template-provenance/elsevier.json",
             "template-provenance/ELSEVIER-NOTICE.md"]
    names += ["figures/" + name + ".pdf" for name in (
        "figure_pipeline", "figure_training_validation_loss",
        "figure_validation_test_gap_effects", "figure_time_to_ten_percent_gap")]
    payload = {name: (root / name).read_bytes() for name in names}
    if UNSAFE.search(payload["index.tex"].decode("utf-8")):
        raise ValueError("private content in generated article source")
    instructions = (
        "# Editable Elsevier LaTeX article\n\n"
        "Compile with an existing TeX distribution:\n\n"
        "    pdflatex -halt-on-error index.tex\n"
        "    bibtex index\n"
        "    pdflatex -halt-on-error index.tex\n"
        "    pdflatex -halt-on-error index.tex\n\n"
        "Required packages include orcidlink, amsmath, amssymb, graphicx, booktabs, "
        "longtable, array, calc, hyperref, and natbib. The class loads natbib.\n\n"
        "Original article material uses MIT. Unmodified Elsevier class and style "
        "retain LPPL rights. Inspect the PDF before author approval or submission. "
        "A source archive is not proof of successful compilation or scientific validity.\n"
    )
    payload["README.md"] = instructions.encode("utf-8")
    receipt = {"schema_version": 1, "files": {n: hashlib.sha256(v).hexdigest() for n, v in payload.items()},
               "scope": "editable_article_source_and_vector_figures", "research_execution_performed": False}
    payload["MANIFEST.json"] = (json.dumps(receipt, indent=2) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(payload.items()):
            archive.writestr(name, value)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity failure")
    print("PR62_LATEX_SOURCE_PACKAGE_OK")
    print("SHA256=" + hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    package(parser.parse_args().output)
