"""Four publication figures from hash-verified PR87 tables; no training."""

import argparse
import csv
import io
from pathlib import Path

import review_pr87_training_pair as review

NAMES = (
    "training_time_cost",
    "predictive_quality",
    "learning_curves",
    "resource_memory",
)
COLORS = ("#365f9a", "#b86b24")


def table(directory, name):
    return list(
        csv.DictReader(
            io.StringIO((directory / (name + ".csv")).read_text(encoding="utf-8"))
        )
    )


def figures(directory):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    c = review.c
    manifest = c.read(directory / "manifest.json")
    for name, digest in manifest["outputs"].items():
        c.require(c.sha((directory / name).read_bytes()) == digest, "figure_input_hash")
    plt.rcParams.update(
        {
            "font.size": 10,
            "font.family": "DejaVu Sans",
            "svg.hashsalt": "pr87-seed42-pair",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    summary, timing = table(directory, "summary"), table(directory, "timings")
    quality, deltas = table(directory, "aggregates"), table(directory, "deltas")
    history, ranks = table(directory, "history"), table(directory, "ranks")
    assets = {}

    def finish(fig, name, title, note):
        fig.suptitle(title, fontsize=14)
        fig.text(0.04, 0.025, note, fontsize=9, va="bottom")
        fig.tight_layout(rect=(0.015, 0.15, 0.99, 0.92))
        for ext in ("svg", "png", "pdf"):
            stream = io.BytesIO()
            metadata = (
                {"CreationDate": None, "ModDate": None}
                if ext == "pdf"
                else {"Date": None}
                if ext == "svg"
                else {}
            )
            fig.savefig(stream, format=ext, dpi=180, metadata=metadata)
            raw = stream.getvalue()
            if ext == "svg":
                raw = b"\n".join(line.rstrip() for line in raw.splitlines()) + b"\n"
            review.save({name + "." + ext: raw}, directory)
            assets[name + "." + ext] = c.sha(raw)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.3))
    scopes = (
        "training_loop_seconds",
        "training_validation_checkpoint_seconds",
        "job_elapsed_seconds",
    )
    selected = [next(r for r in timing if r["scope"] == scope) for scope in scopes]
    for i, label in enumerate(("Serial 1 GPU", "DDP4")):
        values = [
            float(row[("serial_seconds", "ddp4_seconds")[i]]) / 60 for row in selected
        ]
        bars = axes[0].bar(
            [x + (i - 0.5) * 0.34 for x in range(3)],
            values,
            width=0.34,
            color=COLORS[i],
            label=label,
        )
        axes[0].bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    axes[0].set_xticks(range(3), ("Lazo", "Entr. + valid.\n+ checkpoint", "Job Slurm"))
    axes[0].set_ylabel("Minutos")
    axes[0].set_ylim(0, 40)
    axes[0].legend(frameon=False)
    axes[0].grid(axis="y", alpha=0.2)
    bars = axes[1].bar(
        ("Serial 1 GPU", "DDP4"),
        [float(r["allocated_gpu_hours"]) for r in summary],
        color=COLORS,
    )
    axes[1].bar_label(bars, fmt="%.3f", padding=4)
    axes[1].set_ylabel("GPU-h asignadas (GPUs x elapsed Slurm)")
    axes[1].set_ylim(0, 1.5)
    axes[1].grid(axis="y", alpha=0.2)
    finish(
        fig,
        "training_time_cost",
        "Tiempo y coste de asignación: mismo trabajo de aprendizaje",
        "Seed42: una pareja. Aceleración: lazo 2,167x; job 1,831x. Las regiones de tiempo están anidadas, no se suman.\n"
        "1/4 GPUs acompañadas de 4/16 núcleos físicos. GPU-h asignadas no equivalen a tiempo GPU activo ni a energía.",
    )

    fig, axes = plt.subplots(1, 3, figsize=(14, 5.4))
    for ax, metric, title in zip(
        axes[:2], ("f1_score", "pr_auc"), ("F1 por padre", "PR-AUC por padre")
    ):
        rows = sorted(
            [
                r
                for r in deltas
                if r["metric"] == metric and r["checkpoint"] == "selected"
            ],
            key=lambda r: (r["difficulty"] != "easy", int(r["alias"][1:])),
        )
        ax.bar(
            [r["alias"] for r in rows],
            [float(r["ddp4_minus_serial"]) for r in rows],
            color=["#365f9a" if r["difficulty"] == "easy" else "#b86b24" for r in rows],
        )
        ax.axhline(0, color="#333333", linewidth=0.8)
        ax.axhline(-0.02, color="#b12626", linestyle="--", label="Margen -0,02")
        ax.set_title(title)
        ax.set_ylabel("DDP4 - serial (seleccionado)")
        ax.tick_params(axis="x", rotation=55)
        ax.legend(frameon=False, fontsize=8)
        ax.grid(axis="y", alpha=0.2)
    categories = [
        ("selected", "f1_score"),
        ("selected", "pr_auc"),
        ("terminal", "f1_score"),
        ("terminal", "pr_auc"),
    ]
    for i, arm in enumerate(("serial1", "ddp4")):
        values = [
            float(
                next(
                    r
                    for r in quality
                    if r["arm"] == arm
                    and r["checkpoint"] == which
                    and r["scope"] == "all"
                    and r["averaging"] == "parent_macro"
                )[metric]
            )
            for which, metric in categories
        ]
        axes[2].bar(
            [x + (i - 0.5) * 0.34 for x in range(4)],
            values,
            0.34,
            color=COLORS[i],
            label=("Serial", "DDP4")[i],
        )
    axes[2].set_xticks(
        range(4), ("F1\nsel.", "PR-AUC\nsel.", "F1\nterm.", "PR-AUC\nterm.")
    )
    axes[2].set_ylim(0, 1)
    axes[2].set_ylabel("Media por padre (10 padres)")
    axes[2].legend(frameon=False)
    finish(
        fig,
        "predictive_quality",
        "Calidad predictiva: aceleración con pérdida de F1",
        "Seleccionados solo por validación: F1 macro 0,7231 vs 0,6906; diferencia -0,03247, supera la pérdida descriptiva 0,02.\n"
        "PR-AUC trapezoidal, no average precision. Diez padres expuestos históricamente; una seed, sin no-inferioridad estadística.",
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.3))
    for i, arm in enumerate(("serial1", "ddp4")):
        rows = [r for r in history if r["arm"] == arm]
        for ax, metric in zip(axes, ("train_loss", "validation_loss")):
            ax.plot(
                [int(r["epoch"]) for r in rows],
                [float(r[metric]) for r in rows],
                color=COLORS[i],
                label=("Serial 1 GPU", "DDP4")[i],
                linewidth=1.2,
            )
            ax.set_yscale("log")
            ax.set_xlabel("Época")
            ax.set_ylabel("BCE ponderada (escala logarítmica)")
            ax.grid(alpha=0.2)
        best = int(summary[i]["selected_epoch"])
        axes[1].scatter(
            [best],
            [float(summary[i]["selected_validation_loss"])],
            color=COLORS[i],
            s=40,
            zorder=3,
        )
    axes[0].set_title("Entrenamiento")
    axes[1].set_title("Validación: seleccionados en épocas 99 y 92")
    axes[0].legend(frameon=False)
    finish(
        fig,
        "learning_curves",
        "Trayectorias registradas de los dos entrenamientos completos",
        "100 épocas, 3.400 actualizaciones y 13.600 presentaciones globales por brazo. Estado inicial y schedule coinciden por hash.\n"
        "Trayectorias finales distintas; causa numérica concreta no demostrada. No se ajusta ni repite para mejorar el resultado.",
    )

    fig, axes = plt.subplots(1, 3, figsize=(14, 5.4))
    for i, metric in enumerate(("slurm_batch_maxrss_gib", "sampled_cgroup_peak_gib")):
        bars = axes[0].bar(
            [x + (i - 0.5) * 0.34 for x in range(2)],
            [float(r[metric]) for r in summary],
            0.34,
            label=("Slurm MaxRSS batch", "Cgroup muestreado")[i],
            color=("#777777", "#517f65")[i],
        )
        axes[0].bar_label(bars, fmt="%.2f", fontsize=8, padding=3)
    axes[0].set_xticks(range(2), ("Serial", "DDP4"))
    axes[0].set_ylabel("RAM host (GiB)")
    axes[0].set_ylim(0, 20)
    axes[0].legend(frameon=False, fontsize=8)
    labels = [("S" if r["arm"] == "serial1" else "D") + r["rank"] for r in ranks]
    for i, metric in enumerate(("gpu_allocated_peak_gib", "gpu_reserved_peak_gib")):
        axes[1].bar(
            [x + (i - 0.5) * 0.34 for x in range(5)],
            [float(r[metric]) for r in ranks],
            0.34,
            color=("#365f9a", "#9cafd0")[i],
            label=("Asignado", "Reservado")[i],
        )
    axes[1].set_xticks(range(5), labels)
    axes[1].set_ylabel("Alocador GPU por rank (GiB)")
    axes[1].set_ylim(0, 10)
    axes[1].legend(frameon=False, fontsize=8)
    axes[2].bar(
        labels,
        [float(r["gpu_utilization_sample_mean_pct"]) for r in ranks],
        color=[COLORS[0]] + [COLORS[1]] * 4,
    )
    axes[2].set_ylabel("Utilización GPU muestreada (%)")
    axes[2].set_ylim(0, 100)
    for ax in axes:
        ax.grid(axis="y", alpha=0.2)
    finish(
        fig,
        "resource_memory",
        "Recursos: conservar los distintos alcances de medición",
        "S0: serial/rank0; D0-D3: ranks DDP. RSS y cgroup no son equivalentes. Alocador: máximo hasta final de train/validación.\n"
        "Telemetría de dispositivos cada 5s: 400/218 muestras, sin consultas ausentes; no implica exclusividad ni máximo continuo.",
    )
    review.save(
        {
            "figures_manifest.json": review.encoded(
                {
                    "source_return_sha256": review.SHA,
                    "analysis_manifest_sha256": c.sha(
                        (directory / "manifest.json").read_bytes()
                    ),
                    "generator": "scripts/evidence/plot_pr87_training_pair.py",
                    "matplotlib": matplotlib.__version__,
                    "outputs": assets,
                }
            )
        },
        directory,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=review.DEST)
    args = parser.parse_args()
    figures(args.directory)


if __name__ == "__main__":
    main()
