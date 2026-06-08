#!/usr/bin/env python3
"""
generate_plots_distributii.py — Grafice comparative pentru experimentele
de distribuție date (experiments_tavi/).

Compară 4 distribuții de date cu FedAvg fix:
  --iid         : IID strict (distribuție ideală)
  --noniid      : Non-IID extrem (Dirichlet α=0.1)
  --pneumonia   : Concentrare pneumonie (75% la node1)
  --qty         : Dezechilibru cantitativ (node1 = 3x)

Produce:
  results/
    comparison_table.csv / .md
    auc_vs_round.png
    f1_vs_round.png
    f2_vs_round.png
    test_loss_vs_round.png
    sensitivity_specificity_vs_round.png
    update_norm_vs_round.png
    roc_curves.png
    pr_curves.png
    confusion_matrices.png
    per_node_auc_iid.png
    per_node_f2_iid.png
    per_node_auc_noniid.png   ...etc

Utilizare:
  python scripts/generate_plots_distributii.py \\
      --iid       experiments_tavi/dist_iid_strict_run01 \\
      --noniid    experiments_tavi/dist_noniid_extreme_run01 \\
      --pneumonia experiments_tavi/dist_pneumonia_concentration_run01 \\
      --qty       experiments_tavi/dist_quantity_imbalance_run01 \\
      --output-dir results/tavi_comparative \\
      --num-nodes 4
"""
import argparse
import csv
import json
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# ============================================================================
# Configurație distribuții — chei, culori, labels
# ============================================================================

DIST_CONFIG: Dict[str, Dict] = {
    "iid": {
        "label":  "IID strict",
        "color":  "#2196F3",   # albastru
        "marker": "o",
    },
    "noniid": {
        "label":  "Non-IID extrem (α=0.1)",
        "color":  "#F44336",   # roșu
        "marker": "s",
    },
    "pneumonia": {
        "label":  "Concentrare pneumonie (75%)",
        "color":  "#FF9800",   # portocaliu
        "marker": "^",
    },
    "qty": {
        "label":  "Dezechilibru cantitativ (3×)",
        "color":  "#9C27B0",   # violet
        "marker": "D",
    },
}


# ============================================================================
# Utilitare de citire
# ============================================================================

def _warn(msg: str) -> None:
    print(f"  WARN: {msg}", file=sys.stderr)


def read_csv(path: str) -> Optional[List[Dict]]:
    p = Path(path)
    if not p.exists():
        _warn(f"Fișier lipsă — {path}")
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        _warn(f"Eroare la citirea {path}: {e}")
        return None


def read_json(path: str) -> Optional[dict]:
    p = Path(path)
    if not p.exists():
        _warn(f"Fișier lipsă — {path}")
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _warn(f"Eroare la citirea {path}: {e}")
        return None


def _float(val) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def pred_path(exp_dir: str) -> str:
    return str(Path(exp_dir) / "central" / "best_model" / "predictions_test.csv")


def cm_path(exp_dir: str) -> str:
    return str(Path(exp_dir) / "central" / "best_model" / "confusion_matrix.json")


def rounds_path(exp_dir: str) -> str:
    return str(Path(exp_dir) / "central" / "metrics_by_round.csv")


# ============================================================================
# Metrici din predictions_test.csv
# ============================================================================

def compute_metrics_from_predictions(predictions_path: str) -> Optional[Dict]:
    rows = read_csv(predictions_path)
    if rows is None:
        return None
    try:
        from sklearn.metrics import (
            roc_auc_score, f1_score, fbeta_score,
            average_precision_score, confusion_matrix,
        )
        y_true  = [int(r["y_true"])   for r in rows]
        y_score = [float(r["y_score"]) for r in rows]
        y_pred  = [1 if s >= 0.5 else 0 for s in y_score]

        auc    = roc_auc_score(y_true, y_score)
        f1     = f1_score(y_true, y_pred)
        f2     = fbeta_score(y_true, y_pred, beta=2)
        pr_auc = average_precision_score(y_true, y_score)

        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel()
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

        return {
            "auc":         round(auc, 4),
            "f1":          round(f1, 4),
            "f2":          round(f2, 4),
            "sensitivity": round(sensitivity, 4),
            "specificity": round(specificity, 4),
            "pr_auc":      round(pr_auc, 4),
            "y_true":  y_true,
            "y_score": y_score,
        }
    except Exception as e:
        _warn(f"Eroare metrici {predictions_path}: {e}")
        return None


# ============================================================================
# 1. Tabel comparativ
# ============================================================================

def generate_comparison_table(experiments: Dict[str, str], output_dir: str) -> None:
    print("\n[1] Generare tabel comparativ...")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for key, exp_dir in experiments.items():
        cfg  = DIST_CONFIG[key]
        m    = compute_metrics_from_predictions(pred_path(exp_dir))
        if m is None:
            rows.append({"Distribuție": cfg["label"],
                         "AUC": "N/A", "F1": "N/A", "F2": "N/A",
                         "Sensitivity": "N/A", "Specificity": "N/A", "PR_AUC": "N/A"})
        else:
            rows.append({"Distribuție": cfg["label"],
                         "AUC": m["auc"], "F1": m["f1"], "F2": m["f2"],
                         "Sensitivity": m["sensitivity"],
                         "Specificity": m["specificity"],
                         "PR_AUC": m["pr_auc"]})

    fields = ["Distribuție", "AUC", "F1", "F2", "Sensitivity", "Specificity", "PR_AUC"]

    csv_out = out / "comparison_table.csv"
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    print(f"  ✓ {csv_out}")

    md_out = out / "comparison_table.md"
    with open(md_out, "w", encoding="utf-8") as f:
        f.write("# Tabel Comparativ — Distribuții de Date (FedAvg)\n\n")
        f.write("| Distribuție | AUC | F1 | F2 | Sensitivity | Specificity | PR-AUC |\n")
        f.write("|-------------|-----|----|----|-------------|-------------|--------|\n")
        for r in rows:
            f.write(f"| {r['Distribuție']} | {r['AUC']} | {r['F1']} | {r['F2']} | "
                    f"{r['Sensitivity']} | {r['Specificity']} | {r['PR_AUC']} |\n")
    print(f"  ✓ {md_out}")


# ============================================================================
# 2. Metrică vs. rundă
# ============================================================================

def plot_metric_vs_round(
    experiments: Dict[str, str],
    metric: str,
    output_path: str,
    title: str,
    ylabel: str,
    ylim: Tuple[float, float] = (0.7, 1.01),
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    has_data = False

    for key, exp_dir in experiments.items():
        cfg  = DIST_CONFIG[key]
        rows = read_csv(rounds_path(exp_dir))
        if rows is None:
            continue
        rounds, values = [], []
        for row in rows:
            r = _float(row.get("round"))
            v = _float(row.get(metric))
            if r is not None and v is not None:
                rounds.append(r); values.append(v)
        if rounds:
            ax.plot(rounds, values,
                    color=cfg["color"], label=cfg["label"],
                    linewidth=2, marker=cfg["marker"], markersize=4)
            has_data = True

    if not has_data:
        plt.close(fig)
        _warn(f"Nu există date pentru {metric}")
        return

    ax.set_xlabel("Rundă FL", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    if ylim:
        ax.set_ylim(*ylim)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {output_path}")


# ============================================================================
# 3. ROC și PR curves
# ============================================================================

def plot_roc_pr_curves(experiments: Dict[str, str], output_dir: str) -> None:
    print("\n[3] Generare ROC și PR curves...")
    from sklearn.metrics import roc_curve, precision_recall_curve, auc

    fig_roc, ax_roc = plt.subplots(figsize=(8, 7))
    fig_pr,  ax_pr  = plt.subplots(figsize=(8, 7))
    has_roc = has_pr = False

    for key, exp_dir in experiments.items():
        cfg  = DIST_CONFIG[key]
        rows = read_csv(pred_path(exp_dir))
        if rows is None:
            continue
        try:
            y_true  = [int(r["y_true"])    for r in rows]
            y_score = [float(r["y_score"]) for r in rows]

            fpr, tpr, _ = roc_curve(y_true, y_score)
            roc_auc = auc(fpr, tpr)
            ax_roc.plot(fpr, tpr, color=cfg["color"],
                        label=f"{cfg['label']} (AUC={roc_auc:.3f})", linewidth=2)
            has_roc = True

            precision, recall, _ = precision_recall_curve(y_true, y_score)
            pr_auc = auc(recall, precision)
            ax_pr.plot(recall, precision, color=cfg["color"],
                       label=f"{cfg['label']} (PR-AUC={pr_auc:.3f})", linewidth=2)
            has_pr = True
        except Exception as e:
            _warn(f"ROC/PR eroare {key}: {e}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if has_roc:
        ax_roc.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random")
        ax_roc.set_xlabel("False Positive Rate", fontsize=12)
        ax_roc.set_ylabel("True Positive Rate", fontsize=12)
        ax_roc.set_title("ROC Curves — Comparație Distribuții", fontsize=14)
        ax_roc.legend(fontsize=10); ax_roc.grid(True, alpha=0.3)
        p = str(out / "roc_curves.png")
        fig_roc.tight_layout(); fig_roc.savefig(p, dpi=150, bbox_inches="tight")
        print(f"  ✓ {p}")
    plt.close(fig_roc)

    if has_pr:
        ax_pr.set_xlabel("Recall", fontsize=12)
        ax_pr.set_ylabel("Precision", fontsize=12)
        ax_pr.set_title("Precision-Recall Curves — Comparație Distribuții", fontsize=14)
        ax_pr.legend(fontsize=10); ax_pr.grid(True, alpha=0.3)
        p = str(out / "pr_curves.png")
        fig_pr.tight_layout(); fig_pr.savefig(p, dpi=150, bbox_inches="tight")
        print(f"  ✓ {p}")
    plt.close(fig_pr)


# ============================================================================
# 4. Confusion matrices
# ============================================================================

def plot_confusion_matrices(experiments: Dict[str, str], output_dir: str) -> None:
    print("\n[4] Generare confusion matrices...")
    cms = {k: read_json(cm_path(v)) for k, v in experiments.items()}
    cms = {k: v for k, v in cms.items() if v is not None}
    if not cms:
        _warn("Nicio confusion matrix disponibilă")
        return

    n   = len(cms)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5))
    if n == 1:
        axes = [axes]

    for ax, (key, cm_data) in zip(axes, cms.items()):
        cfg = DIST_CONFIG[key]
        tp = cm_data.get("TP", 0); fp = cm_data.get("FP", 0)
        tn = cm_data.get("TN", 0); fn = cm_data.get("FN", 0)
        matrix = np.array([[tn, fp], [fn, tp]])

        ax.imshow(matrix, interpolation="nearest", cmap="Blues")
        ax.set_title(cfg["label"], fontsize=11, fontweight="bold")
        ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
        ax.set_xticklabels(["NORMAL", "PNEUMONIA"], fontsize=9)
        ax.set_yticklabels(["NORMAL", "PNEUMONIA"], fontsize=9)

        total = tp + fp + tn + fn
        for i in range(2):
            for j in range(2):
                val = matrix[i, j]
                pct = val / total * 100 if total > 0 else 0
                ax.text(j, i, f"{val}\n({pct:.1f}%)",
                        ha="center", va="center", fontsize=10,
                        color="white" if val > matrix.max() * 0.6 else "black")

        acc  = cm_data.get("accuracy",    0)
        sens = cm_data.get("sensitivity", 0)
        spec = cm_data.get("specificity", 0)
        ax.set_xlabel(
            f"Predicție\nAcc={acc:.3f} | Sens={sens:.3f} | Spec={spec:.3f}",
            fontsize=9)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "confusion_matrices.png")
    fig.suptitle("Confusion Matrices — Comparație Distribuții", fontsize=13,
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 5. Sensitivity / Specificity vs. rundă
# ============================================================================

def plot_sensitivity_specificity_vs_round(
    experiments: Dict[str, str], output_dir: str
) -> None:
    print("\n[5] Generare sensitivity/specificity vs round...")
    n = len(experiments)
    if n == 0:
        return

    fig, axes = plt.subplots(1, n, figsize=(7 * n, 5), sharey=True)
    if n == 1:
        axes = [axes]

    has_any = False
    for ax, (key, exp_dir) in zip(axes, experiments.items()):
        cfg  = DIST_CONFIG[key]
        rows = read_csv(rounds_path(exp_dir))
        if rows is None:
            ax.set_title(cfg["label"]); continue

        rounds, sens_vals, spec_vals = [], [], []
        for row in rows:
            r  = _float(row.get("round"))
            s  = _float(row.get("test_sensitivity"))
            sp = _float(row.get("test_specificity"))
            if r is not None and s is not None and sp is not None:
                rounds.append(r); sens_vals.append(s); spec_vals.append(sp)

        if not rounds:
            ax.set_title(cfg["label"]); continue

        ax.plot(rounds, sens_vals, color="#E53935", linewidth=2, marker="o",
                markersize=5, label="Sensitivity (recall PNEUMONIE)")
        ax.plot(rounds, spec_vals, color="#1E88E5", linewidth=2, marker="s",
                markersize=5, linestyle="--", label="Specificity (recall NORMAL)")

        ax.set_xlabel("Rundă FL", fontsize=11)
        ax.set_ylabel("Valoare", fontsize=11)
        ax.set_title(cfg["label"], fontsize=12, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0.7, 1.01)
        has_any = True

    if not has_any:
        plt.close(fig); return

    fig.suptitle("Sensitivity vs. Specificity — Comparație Distribuții",
                 fontsize=13, fontweight="bold")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "sensitivity_specificity_vs_round.png")
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 6. Update norm vs. rundă
# ============================================================================

def plot_update_norm_vs_round(
    experiments: Dict[str, str], output_dir: str
) -> None:
    print("\n[6] Generare update_norm vs round...")
    fig, ax = plt.subplots(figsize=(10, 6))
    has_data = False

    for key, exp_dir in experiments.items():
        cfg  = DIST_CONFIG[key]
        rows = read_csv(rounds_path(exp_dir))
        if rows is None:
            continue
        rounds, values = [], []
        for row in rows:
            r = _float(row.get("round"))
            v = _float(row.get("update_norm"))
            if r is not None and v is not None and v > 0:
                rounds.append(r); values.append(v)
        if rounds:
            ax.plot(rounds, values, color=cfg["color"], label=cfg["label"],
                    linewidth=2, marker=cfg["marker"], markersize=5)
            has_data = True

    if not has_data:
        plt.close(fig); return

    ax.set_xlabel("Rundă FL", fontsize=12)
    ax.set_ylabel("||W_t − W_{t−1}||₂", fontsize=12)
    ax.set_title("Convergență Model Global — Update Norm vs. Rundă FL\n"
                 "(Comparație Distribuții)", fontsize=14)
    ax.legend(fontsize=10); ax.grid(True, alpha=0.3)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "update_norm_vs_round.png")
    fig.tight_layout(); fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 7. Test loss vs. rundă
# ============================================================================

def plot_test_loss_vs_round(
    experiments: Dict[str, str], output_dir: str
) -> None:
    print("\n[7] Generare test loss vs round...")
    fig, ax = plt.subplots(figsize=(10, 6))
    has_data = False

    for key, exp_dir in experiments.items():
        cfg  = DIST_CONFIG[key]
        rows = read_csv(rounds_path(exp_dir))
        if rows is None:
            continue
        rounds, values = [], []
        for row in rows:
            r = _float(row.get("round"))
            v = _float(row.get("test_loss"))
            if r is not None and v is not None:
                rounds.append(r); values.append(v)
        if rounds:
            ax.plot(rounds, values, color=cfg["color"], label=cfg["label"],
                    linewidth=2, marker=cfg["marker"], markersize=4)
            has_data = True

    if not has_data:
        plt.close(fig); return

    ax.set_xlabel("Rundă FL", fontsize=12)
    ax.set_ylabel("Test Loss (cross-entropy)", fontsize=12)
    ax.set_title("Test Loss vs. Rundă FL — Comparație Distribuții", fontsize=14)
    ax.legend(fontsize=10); ax.grid(True, alpha=0.3)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "test_loss_vs_round.png")
    fig.tight_layout(); fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 8. Per-nod metrică vs. rundă
# ============================================================================

def plot_per_node_metric(
    exp_dir: str,
    dist_key: str,
    output_dir: str,
    metric: str,
    ylabel: str,
    filename_suffix: str,
    num_nodes: int = 4,
) -> None:
    node_colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336"]
    fig, ax = plt.subplots(figsize=(10, 6))
    has_data = False

    for i in range(1, num_nodes + 1):
        rows = read_csv(str(
            Path(exp_dir) / "nodes" / f"node{i}_metrics_by_round.csv"
        ))
        if rows is None:
            continue
        rounds, values = [], []
        for row in rows:
            r = _float(row.get("round"))
            v = _float(row.get(metric))
            if r is not None and v is not None:
                rounds.append(r); values.append(v)
        if rounds:
            ax.plot(rounds, values,
                    color=node_colors[(i - 1) % len(node_colors)],
                    label=f"Node {i}", linewidth=2, marker="o", markersize=4)
            has_data = True

    if not has_data:
        plt.close(fig); return

    cfg = DIST_CONFIG[dist_key]
    ax.set_xlabel("Rundă FL", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{ylabel} per Nod — {cfg['label']}", fontsize=14)
    ax.legend(fontsize=11); ax.grid(True, alpha=0.3)
    ax.set_ylim(0.7, 1.01)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / f"{filename_suffix}_{dist_key}.png")
    fig.tight_layout(); fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grafice comparative pentru distribuții de date (experiments_tavi/)."
    )
    parser.add_argument("--iid",       type=str, default=None,
                        help="Directorul experimentului IID strict")
    parser.add_argument("--noniid",    type=str, default=None,
                        help="Directorul experimentului Non-IID extrem")
    parser.add_argument("--pneumonia", type=str, default=None,
                        help="Directorul experimentului concentrare pneumonie")
    parser.add_argument("--qty",       type=str, default=None,
                        help="Directorul experimentului dezechilibru cantitativ")
    parser.add_argument("--output-dir", type=str, default="results/tavi",
                        help="Directorul de output (default: results/tavi)")
    parser.add_argument("--num-nodes", type=int, default=4,
                        help="Numărul de noduri FL (default: 4)")

    args = parser.parse_args()

    experiments: Dict[str, str] = {}
    for key in ["iid", "noniid", "pneumonia", "qty"]:
        val = getattr(args, key)
        if val:
            experiments[key] = val

    if not experiments:
        print("EROARE: Niciun experiment specificat.")
        print("Folosește: --iid, --noniid, --pneumonia, --qty")
        sys.exit(1)

    print(f"\nExperimente disponibile:")
    for key, path in experiments.items():
        print(f"  {DIST_CONFIG[key]['label']:40s} → {path}")
    print(f"Output dir: {args.output_dir}")

    # 1. Tabel comparativ
    generate_comparison_table(experiments, args.output_dir)

    # 2. Metrici vs. rundă
    print("\n[2] Generare metrici vs round...")
    for metric, title, ylabel, ylim in [
        ("test_auc",  "AUC vs. Rundă FL — Comparație Distribuții",
         "AUC-ROC",   (0.7, 1.01)),
        ("test_f1",   "F1 vs. Rundă FL — Comparație Distribuții",
         "F1 Score",  (0.7, 1.01)),
        ("test_f2",   "F2 vs. Rundă FL — Comparație Distribuții",
         "F2 Score",  (0.7, 1.01)),
    ]:
        plot_metric_vs_round(
            experiments, metric,
            str(Path(args.output_dir) / f"{metric.replace('test_', '')}_vs_round.png"),
            title, ylabel, ylim,
        )

    # 3. ROC și PR curves
    plot_roc_pr_curves(experiments, args.output_dir)

    # 4. Confusion matrices
    plot_confusion_matrices(experiments, args.output_dir)

    # 5. Sensitivity / Specificity vs. rundă
    plot_sensitivity_specificity_vs_round(experiments, args.output_dir)

    # 6. Update norm vs. rundă
    plot_update_norm_vs_round(experiments, args.output_dir)

    # 7. Test loss vs. rundă
    plot_test_loss_vs_round(experiments, args.output_dir)

    # 8. Per-nod metrici
    print("\n[8] Generare per-nod metrici...")
    for key, exp_dir in experiments.items():
        plot_per_node_metric(exp_dir, key, args.output_dir,
                             "val_auc", "Val AUC (local)",
                             "per_node_auc", args.num_nodes)
        plot_per_node_metric(exp_dir, key, args.output_dir,
                             "val_f2",  "Val F2 (local)",
                             "per_node_f2",  args.num_nodes)

    print(f"\n✅ Toate graficele generate în {args.output_dir}/")


if __name__ == "__main__":
    main()
