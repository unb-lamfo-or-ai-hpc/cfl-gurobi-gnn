"""Descriptive seed42 figures from immutable CSVs; no experiments or interpolation."""

import io
import json
import math

import build_pr88_methodology as m

COLORS = {"M0": "#365f9a", "M1": "#c47720", "M2": "#16836b"}


def rows(name):
    import csv

    return list(
        csv.DictReader(io.StringIO((m.DEST / name).read_text(encoding="utf-8")))
    )


def render():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    m.build(check=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "svg.hashsalt": "pr88-seed42",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )
    assets = {}

    def save(fig, name, note):
        fig.text(0.035, 0.025, note, fontsize=9, va="bottom")
        fig.tight_layout(rect=(0, 0.14, 1, 0.94))
        for ext in ("svg", "pdf", "png"):
            metadata = (
                {"Date": None}
                if ext == "svg"
                else {"CreationDate": None, "ModDate": None}
                if ext == "pdf"
                else {}
            )
            output = io.BytesIO()
            fig.savefig(output, format=ext, metadata=metadata, dpi=150)
            raw = output.getvalue()
            if ext == "svg":
                raw = b"\n".join(line.rstrip() for line in raw.splitlines()) + b"\n"
            path = m.DEST / f"{name}.{ext}"
            if path.exists():
                m.require(path.read_bytes() == raw, "preserve_existing_figure")
            else:
                with path.open("xb") as stream:
                    stream.write(raw)
            assets[path.name] = m.digest(raw)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4.7))
    ax.set_axis_off()
    boxes = [
        (0.02, 0.72, "MILP\nMINIMIZE"),
        (0.23, 0.72, "Raíz LP + grafo\nCoste compartido"),
        (0.47, 0.72, "GNN congelada\nInferencia"),
        (0.72, 0.72, "Selección class-aware\nStart binario parcial"),
        (
            0.72,
            0.2,
            "Gurobi: modelo original\nM0: sin Start externo\nM1: LP emparejado\nM2: GNN",
        ),
    ]
    for x, y, text in boxes:
        ax.text(
            x,
            y,
            text,
            transform=ax.transAxes,
            va="center",
            bbox={
                "boxstyle": "round,pad=.5",
                "facecolor": "#edf3f8",
                "edgecolor": "#365f9a",
            },
        )
    for start, end in [
        ((0.16, 0.72), (0.22, 0.72)),
        ((0.41, 0.72), (0.46, 0.72)),
        ((0.62, 0.72), (0.71, 0.72)),
        ((0.83, 0.59), (0.83, 0.36)),
        ((0.31, 0.59), (0.72, 0.32)),
    ]:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            xycoords="axes fraction",
            arrowprops={"arrowstyle": "->", "color": "#444444"},
        )
    ax.set_title("Mecanismo de orientación y fronteras de coste", pad=14)
    save(
        fig,
        "mechanism",
        "M1 usa soporte/número de unos definidos por M2; no es un baseline LP independiente.\nStart no fija bounds ni restringe la región factible; el solver completa variables indefinidas.",
    )

    pairs = rows("seed42_paired_speedups.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5))
    for ax, comparison in zip(axes, ("M2_vs_M0", "M2_vs_M1")):
        for i, cap in enumerate(m.CAPS):
            selected = [
                r
                for r in pairs
                if r["threads"] == str(cap)
                and r["comparison"] == comparison
                and r["alias"].startswith("F")
                and r["eligible_common_terminal_target"] == "True"
            ]
            values = [float(r["speedup_baseline_over_M2"]) for r in selected]
            ax.scatter([i] * len(values), values, alpha=0.45, color=COLORS["M2"])
            if values:
                ax.scatter(
                    i,
                    math.exp(sum(map(math.log, values)) / len(values)),
                    color="black",
                    marker="D",
                )
        ax.axhline(1, ls="--", color="gray")
        ax.set(
            xticks=range(5),
            xticklabels=m.CAPS,
            xlabel="Límite físico de hilos",
            ylabel="Speedup T_baseline / T_M2",
            title=comparison,
            yscale="log",
        )
    save(
        fig,
        "warm_start_seed42",
        "Seis fáciles expuestos; puntos=padres, rombo=media geométrica descriptiva; >1 favorece M2.\nMedios no representados como speedup: censura/sensibilidad y denominadores en la tabla pareada; no son réplicas independientes.",
    )

    values = rows("seed42_cpu_scaling.csv")
    main = rows("seed42_main.csv")
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.3))
    for method, color in COLORS.items():
        for panel, metric in enumerate(
            ("solver_seconds", "same_method_cpu_speedup", "same_method_cpu_efficiency")
        ):
            data = main if panel == 0 else values
            y = []
            for cap in m.CAPS:
                selected = [
                    float(r[metric])
                    for r in data
                    if r["method"] == method
                    and r["threads"] == str(cap)
                    and r["alias"].startswith("F")
                    and r[metric] != ""
                ]
                y.append(math.exp(sum(map(math.log, selected)) / len(selected)))
            axes[panel].plot(range(5), y, marker="o", color=color, label=method)
    for ax, ylabel in zip(
        axes,
        ("Solver runtime (s)", "CPU speedup T_m(1)/T_m(r)", "CPU efficiency speedup/r"),
    ):
        ax.set(
            xticks=range(5),
            xticklabels=m.CAPS,
            xlabel="Límite físico de hilos",
            ylabel=ylabel,
        )
        ax.legend()
    save(
        fig,
        "cpu_scalability_seed42",
        "Medias geométricas de seis fáciles, seed42; mismo método y criterio terminal.\nNo es aceleración neural, consumo de CPU o escalabilidad GPU; sin intervalos multiseed.",
    )

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    for ax, medium in zip(axes, (False, True)):
        for method, color in COLORS.items():
            for cap in m.CAPS:
                selected = [
                    float(r["sampled_cgroup_peak_bytes"]) / 1024**3
                    for r in main
                    if r["method"] == method
                    and r["threads"] == str(cap)
                    and r["alias"].startswith("M") == medium
                    and r["sampled_cgroup_peak_bytes"] != ""
                ]
                ax.scatter(
                    [m.CAPS.index(cap)] * len(selected),
                    selected,
                    color=color,
                    alpha=0.45,
                    label=method if cap == 1 else None,
                )
        ax.set(
            xticks=range(5),
            xticklabels=m.CAPS,
            xlabel="Límite físico de hilos",
            ylabel="RAM cgroup muestreada (GiB)",
            title="Medias (incluye M4/M12 sensibles)" if medium else "Fáciles",
        )
        ax.legend()
    save(
        fig,
        "sampled_memory_seed42",
        "Diez padres expuestos, seed42; puntos por método/cap/padre, relacionados dentro de un padre.\nPico muestreado del cgroup no equivale a RSS, Slurm MaxRSS, RAM reservada o memoria GPU; no mide utilización CPU.",
    )
    receipt = {
        "data_manifest_sha256": m.digest((m.DEST / "manifest.json").read_bytes()),
        "matplotlib": matplotlib.__version__,
        "assets": assets,
        "experimental_runs_added": 0,
        "historical_figures_modified": False,
    }
    path = m.DEST / "figures_manifest.json"
    raw = m.json_bytes(receipt)
    if path.exists():
        m.require(path.read_bytes() == raw, "preserve_figure_manifest")
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    return receipt


if __name__ == "__main__":
    print(json.dumps(render(), indent=2))
