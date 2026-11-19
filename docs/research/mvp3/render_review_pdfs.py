"""Render the two PR99 review documents; no solver, dataset or scientific imports.

Dependencies: Quarto/Pandoc, pdflatex, Poppler, ReportLab and Pillow.
All intermediates stay below output-dir/tmp. Fonts are embedded from font-dir.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, ListFlowable, ListItem,
    LongTable, PageTemplate, Paragraph, Spacer, TableStyle,
)

REPO = "https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn"
SOURCES = (
    ("coauthor-methodological-protocol.md",
     "CFL-GNN-MVP3-Protocolo-Metodologico-PR99.pdf", "Methodological protocol"),
    ("gurobi-adequacy-and-shared-architecture.md",
     "CFL-GNN-MVP3-Nota-Tecnica-Gurobi-PR99.pdf", "Technical Gurobi note"),
)
TEAL = colors.HexColor("#14616D")
INK = colors.HexColor("#1E2933")
MUTED = colors.HexColor("#52616B")
PT = 72 / 72.27


def run(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font_setup(folder):
    for name, filename in (
        ("ReviewSerif", "times.ttf"), ("ReviewSerif-Bold", "timesbd.ttf"),
        ("ReviewSerif-Italic", "timesi.ttf"), ("ReviewSerif-BoldItalic", "timesbi.ttf"),
        ("ReviewSans", "arial.ttf"), ("ReviewSans-Bold", "arialbd.ttf"),
        ("ReviewMono", "cour.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
    pdfmetrics.registerFontFamily(
        "ReviewSerif", normal="ReviewSerif", bold="ReviewSerif-Bold",
        italic="ReviewSerif-Italic", boldItalic="ReviewSerif-BoldItalic",
    )
    pdfmetrics.registerFontFamily(
        "ReviewSans", normal="ReviewSans", bold="ReviewSans-Bold"
    )


def prepare_math(documents, args, work):
    keys = []

    def visit(obj):
        if isinstance(obj, dict):
            if obj.get("t") == "Math":
                kind, expr = obj["c"]
                key = (kind["t"], expr)
                if key not in keys:
                    keys.append(key)
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for value in obj:
                visit(value)

    for doc in documents:
        visit(doc)
    work = work / hashlib.sha256(json.dumps(keys).encode("utf-8")).hexdigest()[:16]
    work.mkdir(parents=True, exist_ok=True)
    preamble = r"""\documentclass{article}
\usepackage{amsmath,amssymb}
\pagestyle{empty}
\begin{document}
\hoffset=-1in
\voffset=-1in
"""
    parts = [preamble]
    for i, (kind, expr) in enumerate(keys, 1):
        style = r"\displaystyle" if kind == "DisplayMath" else r"\textstyle"
        parts.append(
            r"\setbox0=\hbox{\fontsize{10.5}{12}\selectfont$"
            + style + " " + expr + "$}\n"
            + r"\typeout{FORMULA|" + str(i)
            + r"|\the\wd0|\the\ht0|\the\dp0}" + "\n"
            + r"\pdfpagewidth=\dimexpr\wd0+4pt\relax" + "\n"
            + r"\pdfpageheight=\dimexpr\ht0+\dp0+4pt\relax" + "\n"
            + r"\shipout\vbox{\kern2pt\hbox{\kern2pt\box0\kern2pt}\kern2pt}" + "\n"
        )
    parts.append(r"\end{document}" + "\n")
    tex = work / "formulas.tex"
    tex.write_text("".join(parts), encoding="utf-8")
    if not keys:
        return {}, []
    run([str(args.pdflatex), "-no-shell-escape", "-interaction=nonstopmode",
         "-halt-on-error", tex.name], cwd=work)
    run([str(args.pdftoppm), "-r", "300", "-png",
         str(work / "formulas.pdf"), str(work / "formula")])
    metrics = {}
    log = (work / "formulas.log").read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(
        r"FORMULA\|(\d+)\|([\d.]+)pt\|([\d.]+)pt\|([\d.]+)pt", log
    ):
        index, w, h, d = match.groups()
        metrics[int(index)] = tuple(float(v) * PT for v in (w, h, d))
    pngs = sorted(work.glob("formula-*.png"))
    if len(pngs) != len(keys) or len(metrics) != len(keys):
        raise ValueError("formula raster/metric count mismatch")
    images = {}
    for i, (key, png) in enumerate(zip(keys, pngs), 1):
        w, h, d = metrics[i]
        images[key] = (png, w + 4 * PT, h + d + 4 * PT, d + 2 * PT)
    return images, keys


class ReviewDoc(BaseDocTemplate):
    def __init__(self, filename, title, short_title, revision):
        self.review_title = title
        self.short_title = short_title
        self.revision = revision
        super().__init__(
            str(filename), pagesize=A4, leftMargin=49, rightMargin=49,
            topMargin=57, bottomMargin=48, title=title,
            author="CFL-GNN research project", allowSplitting=1,
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id="review", frames=[frame],
                                          onPage=self.decorate))
        self.bookmarks = 0

    def decorate(self, c, doc):
        c.saveState()
        c.setStrokeColor(TEAL)
        c.setLineWidth(0.6)
        c.line(self.leftMargin, A4[1] - 39, A4[0] - self.rightMargin, A4[1] - 39)
        c.setFont("ReviewSans", 8)
        c.setFillColor(MUTED)
        c.drawString(self.leftMargin, A4[1] - 31, "CFL-GNN | MVP 3.0 | COAUTHOR REVIEW")
        c.setFont("ReviewSans", 7.4)
        c.drawString(self.leftMargin, 29,
                     f"19 November 2026 | PR99 Draft | {self.revision[:8]}")
        c.drawRightString(A4[0] - self.rightMargin, 29, str(doc.page))
        c.restoreState()

    def afterFlowable(self, item):
        if isinstance(item, Paragraph) and item.style.name.startswith("Heading"):
            self.bookmarks += 1
            label = item.getPlainText()
            key = f"section-{self.bookmarks}"
            self.canv.bookmarkPage(key)
            level = int(item.style.name[-1]) - 1
            # The title is a root outline entry; all heading levels are sequential.
            self.canv.addOutlineEntry(label, key, level=max(0, level), closed=False)


class Renderer:
    def __init__(self, math_images, revision):
        self.math_images = math_images
        self.revision = revision
        self.styles = getSampleStyleSheet()
        base = dict(fontName="ReviewSerif", fontSize=10.5, leading=13.6,
                    textColor=INK, spaceAfter=6, alignment=TA_LEFT,
                    autoLeading="max", splitLongWords=1, allowWidows=0, allowOrphans=0)
        self.body = ParagraphStyle("ReviewBody", **base)
        self.small = ParagraphStyle("ReviewSmall", parent=self.body, fontSize=9.1, leading=12)
        self.cell = ParagraphStyle("ReviewCell", parent=self.body, fontSize=8.5,
                                   leading=11, spaceAfter=0, allowWidows=1, allowOrphans=1)
        self.head_cell = ParagraphStyle("ReviewHeadCell", parent=self.cell,
                                        fontName="ReviewSans-Bold", fontSize=8.1)
        self.headings = {}
        for level, size in ((1, 22), (2, 14), (3, 11.5), (4, 10.6)):
            self.headings[level] = ParagraphStyle(
                f"Heading{level}", parent=self.body, fontName="ReviewSans-Bold",
                fontSize=size, leading=size * 1.23, textColor=TEAL if level <= 2 else INK,
                spaceBefore=16 if level > 1 else 6, spaceAfter=8,
                keepWithNext=True,
            )

    def link(self, target):
        if re.match(r"https?://", target) or target.startswith("#"):
            return target
        resolved = os.path.normpath("docs/research/mvp3/" + target).replace("\\", "/")
        return f"{REPO}/blob/{self.revision}/{resolved}"

    def inline(self, items, table=False):
        parts = []
        for obj in items:
            t, c = obj["t"], obj.get("c")
            if t == "Str":
                parts.append(html.escape(c))
            elif t in ("Space", "SoftBreak"):
                parts.append(" ")
            elif t == "LineBreak":
                parts.append("<br/>")
            elif t in ("Strong", "Emph"):
                tag = "b" if t == "Strong" else "i"
                parts.append(f"<{tag}>" + self.inline(c, table) + f"</{tag}>")
            elif t == "Code":
                size = "7.7" if table else "9.1"
                parts.append(f'<font name="ReviewMono" size="{size}">'
                             + html.escape(c[1]) + "</font>")
            elif t == "Math":
                kind, expr = c
                png, w, h, depth = self.math_images[(kind["t"], expr)]
                parts.append(f'<img src="{html.escape(str(png))}" width="{w:.3f}" '
                             f'height="{h:.3f}" valign="{-depth:.3f}"/>')
            elif t == "Link":
                label = self.inline(c[1], table)
                url = html.escape(self.link(c[2][0]), quote=True)
                parts.append(f'<link href="{url}" color="#14616D">{label}</link>')
            elif t == "Quoted":
                parts.append("“" + self.inline(c[1], table) + "”")
            elif t in ("Superscript", "Subscript"):
                tag = "super" if t == "Superscript" else "sub"
                parts.append(f"<{tag}>" + self.inline(c, table) + f"</{tag}>")
            elif t == "Span":
                parts.append(self.inline(c[1], table))
            elif t == "RawInline":
                raise ValueError("unreviewed raw inline: " + str(c))
            else:
                raise ValueError("unsupported inline: " + t)
        return "".join(parts)

    def table(self, content, width):
        _, caption, specs, head, bodies, foot = content
        rows = list(head[1])
        for body in bodies:
            rows.extend(body[2])
            rows.extend(body[3])
        rows.extend(foot[1])
        data = []
        for ridx, (_, cells) in enumerate(rows):
            row = []
            for _, align, row_span, col_span, blocks in cells:
                if row_span != 1 or col_span != 1:
                    raise ValueError("unexpected spanning cell")
                text = "<br/>".join(self.inline(b["c"], True) for b in blocks
                                    if b["t"] in ("Plain", "Para"))
                row.append(Paragraph(text, self.head_cell if ridx == 0 else self.cell))
            data.append(row)
        count = len(data[0])
        first = " ".join(data[0][0].getPlainText().split()).lower()
        if count == 3:
            ratios = (0.27, 0.23, 0.50)
        elif count == 4 and first == "stage":
            ratios = (0.40, 0.11, 0.245, 0.245)
        elif count == 4 and first.startswith("candidate"):
            ratios = (0.18, 0.265, 0.265, 0.29)
        elif count == 4:
            ratios = (0.40, 0.20, 0.20, 0.20)
        else:
            ratios = [1 / count] * count
        table = LongTable(
            data, colWidths=[width * r for r in ratios], repeatRows=1,
            hAlign="LEFT", splitByRow=1, splitInRow=1,
        )
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2F4")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.7, TEAL),
            ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#9CAEB2")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F6F8F9")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return [table, Spacer(1, 9)]

    def blocks(self, blocks, width):
        out = []
        for obj in blocks:
            t, c = obj["t"], obj.get("c")
            if t == "Header":
                level, attr, items = c
                out.append(Paragraph(self.inline(items), self.headings[min(level, 4)]))
            elif t in ("Para", "Plain"):
                if len(c) == 1 and c[0]["t"] == "Math" and c[0]["c"][0]["t"] == "DisplayMath":
                    key = (c[0]["c"][0]["t"], c[0]["c"][1])
                    png, w, h, _ = self.math_images[key]
                    if w > width:
                        h *= width / w
                        w = width
                    image = Image(str(png), width=w, height=h, hAlign="CENTER")
                    out.extend([Spacer(1, 3), image, Spacer(1, 9)])
                else:
                    out.append(Paragraph(self.inline(c), self.body))
            elif t in ("BulletList", "OrderedList"):
                items = c if t == "BulletList" else c[1]
                flow = [ListItem(self.blocks(item, width - 20), leftIndent=0)
                        for item in items]
                out.extend([ListFlowable(
                    flow, bulletType="bullet" if t == "BulletList" else "1",
                    start=None if t == "BulletList" else c[0][0],
                    leftIndent=16, bulletFontName="ReviewSerif",
                    bulletFontSize=8.5, spaceAfter=8,
                )])
            elif t == "Table":
                out.extend(self.table(c, width))
            elif t == "HorizontalRule":
                out.append(Spacer(1, 8))
            elif t == "BlockQuote":
                out.extend(self.blocks(c, width - 16))
            elif t == "Div":
                out.extend(self.blocks(c[1], width))
            else:
                raise ValueError("unsupported block: " + t)
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dir", type=Path, default=Path(__file__).parent)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--quarto", default="quarto")
    ap.add_argument("--pdflatex", type=Path, required=True)
    ap.add_argument("--pdftoppm", default="pdftoppm")
    ap.add_argument("--font-dir", type=Path, default=Path("C:/Windows/Fonts"))
    args = ap.parse_args()
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source = args.source_dir.resolve()
    asts = [json.loads(run([args.quarto, "pandoc", str(source / name),
                           "--from=markdown+tex_math_dollars", "--to=json"]))
            for name, _, _ in SOURCES]
    font_setup(args.font_dir)
    images, expressions = prepare_math(asts, args, args.output_dir / "tmp/pdfs/math")
    renderer = Renderer(images, args.revision)
    receipts = []
    for (name, filename, short), ast in zip(SOURCES, asts):
        title = ast["blocks"][0]["c"][2]
        plain_title = " ".join(x.get("c", "") for x in title if x["t"] == "Str")
        output = args.output_dir / filename
        doc = ReviewDoc(output, plain_title, short, args.revision)
        doc.build(renderer.blocks(ast["blocks"], doc.width))
        receipts.append({
            "file": filename, "sha256": sha(output),
            "source": name, "source_sha256": sha(source / name),
        })
    receipt = {
        "source_revision": args.revision, "date": "2026-11-19",
        "scope": "PR99 documentary review, not experimental execution",
        "renderer": "ReportLab with native LaTeX formulas rasterized at 300dpi",
        "math_expressions": len(expressions), "documents": receipts,
    }
    (args.output_dir / "review-build.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
