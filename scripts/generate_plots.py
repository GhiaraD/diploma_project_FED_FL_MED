#!/usr/bin/env python3
"""
generate_plots.py — Generare grafice și tabele comparative pentru disertație.

Citește fișierele de metrici din directoarele de experiment și produce:
  results/
    comparison_table.csv
    comparison_table.md
    auc_vs_round.png
    f1_vs_round.png
    roc_curves.png
    pr_curves.png
    confusion_matrices.png
    per_node_auc_fedavg.png
    per_node_auc_fedavgm.png
    per_node_auc_fedprox.png

Utilizare:
  python scripts/generate_plots.py \\
      --centralized experiments/centralized_effb0_run01 \\
      --fedavg experiments/fl_fedavg_effb0_run01 \\
      --fedavgm experiments/fl_fedavgm_effb0_run01 \\
      --fedprox experiments/fl_fedprox_effb0_run01 \\
      --output-dir results
"""
import argparse
import csv
import json
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Matplotlib în mod non-interactiv (fără display)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

warnings.filterwarnings("ignore")


# ============================================================================
# Utilitare de citire
# ============================================================================

def _warn_missing(path: str) -> None:
    print(f"  WARN: Fișier lipsă — {path}", file=sys.stderr)


def read_csv(path: str) -> Optional[List[Dict]]:
    """Citește un CSV și returnează lista de dict-uri, sau None dacă lipsește."""
    p = Path(path)
    if not p.exists():
        _warn_missing(path)
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"  WARN: Eroare la citirea {path}: {e}", file=sys.stderr)
        return None


def read_json(path: str) -> Optional[dict]:
    """Citește un JSON și returnează dict-ul, sau None dacă lipsește."""
    p = Path(path)
    if not p.exists():
        _warn_missing(path)
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  WARN: Eroare la citirea {path}: {e}", file=sys.stderr)
        return None


def _float(val) -> Optional[float]:
    """Convertește la float, returnează None dacă e gol sau invalid."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ============================================================================
# Calcul metrici din predictions_test.csv
# ============================================================================

def compute_metrics_from_predictions(
    predictions_path: str,
    threshold: float = 0.5,
) -> Optional[Dict]:
    """
    Calculează AUC, F1, Sensitivity, Specificity, PR-AUC din predictions_test.csv.

    Returns:
        Dict cu metrici sau None dacă fișierul lipsește.
    """
    rows = read_csv(predictions_path)
    if rows is None:
        return None

    try:
        from sklearn.metrics import (
            roc_auc_score, f1_score, average_precision_score,
            confusion_matrix
        )

        y_true = [int(r["y_true"]) for r in rows]
        y_score = [float(r["y_score"]) for r in rows]
        y_pred = [1 if s >= threshold else 0 for s in y_score]

        auc = roc_auc_score(y_true, y_score)
        f1 = f1_score(y_true, y_pred)
        pr_auc = average_precision_score(y_true, y_score)

        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel()
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

        return {
            "auc": round(auc, 4),
            "f1": round(f1, 4),
            "sensitivity": round(sensitivity, 4),
            "specificity": round(specificity, 4),
            "pr_auc": round(pr_auc, 4),
            "y_true": y_true,
            "y_score": y_score,
        }
    except Exception as e:
        print(f"  WARN: Eroare la calculul metricilor din {predictions_path}: {e}", file=sys.stderr)
        return None


# ============================================================================
# 1. Tabel comparativ
# ============================================================================

def generate_comparison_table(
    experiments: Dict[str, str],
    output_dir: str,
) -> None:
    """
    Citește predictions_test.csv din best_model/ al fiecărui experiment.
    Calculează AUC, F1, Sensitivity, Specificity, PR-AUC la threshold 0.5.
    Scrie results/comparison_table.csv și results/comparison_table.md.
    """
    print("\n[1] Generare tabel comparativ...")

    rows = []
    for name, exp_dir in experiments.items():
        # Centralizat: artifacts/best_model/; FL: central/best_model/
        if name == "centralized":
            pred_path = str(Path(exp_dir) / "artifacts" / "best_model" / "predictions_test.csv")
        else:
            pred_path = str(Path(exp_dir) / "central" / "best_model" / "predictions_test.csv")

        metrics = compute_metrics_from_predictions(pred_path)
        if metrics is None:
            print(f"  WARN: Nu s-au putut calcula metricile pentru {name}")
            rows.append({
                "model": name, "AUC": "N/A", "F1": "N/A",
                "Sensitivity": "N/A", "Specificity": "N/A", "PR_AUC": "N/A",
            })
        else:
            rows.append({
                "model": name,
                "AUC": metrics["auc"],
                "F1": metrics["f1"],
                "Sensitivity": metrics["sensitivity"],
                "Specificity": metrics["specificity"],
                "PR_AUC": metrics["pr_auc"],
            })

    if not rows:
        print("  WARN: Niciun experiment disponibil pentru tabel")
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # CSV
    csv_path = out / "comparison_table.csv"
    fieldnames = ["model", "AUC", "F1", "Sensitivity", "Specificity", "PR_AUC"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ {csv_path}")

    # Markdown
    md_path = out / "comparison_table.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Tabel Comparativ — Rezultate pe test_global\n\n")
        f.write("| Model | AUC | F1 | Sensitivity | Specificity | PR-AUC |\n")
        f.write("|-------|-----|-----|-------------|-------------|--------|\n")
        for row in rows:
            f.write(
                f"| {row['model']} | {row['AUC']} | {row['F1']} | "
                f"{row['Sensitivity']} | {row['Specificity']} | {row['PR_AUC']} |\n"
            )
    print(f"  ✓ {md_path}")


# ============================================================================
# 2. Metrică vs. rundă (AUC și F1)
# ============================================================================

def plot_metric_vs_round(
    fl_experiments: Dict[str, str],
    centralized_value: Optional[float],
    metric: str,
    output_path: str,
    title: str = None,
    ylabel: str = None,
) -> None:
    """
    Trasează metrica vs. rundă pentru strategiile FL + linie orizontală centralizat.

    Args:
        fl_experiments: {"fedavg": path, "fedavgm": path, "fedprox": path}
        centralized_value: valoarea metricii pentru modelul centralizat
        metric: coloana din metrics_by_round.csv (ex. "test_auc")
        output_path: calea fișierului PNG de output
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    colors = {"fedavg": "#2196F3", "fedavgm": "#4CAF50", "fedprox": "#FF9800"}
    labels = {"fedavg": "FedAvg", "fedavgm": "FedAvgM", "fedprox": "FedProx"}

    has_data = False
    for strategy, exp_dir in fl_experiments.items():
        csv_path = str(Path(exp_dir) / "central" / "metrics_by_round.csv")
        rows = read_csv(csv_path)
        if rows is None:
            continue

        rounds = []
        values = []
        for row in rows:
            r = _float(row.get("round"))
            v = _float(row.get(metric))
            if r is not None and v is not None:
                rounds.append(r)
                values.append(v)

        if rounds:
            ax.plot(
                rounds, values,
                color=colors.get(strategy, "gray"),
                label=labels.get(strategy, strategy),
                linewidth=2,
                marker="o",
                markersize=4,
            )
            has_data = True

    if centralized_value is not None:
        ax.axhline(
            y=centralized_value,
            color="#F44336",
            linestyle="--",
            linewidth=2,
            label=f"Centralizat ({centralized_value:.4f})",
        )
        has_data = True

    if not has_data:
        plt.close(fig)
        print(f"  WARN: Nu există date pentru {metric} vs round")
        return

    ax.set_xlabel("Rundă FL", fontsize=12)
    ax.set_ylabel(ylabel or metric, fontsize=12)
    ax.set_title(title or f"{metric} vs. Rundă FL", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {output_path}")


# ============================================================================
# 3. ROC și PR curves
# ============================================================================

def plot_roc_pr_curves(
    experiments: Dict[str, str],
    output_dir: str,
) -> None:
    """
    Trasează ROC curves și PR curves suprapuse pentru toate experimentele.
    """
    print("\n[3] Generare ROC și PR curves...")

    from sklearn.metrics import roc_curve, precision_recall_curve, auc

    colors = {
        "centralized": "#F44336",
        "fedavg": "#2196F3",
        "fedavgm": "#4CAF50",
        "fedprox": "#FF9800",
    }
    display_names = {
        "centralized": "Centralizat",
        "fedavg": "FedAvg",
        "fedavgm": "FedAvgM",
        "fedprox": "FedProx",
    }

    fig_roc, ax_roc = plt.subplots(figsize=(8, 7))
    fig_pr, ax_pr = plt.subplots(figsize=(8, 7))

    has_roc = False
    has_pr = False

    for name, exp_dir in experiments.items():
        if name == "centralized":
            pred_path = str(Path(exp_dir) / "artifacts" / "best_model" / "predictions_test.csv")
        else:
            pred_path = str(Path(exp_dir) / "central" / "best_model" / "predictions_test.csv")

        rows = read_csv(pred_path)
        if rows is None:
            continue

        try:
            y_true = [int(r["y_true"]) for r in rows]
            y_score = [float(r["y_score"]) for r in rows]

            # ROC
            fpr, tpr, _ = roc_curve(y_true, y_score)
            roc_auc = auc(fpr, tpr)
            ax_roc.plot(
                fpr, tpr,
                color=colors.get(name, "gray"),
                label=f"{display_names.get(name, name)} (AUC={roc_auc:.3f})",
                linewidth=2,
            )
            has_roc = True

            # PR
            precision, recall, _ = precision_recall_curve(y_true, y_score)
            pr_auc = auc(recall, precision)
            ax_pr.plot(
                recall, precision,
                color=colors.get(name, "gray"),
                label=f"{display_names.get(name, name)} (PR-AUC={pr_auc:.3f})",
                linewidth=2,
            )
            has_pr = True

        except Exception as e:
            print(f"  WARN: Eroare la {name}: {e}", file=sys.stderr)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if has_roc:
        ax_roc.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random")
        ax_roc.set_xlabel("False Positive Rate", fontsize=12)
        ax_roc.set_ylabel("True Positive Rate", fontsize=12)
        ax_roc.set_title("ROC Curves — Comparație Modele", fontsize=14)
        ax_roc.legend(fontsize=10)
        ax_roc.grid(True, alpha=0.3)
        roc_path = str(out / "roc_curves.png")
        fig_roc.tight_layout()
        fig_roc.savefig(roc_path, dpi=150, bbox_inches="tight")
        print(f"  ✓ {roc_path}")
    plt.close(fig_roc)

    if has_pr:
        ax_pr.set_xlabel("Recall", fontsize=12)
        ax_pr.set_ylabel("Precision", fontsize=12)
        ax_pr.set_title("Precision-Recall Curves — Comparație Modele", fontsize=14)
        ax_pr.legend(fontsize=10)
        ax_pr.grid(True, alpha=0.3)
        pr_path = str(out / "pr_curves.png")
        fig_pr.tight_layout()
        fig_pr.savefig(pr_path, dpi=150, bbox_inches="tight")
        print(f"  ✓ {pr_path}")
    plt.close(fig_pr)


# ============================================================================
# 4. Confusion matrices
# ============================================================================

def plot_confusion_matrices(
    experiments: Dict[str, str],
    output_dir: str,
) -> None:
    """
    Trasează un grid de confusion matrices pentru toate experimentele.
    """
    print("\n[4] Generare confusion matrices...")

    display_names = {
        "centralized": "Centralizat",
        "fedavg": "FedAvg",
        "fedavgm": "FedAvgM",
        "fedprox": "FedProx",
    }

    cms = {}
    for name, exp_dir in experiments.items():
        if name == "centralized":
            cm_path = str(Path(exp_dir) / "artifacts" / "best_model" / "confusion_matrix.json")
        else:
            cm_path = str(Path(exp_dir) / "central" / "best_model" / "confusion_matrix.json")

        cm_data = read_json(cm_path)
        if cm_data:
            cms[name] = cm_data

    if not cms:
        print("  WARN: Nicio confusion matrix disponibilă")
        return

    n = len(cms)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 5))
    if n == 1:
        axes = [axes]

    import matplotlib.colors as mcolors

    for ax, (name, cm_data) in zip(axes, cms.items()):
        tp = cm_data.get("TP", 0)
        fp = cm_data.get("FP", 0)
        tn = cm_data.get("TN", 0)
        fn = cm_data.get("FN", 0)

        matrix = np.array([[tn, fp], [fn, tp]])
        im = ax.imshow(matrix, interpolation="nearest", cmap="Blues")

        ax.set_title(display_names.get(name, name), fontsize=13, fontweight="bold")
        ax.set_xlabel("Predicție", fontsize=11)
        ax.set_ylabel("Real", fontsize=11)
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["NORMAL", "PNEUMONIA"], fontsize=10)
        ax.set_yticklabels(["NORMAL", "PNEUMONIA"], fontsize=10)

        total = tp + fp + tn + fn
        for i in range(2):
            for j in range(2):
                val = matrix[i, j]
                pct = val / total * 100 if total > 0 else 0
                ax.text(
                    j, i, f"{val}\n({pct:.1f}%)",
                    ha="center", va="center",
                    fontsize=11,
                    color="white" if val > matrix.max() * 0.6 else "black",
                )

        acc = cm_data.get("accuracy", 0)
        sens = cm_data.get("sensitivity", 0)
        spec = cm_data.get("specificity", 0)
        ax.set_xlabel(
            f"Predicție\nAcc={acc:.3f} | Sens={sens:.3f} | Spec={spec:.3f}",
            fontsize=10
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cm_path = str(out / "confusion_matrices.png")
    fig.suptitle("Confusion Matrices — Comparație Modele", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(cm_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {cm_path}")


# ============================================================================
# 5. Per-nod AUC vs. rundă
# ============================================================================

def plot_per_node_auc(
    fl_experiment_path: str,
    strategy_name: str,
    output_dir: str,
    num_nodes: int = 5,
) -> None:
    """
    Trasează val_auc vs. rundă pentru fiecare nod FL.
    """
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336"]
    fig, ax = plt.subplots(figsize=(10, 6))

    has_data = False
    for i in range(1, num_nodes + 1):
        csv_path = str(
            Path(fl_experiment_path) / "nodes" / f"node{i}_metrics_by_round.csv"
        )
        rows = read_csv(csv_path)
        if rows is None:
            continue

        rounds = []
        values = []
        for row in rows:
            r = _float(row.get("round"))
            v = _float(row.get("val_auc"))
            if r is not None and v is not None:
                rounds.append(r)
                values.append(v)

        if rounds:
            ax.plot(
                rounds, values,
                color=colors[(i - 1) % len(colors)],
                label=f"Node {i}",
                linewidth=2,
                marker="o",
                markersize=4,
            )
            has_data = True

    if not has_data:
        plt.close(fig)
        print(f"  WARN: Nu există date per-nod pentru {strategy_name}")
        return

    ax.set_xlabel("Rundă FL", fontsize=12)
    ax.set_ylabel("Val AUC (local)", fontsize=12)
    ax.set_title(f"AUC per Nod — {strategy_name.upper()}", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = str(out / f"per_node_auc_{strategy_name.lower()}.png")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {output_path}")


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generare grafice și tabele comparative pentru disertație Fed-Med-FL."
    )
    parser.add_argument("--centralized", type=str, default=None,
                        help="Directorul experimentului centralizat")
    parser.add_argument("--fedavg", type=str, default=None,
                        help="Directorul experimentului FL FedAvg")
    parser.add_argument("--fedavgm", type=str, default=None,
                        help="Directorul experimentului FL FedAvgM")
    parser.add_argument("--fedprox", type=str, default=None,
                        help="Directorul experimentului FL FedProx")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directorul de output pentru grafice (default: results)")
    parser.add_argument("--num-nodes", type=int, default=5,
                        help="Numărul de noduri FL (default: 5)")

    args = parser.parse_args()

    # Construiește dicționarele de experimente
    all_experiments: Dict[str, str] = {}
    fl_experiments: Dict[str, str] = {}

    if args.centralized:
        all_experiments["centralized"] = args.centralized
    if args.fedavg:
        all_experiments["fedavg"] = args.fedavg
        fl_experiments["fedavg"] = args.fedavg
    if args.fedavgm:
        all_experiments["fedavgm"] = args.fedavgm
        fl_experiments["fedavgm"] = args.fedavgm
    if args.fedprox:
        all_experiments["fedprox"] = args.fedprox
        fl_experiments["fedprox"] = args.fedprox

    if not all_experiments:
        print("EROARE: Niciun experiment specificat. Folosește --centralized, --fedavg, etc.")
        sys.exit(1)

    print(f"\nExperimente disponibile: {list(all_experiments.keys())}")
    print(f"Output dir: {args.output_dir}")

    # 1. Tabel comparativ
    generate_comparison_table(all_experiments, args.output_dir)

    # 2. AUC vs round
    if fl_experiments:
        print("\n[2] Generare AUC vs round și F1 vs round...")

        # Valoarea centralizată pentru linia orizontală
        centralized_auc = None
        centralized_f1 = None
        if args.centralized:
            pred_path = str(
                Path(args.centralized) / "artifacts" / "best_model" / "predictions_test.csv"
            )
            m = compute_metrics_from_predictions(pred_path)
            if m:
                centralized_auc = m["auc"]
                centralized_f1 = m["f1"]

        plot_metric_vs_round(
            fl_experiments=fl_experiments,
            centralized_value=centralized_auc,
            metric="test_auc",
            output_path=str(Path(args.output_dir) / "auc_vs_round.png"),
            title="AUC vs. Rundă FL",
            ylabel="AUC-ROC",
        )

        plot_metric_vs_round(
            fl_experiments=fl_experiments,
            centralized_value=centralized_f1,
            metric="test_f1",
            output_path=str(Path(args.output_dir) / "f1_vs_round.png"),
            title="F1 vs. Rundă FL",
            ylabel="F1 Score",
        )

    # 3. ROC și PR curves
    plot_roc_pr_curves(all_experiments, args.output_dir)

    # 4. Confusion matrices
    plot_confusion_matrices(all_experiments, args.output_dir)

    # 5. Per-nod AUC
    if fl_experiments:
        print("\n[5] Generare per-nod AUC...")
        for strategy, exp_dir in fl_experiments.items():
            plot_per_node_auc(
                fl_experiment_path=exp_dir,
                strategy_name=strategy,
                output_dir=args.output_dir,
                num_nodes=args.num_nodes,
            )

    print(f"\n✅ Toate graficele generate în {args.output_dir}/")


if __name__ == "__main__":
    main()
