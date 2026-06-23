#!/usr/bin/env python3
"""
Generate ROC and PR comparison plots: Centralized vs FL scenarios.
Output: grafice/comparison/roc_comparison.png
        grafice/comparison/pr_comparison.png
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc, precision_recall_curve, average_precision_score
from pathlib import Path

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f8f9fa",
    "axes.grid": True,
    "grid.color": "white",
    "grid.linewidth": 1.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 11,
})

MODELS = {
    "Centralizat (best)":               ("centralized_dragos/predictions_test.csv",                                                              "#e74c3c", "--", 2.5),
    "FL — IID strict":                  ("experiments_tavi/dist_iid_strict_run01/central/best_model/predictions_test.csv",                        "#2196F3", "-",  2.0),
    "FL — Dezechilibru cantitativ (3×)":("experiments_tavi/dist_dezechilibru_cantitativ_node1_3x_run01/central/best_model/predictions_test.csv",  "#4CAF50", "-",  2.0),
    "FL — Concentrare pneumonie (75%)": ("experiments_tavi/dist_concentrare_pneumonie_75%_la_node1_run01/central/best_model/predictions_test.csv","#FF9800", "-",  2.0),
    "FL — Non-IID extrem (α=0.1)":      ("experiments_tavi/dist_non-iid_extrem_dirichlet_0_1_run02/central/best_model/predictions_test.csv",     "#9C27B0", "-",  2.0),
}

out_dir = Path("grafice/comparison")
out_dir.mkdir(parents=True, exist_ok=True)

fig_roc, ax_roc = plt.subplots(figsize=(9, 7))
fig_pr,  ax_pr  = plt.subplots(figsize=(9, 7))

for name, (path, color, ls, lw) in MODELS.items():
    df = pd.read_csv(path)
    y_true  = df["y_true"].values
    y_score = df["y_score"].values

    # ROC
    fpr, tpr, _ = roc_curve(y_true, y_score)
    roc_auc = auc(fpr, tpr)
    ax_roc.plot(fpr, tpr, color=color, linestyle=ls, linewidth=lw,
                label=f"{name} (AUC={roc_auc:.4f})")

    # PR
    prec, rec, _ = precision_recall_curve(y_true, y_score)
    pr_auc = average_precision_score(y_true, y_score)
    ax_pr.plot(rec, prec, color=color, linestyle=ls, linewidth=lw,
               label=f"{name} (PR-AUC={pr_auc:.4f})")

# ROC finish
ax_roc.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.4, label="Random")
ax_roc.set_xlabel("False Positive Rate", fontsize=12)
ax_roc.set_ylabel("True Positive Rate", fontsize=12)
ax_roc.set_title("Curbe ROC — FL vs. Centralizat", fontsize=14, fontweight="bold")
ax_roc.legend(fontsize=9, loc="lower right")
fig_roc.tight_layout()
roc_path = out_dir / "roc_comparison.png"
fig_roc.savefig(roc_path, dpi=150, bbox_inches="tight")
print(f"Saved → {roc_path}")
plt.close(fig_roc)

# PR finish
ax_pr.set_xlabel("Recall", fontsize=12)
ax_pr.set_ylabel("Precision", fontsize=12)
ax_pr.set_title("Curbe Precision-Recall — FL vs. Centralizat", fontsize=14, fontweight="bold")
ax_pr.legend(fontsize=9, loc="lower left")
fig_pr.tight_layout()
pr_path = out_dir / "pr_comparison.png"
fig_pr.savefig(pr_path, dpi=150, bbox_inches="tight")
print(f"Saved → {pr_path}")
plt.close(fig_pr)
