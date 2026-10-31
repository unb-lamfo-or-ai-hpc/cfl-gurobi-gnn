"""Static, descriptive assets for the sealed partial CPU subset. No solver."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("docs/evidence/pr89/partial-20261031")
MANIFEST_SHA = "d8f8e3fe7b95ad688cc6ab8e6218bdf133b16df88e28f39882dcb822426eec2b"
TABLES = ("partial_cpu_m0", "partial_cpu_m7", "partial_cpu_all")
FIGURE = "partial_cpu_time_gap"


def require(ok, code):
    if not ok:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_sources(repository=ROOT):
    directory = repository / SOURCE
    raw = (directory / "manifest.json").read_bytes()
    require(digest(raw) == MANIFEST_SHA, "partial_manifest_hash")
    m = json.loads(raw)
    require(
        m["scientific_reporting_eligible"] is False
        and m["final_campaign_return"] is False
        and m["received_cells"] == 50
        and m["planned_cells"] == 60,
        "partial_scope",
    )
    sources = {}
    for name, expected in m["files"].items():
        require(
            name
            in (
                "cells.csv",
                "thresholds.csv",
                "horizons.csv",
                "disposition.csv",
                "review.json",
            ),
            "partial_source_name",
        )
        path = directory / name
        require(not path.is_symlink(), "partial_source_symlink")
        raw = path.read_bytes()
        require(digest(raw) == expected, "partial_source_hash:" + name)
        sources[name] = (
            json.loads(raw)
            if name.endswith(".json")
            else list(csv.DictReader(io.StringIO(raw.decode(), newline="")))
        )
    rows = sources["cells.csv"]
    require(
        len(rows) == 50
        and [r["job_id"] for r in rows] == [str(j) for j in range(3675, 3725)],
        "partial_cells",
    )
    require(
        len({(r["alias"], r["threads"], r["method"]) for r in rows}) == 50,
        "partial_duplicate_cell",
    )
    require(
        all(
            r["scientific_reporting_eligible"] == "False"
            and r["scheduler_state"] == "COMPLETED"
            for r in rows
        ),
        "partial_promotion",
    )
    require(
        sum(r["status"] == "2" for r in rows) == 37
        and sum(r["status"] == "9" for r in rows) == 13,
        "partial_stops",
    )
    for r in rows:
        require(r["right_censored"] == str(r["status"] == "9"), "partial_censoring")
        require(
            r["numerically_sensitive"] == str(r["alias"] in ("M4", "M12")),
            "partial_numerical_scope",
        )
        require(
            all(
                math.isfinite(float(r[k]))
                for k in ("runtime_seconds", "primal", "dual", "gap_fraction")
            ),
            "partial_nonfinite",
        )
        require(
            math.isclose(
                abs(float(r["primal"]) - float(r["dual"])) / abs(float(r["primal"])),
                float(r["gap_fraction"]),
                rel_tol=1e-10,
                abs_tol=1e-14,
            ),
            "partial_gap",
        )
    ts = sources["thresholds.csv"]
    require(
        len(ts) == 200
        and len(sources["horizons.csv"]) == 200
        and len(sources["disposition.csv"]) == 60,
        "partial_temporal_coverage",
    )
    require(
        len({(r["job_id"], float(r["threshold"])) for r in ts}) == 200,
        "partial_threshold_duplicate",
    )
    require(
        all(r["state"] in ("observed", "right_censored") for r in ts),
        "partial_threshold_state",
    )
    require(
        sources["review.json"]["nested_triplets_verified"] == 50
        and sources["review.json"]["scientific_reporting_eligible"] is False,
        "partial_review_scope",
    )
    return sources


def threshold(sources, job, target=0.0001):
    selected = [
        r
        for r in sources["thresholds.csv"]
        if r["job_id"] == job and float(r["threshold"]) == target
    ]
    require(len(selected) == 1, "partial_threshold_unique")
    return selected[0]


def time_ratio(left, right, sensitive=False):
    if sensitive or left["state"] != "observed" or right["state"] != "observed":
        return None
    a, b = float(left["observed_seconds"]), float(right["observed_seconds"])
    require(
        math.isfinite(a) and math.isfinite(b) and a >= 0 and b > 0,
        "partial_ratio_duration",
    )
    return a / b


def check_source(manuscript, repository=ROOT):
    try:
        sources = load_sources(repository)
        rows = sources["cells.csv"]
        article = (manuscript / "index.qmd").read_text(encoding="utf-8")
        appendix = (manuscript / "supplement/extended-results.md").read_text(
            encoding="utf-8"
        )
        section = article.split("## Exploratory long-horizon CPU observations", 1)[
            1
        ].split("\n## ", 1)[0]
        require(
            "50 of 60 planned configurations" in section
            and "Thirty-seven" in section
            and "13 were time-limited, all on M7" in section,
            "partial_article_counts",
        )
        wins = 0
        for cap in (1, 2, 4, 8, 16):
            group = {
                r["presentation"]: r
                for r in rows
                if r["alias"] == "M0" and int(r["threads"]) == cap
            }
            wins += float(
                threshold(sources, group["G"]["job_id"])["observed_seconds"]
            ) < float(threshold(sources, group["B"]["job_id"])["observed_seconds"])
        require(
            wins == 4 and "before B at four of five caps" in section,
            "partial_article_m0_contrast",
        )
        require(
            len({r["primal"] for r in rows if r["alias"] == "M7"}) == 1
            and "same reported primal value" in section,
            "partial_article_m7_primal",
        )
        require(
            "do not establish certified speedups" in section
            and "completion-based subset" in section
            and "separately from the 150-observation" in section,
            "partial_article_scope",
        )
        for value in (
            "5.428377599678637",
            "0.132417%",
            "0.009495%",
            "0.000524%",
            "31.43",
            "47.57",
            "9.04",
        ):
            require(value in appendix, "partial_appendix_value:" + value)
        require(
            "not certified speedups" in appendix
            and "private models, solution vectors and solver logs were not reopened"
            in appendix,
            "partial_appendix_qualification",
        )
        for alias, low, high in (
            ("M4", "4.900767176540", "4.907256631978"),
            ("M12", "4.740932705477", "4.741382854739"),
            ("M0", "4.608296033273", "4.608320190371"),
        ):
            group = [r for r in rows if r["alias"] == alias]
            require(
                f"{min(float(r['primal']) for r in group):.12f}" == low
                and f"{max(float(r['dual']) for r in group):.12f}" == high,
                "partial_cross_run_bounds:" + alias,
            )
        return []
    except (OSError, KeyError, ValueError, IndexError, TypeError) as error:
        return ["partial_cpu_invalid:" + str(error)]


def table(headers, rows, caption, identity, small=False):
    raw = (
        "| "
        + " | ".join(headers)
        + " |\n| "
        + " | ".join("---" for _ in headers)
        + " |\n"
    )
    raw += "\n".join("| " + " | ".join(map(str, row)) + " |" for row in rows)
    raw += "\n\n: " + caption + " {#" + identity + "}\n"
    if small:
        fence = chr(96) * 3
        raw = (
            fence
            + "{=latex}\n\\begingroup\n\\small\n"
            + fence
            + "\n\n"
            + raw
            + "\n"
            + fence
            + "{=latex}\n\\endgroup\n"
            + fence
            + "\n"
        )
    return raw


def build(manuscript=None):
    manuscript = manuscript or ROOT / "manuscript"
    sources = load_sources(manuscript.parent)
    rows = sources["cells.csv"]
    tables, figures = manuscript / "tables", manuscript / "figures"
    tables.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    m0_rows = []
    m7_rows = []
    for cap in (1, 2, 4, 8, 16):
        group = {
            r["presentation"]: r
            for r in rows
            if r["alias"] == "M0" and int(r["threads"]) == cap
        }
        times = [threshold(sources, group[m]["job_id"]) for m in ("B", "R", "G")]
        m0_rows.append(
            [
                cap,
                *[f"{float(t['observed_seconds']) / 60:.2f}" for t in times],
                f"{time_ratio(times[0], times[2]):.3f}",
                f"{time_ratio(times[1], times[2]):.3f}",
            ]
        )
        group = {
            r["presentation"]: r
            for r in rows
            if r["alias"] == "M7" and int(r["threads"]) == cap
        }
        m7_rows.append(
            [
                cap,
                *[
                    f"{100 * float(group[m]['gap_fraction']):.6f}"
                    + (" C" if group[m]["right_censored"] == "True" else "")
                    for m in ("B", "R", "G")
                ],
            ]
        )
    (tables / "partial_cpu_m0.qmd").write_text(
        table(
            ["Threads", "B (min)", "R (min)", "G (min)", "B/G", "R/G"],
            m0_rows,
            "M0: first observed reported gap at most 0.01%; conditional time ratios.",
            "tbl-partial-cpu-m0",
        ),
        encoding="utf-8",
    )
    (tables / "partial_cpu_m7.qmd").write_text(
        table(
            ["Threads", "B gap (%)", "R gap (%)", "G gap (%)"],
            m7_rows,
            "M7: terminal reported gaps. C denotes terminal-target censoring.",
            "tbl-partial-cpu-m7",
        ),
        encoding="utf-8",
    )
    all_rows = [
        [
            r["alias"],
            r["threads"],
            r["presentation"],
            f"{float(r['runtime_seconds']):.2f}",
            f"{float(r['primal']):.8f}",
            f"{float(r['dual']):.8f}",
            f"{100 * float(r['gap_fraction']):.6f}",
            "C" if r["right_censored"] == "True" else "Attained",
        ]
        for r in rows
    ]
    (tables / "partial_cpu_all.qmd").write_text(
        table(
            [
                "Instance",
                "Threads",
                "Method",
                "Runtime (s)",
                "Primal",
                "Dual",
                "Gap (%)",
                "Target",
            ],
            all_rows,
            "All 50 received terminal records. M4/M12 retain numerical restrictions; no exact certificates are asserted.",
            "tbl-partial-cpu-all",
            small=True,
        ),
        encoding="utf-8",
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": "cfl-partial-cpu-20261031",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.1), layout="constrained")
    caps = [1, 2, 4, 8, 16]
    for method, color in (("B", "#56616D"), ("R", "#CF792A"), ("G", "#007F98")):
        times = [
            float(
                threshold(
                    sources,
                    next(
                        r["job_id"]
                        for r in rows
                        if r["alias"] == "M0"
                        and int(r["threads"]) == cap
                        and r["presentation"] == method
                    ),
                )["observed_seconds"]
            )
            / 60
            for cap in caps
        ]
        axes[0].plot(caps, times, "o-", color=color, label=method, lw=1.3, markersize=3)
        g7 = [
            next(
                r
                for r in rows
                if r["alias"] == "M7"
                and int(r["threads"]) == cap
                and r["presentation"] == method
            )
            for cap in caps
        ]
        gaps = [100 * float(r["gap_fraction"]) for r in g7]
        axes[1].plot(caps, gaps, color=color, lw=1.1)
        for cap, gap, r in zip(caps, gaps, g7):
            axes[1].scatter(
                cap,
                gap,
                color=color,
                s=22,
                marker="x" if r["right_censored"] == "True" else "o",
            )
    for ax in axes:
        ax.set_xscale("log", base=2)
        ax.set_xticks(caps, labels=list(map(str, caps)))
        ax.set_xlabel("Physical-thread cap")
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_title("M0: first observed gap ≤ 0.01%", loc="left", fontsize=9)
    axes[0].set_ylabel("Observed time (min)")
    axes[0].set_ylim(bottom=0)
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].set_title("M7: terminal reported gap", loc="left", fontsize=9)
    axes[1].set_ylabel("Gap (%)")
    axes[1].set_ylim(-0.25, 10)
    axes[1].text(
        0.98,
        0.98,
        "×: 12 h limit; ●: criterion",
        ha="right",
        va="top",
        transform=axes[1].transAxes,
        fontsize=7,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.95},
    )
    for suffix in ("pdf", "svg", "png"):
        options = {"dpi": 220}
        if suffix == "pdf":
            options["metadata"] = {"CreationDate": None, "ModDate": None}
        if suffix == "svg":
            options["metadata"] = {"Date": None}
        fig.savefig(figures / (FIGURE + "." + suffix), **options)
    plt.close(fig)
    outputs = [tables / (n + ".qmd") for n in TABLES] + [
        figures / (FIGURE + "." + ext) for ext in ("pdf", "svg", "png")
    ]
    receipt = {
        "kind": "partial_descriptive_assets",
        "manifest_sha256": MANIFEST_SHA,
        "received_cells": 50,
        "planned_cells": 60,
        "research_execution_performed": False,
        "scientific_reporting_eligible": False,
        "outputs": {
            p.relative_to(manuscript).as_posix(): digest(p.read_bytes())
            for p in outputs
        },
    }
    (tables / "partial_cpu_assets.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def check_outputs(manuscript, output):
    try:
        record = json.loads((output / "tables/partial_cpu_assets.json").read_text())
        require(
            record["manifest_sha256"] == MANIFEST_SHA
            and record["received_cells"] == 50
            and record["planned_cells"] == 60
            and record["research_execution_performed"] is False
            and record["scientific_reporting_eligible"] is False,
            "partial_asset_scope",
        )
        require(len(record["outputs"]) == 6, "partial_asset_count")
        for name, expected in record["outputs"].items():
            path = output / name
            require(
                path.resolve().is_relative_to(output.resolve())
                and not path.is_symlink(),
                "partial_asset_path",
            )
            require(digest(path.read_bytes()) == expected, "partial_asset_hash:" + name)
        return []
    except (OSError, KeyError, ValueError, TypeError) as error:
        return ["partial_cpu_output_invalid:" + str(error)]


if __name__ == "__main__":
    build()
