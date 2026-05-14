"""
ExperimentLogger — centralizează logica de scriere a fișierelor de metrici
pentru experimentele Fed-Med-FL (centralizat și federated learning).

Folosit de:
  - FedMedStrategy (flower_strategy.py) — metrici per rundă + per nod
  - FedMedClient (flower_client.py) — metrici per nod (opțional)
  - Notebook centralizat — metrici per epocă
"""
import csv
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, asdict, fields
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import torch
import torch.nn as nn


# ============================================================================
# Dataclasses pentru metrici
# ============================================================================

@dataclass
class EpochMetrics:
    """Metrici per epocă pentru antrenarea centralizată."""
    epoch: int
    train_loss: float
    val_loss: float
    val_auc: float
    val_f1: float
    val_sensitivity: float
    val_specificity: float
    val_pr_auc: float
    lr: float
    time_epoch_sec: float


@dataclass
class RoundMetrics:
    """Metrici per rundă FL la nivel central (include evaluare pe test_global)."""
    round: int
    num_clients: int
    aggregation_method: str
    time_round_sec: float
    update_norm: float
    test_auc: Optional[float]        # None dacă evaluarea a eșuat
    test_f1: Optional[float]
    test_sensitivity: Optional[float]
    test_specificity: Optional[float]
    test_pr_auc: Optional[float]


@dataclass
class NodeRoundMetrics:
    """Metrici per rundă per nod FL."""
    round: int
    node_id: str
    n_train_samples_used: int
    val_auc: float
    val_f1: float
    val_sensitivity: float
    val_specificity: float
    val_pr_auc: float
    local_train_time_sec: float
    delta_norm: float


# ============================================================================
# Utilitare interne
# ============================================================================

def _get_git_commit_hash() -> str:
    """Returnează hash-ul commit-ului curent sau 'unknown' dacă git nu e disponibil."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


def _compute_model_hash_sha256(model: nn.Module) -> str:
    """Calculează hash-ul SHA-256 al state_dict-ului unui model PyTorch."""
    hasher = hashlib.sha256()
    state_dict = model.state_dict()
    # Sortăm cheile pentru determinism
    for key in sorted(state_dict.keys()):
        tensor = state_dict[key]
        hasher.update(key.encode("utf-8"))
        hasher.update(tensor.cpu().numpy().tobytes())
    return hasher.hexdigest()


def _compute_weights_hash_sha256(parameters: List[np.ndarray]) -> str:
    """Calculează hash-ul SHA-256 al unei liste de parametri numpy."""
    hasher = hashlib.sha256()
    for param in parameters:
        hasher.update(param.tobytes())
    return hasher.hexdigest()


def _append_csv(path: Path, row: dict, fieldnames: List[str]) -> None:
    """
    Adaugă un rând într-un fișier CSV.
    Dacă fișierul nu există, îl creează cu header.
    Valorile None sunt scrise ca string gol.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        # Convertim None → "" pentru CSV
        clean_row = {k: ("" if v is None else v) for k, v in row.items()}
        writer.writerow(clean_row)


# ============================================================================
# ExperimentLogger
# ============================================================================

class ExperimentLogger:
    """
    Centralizează toată logica de scriere a fișierelor de metrici și artefacte
    pentru un experiment Fed-Med-FL.

    Structura de directoare produsă:

    Centralizat:
        {run_dir}/
            run_config.json
            metrics_by_epoch.csv
            artifacts/best_model/
                weights.pt
                model_hash.txt
                predictions_test.csv
                confusion_matrix.json

    FL:
        {run_dir}/
            run_config.json
            central/
                metrics_by_round.csv
                global_models/
                    round_000_weights.pt
                    ...
                best_model/
                    weights.pt
                    model_hash.txt
                    predictions_test.csv
                    confusion_matrix.json
            nodes/
                node1_metrics_by_round.csv
                ...
    """

    def __init__(self, run_dir: str):
        """
        Args:
            run_dir: calea către directorul experimentului
                     ex: "experiments/fl_fedavg_effb0_run01"
        """
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Configurație experiment
    # -------------------------------------------------------------------------

    def write_run_config(self, config: dict) -> None:
        """
        Scrie run_config.json în run_dir/.
        Adaugă automat câmpul 'git_commit_hash'.
        Suprascrie dacă există deja.
        """
        config_with_meta = {
            "timestamp": datetime.utcnow().isoformat(),
            "git_commit_hash": _get_git_commit_hash(),
            **config,
        }
        config_path = self.run_dir / "run_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_with_meta, f, indent=2, ensure_ascii=False)

    def update_run_config(self, updates: dict) -> None:
        """
        Actualizează câmpuri specifice în run_config.json existent.
        Util pentru a adăuga 'early_stopped_at_epoch' după antrenare.
        """
        config_path = self.run_dir / "run_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
        config.update(updates)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # Metrici per epocă (centralizat)
    # -------------------------------------------------------------------------

    def append_epoch_metrics(self, metrics: EpochMetrics) -> None:
        """
        Adaugă un rând în run_dir/metrics_by_epoch.csv.
        Creează fișierul cu header dacă nu există.
        """
        path = self.run_dir / "metrics_by_epoch.csv"
        fieldnames = [f.name for f in fields(EpochMetrics)]
        _append_csv(path, asdict(metrics), fieldnames)

    # -------------------------------------------------------------------------
    # Metrici per rundă FL (central)
    # -------------------------------------------------------------------------

    def append_round_metrics(self, metrics: RoundMetrics) -> None:
        """
        Adaugă un rând în run_dir/central/metrics_by_round.csv.
        Creează fișierul cu header dacă nu există.
        Valorile None sunt scrise ca string gol.
        """
        path = self.run_dir / "central" / "metrics_by_round.csv"
        fieldnames = [f.name for f in fields(RoundMetrics)]
        _append_csv(path, asdict(metrics), fieldnames)

    # -------------------------------------------------------------------------
    # Metrici per nod FL
    # -------------------------------------------------------------------------

    def append_node_metrics(self, metrics: NodeRoundMetrics) -> None:
        """
        Adaugă un rând în run_dir/nodes/node{N}_metrics_by_round.csv.
        Creează fișierul cu header dacă nu există.
        """
        node_id = metrics.node_id
        path = self.run_dir / "nodes" / f"{node_id}_metrics_by_round.csv"
        fieldnames = [f.name for f in fields(NodeRoundMetrics)]
        _append_csv(path, asdict(metrics), fieldnames)

    # -------------------------------------------------------------------------
    # Salvare modele
    # -------------------------------------------------------------------------

    def save_best_model(
        self,
        model: nn.Module,
        model_name: str,
        subdir: str = "artifacts/best_model",
    ) -> None:
        """
        Salvează weights.pt și model_hash.txt în run_dir/subdir/.

        Args:
            model: modelul PyTorch de salvat
            model_name: numele arhitecturii (ex. "efficientnet_b0")
            subdir: subdirectorul relativ față de run_dir
                    "artifacts/best_model" pentru centralizat
                    "central/best_model" pentru FL
        """
        dest = self.run_dir / subdir
        dest.mkdir(parents=True, exist_ok=True)

        # Salvează weights
        weights_path = dest / "weights.pt"
        torch.save(
            {"state_dict": model.state_dict(), "model_name": model_name},
            weights_path,
        )

        # Calculează și salvează hash
        model_hash = _compute_model_hash_sha256(model)
        hash_path = dest / "model_hash.txt"
        hash_path.write_text(model_hash, encoding="utf-8")

    def save_round_weights(
        self,
        parameters: List[np.ndarray],
        model: nn.Module,
        round_num: int,
    ) -> None:
        """
        Salvează run_dir/central/global_models/round_{NNN}_weights.pt
        unde NNN = f"{round_num:03d}".

        Args:
            parameters: lista de numpy arrays cu parametrii modelului
            model: modelul PyTorch (pentru a obține cheile state_dict)
            round_num: numărul rundei (0-indexed sau 1-indexed, consistent cu Flower)
        """
        dest = self.run_dir / "central" / "global_models"
        dest.mkdir(parents=True, exist_ok=True)

        # Reconstruiește state_dict din parametri
        params_dict = zip(model.state_dict().keys(), parameters)
        state_dict = {k: torch.tensor(v) for k, v in params_dict}

        weights_path = dest / f"round_{round_num:03d}_weights.pt"
        torch.save({"state_dict": state_dict}, weights_path)

    def copy_best_model_from_round(
        self,
        round_num: int,
        model: nn.Module,
        subdir: str = "central/best_model",
    ) -> None:
        """
        Copiază round_{NNN}_weights.pt în subdir/weights.pt și
        calculează model_hash.txt.

        Folosit de _finalize_best_model() din FedMedStrategy.
        """
        src = self.run_dir / "central" / "global_models" / f"round_{round_num:03d}_weights.pt"
        dest = self.run_dir / subdir
        dest.mkdir(parents=True, exist_ok=True)

        if not src.exists():
            raise FileNotFoundError(f"Round weights not found: {src}")

        # Copiază weights
        shutil.copy2(src, dest / "weights.pt")

        # Calculează hash din fișierul copiat
        checkpoint = torch.load(dest / "weights.pt", map_location="cpu", weights_only=False)
        state_dict = checkpoint.get("state_dict", checkpoint)
        hasher = hashlib.sha256()
        for key in sorted(state_dict.keys()):
            hasher.update(key.encode("utf-8"))
            tensor = state_dict[key]
            if isinstance(tensor, torch.Tensor):
                hasher.update(tensor.cpu().numpy().tobytes())
        model_hash = hasher.hexdigest()
        (dest / "model_hash.txt").write_text(model_hash, encoding="utf-8")

    # -------------------------------------------------------------------------
    # Predicții și confusion matrix
    # -------------------------------------------------------------------------

    def save_predictions(
        self,
        filenames: List[str],
        y_true: List[int],
        y_score: List[float],
        subdir: str = "artifacts/best_model",
    ) -> None:
        """
        Scrie predictions_test.csv cu coloanele: filename, y_true, y_score.

        Args:
            filenames: lista de nume de fișiere (basename sau path relativ)
            y_true: etichete reale (0=NORMAL, 1=PNEUMONIA)
            y_score: probabilități pentru clasa PNEUMONIA (softmax[:, 1])
            subdir: subdirectorul relativ față de run_dir
        """
        dest = self.run_dir / subdir
        dest.mkdir(parents=True, exist_ok=True)

        path = dest / "predictions_test.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "y_true", "y_score"])
            writer.writeheader()
            for fname, yt, ys in zip(filenames, y_true, y_score):
                writer.writerow({"filename": fname, "y_true": int(yt), "y_score": float(ys)})

    def save_confusion_matrix(
        self,
        y_true: List[int],
        y_score: List[float],
        threshold: float = 0.5,
        subdir: str = "artifacts/best_model",
    ) -> None:
        """
        Calculează și scrie confusion_matrix.json.

        Câmpuri: threshold, TP, FP, TN, FN, accuracy, sensitivity, specificity.

        Args:
            y_true: etichete reale (0/1)
            y_score: probabilități pentru clasa pozitivă (PNEUMONIA)
            threshold: pragul de decizie (default 0.5)
            subdir: subdirectorul relativ față de run_dir
        """
        dest = self.run_dir / subdir
        dest.mkdir(parents=True, exist_ok=True)

        y_pred = [1 if s >= threshold else 0 for s in y_score]

        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
        tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

        total = tp + fp + tn + fn
        accuracy = (tp + tn) / total if total > 0 else 0.0
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

        cm = {
            "threshold": threshold,
            "TP": tp,
            "FP": fp,
            "TN": tn,
            "FN": fn,
            "accuracy": round(accuracy, 6),
            "sensitivity": round(sensitivity, 6),
            "specificity": round(specificity, 6),
        }

        path = dest / "confusion_matrix.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cm, f, indent=2)

    # -------------------------------------------------------------------------
    # Best round
    # -------------------------------------------------------------------------

    def get_best_round(self) -> Optional[int]:
        """
        Citește central/metrics_by_round.csv și returnează numărul rundei
        cu test_auc maxim (prima dacă există egalitate).

        Returns:
            Numărul rundei (câmpul 'round') sau None dacă fișierul lipsește,
            e gol, sau toate valorile test_auc sunt None/goale.
        """
        path = self.run_dir / "central" / "metrics_by_round.csv"
        if not path.exists():
            return None

        best_round = None
        best_auc = -1.0

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                auc_str = row.get("test_auc", "")
                if auc_str == "" or auc_str is None:
                    continue
                try:
                    auc_val = float(auc_str)
                except ValueError:
                    continue
                if auc_val > best_auc:
                    best_auc = auc_val
                    try:
                        best_round = int(row["round"])
                    except (KeyError, ValueError):
                        best_round = None

        return best_round
