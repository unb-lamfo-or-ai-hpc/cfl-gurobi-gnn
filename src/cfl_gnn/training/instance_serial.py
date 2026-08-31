"""Serial Gasse training for the audited Gurobi parent-instance baseline."""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Sequence

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.instance_plan import (
    InstanceTrainingPlan,
    build_instance_training_plan,
    write_instance_training_plan,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train Gasse serially on audited parent-instance graphs without "
            "reusing the incumbent-conditioned random split."
        )
    )
    parser.add_argument("--base_pyg_dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rotation", type=int, choices=range(5), default=0)
    parser.add_argument(
        "--label_policy",
        choices=("optimal_only", "all_available"),
        default="optimal_only",
    )
    parser.add_argument(
        "--development_only",
        action="store_true",
        help=(
            "Permit a partial inventory or non-optimal labels. Outputs from "
            "such a run are not eligible for scientific reporting."
        ),
    )
    parser.add_argument("--experiment_name", default="instance_rotation_0")
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--hidden_dim", type=int, default=32)
    parser.add_argument("--num_layers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--grad_clip", type=float, default=1.0)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num_workers", type=int, default=0)
    parser.add_argument("--clear_cache", action="store_true")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser


def _validate_numeric_arguments(args: argparse.Namespace) -> None:
    positive = {
        "hidden_dim": args.hidden_dim,
        "num_layers": args.num_layers,
        "lr": args.lr,
        "epochs": args.epochs,
        "patience": args.patience,
    }
    invalid = [name for name, value in positive.items() if value <= 0]
    if invalid:
        raise ValueError("arguments must be positive: " + ", ".join(invalid))
    if args.grad_clip < 0 or args.num_workers < 0:
        raise ValueError("grad_clip and num_workers must be nonnegative")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.experiment_name):
        raise ValueError(
            "experiment_name must contain only letters, digits, dot, dash, "
            "or underscore"
        )


def _resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir is not None:
        return args.output_dir.resolve()
    return (
        PROJECT_ROOT
        / "data"
        / "models"
        / "instance_baseline"
        / args.experiment_name
    ).resolve()


def _print_plan(plan: InstanceTrainingPlan, report_path: Path) -> None:
    counts = {
        role: len(plan.records_for_role(role))
        for role in ("train", "validation", "test")
    }
    print(
        "[INFO] "
        f"contract={plan.contract_sha256} | "
        f"train={counts['train']} | validation={counts['validation']} | "
        f"test={counts['test']}"
    )
    print(
        "[INFO] "
        f"label_policy={plan.audit.label_policy} | "
        f"development_only={plan.development_only} | "
        f"scientific_reporting_eligible={plan.scientific_reporting_eligible}"
    )
    print("[INFO] test partition is held out and is not loaded during training")
    print(f"[INFO] Plan: {report_path}")


def _select_device(torch_module, requested: str):
    if requested == "cuda" and not torch_module.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    if requested == "auto":
        requested = "cuda" if torch_module.cuda.is_available() else "cpu"
    return torch_module.device(requested)


def _run_training(
    args: argparse.Namespace,
    plan: InstanceTrainingPlan,
    output_dir: Path,
) -> None:
    # Heavy ML imports remain behind the audited, CPU-only planning gate.
    import matplotlib
    import torch
    import torch.nn as nn
    from torch_geometric.loader import DataLoader

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from cfl_gnn.graph.instance_dataset import ParentInstanceDataset
    from cfl_gnn.models.gasse import GasseGNN
    from cfl_gnn.training.serial import (
        calc_metrics,
        compute_pos_weight,
        eval_loop,
        set_global_seed,
        train_loop,
    )

    checkpoint = output_dir / "best_model.pt"
    if checkpoint.exists() and not args.overwrite:
        raise FileExistsError(
            f"checkpoint already exists: {checkpoint}; choose a new experiment "
            "or pass --overwrite explicitly"
        )

    set_global_seed(args.seed)
    device = _select_device(torch, args.device)
    train_data = ParentInstanceDataset(plan.records_for_role("train"))
    validation_data = ParentInstanceDataset(plan.records_for_role("validation"))
    # The test partition is intentionally not instantiated here.
    train_loader = DataLoader(
        train_data,
        batch_size=1,
        shuffle=True,
        num_workers=args.num_workers,
    )
    validation_loader = DataLoader(
        validation_data,
        batch_size=1,
        shuffle=False,
        num_workers=args.num_workers,
    )

    representative = next(iter(train_loader)).to(device)
    edge_store = representative["variable", "rev_coef", "constraint"]
    edge_attr = edge_store.edge_attr
    edge_dim = int(edge_attr.shape[-1]) if edge_attr is not None else 0
    model = GasseGNN(
        var_in_dim=int(representative["variable"].x.shape[-1]),
        cons_in_dim=int(representative["constraint"].x.shape[-1]),
        edge_dim=edge_dim,
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
    ).to(device)
    model.fit_prenorm(
        x_var=representative["variable"].x,
        x_cons=representative["constraint"].x,
        edge_v2c=edge_store.edge_index,
        edge_attr=edge_attr,
    )
    del representative

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    pos_weight = compute_pos_weight(train_loader, device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    history = {
        "train_loss": [],
        "validation_loss": [],
        "accuracy": [],
        "f1": [],
        "precision": [],
        "recall": [],
    }
    best_validation_loss = float("inf")
    best_epoch: dict[str, float | int] = {}
    patience_counter = 0
    log_path = output_dir / "training_log_serial.csv"

    with log_path.open("w", encoding="utf-8") as stream:
        stream.write("epoch,train_loss,val_loss,acc,f1,prec,rec\n")
        for epoch in range(args.epochs):
            train_loss = train_loop(
                model, train_loader, optimizer, loss_fn, device, args
            )
            val_loss, tp, tn, fp, fn = eval_loop(
                model, validation_loader, loss_fn, device, args
            )
            accuracy, precision, recall, f1 = calc_metrics(tp, tn, fp, fn)
            history["train_loss"].append(train_loss)
            history["validation_loss"].append(val_loss)
            history["accuracy"].append(accuracy)
            history["f1"].append(f1)
            history["precision"].append(precision)
            history["recall"].append(recall)
            stream.write(
                f"{epoch + 1},{train_loss},{val_loss},{accuracy},{f1},"
                f"{precision},{recall}\n"
            )
            stream.flush()

            if val_loss < best_validation_loss:
                best_validation_loss = val_loss
                patience_counter = 0
                torch.save(model.state_dict(), checkpoint)
                best_epoch = {
                    "best_epoch": epoch + 1,
                    "validation_loss": val_loss,
                    "accuracy": accuracy,
                    "f1_score": f1,
                    "precision": precision,
                    "recall": recall,
                }
            else:
                patience_counter += 1

            LOGGER.info(
                "epoch=%d train_loss=%.6f validation_loss=%.6f f1=%.6f",
                epoch + 1,
                train_loss,
                val_loss,
                f1,
            )
            if patience_counter >= args.patience:
                LOGGER.info("early stopping at epoch %d", epoch + 1)
                break

    epochs = range(1, len(history["train_loss"]) + 1)
    figure, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes[0, 0].plot(epochs, history["train_loss"], label="Train loss")
    axes[0, 0].plot(epochs, history["validation_loss"], label="Validation loss")
    axes[0, 1].plot(epochs, history["f1"], label="Validation F1")
    axes[1, 0].plot(epochs, history["precision"], label="Precision")
    axes[1, 0].plot(epochs, history["recall"], label="Recall")
    axes[1, 1].plot(epochs, history["accuracy"], label="Accuracy")
    for axis in axes.flat:
        axis.legend()
        axis.grid(alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_dir / "training_dashboard.png", dpi=150)
    plt.close(figure)

    experiment_summary = {
        "experiment_name": args.experiment_name,
        "dataset_variant": "gurobi_parent_instance",
        "contract_sha256": plan.contract_sha256,
        "rotation": plan.audit.rotation,
        "label_policy": plan.audit.label_policy,
        "development_only": plan.development_only,
        "scientific_reporting_eligible": plan.scientific_reporting_eligible,
        "test_partition_usage": "held_out_not_loaded_during_training",
        "hyperparameters": {
            "hidden_dim": args.hidden_dim,
            "num_layers": args.num_layers,
            "learning_rate": args.lr,
            "seed": args.seed,
            "pos_weight": pos_weight.item(),
        },
        "best_epoch_results": best_epoch,
    }
    (output_dir / "experiment_summary.json").write_text(
        json.dumps(experiment_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = build_parser().parse_args(argv)
    _validate_numeric_arguments(args)
    plan = build_instance_training_plan(
        args.base_pyg_dir,
        args.manifest,
        rotation=args.rotation,
        label_policy=args.label_policy,
        development_only=args.development_only,
    )
    output_dir = _resolve_output_dir(args)
    checkpoint = output_dir / "best_model.pt"
    if checkpoint.exists() and not args.dry_run and not args.overwrite:
        raise FileExistsError(
            f"checkpoint already exists: {checkpoint}; choose a new experiment "
            "or pass --overwrite explicitly"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "instance_training_plan.json"
    write_instance_training_plan(report_path, plan)
    _print_plan(plan, report_path)
    if args.dry_run:
        return 0
    _run_training(args, plan, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

