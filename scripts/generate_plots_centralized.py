#!/usr/bin/env python3
"""
generate_plots_centralized.py — Grafice pentru antrenarea centralizată.

Produce, pentru fiecare fold și pentru best model:
  - ROC curves per fold (suprapuse)
  - PR curves per fold (suprapuse)
  - F2 bar chart per fold
  - Confusion matrices per fold
  - Tabel comparativ fold vs. best model (CSV + Markdown)

Utilizare:
  python scripts/generate_plots_centralized.py \\
      --centralized-dir centralized_dragos \\
      --output-dir      centralized_dragos/results \\
      --fl-best-model   experiments/fl_fedavg_efficientnet_b0_run15

  # Fără comparație FL (doar centralizat):
  python scripts/generate_plots_centralized.py \\
      --centralized-dir centralized_dragos \\
      --output-dir      centralized_dragos/results
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
# Culori per fold
# ============================================================================

FOLD_COLORS = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336"]
BEST_COLOR  = "#E53935"   # roșu pentru best model
FL_COLOR    = "#00BCD4"   # cyan pentru FL best


# ============================================================================
# Utilitare
# ============================================================================

def _warn(msg: str) -> None:
    print(f"  WARN: {msg}", file=sys.stderr)


def read_predictions(path: str) -> Optional[Tuple[List[int], List[float]]]:
    """Citește y_true și y_score dintr-un predictions_test.csv."""
    p = Path(path)
    if not p.exists():
        _warn(f"Fișier lipsă: {path}")
        return None
    try:
        y_true, y_score = [], []
        with open(p, "r") as f:
            for row in csv.DictReader(f):
                y_true.append(int(row["y_true"]))
                y_score.append(float(row["y_score"]))
        return y_true, y_score
    except Exception as e:
        _warn(f"Eroare citire {path}: {e}")
        return None


def compute_metrics(y_true: List[int], y_score: List[float]) -> Dict:
    """Calculează toate metricile dintr-o dată."""
    from sklearn.metrics import (
        roc_auc_score, f1_score, fbeta_score, average_precision_score,
        confusion_matrix, precision_score, recall_score, accuracy_score,
    )
    y_pred = [1 if s >= 0.5 else 0 for s in y_score]
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    return {
        "auc":         round(roc_auc_score(y_true, y_score), 4),
        "f1":          round(f1_score(y_true, y_pred, zero_division=0), 4),
        "f2":          round(fbeta_score(y_true, y_pred, beta=2, zero_division=0), 4),
        "pr_auc":      round(average_precision_score(y_true, y_score), 4),
        "accuracy":    round(accuracy_score(y_true, y_pred), 4),
        "precision":   round(precision_score(y_true, y_pred, zero_division=0), 4),
        "sensitivity": round(tp / (tp + fn) if (tp + fn) > 0 else 0.0, 4),
        "specificity": round(tn / (tn + fp) if (tn + fp) > 0 else 0.0, 4),
        "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn),
        "y_pred": y_pred,
    }


# ============================================================================
# Detectare fișiere fold
# ============================================================================

def discover_folds(centralized_dir: str) -> List[Dict]:
    """
    Găsește toate fișierele predictions_test_*fold*.csv din centralized_dir.
    Returnează lista sortată după fold index.
    """
    d = Path(centralized_dir)
    fold_files = sorted(d.glob("predictions_test_*fold*.csv"))

    folds = []
    for i, f in enumerate(fold_files):
        # Extrage val F1 din numele fișierului (ex. _f10.9918.pt)
        name = f.stem  # predictions_test_efficientnet_b0_fold0_f10.9918.pt
        val_f1 = None
        import re
        m = re.search(r'_f1(\d+\.\d+)', name)
        if m:
            val_f1 = float(m.group(1))
        folds.append({
            "label":   f"Fold {i}",
            "path":    str(f),
            "val_f1":  val_f1,
            "color":   FOLD_COLORS[i % len(FOLD_COLORS)],
        })
    return folds


def get_best_model_predictions(centralized_dir: str) -> Optional[str]:
    """Returnează calea predictions_test.csv (best model)."""
    p = Path(centralized_dir) / "predictions_test.csv"
    return str(p) if p.exists() else None


# ============================================================================
# 1. ROC Curves per fold
# ============================================================================

def plot_roc_per_fold(
    folds: List[Dict],
    best_path: Optional[str],
    output_dir: str,
) -> None:
    print("\n[1] ROC curves per fold...")
    from sklearn.metrics import roc_curve, auc

    fig, ax = plt.subplots(figsize=(8, 7))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random")

    has_data = False
    for fold in folds:
        data = read_predictions(fold["path"])
        if data is None:
            continue
        y_true, y_score = data
        fpr, tpr, _ = roc_curve(y_true, y_score)
        roc_auc = auc(fpr, tpr)
        ax.plot(fpr, tpr, color=fold["color"], linewidth=2,
                label=f"{fold['label']} (AUC={roc_auc:.3f})")
        has_data = True

    if best_path:
        data = read_predictions(best_path)
        if data:
            y_true, y_score = data
            fpr, tpr, _ = roc_curve(y_true, y_score)
            roc_auc = auc(fpr, tpr)
            ax.plot(fpr, tpr, color=BEST_COLOR, linewidth=2.5, linestyle="--",
                    label=f"Best Model (AUC={roc_auc:.3f})")

    if not has_data:
        plt.close(fig)
        _warn("Fără date pentru ROC per fold")
        return

    ax.set_xlabel("False Positive Rate", fontsize=12)
    ax.set_ylabel("True Positive Rate", fontsize=12)
    ax.set_title("ROC Curves per Fold — Centralizat (EfficientNet-B0)", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "roc_curves_per_fold.png")
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 2. PR Curves per fold
# ============================================================================

def plot_pr_per_fold(
    folds: List[Dict],
    best_path: Optional[str],
    output_dir: str,
) -> None:
    print("\n[2] PR curves per fold...")
    from sklearn.metrics import precision_recall_curve, auc

    fig, ax = plt.subplots(figsize=(8, 7))
    has_data = False

    for fold in folds:
        data = read_predictions(fold["path"])
        if data is None:
            continue
        y_true, y_score = data
        precision, recall, _ = precision_recall_curve(y_true, y_score)
        pr_auc = auc(recall, precision)
        ax.plot(recall, precision, color=fold["color"], linewidth=2,
                label=f"{fold['label']} (PR-AUC={pr_auc:.3f})")
        has_data = True

    if best_path:
        data = read_predictions(best_path)
        if data:
            y_true, y_score = data
            precision, recall, _ = precision_recall_curve(y_true, y_score)
            pr_auc = auc(recall, precision)
            ax.plot(recall, precision, color=BEST_COLOR, linewidth=2.5, linestyle="--",
                    label=f"Best Model (PR-AUC={pr_auc:.3f})")

    if not has_data:
        plt.close(fig)
        return

    ax.set_xlabel("Recall", fontsize=12)
    ax.set_ylabel("Precision", fontsize=12)
    ax.set_title("Precision-Recall Curves per Fold — Centralizat", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "pr_curves_per_fold.png")
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 3. F2 (și alte metrici) bar chart per fold
# ============================================================================

def plot_metrics_per_fold(
    folds: List[Dict],
    best_path: Optional[str],
    output_dir: str,
) -> None:
    print("\n[3] Metrici per fold (bar chart)...")

    metrics_data = []
    for fold in folds:
        data = read_predictions(fold["path"])
        if data is None:
            continue
        y_true, y_score = data
        m = compute_metrics(y_true, y_score)
        metrics_data.append({"label": fold["label"], "color": fold["color"], **m})

    if best_path:
        data = read_predictions(best_path)
        if data:
            y_true, y_score = data
            m = compute_metrics(y_true, y_score)
            metrics_data.append({"label": "Best Model", "color": BEST_COLOR, **m})

    if not metrics_data:
        _warn("Fără date pentru metrici per fold")
        return

    # Grafic cu 4 metrici cheie
    metric_keys  = ["f2",    "auc",   "sensitivity", "specificity"]
    metric_labels = ["F2",   "AUC",   "Sensitivity",  "Specificity"]

    fig, axes = plt.subplots(1, 4, figsize=(16, 5))
    x_labels = [d["label"] for d in metrics_data]
    colors   = [d["color"] for d in metrics_data]
    x_pos    = np.arange(len(metrics_data))

    for ax, key, label in zip(axes, metric_keys, metric_labels):
        values = [d[key] for d in metrics_data]
        bars = ax.bar(x_pos, values, color=colors, width=0.6, edgecolor="white")

        # Valoare deasupra fiecărui bar
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.002,
                    f"{val:.4f}", ha="center", va="bottom", fontsize=8)

        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels, rotation=25, ha="right", fontsize=9)
        ax.set_ylim(0.85, 1.02)
        ax.grid(True, alpha=0.3, axis="y")
        ax.set_ylabel("Valoare", fontsize=10)

    fig.suptitle("Metrici per Fold — Centralizat (EfficientNet-B0)",
                 fontsize=13, fontweight="bold")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "metrics_per_fold.png")
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 4. Confusion matrices per fold
# ============================================================================

def plot_confusion_matrices_per_fold(
    folds: List[Dict],
    best_path: Optional[str],
    output_dir: str,
) -> None:
    print("\n[4] Confusion matrices per fold...")

    entries = []
    for fold in folds:
        data = read_predictions(fold["path"])
        if data is None:
            continue
        y_true, y_score = data
        m = compute_metrics(y_true, y_score)
        entries.append({"label": fold["label"], **m})

    if best_path:
        data = read_predictions(best_path)
        if data:
            y_true, y_score = data
            m = compute_metrics(y_true, y_score)
            entries.append({"label": "Best Model", **m})

    if not entries:
        return

    n   = len(entries)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5))
    if n == 1:
        axes = [axes]

    for ax, entry in zip(axes, entries):
        matrix = np.array([
            [entry["TN"], entry["FP"]],
            [entry["FN"], entry["TP"]],
        ])
        ax.imshow(matrix, interpolation="nearest", cmap="Blues")
        ax.set_title(entry["label"], fontsize=11, fontweight="bold")
        ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
        ax.set_xticklabels(["NORMAL", "PNEUMONIA"], fontsize=9)
        ax.set_yticklabels(["NORMAL", "PNEUMONIA"], fontsize=9)

        total = matrix.sum()
        for i in range(2):
            for j in range(2):
                val = matrix[i, j]
                pct = val / total * 100 if total > 0 else 0
                ax.text(j, i, f"{val}\n({pct:.1f}%)",
                        ha="center", va="center", fontsize=10,
                        color="white" if val > matrix.max() * 0.6 else "black")

        ax.set_xlabel(
            f"Acc={entry['accuracy']:.3f} | Sens={entry['sensitivity']:.3f} | "
            f"Spec={entry['specificity']:.3f}",
            fontsize=9
        )

    fig.suptitle("Confusion Matrices per Fold — Centralizat", fontsize=13,
                 fontweight="bold")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = str(out / "confusion_matrices_per_fold.png")
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {p}")


# ============================================================================
# 5. Tabel comparativ fold vs. best FL model
# ============================================================================

def generate_comparison_table(
    folds: List[Dict],
    best_path: Optional[str],
    fl_best_path: Optional[str],
    output_dir: str,
) -> None:
    print("\n[5] Tabel comparativ fold vs. best model...")

    rows = []

    # Folduri centralizate
    for fold in folds:
        data = read_predictions(fold["path"])
        if data is None:
            rows.append({"Model": fold["label"], "Val F1": fold.get("val_f1", "N/A"),
                         "AUC": "N/A", "F1": "N/A", "F2": "N/A",
                         "Sensitivity": "N/A", "Specificity": "N/A",
                         "PR-AUC": "N/A", "FN": "N/A"})
            continue
        y_true, y_score = data
        m = compute_metrics(y_true, y_score)
        rows.append({
            "Model":       fold["label"],
            "Val F1":      fold.get("val_f1", "-"),
            "AUC":         m["auc"],
            "F1":          m["f1"],
            "F2":          m["f2"],
            "Sensitivity": m["sensitivity"],
            "Specificity": m["specificity"],
            "PR-AUC":      m["pr_auc"],
            "FN":          m["FN"],
        })

    # Best model centralizat
    if best_path:
        data = read_predictions(best_path)
        if data:
            y_true, y_score = data
            m = compute_metrics(y_true, y_score)
            rows.append({
                "Model": "Centralizat Best",
                "Val F1": "-",
                "AUC":         m["auc"],
                "F1":          m["f1"],
                "F2":          m["f2"],
                "Sensitivity": m["sensitivity"],
                "Specificity": m["specificity"],
                "PR-AUC":      m["pr_auc"],
                "FN":          m["FN"],
            })

    # Best FL model
    if fl_best_path:
        fl_pred = Path(fl_best_path) / "central" / "best_model" / "predictions_test.csv"
        data = read_predictions(str(fl_pred))
        if data:
            y_true, y_score = data
            m = compute_metrics(y_true, y_score)
            fl_name = Path(fl_best_path).name
            rows.append({
                "Model": f"FL Best ({fl_name})",
                "Val F1": "-",
                "AUC":         m["auc"],
                "F1":          m["f1"],
                "F2":          m["f2"],
                "Sensitivity": m["sensitivity"],
                "Specificity": m["specificity"],
                "PR-AUC":      m["pr_auc"],
                "FN":          m["FN"],
            })
        else:
            _warn(f"predictions_test.csv nu există în {fl_pred}")

    if not rows:
        _warn("Nicio dată pentru tabel comparativ")
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    fields = ["Model", "Val F1", "AUC", "F1", "F2",
              "Sensitivity", "Specificity", "PR-AUC", "FN"]

    # CSV
    csv_path = out / "comparison_table_folds.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ {csv_path}")

    # Markdown
    md_path = out / "comparison_table_folds.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Tabel Comparativ — Centralizat per Fold vs. Best Model\n\n")
        f.write("| " + " | ".join(fields) + " |\n")
        f.write("| " + " | ".join(["---"] * len(fields)) + " |\n")
        for row in rows:
            f.write("| " + " | ".join(str(row[k]) for k in fields) + " |\n")
    print(f"  ✓ {md_path}")


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grafice pentru antrenarea centralizată (per fold)."
    )
    parser.add_argument("--centralized-dir", type=str, required=True,
                        help="Directorul cu fișierele centralizate (ex. centralized_dragos)")
    parser.add_argument("--output-dir", type=str, default="centralized_dragos/results",
                        help="Directorul de output (default: centralized_dragos/results)")
    parser.add_argument("--fl-best-model", type=str, default=None,
                        help="Directorul unui experiment FL pentru comparație "
                             "(ex. experiments/fl_fedavg_efficientnet_b0_run15)")

    args = parser.parse_args()

    # Descoperă folduri
    folds = discover_folds(args.centralized_dir)
    if not folds:
        print(f"EROARE: Niciun fișier predictions_test_*fold*.csv în {args.centralized_dir}")
        sys.exit(1)

    print(f"\nFolduri găsite: {len(folds)}")
    for f in folds:
        print(f"  {f['label']}: {f['path']} (val F1={f['val_f1']})")

    best_path = get_best_model_predictions(args.centralized_dir)
    if best_path:
        print(f"Best model: {best_path}")
    else:
        print("WARN: predictions_test.csv (best model) nu a fost găsit")

    if args.fl_best_model:
        print(f"FL comparație: {args.fl_best_model}")

    print(f"Output dir: {args.output_dir}")

    # Generare grafice
    plot_roc_per_fold(folds, best_path, args.output_dir)
    plot_pr_per_fold(folds, best_path, args.output_dir)
    plot_metrics_per_fold(folds, best_path, args.output_dir)
    plot_confusion_matrices_per_fold(folds, best_path, args.output_dir)
    generate_comparison_table(folds, best_path, args.fl_best_model, args.output_dir)

    print(f"\n✅ Toate graficele generate în {args.output_dir}/")


if __name__ == "__main__":
    main()
