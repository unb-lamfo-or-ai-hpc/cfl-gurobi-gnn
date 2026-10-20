"""Publication-only BCE curves from the reviewed pair; no HPC or model loading."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from pathlib import Path

import review_pr87_training_pair as review

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("docs/evidence/pr87/jobs3673-3674")
DEST = Path("docs/evidence/pr88/gpu")
ARTICLE = Path("manuscript/figures")
STEM = "gpu_bce_by_epoch"
ARTICLE_STEM = "gpu_bce_by_epoch_article_en"


def data(root=ROOT):
    source = root / SOURCE
    expected = review.products((source / "public_return.json").read_bytes())
    for name, raw in expected.items():
        if (source / name).read_bytes() != raw:
            raise ValueError("reviewed_source_changed:" + name)
    history = list(csv.DictReader(io.StringIO(expected["history.csv"].decode())))
    summary = list(csv.DictReader(io.StringIO(expected["summary.csv"].decode())))
    arms = {}
    for info in summary:
        rows = [r for r in history if r["arm"] == info["arm"]]
        assert [int(r["epoch"]) for r in rows] == list(range(1, 101))
        curves = {
            key: [float(r[key]) for r in rows]
            for key in ("train_loss", "validation_loss")
        }
        assert all(math.isfinite(x) and x > 0 for xs in curves.values() for x in xs)
        best = min(range(100), key=curves["validation_loss"].__getitem__)
        assert best + 1 == int(info["selected_epoch"])
        arms[info["arm"]] = {
            "job_id": info["job_id"],
            "epochs": list(range(1, 101)),
            **curves,
            "selected_epoch": best + 1,
            "selected_validation_loss": curves["validation_loss"][best],
        }
    return {
        "source_return_sha256": review.SHA,
        "loss": "BCEWithLogitsLoss, positive weight 1132.975830078125",
        "training_aggregation": "mean of 136 per-graph losses during updates",
        "validation_aggregation": "mean of ten per-parent losses after each epoch",
        "smoothing_or_interpolation": False,
        "seed": 42,
        "global_batch": 4,
        "global_presentations_per_arm": 13600,
        "optimizer_updates_per_arm": 3400,
        "arms": arms,
    }


def write_identical(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("preserve_existing_output:" + str(path))
    else:
        with path.open("xb") as stream:
            stream.write(raw)


def render(root=ROOT):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    value = data(root)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": "pr88-matched-seed42-bce-v1",
            "pdf.fonttype": 42,
        }
    )
    outputs = {}
    for lang in ("es", "en"):
        es = lang == "es"
        fig, axes = plt.subplots(
            1, 2, figsize=(11.8, 5.0) if es else (7.6, 3.4), sharey=True
        )
        labels = ("Serial: 1 GPU", "DDP: 4 GPUs")
        for arm, color, style, label in zip(
            ("serial1", "ddp4"), ("#214e78", "#c05b24"), ("-", "--"), labels
        ):
            obs = value["arms"][arm]
            for ax, key in zip(axes, ("train_loss", "validation_loss")):
                ax.plot(
                    obs["epochs"],
                    obs[key],
                    color=color,
                    linestyle=style,
                    linewidth=1.5,
                    label=label,
                )
            best, minimum = obs["selected_epoch"], obs["selected_validation_loss"]
            axes[1].scatter(
                best,
                minimum,
                color=color,
                s=55,
                marker="o",
                zorder=4,
                edgecolors="white",
                linewidths=0.7,
            )
            suffix = f"{minimum:.4f}".replace(".", ",") if es else f"{minimum:.4f}"
            axes[1].annotate(
                f"{label}\n{'Época' if es else 'Epoch'} {best}: {suffix}",
                (best, minimum),
                xytext=(
                    40 if arm == "serial1" else 8,
                    0.10 if arm == "serial1" else 0.21,
                ),
                textcoords="data",
                fontsize=8.5 if es else 7,
                color=color,
                arrowprops={"arrowstyle": "-", "color": color, "lw": 0.8},
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9},
            )
        for ax, title in zip(
            axes, ("Entrenamiento", "Validación") if es else ("Training", "Validation")
        ):
            ax.set_title(
                title, loc="left", fontsize=12 if es else 10, fontweight="bold", pad=12
            )
            ax.set_yscale("log")
            ax.set_xlim(1, 101)
            ax.set_ylim(0.02, 2.2)
            ax.set_yticks((0.02, 0.05, 0.1, 0.2, 0.5, 1, 2))
            ax.yaxis.set_major_formatter(
                FuncFormatter(
                    lambda x, _: f"{x:g}".replace(".", ",") if es else f"{x:g}"
                )
            )
            ax.set_xlabel("Época del protocolo" if es else "Protocol epoch")
            ax.grid(axis="y", which="major", alpha=0.2)
            ax.legend(loc="upper right", frameon=False, fontsize=9 if es else 8)
        axes[0].set_ylabel(
            "BCE ponderada (escala logarítmica)" if es else "Weighted BCE (log scale)"
        )
        fig.suptitle(
            "Aprendizaje equivalente: serial 1 GPU frente a DDP4"
            if es
            else "Matched learning work: serial 1 GPU versus DDP4",
            x=0.07,
            ha="left",
            fontsize=15,
            fontweight="bold",
            y=0.98,
        )
        fig.text(
            0.07,
            0.895,
            "Seed 42 | 100 épocas | 13.600 presentaciones | 3.400 actualizaciones por brazo"
            if es
            else "Seed 42 | 100 epochs | 13,600 presentations | 3,400 updates per arm",
            fontsize=10,
            color="#444444",
        )
        footer = (
            "Menor BCE indica menor pérdida; no equivale a mayor F1. Puntos: mínimos de validación (épocas 99 y 92).\n"
            "Curvas originales, sin suavizado. Una seed; diez padres de validación. Jobs 3673/3674, recibo 909f6ce85dfd."
            if es
            else "Lower BCE means lower loss, not necessarily higher F1. Dots: validation minima (epochs 99 and 92).\n"
            "Unsmoothed observations. One seed; ten validation parents. Jobs 3673/3674, receipt 909f6ce85dfd."
        )
        fig.text(0.07, 0.035, footer, fontsize=9, linespacing=1.5)
        fig.subplots_adjust(left=0.075, right=0.98, top=0.79, bottom=0.22, wspace=0.15)
        if not es:
            # At article width, caption/body carry work and scope; avoid shrinking
            # presentation-sized text into unreadable in-paper annotations.
            for text in list(fig.texts):
                text.remove()
            fig.subplots_adjust(
                left=0.10, right=0.98, top=0.86, bottom=0.19, wspace=0.15
            )
        directory = DEST if es else ARTICLE
        for ext in ("pdf", "svg", "png"):
            buffer = io.BytesIO()
            metadata = (
                {"CreationDate": None, "ModDate": None}
                if ext == "pdf"
                else {"Date": None}
                if ext == "svg"
                else {"Software": "PR88 BCE"}
            )
            fig.savefig(buffer, format=ext, dpi=240, metadata=metadata)
            name = directory / (f"{STEM}_es.{ext}" if es else f"{ARTICLE_STEM}.{ext}")
            write_identical(root / name, buffer.getvalue())
            outputs[name.as_posix()] = review.c.sha(buffer.getvalue())
        plt.close(fig)
    encoded = review.encoded(value)
    write_identical(root / DEST / "curves.json", encoded)
    outputs[(DEST / "curves.json").as_posix()] = review.c.sha(encoded)
    manifest = {
        "source_return_sha256": review.SHA,
        "sources": {
            str(SOURCE / n).replace("\\", "/"): review.c.sha(
                (root / SOURCE / n).read_bytes()
            )
            for n in ("public_return.json", "history.csv", "summary.csv")
        },
        "generator": "scripts/evidence/plot_pr88_gpu_bce.py",
        "matplotlib_version": matplotlib.__version__,
        "outputs": outputs,
        "training_runs_added": 0,
        "optimization_runs_added": 0,
        "original_scientific_flag_unchanged": True,
    }
    write_identical(root / DEST / "manifest.json", review.encoded(manifest))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(render(), indent=2))
