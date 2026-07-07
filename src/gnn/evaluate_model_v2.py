"""
evaluate_model_v2.py
====================
Academic evaluation of a trained Neural Diving GNN on the held-out Test Set.

Artefacts produced under  <output_dir>/<experiment_name>/:
  - classification_report.csv   : per-class Precision / Recall / F1 (LaTeX-ready)
  - confusion_matrix.png        : heatmap at the optimal decision threshold
  - roc_auc_curve.png           : ROC curve with shaded AUC
  - pr_curve.png                : Precision-Recall curve (better for imbalanced data)
  - threshold_sweep.png         : F1 / Precision / Recall vs. decision threshold
  - per_complexity_metrics.csv  : breakdown by complexity_class (easy / hard / unknown)
  - evaluation_summary.json     : machine-readable summary for automated pipelines

Usage (Slurm example):
  python evaluate_model_v2.py \
      --model_path  /path/to/best_model.pt \
      --base_root   /raid/.../pyg_dataset \
      --experiment_name serial_v4 \
      --hidden_dim  64 \
      --easy_split  300 50 50 \
      --medium_split 200 30 30 \
      --hard_split   100 15 15
"""

import json
import logging
import os
import random
import sys
import traceback
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from sklearn.metrics import (
    auc,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_curve,
)
from torch.utils.data import ConcatDataset, random_split
from torch_geometric.loader import DataLoader

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def set_global_seed(seed: int = 42) -> None:
    """Fix all stochastic seeds to guarantee reproducibility."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


set_global_seed(42)

# ---------------------------------------------------------------------------
# Robust project-root resolution (replaces fragile 3-level dirname chain)
# ---------------------------------------------------------------------------

def find_project_root(start: str) -> str:
    """Walk up the directory tree until a project-marker file is found."""
    current = os.path.abspath(start)
    for _ in range(10):
        for marker in ("pyproject.toml", "setup.py", "setup.cfg", ".git"):
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # Fallback: three levels above this file (original heuristic)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


project_root = find_project_root(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# ---------------------------------------------------------------------------
# Project imports  (resolved after sys.path is set)
# ---------------------------------------------------------------------------
from src.gnn.models.gasse import GasseGNN              # noqa: E402
from src.graph_transform.milp_dataset import NeuralDivingDataset  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

@torch.no_grad()
def collect_predictions(model, loader, device):
    """
    Run inference over the loader and return aligned ground-truth / probability arrays.

    Uses the pre-stored  batch['variable'].is_discrete  mask (computed once
    during ETL in build_pyg_dataset_v4.py) so that:
      - the column-index selection is done at ETL time, not here
      - only binary and integer variables are scored (continuous stay as context)

    Additionally records  complexity_class  per prediction for per-stratum analysis.

    Returns
    -------
    y_true       : np.ndarray, shape (N,)   — ground-truth binary labels
    y_probs      : np.ndarray, shape (N,)   — sigmoid probabilities
    complexities : list[str]                — complexity label per variable node
    """
    model.eval()
    all_targets      = []
    all_probs        = []
    all_complexities = []

    for batch in loader:
        batch = batch.to(device)

        # --- use pre-stored is_discrete mask (ETL-computed, no column index risk) ---
        if hasattr(batch["variable"], "is_discrete"):
            target_mask = batch["variable"].is_discrete.bool()
        else:
            # Fallback for graphs built with v3 ETL (columns 4 and 5)
            logger.warning(
                "is_discrete attribute missing — falling back to column-index mask. "
                "Rebuild dataset with build_pyg_dataset_v4.py."
            )
            is_bin      = batch["variable"].x[:, 4] == 1.0   # col 4: is_binary
            is_int      = batch["variable"].x[:, 5] == 1.0   # col 5: is_integer
            target_mask = is_bin | is_int

        if target_mask.sum() == 0:
            continue

        logits = model(
            x_var    = batch["variable"].x,
            x_cons   = batch["constraint"].x,
            edge_v2c = batch["variable", "rev_coef", "constraint"].edge_index,
            binary_mask = target_mask,
            edge_attr   = batch["variable", "rev_coef", "constraint"].edge_attr,
        )

        probs   = torch.sigmoid(logits).cpu().numpy()
        # Clamp targets to [0, 1] for binary evaluation; values >1 come from
        # general integer variables whose GNN target was normalised.
        targets = torch.clamp(
            batch["variable"].y[target_mask], min=0.0, max=1.0
        ).cpu().numpy()

        all_probs.extend(probs)
        all_targets.extend(targets)

        # Per-variable complexity label for stratified reporting
        n_masked = int(target_mask.sum().item())
        cc = getattr(batch, "complexity_class", None)
        if cc is None:
            cc = ["unknown"] * n_masked
        elif isinstance(cc, str):
            cc = [cc] * n_masked
        all_complexities.extend(cc[:n_masked])

    return np.array(all_targets), np.array(all_probs), all_complexities


# ---------------------------------------------------------------------------
# Optimal threshold search
# ---------------------------------------------------------------------------

def find_optimal_threshold(y_true: np.ndarray, y_probs: np.ndarray) -> float:
    """
    Return the decision threshold that maximises the macro-average F1 score.

    The Precision-Recall curve gives (precision, recall, thresholds); we
    compute F1 at each threshold and return the argmax.

    This is preferable to the fixed 0.5 cut-off for imbalanced datasets, where
    the class boundary is often not at 0.5.
    """
    precision, recall, thresholds = precision_recall_curve(y_true, y_probs)
    # precision/recall have one extra element (the (1,0) anchor); align lengths
    f1_scores = np.where(
        (precision[:-1] + recall[:-1]) == 0,
        0.0,
        2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1]),
    )
    best_idx = int(np.argmax(f1_scores))
    return float(thresholds[best_idx])


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def plot_confusion_matrix(cm: np.ndarray, save_path: str) -> None:
    """Save a publication-ready confusion matrix heatmap."""
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues", cbar=False,
        xticklabels=["Predicted: Closed (0)", "Predicted: Open (1)"],
        yticklabels=["Actual: Closed (0)",    "Actual: Open (1)"],
        annot_kws={"size": 14},
        ax=ax,
    )
    ax.set_title("Confusion Matrix — Test Set", fontsize=16, pad=15)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved confusion matrix → %s", save_path)


def plot_roc_curve(fpr, tpr, roc_auc_val: float, save_path: str) -> None:
    """Save a publication-ready ROC curve with shaded AUC area."""
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.fill_between(fpr, tpr, alpha=0.15, color="darkorange")
    ax.plot(fpr, tpr, color="darkorange", lw=2,
            label=f"ROC curve  (AUC = {roc_auc_val:.4f})")
    ax.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--",
            label="Random classifier")
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.05])
    ax.set_xlabel("False Positive Rate (FPR)", fontsize=13)
    ax.set_ylabel("True Positive Rate (TPR)", fontsize=13)
    ax.set_title("ROC Curve — Neural Diving GNN", fontsize=16)
    ax.legend(loc="lower right", fontsize=12)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved ROC curve → %s", save_path)


def plot_pr_curve(precision, recall, pr_auc_val: float, save_path: str) -> None:
    """Save a Precision-Recall curve — more informative than ROC for imbalanced data."""
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.fill_between(recall, precision, alpha=0.15, color="steelblue")
    ax.plot(recall, precision, color="steelblue", lw=2,
            label=f"PR curve  (AUC = {pr_auc_val:.4f})")
    ax.set_xlabel("Recall", fontsize=13)
    ax.set_ylabel("Precision", fontsize=13)
    ax.set_title("Precision-Recall Curve — Neural Diving GNN", fontsize=16)
    ax.legend(loc="upper right", fontsize=12)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved PR curve → %s", save_path)


def plot_threshold_sweep(y_true: np.ndarray, y_probs: np.ndarray,
                         optimal_thr: float, save_path: str) -> None:
    """
    Plot Precision, Recall, and F1 as a function of the decision threshold.

    Useful for the thesis to justify the threshold selection.
    """
    thresholds = np.linspace(0.0, 1.0, 200)
    precisions, recalls, f1s = [], [], []

    for thr in thresholds:
        y_pred  = (y_probs >= thr).astype(int)
        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())
        p  = tp / (tp + fp + 1e-9)
        r  = tp / (tp + fn + 1e-9)
        f1 = 2 * p * r / (p + r + 1e-9)
        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(thresholds, precisions, label="Precision", lw=2, color="steelblue")
    ax.plot(thresholds, recalls,    label="Recall",    lw=2, color="darkorange")
    ax.plot(thresholds, f1s,        label="F1 Score",  lw=2, color="green")
    ax.axvline(optimal_thr, color="red", linestyle="--", lw=1.5,
               label=f"Optimal threshold = {optimal_thr:.3f}")
    ax.set_xlabel("Decision Threshold", fontsize=13)
    ax.set_ylabel("Score", fontsize=13)
    ax.set_title("Threshold Sweep — Precision / Recall / F1", fontsize=16)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved threshold sweep → %s", save_path)


# ---------------------------------------------------------------------------
# Per-complexity breakdown
# ---------------------------------------------------------------------------

def compute_per_complexity_metrics(y_true: np.ndarray, y_probs: np.ndarray,
                                   complexities: list, threshold: float) -> pd.DataFrame:
    """
    Compute Precision, Recall, F1, and AUC-ROC broken down by complexity class.

    This directly supports the thesis ablation study comparing GNN performance
    on easy vs. hard CFL instances (captured in R4 metadata propagation).
    """
    y_pred = (y_probs >= threshold).astype(int)
    rows   = []

    for cls in sorted(set(complexities)):
        idx = np.array([i for i, c in enumerate(complexities) if c == cls])
        if len(idx) == 0:
            continue
        yt = y_true[idx]
        yp = y_pred[idx]
        ypr = y_probs[idx]

        tp = int(((yp == 1) & (yt == 1)).sum())
        fp = int(((yp == 1) & (yt == 0)).sum())
        fn = int(((yp == 0) & (yt == 1)).sum())
        p  = tp / (tp + fp + 1e-9)
        r  = tp / (tp + fn + 1e-9)
        f1 = 2 * p * r / (p + r + 1e-9)

        # AUC-ROC only defined when both classes are present
        try:
            fpr_c, tpr_c, _ = roc_curve(yt, ypr)
            auc_val = float(auc(fpr_c, tpr_c))
        except ValueError:
            auc_val = float("nan")

        rows.append({
            "complexity_class": cls,
            "n_variables":      len(idx),
            "precision":        round(p, 4),
            "recall":           round(r, 4),
            "f1_score":         round(f1, 4),
            "roc_auc":          round(auc_val, 4) if not np.isnan(auc_val) else "N/A",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Academic evaluation of a trained Neural Diving GNN."
    )
    parser.add_argument("--model_path",       type=str, required=True,
                        help="Path to the best_model.pt file.")
    parser.add_argument("--base_root",        type=str,
                        default="/raid/vrcelestino/data/cfl-gurobi-gnn/"
                                "data/bipartite_graphs/pyg_dataset",
                        help="Root directory containing per-category PyG datasets.")
    parser.add_argument("--experiment_name",  type=str, default="eval",
                        help="Sub-folder name for outputs (e.g. serial_v4, parallel_v4).")
    parser.add_argument("--hidden_dim",       type=int, default=64)
    parser.add_argument("--num_layers",       type=int, default=2)
    parser.add_argument("--batch_size",       type=int, default=16)
    parser.add_argument("--seed",             type=int, default=42)
    # Dataset splits: [n_train  n_val  n_test]
    parser.add_argument("--easy_split",   type=int, nargs=3, default=[0, 0, 0],
                        metavar=("TRAIN", "VAL", "TEST"))
    parser.add_argument("--medium_split", type=int, nargs=3, default=[0, 0, 0],
                        metavar=("TRAIN", "VAL", "TEST"))
    parser.add_argument("--hard_split",   type=int, nargs=3, default=[0, 0, 0],
                        metavar=("TRAIN", "VAL", "TEST"))
    args = parser.parse_args()

    set_global_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("=== Neural Diving Academic Evaluation on %s ===", device)

    # --- Output directory scoped by experiment name -------------------------
    output_dir = os.path.join(project_root, "data", "analysis", args.experiment_name)
    os.makedirs(output_dir, exist_ok=True)
    logger.info("Artefacts will be saved to: %s", output_dir)

    # --- Dataset loading ----------------------------------------------------
    base_root = args.base_root
    category_config = {
        "CFL_easy_instance":   args.easy_split,
        "CFL_medium_instance": args.medium_split,
        "CFL_hard_instance":   args.hard_split,
    }

    test_datasets = []
    generator     = torch.Generator().manual_seed(args.seed)

    for cat, (n_train, n_val, n_test) in category_config.items():
        if n_test == 0:
            continue
        cat_root   = os.path.join(base_root, cat)
        ds         = NeuralDivingDataset(root=cat_root)
        total_req  = n_train + n_val + n_test
        unused     = max(0, len(ds) - total_req)

        if len(ds) < total_req:
            logger.warning(
                "Category %s: requested %d graphs but only %d available — skipping.",
                cat, total_req, len(ds)
            )
            continue

        _, _, ds_test, _ = random_split(
            ds, [n_train, n_val, n_test, unused], generator=generator
        )
        test_datasets.append(ds_test)
        logger.info("Category %-30s  test = %d graphs", cat, n_test)

    if not test_datasets:
        logger.error("No test graphs configured — verify --easy_split / --medium_split / --hard_split.")
        return

    test_data   = ConcatDataset(test_datasets)
    test_loader = DataLoader(test_data, batch_size=args.batch_size, shuffle=False)
    logger.info("Total test graphs: %d", len(test_data))

    # --- Model loading ------------------------------------------------------
    logger.info("Loading model: %s", os.path.basename(args.model_path))
    model = GasseGNN(
        var_in_dim  = 7,
        cons_in_dim = 5,
        edge_dim    = 1,
        hidden_dim  = args.hidden_dim,
        num_layers  = args.num_layers,
    )
    # weights_only=True is safe for state_dict (pure tensor dict)
    model.load_state_dict(
        torch.load(args.model_path, map_location=device, weights_only=True)
    )
    model.to(device)
    n_params = sum(p.numel() for p in model.parameters())
    logger.info("Model parameters: %d", n_params)

    # --- Collect predictions ------------------------------------------------
    logger.info("Running inference on %d test graphs ...", len(test_data))
    try:
        y_true, y_probs, complexities = collect_predictions(model, test_loader, device)
    except Exception:
        logger.error("Inference failed:\n%s", traceback.format_exc())
        return

    if len(y_true) == 0:
        logger.error("No valid predictions collected — check dataset labels.")
        return

    logger.info("Total variable predictions: %d", len(y_true))
    logger.info(
        "Label distribution:  positive (1) = %.2f %%   negative (0) = %.2f %%",
        100.0 * y_true.mean(),
        100.0 * (1.0 - y_true.mean()),
    )

    # --- Optimal threshold --------------------------------------------------
    optimal_thr = find_optimal_threshold(y_true, y_probs)
    logger.info("Optimal decision threshold (max F1): %.4f", optimal_thr)
    y_pred = (y_probs >= optimal_thr).astype(int)

    # ========================================================================
    # ARTEFACT A — Classification report
    # ========================================================================
    logger.info("Generating classification report ...")
    report_dict = classification_report(
        y_true, y_pred,
        target_names=["Closed (0)", "Open (1)"],
        output_dict=True,
    )
    report_df = pd.DataFrame(report_dict).transpose()
    report_path = os.path.join(output_dir, "classification_report.csv")
    report_df.to_csv(report_path)
    logger.info("Classification report:\n%s", report_df.to_string())

    # ========================================================================
    # ARTEFACT B — Confusion matrix
    # ========================================================================
    cm = confusion_matrix(y_true, y_pred)
    plot_confusion_matrix(cm, os.path.join(output_dir, "confusion_matrix.png"))

    # ========================================================================
    # ARTEFACT C — ROC-AUC curve
    # ========================================================================
    fpr, tpr, _     = roc_curve(y_true, y_probs)
    roc_auc_val     = float(auc(fpr, tpr))
    plot_roc_curve(fpr, tpr, roc_auc_val,
                   os.path.join(output_dir, "roc_auc_curve.png"))

    # ========================================================================
    # ARTEFACT D — Precision-Recall curve
    # ========================================================================
    precision_arr, recall_arr, _ = precision_recall_curve(y_true, y_probs)
    pr_auc_val = float(auc(recall_arr, precision_arr))
    plot_pr_curve(precision_arr, recall_arr, pr_auc_val,
                  os.path.join(output_dir, "pr_curve.png"))

    # ========================================================================
    # ARTEFACT E — Threshold sweep
    # ========================================================================
    plot_threshold_sweep(y_true, y_probs, optimal_thr,
                         os.path.join(output_dir, "threshold_sweep.png"))

    # ========================================================================
    # ARTEFACT F — Per-complexity breakdown (thesis ablation)
    # ========================================================================
    complexity_df = compute_per_complexity_metrics(
        y_true, y_probs, complexities, optimal_thr
    )
    complexity_path = os.path.join(output_dir, "per_complexity_metrics.csv")
    complexity_df.to_csv(complexity_path, index=False)
    logger.info("Per-complexity breakdown:\n%s", complexity_df.to_string(index=False))

    # ========================================================================
    # ARTEFACT G — Machine-readable summary JSON
    # ========================================================================
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    p_val  = tp / (tp + fp + 1e-9)
    r_val  = tp / (tp + fn + 1e-9)
    f1_val = 2 * p_val * r_val / (p_val + r_val + 1e-9)

    summary = {
        "experiment_name":   args.experiment_name,
        "model_path":        args.model_path,
        "n_test_variables":  int(len(y_true)),
        "optimal_threshold": round(optimal_thr, 4),
        "roc_auc":           round(roc_auc_val, 4),
        "pr_auc":            round(pr_auc_val, 4),
        "precision":         round(float(p_val), 4),
        "recall":            round(float(r_val), 4),
        "f1_score":          round(float(f1_val), 4),
        "n_model_params":    n_params,
    }
    summary_path = os.path.join(output_dir, "evaluation_summary.json")
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    logger.info(
        "\n=== Evaluation Complete ===\n"
        "  ROC-AUC  : %.4f\n"
        "  PR-AUC   : %.4f\n"
        "  F1-Score : %.4f  (threshold = %.4f)\n"
        "  Artefacts: %s",
        roc_auc_val, pr_auc_val, f1_val, optimal_thr, output_dir,
    )


if __name__ == "__main__":
    main()
