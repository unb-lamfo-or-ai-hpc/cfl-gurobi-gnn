"""Publication figures from reviewed CSVs; optional Matplotlib, no solver/HPC."""

import argparse
import csv
import io
import json
import math
import platform
import statistics as stats
from pathlib import Path

import review_pr86_final as review

COLORS = {"M0": "#365f9a", "M1": "#c47720", "M2": "#16836b"}
NAMES = (
    "easy_paired_ratios",
    "easy_cpu_scaling",
    "medium_terminal_gap",
    "sampled_memory_cpu",
    "preparation_cost_sensitivity",
    "one_thread_repeatability",
)


def table(directory, name):
    return list(
        csv.DictReader(io.StringIO((directory / name).read_text(encoding="utf-8")))
    )


def figures(directory):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    q = review.q
    manifest = json.loads(q.read(directory / "manifest.json"))
    for name, digest in manifest["outputs"].items():
        q.require(q.digest(q.read(directory / name)) == digest, "figure_input_hash")
    plt.rcParams.update(
        {
            "font.size": 10,
            "font.family": "DejaVu Sans",
            "svg.hashsalt": "pr86-final210",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    rows = review.read_csv(q.read(directory / "campaign_results.csv"))
    paired = table(directory, "paired_uncertainty.csv")
    effects = table(directory, "paired_parent_effects.csv")
    caps = review.CAPS
    sources = (
        "campaign_results.csv",
        "paired_uncertainty.csv",
        "paired_parent_effects.csv",
        "easy_cpu_scaling.csv",
        "paired_seed_repeatability.csv",
        "cost_scenarios.csv",
    )
    assets = {}

    def finish(fig, name, title, note):
        fig.suptitle(title, fontsize=14)
        fig.text(0.045, 0.025, note, fontsize=9, va="bottom")
        fig.tight_layout(rect=(0.015, 0.14, 0.99, 0.92))
        for ext in ("svg", "png", "pdf"):
            metadata = (
                {"CreationDate": None, "ModDate": None}
                if ext == "pdf"
                else {"Date": None}
                if ext == "svg"
                else {}
            )
            path = directory / f"{name}.{ext}"
            # Deterministic generation in memory, never overwrite a different asset.
            stream = io.BytesIO()
            fig.savefig(stream, format=ext, dpi=180, metadata=metadata)
            raw = stream.getvalue()
            if ext == "svg":
                raw = b"\n".join(line.rstrip() for line in raw.splitlines()) + b"\n"
            if path.exists():
                q.require(q.read(path) == raw, "preserve_figure")
            else:
                with path.open("xb") as handle:
                    handle.write(raw)
            assets[path.name] = q.digest(raw)
        plt.close(fig)

    def axis(ax):
        ax.set_xticks(range(5), caps)
        ax.set_xlabel("Límite de hilos físicos")
        ax.grid(axis="y", alpha=0.22)

    fig, axes = plt.subplots(1, 3, figsize=(13, 5.4))
    for ax, (num, den) in zip(axes, review.COMPARISONS):
        chosen = [
            next(
                r
                for r in paired
                if r["threads"] == str(cap)
                and r["seed_scope"] == "seed42"
                and r["numerator"] == num
                and r["denominator"] == den
                and r["metric"] == "solver_seconds"
            )
            for cap in caps
        ]
        point = [float(r["geometric_mean_ratio"]) for r in chosen]
        ax.errorbar(
            range(5),
            point,
            yerr=[
                [
                    p - float(r["bootstrap_percentile_lower_95"])
                    for p, r in zip(point, chosen)
                ],
                [
                    float(r["bootstrap_percentile_upper_95"]) - p
                    for p, r in zip(point, chosen)
                ],
            ],
            color=COLORS[num],
            marker="o",
            capsize=4,
        )
        for cap in caps:
            observed = [
                float(r["ratio"])
                for r in effects
                if r["threads"] == str(cap)
                and r["numerator"] == num
                and r["denominator"] == den
                and r["metric"] == "solver_seconds"
            ]
            ax.scatter(
                [caps.index(cap)] * len(observed),
                observed,
                color=COLORS[num],
                alpha=0.25,
                s=16,
            )
        ax.axhline(1, color="0.35", ls="--", lw=1)
        ax.set_title(f"{num} / {den}")
        ax.set_ylabel("Razón de tiempo terminal del solver")
        ax.set_yscale("log")
        axis(ax)
    finish(
        fig,
        NAMES[0],
        "Seis fáciles: efectos pareados e incertidumbre exploratoria",
        "Seed42; menor que 1 favorece al numerador. Puntos tenues: padres; barras: percentiles bootstrap95% puntuales.\nRemuestreo de seis padres completos; modelo de intercambiabilidad, sin cobertura poblacional ni control de multiplicidad.",
    )

    scaling = table(directory, "easy_cpu_scaling.csv")
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    for method in COLORS:
        value = [
            math.exp(
                stats.mean(
                    math.log(float(r["own_one_thread_speedup"]))
                    for r in scaling
                    if r["method"] == method and r["threads"] == str(cap)
                )
            )
            for cap in caps
        ]
        ax.plot(range(5), value, marker="o", color=COLORS[method], label=method)
    ax.axhline(1, color="0.4", ls="--")
    axis(ax)
    ax.set_ylabel("Media geométrica de T(1 hilo) / T(c hilos)")
    ax.legend(title="Método")
    finish(
        fig,
        NAMES[1],
        "Escalado CPU respecto al mismo método con un hilo",
        "Seis fáciles, seed42; cada método usa su propia referencia. No confundir con M2/M0.\nMayor que 1 indica menor tiempo que con un hilo; no es evidencia de escalado GPU ni generalización independiente.",
    )

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.6))
    for ax, alias in zip(axes.flat, ("M0", "M4", "M7", "M12")):
        sensitive = alias in ("M4", "M12")
        for method in COLORS:
            selected = [
                next(
                    r
                    for r in rows
                    if r["alias"] == alias
                    and r["method"] == method
                    and r["threads"] == cap
                    and r["seed"] == 42
                )
                for cap in caps
            ]
            ax.plot(
                range(5),
                [r["gap_fraction"] * 100 for r in selected],
                color=COLORS[method],
                label=f"Método {method}",
            )
            for x, row in enumerate(selected):
                ax.scatter(
                    x,
                    row["gap_fraction"] * 100,
                    edgecolor=COLORS[method],
                    facecolor="white" if row["right_censored"] else COLORS[method],
                    s=42,
                    zorder=3,
                )
        ax.axhline(0.01, color="0.4", ls=":", lw=1)
        ax.set_ylim(bottom=-0.5)
        ax.set_title(
            f"Padre {alias}" + (" — sensible a tolerancias" if sensitive else ""),
            fontsize=11,
        )
        ax.set_ylabel("Brecha terminal informada (%)")
        axis(ax)
    axes[0, 0].legend(fontsize=8)
    finish(
        fig,
        NAMES[2],
        "Medios: calidad terminal, censura y alcance numérico",
        "Seed42; círculos vacíos: tiempo censurado; llenos: objetivo informado. La línea punteada es 0,01%.\nM4/M12 se conservan aparte: no certifican óptimo exacto ni speedup. Calidad al terminar, no al horizonte exacto de3.600s.",
    )

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.5))
    for ax, prefix, title in zip(axes, ("F", "M"), ("Seis fáciles", "Cuatro medios")):
        for method in COLORS:
            groups = [
                [
                    r["sampled_cgroup_peak_bytes"] / 2**30
                    for r in rows
                    if r["alias"].startswith(prefix)
                    and r["method"] == method
                    and r["threads"] == cap
                    and r["seed"] == 42
                ]
                for cap in caps
            ]
            ax.plot(
                range(5),
                [stats.median(group) for group in groups],
                color=COLORS[method],
                marker="o",
                label=method,
            )
            for x, group in enumerate(groups):
                ax.scatter(
                    [x] * len(group), group, color=COLORS[method], alpha=0.25, s=15
                )
        ax.axhline(56, color="#ad4b34", ls="--", lw=1)
        ax.axhline(64, color="0.4", ls=":", lw=1)
        ax.set_ylim(0, 68)
        ax.set_title(title)
        ax.set_ylabel("Máximo muestreado de RAM del cgroup (GiB)")
        axis(ax)
    axes[0].legend()
    finish(
        fig,
        NAMES[3],
        "Memoria observada por límite de hilos",
        "Seed42; líneas: medianas por método; puntos: padres. Referencias: parada muestreada56GiB y techo kernel64GiB.\nIncluyeM4/M12 solo como observaciones de recursos; no equivale a SlurmMaxRSS, memoriaGPU ni pico continuo garantizado.",
    )

    fig, axes = plt.subplots(1, 3, figsize=(13, 5.7))
    metric_labels = (
        "Solver",
        "Frío delimitado",
        "Amortizado delimitado/7",
        "Frío con reparto ampliado",
        "Amortizado con reparto/7",
    )
    metric_colors = ("#365f9a", "#c47720", "#16836b", "#b44242", "#7a5a91")
    for ax, (num, den) in zip(axes, review.COMPARISONS):
        for metric, label, color in zip(review.METRICS, metric_labels, metric_colors):
            selected = [
                next(
                    r
                    for r in paired
                    if r["seed_scope"] == "seed42"
                    and r["threads"] == str(cap)
                    and r["numerator"] == num
                    and r["denominator"] == den
                    and r["metric"] == metric
                )
                for cap in caps
            ]
            ax.plot(
                range(5),
                [float(r["geometric_mean_ratio"]) for r in selected],
                marker="o",
                ms=3,
                color=color,
                label=label,
            )
        ax.axhline(1, color="0.4", ls="--")
        ax.set_title(f"{num} / {den}")
        ax.set_ylabel("Razón de coste temporal")
        axis(ax)
    axes[1].legend(fontsize=7, loc="upper right")
    finish(
        fig,
        NAMES[4],
        "El reparto de la preparación modifica el beneficio observado",
        "Seis fáciles, seed42. Escenarios: tentativa supervisada + preparación asignada, una vez o amortizada en siete usos.\nReparto ampliado incluye overhead observado asignado; no es medición independiente de un trabajo frío completo.",
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.7))
    aliases = list(dict.fromkeys(r["alias"] for r in rows))
    easy = [a for a in aliases if a.startswith("F")]
    for num, den in review.COMPARISONS:
        color = {
            ("M1", "M0"): "#c47720",
            ("M2", "M0"): "#16836b",
            ("M2", "M1"): "#7a5a91",
        }[num, den]
        for seed, marker, offset in ((42, "o", -0.14), (43, "s", 0), (44, "^", 0.14)):
            ratios = []
            for alias in easy:
                a, b = (
                    next(
                        r
                        for r in rows
                        if r["alias"] == alias
                        and r["threads"] == 1
                        and r["seed"] == seed
                        and r["method"] == m
                    )
                    for m in (num, den)
                )
                ratios.append(a["solver_seconds"] / b["solver_seconds"])
            axes[0].scatter(
                [i + offset for i in range(6)],
                ratios,
                marker=marker,
                color=color,
                s=28,
                label=f"{num}/{den}" if seed == 42 else None,
            )
    axes[0].axhline(1, color="0.4", ls="--")
    axes[0].set_xticks(range(6), easy)
    axes[0].set_ylabel("Razón pareada de tiempo del solver")
    axes[0].set_title("Fáciles: efectos por padre y seed")
    medium = [a for a in aliases if a.startswith("M")]
    for method, offset in zip(COLORS, (-0.20, 0, 0.20)):
        for i, alias in enumerate(medium):
            selected = [
                r
                for r in rows
                if r["alias"] == alias and r["threads"] == 1 and r["method"] == method
            ]
            for seed, marker in ((42, "o"), (43, "s"), (44, "^")):
                row = next(r for r in selected if r["seed"] == seed)
                axes[1].scatter(
                    i + offset,
                    row["gap_fraction"] * 100,
                    marker=marker,
                    edgecolor=COLORS[method],
                    facecolor="white" if row["right_censored"] else COLORS[method],
                    label=method if i == 0 and seed == 42 else None,
                )
    axes[1].set_xticks(range(4), [a + "*" if a in ("M4", "M12") else a for a in medium])
    axes[1].set_ylabel("Brecha terminal informada (%)")
    axes[1].set_title("Medios: calidad, no speedup de timeouts")
    for ax in axes:
        ax.grid(axis="y", alpha=0.2)
        ax.legend(fontsize=8)
    finish(
        fig,
        NAMES[5],
        "Repetibilidad pareada: tres seeds, solo con un hilo",
        "Círculo=42, cuadrado=43, triángulo=44; vacíos en medios: censura. *M4/M12 numéricamente sensibles.\nSon repeticiones anidadas en padres expuestos, no18fáciles independientes ni repetibilidad en todos los límites.",
    )

    figure_manifest = dict(
        renderer="Matplotlib",
        renderer_version=matplotlib.__version__,
        python=platform.python_version(),
        source_manifest_sha256=q.digest(q.read(directory / "manifest.json")),
        inputs={name: q.digest(q.read(directory / name)) for name in sources},
        outputs=assets,
    )
    raw = q.encoded(figure_manifest)
    path = directory / "figure_manifest.json"
    if path.exists():
        q.require(q.read(path) == raw, "preserve_figure_manifest")
    else:
        with path.open("xb") as handle:
            handle.write(raw)
    return {
        "figures": len(NAMES),
        "assets": len(assets),
        "renderer": matplotlib.__version__,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=review.DEST)
    print(json.dumps(figures(parser.parse_args().directory)))
