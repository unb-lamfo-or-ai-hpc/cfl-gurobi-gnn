"""Deterministic training-diagnostic figures shared by Gasse runners."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence


def write_training_validation_loss_figure(
    history: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    title: str,
) -> None:
    """Plot training and validation loss together on one SVG axis."""
    if not history:
        raise ValueError("training history is empty")
    epochs = [int(row["epoch"]) for row in history]
    training_loss = [float(row["train_loss"]) for row in history]
    validation_loss = [None if row["validation_loss"] is None else float(row["validation_loss"]) for row in history]
    if not all(math.isfinite(value) for value in training_loss + [v for v in validation_loss if v is not None]):
        raise ValueError("training history contains a non-finite loss")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(
        {
            "svg.fonttype": "none",
            "svg.hashsalt": "cfl-gnn-training-validation-loss-v1",
        }
    ):
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.plot(epochs, training_loss, label="Training loss", linewidth=1.8)
        axis.plot(
            [epoch for epoch, value in zip(epochs, validation_loss) if value is not None],
            [value for value in validation_loss if value is not None],
            label="Validation loss",
            linewidth=1.8,
        )
        axis.set_xlabel("Epoch")
        axis.set_ylabel("Weighted binary cross-entropy")
        axis.set_title(title)
        axis.grid(alpha=0.25)
        axis.legend()
        figure.tight_layout()
        figure.savefig(
            path,
            format="svg",
            metadata={"Date": None, "Creator": "cfl-gurobi-gnn"},
        )
        plt.close(figure)
