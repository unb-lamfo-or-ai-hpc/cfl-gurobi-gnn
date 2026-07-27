"""
evaluate_model_v3.py
====================
Academic evaluation of a trained Neural Diving GNN on the held-out Test Set.

V3 Updates:
  - Unified Serial & DDP Support: Auto-detects torchrun.
  - Safe State-Dict Loading: Automatically strips 'module.' prefixes from DDP models.
  - Asymmetric Gathering: Uses dist.all_gather_object for variable-length predictions.
  - New Artefact: Calibration Curve (Reliability Diagram) for confidence analysis.
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
import torch.distributed as dist
from torch.utils.data.distributed import DistributedSampler
from sklearn.metrics import (
    auc,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_curve,
)
from sklearn.calibration import calibration_curve
from torch.utils.data import ConcatDataset, random_split
from torch_geometric.loader import DataLoader

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
def set_global_seed(seed: int = 42) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_global_seed(42)

# Project-root detection
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.graph_transform.milp_dataset_v2 import NeuralDivingDataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
@torch.no_grad()
def collect_predictions(model, loader, device):
    model.eval()
    all_targets, all_probs, all_complexities = [], [], []

    for batch in loader:
        batch = batch.to(device)

        if hasattr(batch["variable"], "is_discrete"):
            target_mask = batch["variable"].is_discrete.bool()
        else:
            is_bin = batch["variable"].x[:, 4] == 1.0
            is_int = batch["variable"].x[:, 5] == 1.0
            target_mask = is_bin | is_int

        if target_mask.sum() == 0: continue

        logits = model(
            x_var=batch["variable"].x, x_cons=batch["constraint"].x,
            edge_v2c=batch["variable", "rev_coef", "constraint"].edge_index,
            binary_mask=target_mask, edge_attr=batch["variable", "rev_coef", "constraint"].edge_attr,
        )

        probs = torch.sigmoid(logits).cpu().numpy().tolist()
        targets = torch.clamp(batch["variable"].y[target_mask], min=0.0, max=1.0).cpu().numpy().tolist()

        all_probs.extend(probs)
        all_targets.extend(targets)

        n_masked = int(target_mask.sum().item())
        cc = getattr(batch, "complexity_class", ["unknown"])
        if isinstance(cc, str): cc = [cc] * n_masked
        all_complexities.extend(cc[:n_masked])

    return all_targets, all_probs, all_complexities


# ---------------------------------------------------------------------------
# Metrics & Plotting
# ---------------------------------------------------------------------------
def find_optimal_threshold(y_true: np.ndarray, y_probs: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, y_probs)
    f1_scores = np.where((precision[:-1] + recall[:-1]) == 0, 0.0, 2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1]))
    return float(thresholds[int(np.argmax(f1_scores))])

def plot_confusion_matrix(cm: np.ndarray, save_path: str):
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False, xticklabels=["Closed (0)", "Open (1)"], yticklabels=["Closed (0)", "Open (1)"], annot_kws={"size": 14}, ax=ax)
    ax.set_title("Confusion Matrix — Test Set", fontsize=16, pad=15)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

def plot_roc_curve(fpr, tpr, roc_auc_val: float, save_path: str):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.fill_between(fpr, tpr, alpha=0.15, color="darkorange")
    ax.plot(fpr, tpr, color="darkorange", lw=2, label=f"ROC (AUC = {roc_auc_val:.4f})")
    ax.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--")
    ax.set(xlim=[0.0, 1.0], ylim=[0.0, 1.05], xlabel="False Positive Rate", ylabel="True Positive Rate", title="ROC Curve")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig)

def plot_pr_curve(precision, recall, pr_auc_val: float, save_path: str):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.fill_between(recall, precision, alpha=0.15, color="steelblue")
    ax.plot(recall, precision, color="steelblue", lw=2, label=f"PR (AUC = {pr_auc_val:.4f})")
    ax.set(xlabel="Recall", ylabel="Precision", title="Precision-Recall Curve")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig)

def plot_calibration_curve(y_true: np.ndarray, y_probs: np.ndarray, save_path: str):
    """Reliability diagram to check if the GNN is overconfident."""
    prob_true, prob_pred = calibration_curve(y_true, y_probs, n_bins=10)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(prob_pred, prob_true, marker='o', linewidth=2, label='Neural Diving GNN', color='purple')
    ax.plot([0, 1], [0, 1], linestyle='--', color='gray', label='Perfectly Calibrated')
    ax.set(xlabel="Mean Predicted Probability", ylabel="Fraction of Positives", title="Calibration Curve (Reliability)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig)

def plot_threshold_sweep(y_true: np.ndarray, y_probs: np.ndarray, optimal_thr: float, save_path: str):
    thresholds = np.linspace(0.0, 1.0, 100)
    precisions, recalls, f1s = [], [], []
    for thr in thresholds:
        y_pred = (y_probs >= thr).astype(int)
        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())
        p, r = tp / (tp + fp + 1e-9), tp / (tp + fn + 1e-9)
        precisions.append(p); recalls.append(r); f1s.append(2 * p * r / (p + r + 1e-9))

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(thresholds, precisions, label="Precision", lw=2, color="steelblue")
    ax.plot(thresholds, recalls, label="Recall", lw=2, color="darkorange")
    ax.plot(thresholds, f1s, label="F1 Score", lw=2, color="green")
    ax.axvline(optimal_thr, color="red", linestyle="--", label=f"Optimal Thr = {optimal_thr:.3f}")
    ax.set(xlabel="Decision Threshold", ylabel="Score", title="Threshold Sweep")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(save_path, dpi=300); plt.close(fig)

def compute_per_complexity_metrics(y_true: np.ndarray, y_probs: np.ndarray, complexities: list, threshold: float) -> pd.DataFrame:
    y_pred = (y_probs >= threshold).astype(int)
    rows = []
    for cls in sorted(set(complexities)):
        idx = np.array([i for i, c in enumerate(complexities) if c == cls])
        if len(idx) == 0: continue
        yt, yp, ypr = y_true[idx], y_pred[idx], y_probs[idx]
        tp, fp, fn = int(((yp == 1) & (yt == 1)).sum()), int(((yp == 1) & (yt == 0)).sum()), int(((yp == 0) & (yt == 1)).sum())
        p, r = tp / (tp + fp + 1e-9), tp / (tp + fn + 1e-9)
        try:
            fpr_c, tpr_c, _ = roc_curve(yt, ypr)
            auc_val = float(auc(fpr_c, tpr_c))
        except ValueError:
            auc_val = float("nan")
        rows.append({"complexity_class": cls, "n_variables": len(idx), "precision": round(p, 4), "recall": round(r, 4), "f1_score": round(2 * p * r / (p + r + 1e-9), 4), "roc_auc": round(auc_val, 4) if not np.isnan(auc_val) else "N/A"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # 1. Auto-detect DDP Environment
    is_ddp = "WORLD_SIZE" in os.environ
    if is_ddp:
        dist.init_process_group(backend="nccl")
        local_rank = int(os.environ["LOCAL_RANK"])
        torch.cuda.set_device(local_rank)
        device = torch.device(f"cuda:{local_rank}")
        is_master = (local_rank == 0)
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        is_master = True

    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--base_root", type=str, default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset")
    parser.add_argument("--experiment_name", type=str, default="eval_v3")
    parser.add_argument("--hidden_dim", type=int, default=64)
    parser.add_argument("--num_layers", type=int, default=2)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--easy_split", type=int, nargs=3, default=[0, 0, 0])
    parser.add_argument("--medium_split", type=int, nargs=3, default=[0, 0, 0])
    parser.add_argument("--hard_split", type=int, nargs=3, default=[0, 0, 0])
    args = parser.parse_args()

    output_dir = os.path.join(project_root, "data", "analysis", args.experiment_name)
    if is_master:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"=== Evaluation started. DDP Mode: {is_ddp} ===")

    # 2. Build Datasets
    category_config = {"CFL_easy_instance": args.easy_split, "CFL_medium_instance": args.medium_split, "CFL_hard_instance": args.hard_split}
    test_datasets = []
    generator = torch.Generator().manual_seed(42)

    for cat, (n_train, n_val, n_test) in category_config.items():
        if n_test == 0: continue
        ds = NeuralDivingDataset(root=os.path.join(args.base_root, cat))
        if len(ds) < (n_train + n_val + n_test): continue
        _, _, ds_test, _ = random_split(ds, [n_train, n_val, n_test, len(ds) - (n_train + n_val + n_test)], generator=generator)
        test_datasets.append(ds_test)

    if not test_datasets:
        if is_master: logger.error("No test graphs configured.")
        sys.exit(1)

    test_data = ConcatDataset(test_datasets)
    sampler = DistributedSampler(test_data, shuffle=False) if is_ddp else None
    test_loader = DataLoader(test_data, batch_size=args.batch_size, sampler=sampler, shuffle=False)

    # 3. Safe Model Loading (Stripping 'module.')
    model = GasseGNN(var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=args.num_layers)
    state_dict = torch.load(args.model_path, map_location=device, weights_only=True)
    clean_state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
    model.load_state_dict(clean_state_dict)
    model.to(device)

    # 4. Inference
    if is_master: logger.info("Running inference...")
    local_targets, local_probs, local_complexities = collect_predictions(model, test_loader, device)

    # 5. DDP Asymmetric Gather
    if is_ddp:
        gathered_data = [None for _ in range(dist.get_world_size())]
        dist.all_gather_object(gathered_data, (local_targets, local_probs, local_complexities))
        
        if is_master:
            y_true = np.concatenate([data[0] for data in gathered_data])
            y_probs = np.concatenate([data[1] for data in gathered_data])
            complexities = [c for data in gathered_data for c in data[2]]
    else:
        y_true, y_probs, complexities = np.array(local_targets), np.array(local_probs), local_complexities

    # 6. Global Metrics & Artefacts (Master Only)
    if is_master:
        if len(y_true) == 0:
            logger.error("No valid predictions collected.")
            return

        optimal_thr = find_optimal_threshold(y_true, y_probs)
        y_pred = (y_probs >= optimal_thr).astype(int)

        logger.info(f"Generating Artefacts in: {output_dir}")
        pd.DataFrame(classification_report(y_true, y_pred, target_names=["Closed (0)", "Open (1)"], output_dict=True)).transpose().to_csv(os.path.join(output_dir, "classification_report.csv"))
        
        plot_confusion_matrix(confusion_matrix(y_true, y_pred), os.path.join(output_dir, "confusion_matrix.png"))
        
        fpr, tpr, _ = roc_curve(y_true, y_probs)
        roc_auc_val = float(auc(fpr, tpr))
        plot_roc_curve(fpr, tpr, roc_auc_val, os.path.join(output_dir, "roc_auc_curve.png"))
        
        precision_arr, recall_arr, _ = precision_recall_curve(y_true, y_probs)
        pr_auc_val = float(auc(recall_arr, precision_arr))
        plot_pr_curve(precision_arr, recall_arr, pr_auc_val, os.path.join(output_dir, "pr_curve.png"))
        
        plot_threshold_sweep(y_true, y_probs, optimal_thr, os.path.join(output_dir, "threshold_sweep.png"))
        plot_calibration_curve(y_true, y_probs, os.path.join(output_dir, "calibration_curve.png"))

        compute_per_complexity_metrics(y_true, y_probs, complexities, optimal_thr).to_csv(os.path.join(output_dir, "per_complexity_metrics.csv"), index=False)

        tp, fp, fn = int(((y_pred == 1) & (y_true == 1)).sum()), int(((y_pred == 1) & (y_true == 0)).sum()), int(((y_pred == 0) & (y_true == 1)).sum())
        p_val, r_val = tp / (tp + fp + 1e-9), tp / (tp + fn + 1e-9)
        f1_val = 2 * p_val * r_val / (p_val + r_val + 1e-9)

        summary = {
            "experiment_name": args.experiment_name,
            "n_test_variables": int(len(y_true)),
            "optimal_threshold": round(optimal_thr, 4),
            "roc_auc": round(roc_auc_val, 4),
            "pr_auc": round(pr_auc_val, 4),
            "precision": round(float(p_val), 4),
            "recall": round(float(r_val), 4),
            "f1_score": round(float(f1_val), 4),
        }
        with open(os.path.join(output_dir, "evaluation_summary.json"), "w") as fh:
            json.dump(summary, fh, indent=2)

        logger.info(f"\n=== Evaluation Complete ===\n  ROC-AUC  : {roc_auc_val:.4f}\n  PR-AUC   : {pr_auc_val:.4f}\n  F1-Score : {f1_val:.4f}  (threshold = {optimal_thr:.4f})")

    if is_ddp:
        dist.barrier()
        dist.destroy_process_group()

if __name__ == "__main__":
    main()
