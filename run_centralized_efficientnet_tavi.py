#!/usr/bin/env python3
"""
run_centralized_efficientnet_tavi.py

Antrenare centralizată pe datele unui singur nod dintr-un split din experiments_tavi.
Evaluare pe test_global.csv din experiments_tavi/.

Utilizare:
    python run_centralized_efficientnet_tavi.py \\
        --train-csv experiments_tavi/splits_noniid_extreme/node1_train.csv

    # Scriptul derivă automat:
    #   val CSV  : experiments_tavi/splits_noniid_extreme/node1_val.csv
    #   test CSV : experiments_tavi/test_global.csv
    #   output   : centralized_tavi/noniid_extreme_node1/
"""
import argparse
import csv
import json
import os
import random
import re

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from sklearn.metrics import (
    accuracy_score, average_precision_score, classification_report,
    confusion_matrix, f1_score, fbeta_score, precision_score,
    recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from torch.utils.data import DataLoader
from torchvision import models, transforms
from torchvision.models import EfficientNet_B0_Weights
from tqdm import tqdm

import warnings
warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURAȚIE (modificabilă)
# ============================================================================

SEED            = 42
K_FOLDS         = 4
MAX_EPOCHS      = 30
PATIENCE        = 10
F1_THRESHOLD    = 0.90
BATCH_SIZE      = 32
LEARNING_RATE   = 1e-4
MODEL_NAME      = "efficientnet_b0"

PROJECT_ROOT    = os.path.expanduser("~/disertatie/diploma_project_FED_FL_MED")

# ============================================================================
# REPRODUCIBILITATE
# ============================================================================

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ============================================================================
# TRANSFORMĂRI
# ============================================================================

train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.Lambda(lambda img: img.convert("RGB")),
    transforms.RandomHorizontalFlip(),
    transforms.RandomAffine(degrees=5, translate=(0.02, 0.02)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

test_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.Lambda(lambda img: img.convert("RGB")),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# ============================================================================
# DATASET DIN CSV
# ============================================================================

class CsvImageDataset(torch.utils.data.Dataset):
    """Dataset care citește (filepath, label) dintr-un CSV cu split-uri fixe."""

    def __init__(self, csv_path: str, root: str, transform=None):
        self.transform = transform
        self.samples = []
        with open(csv_path, "r") as f:
            for row in csv.DictReader(f):
                # Suportă path-uri relative față de PROJECT_ROOT
                filepath = row["filepath"]
                p = filepath if os.path.isabs(filepath) else os.path.join(root, filepath)
                # Fallback: încearcă și cu / prefix (cale Docker)
                if not os.path.exists(p):
                    p_docker = "/" + filepath.lstrip("/")
                    if os.path.exists(p_docker):
                        p = p_docker
                self.samples.append((p, int(row["label"])))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label

# ============================================================================
# MODEL
# ============================================================================

def get_model():
    model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, 2)
    return model.to(device)

# ============================================================================
# EVALUARE
# ============================================================================

def evaluate(model, loader):
    model.eval()
    preds, targets, scores = [], [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            out = model(x)
            probs = torch.softmax(out, dim=1)[:, 1].cpu().tolist()
            scores.extend(probs)
            preds.extend(out.argmax(1).cpu().tolist())
            targets.extend(y.tolist())

    cm = confusion_matrix(targets, preds)
    tn, fp, fn, tp = cm.ravel()
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    try:
        auc_val = roc_auc_score(targets, scores)
        pr_auc  = average_precision_score(targets, scores)
    except Exception:
        auc_val = pr_auc = 0.0

    return {
        "acc":         accuracy_score(targets, preds),
        "f1":          f1_score(targets, preds, zero_division=0),
        "f2":          fbeta_score(targets, preds, beta=2, zero_division=0),
        "precision":   precision_score(targets, preds, zero_division=0),
        "recall":      recall_score(targets, preds, zero_division=0),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "auc":         auc_val,
        "pr_auc":      pr_auc,
        "scores":      scores,
        "targets":     targets,
        "preds":       preds,
    }

# ============================================================================
# ANTRENARE K-FOLD
# ============================================================================

def train_kfold(train_dataset, val_dataset, output_dir: str):
    """
    Antrenare K-Fold pe train_dataset, cu val_dataset fix per fold ca set de validare.
    
    Logică: train_dataset e împărțit în K fold-uri. Val set-ul din CSV e folosit
    pentru early stopping. La finalul fiecărui fold modelul e evaluat pe val_dataset.
    """
    # Construiește labels pentru stratificat K-Fold din train
    full_labels = np.array([train_dataset.samples[i][1]
                            for i in range(len(train_dataset))])

    skf = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)

    label_tensor  = torch.tensor(full_labels)
    class_counts  = torch.bincount(label_tensor)
    class_weights = (1.0 / class_counts.float())
    class_weights = (class_weights / class_weights.sum()).to(device)

    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE,
                            num_workers=4, pin_memory=True)

    best_models  = []
    fold_results = []

    for fold, (train_idx, _) in enumerate(
            skf.split(np.zeros(len(full_labels)), full_labels)):

        print(f"\n{'='*50}")
        print(f"  FOLD {fold + 1}/{K_FOLDS}")
        print(f"{'='*50}")

        from torch.utils.data import Subset
        train_subset = Subset(train_dataset, train_idx)
        train_loader = DataLoader(train_subset, batch_size=BATCH_SIZE, shuffle=True,
                                  num_workers=4, pin_memory=True)

        model     = get_model()
        optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
        criterion = nn.CrossEntropyLoss(weight=class_weights)

        best_f1 = 0.0
        patience_counter = 0
        best_state = None

        for epoch in range(MAX_EPOCHS):
            model.train()
            running_loss = correct = total = 0

            loop = tqdm(train_loader,
                        desc=f"Epoch {epoch+1}/{MAX_EPOCHS} [Fold {fold+1}]",
                        leave=False)
            for inputs, labels in loop:
                inputs, labels = inputs.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                running_loss += loss.item() * inputs.size(0)
                correct += (outputs.argmax(1) == labels).sum().item()
                total   += labels.size(0)
                loop.set_postfix(loss=running_loss/total, acc=correct/total)

            metrics = evaluate(model, val_loader)
            print(f"  Epoch {epoch+1:2d} | "
                  f"Val Acc={metrics['acc']:.4f}  "
                  f"F1={metrics['f1']:.4f}  "
                  f"F2={metrics['f2']:.4f}  "
                  f"AUC={metrics['auc']:.4f}")

            if metrics["f1"] > best_f1:
                best_f1 = metrics["f1"]
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= PATIENCE:
                    print("  Early stopping")
                    break

        fold_results.append(best_f1)

        if best_f1 >= F1_THRESHOLD:
            save_path = os.path.join(
                output_dir, f"{MODEL_NAME}_fold{fold}_f1{best_f1:.4f}.pt"
            )
            torch.save(best_state, save_path)
            print(f"  ✓ Model salvat: {save_path}")
            best_models.append(save_path)
        else:
            print(f"  Fold ignorat (val F1={best_f1:.4f} < {F1_THRESHOLD})")

    return best_models, fold_results

# ============================================================================
# EVALUARE PE TEST_GLOBAL
# ============================================================================

def evaluate_on_test(model_paths, test_dataset, output_dir: str):
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False,
                             num_workers=4, pin_memory=True)
    results = []

    for path in model_paths:
        model = get_model()
        model.load_state_dict(
            torch.load(path, map_location=device, weights_only=False)
        )
        model.to(device)

        m = evaluate(model, test_loader)

        print(f"\n{'='*60}")
        print(f"Model: {os.path.basename(path)}")
        print(f"  Accuracy:    {m['acc']:.4f}")
        print(f"  F1:          {m['f1']:.4f}")
        print(f"  F2:          {m['f2']:.4f}")
        print(f"  AUC:         {m['auc']:.4f}")
        print(f"  PR-AUC:      {m['pr_auc']:.4f}")
        print(f"  Sensitivity: {m['sensitivity']:.4f}")
        print(f"  Specificity: {m['specificity']:.4f}")
        print(classification_report(m['targets'], m['preds'],
                                    target_names=["Normal", "Pneumonia"]))

        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(path))

        # predictions_test.csv
        pred_csv = os.path.join(output_dir, f"predictions_test_{safe_name}.csv")
        with open(pred_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "y_true", "y_score"])
            writer.writeheader()
            for i, (yt, ys) in enumerate(zip(m['targets'], m['scores'])):
                writer.writerow({"filename": f"img_{i}",
                                 "y_true": yt,
                                 "y_score": f"{ys:.6f}"})
        print(f"  ✓ {pred_csv}")

        # confusion_matrix.json
        cm = confusion_matrix(m['targets'], m['preds'])
        tn, fp, fn, tp = cm.ravel()
        cm_path = os.path.join(output_dir, f"confusion_matrix_{safe_name}.json")
        with open(cm_path, "w") as f:
            json.dump({
                "threshold":   0.5,
                "TP": int(tp), "FP": int(fp),
                "TN": int(tn), "FN": int(fn),
                "accuracy":    round(float(m['acc']), 6),
                "sensitivity": round(float(m['sensitivity']), 6),
                "specificity": round(float(m['specificity']), 6),
            }, f, indent=2)
        print(f"  ✓ {cm_path}")

        results.append({**m, "path": path})

    return results

# ============================================================================
# DERIVARE OUTPUT DIR
# ============================================================================

def derive_output_dir(train_csv: str) -> str:
    """
    Din 'experiments_tavi/splits_noniid_extreme/node1_train.csv'
    derivă 'centralized_tavi/noniid_extreme_node1/'
    """
    p = os.path.abspath(train_csv)
    splits_dir  = os.path.basename(os.path.dirname(p))   # splits_noniid_extreme
    filename    = os.path.basename(p)                     # node1_train.csv

    # Strip prefix "splits_"
    dist_name = splits_dir.replace("splits_", "", 1)      # noniid_extreme

    # Node name: node1_train.csv → node1
    node_name = filename.split("_train")[0]                # node1

    folder = f"{dist_name}_{node_name}"                   # noniid_extreme_node1
    return os.path.join("centralized_tavi", folder)


def derive_val_csv(train_csv: str) -> str:
    """
    Din 'experiments_tavi/splits_noniid_extreme/node1_train.csv'
    derivă 'experiments_tavi/splits_noniid_extreme/node1_val.csv'
    """
    return train_csv.replace("_train.csv", "_val.csv")


def find_test_global(train_csv: str) -> str:
    """
    Caută test_global.csv în directorul parinte al splits_* (adică experiments_tavi/).
    """
    splits_dir      = os.path.dirname(os.path.abspath(train_csv))
    experiments_dir = os.path.dirname(splits_dir)
    candidate       = os.path.join(experiments_dir, "test_global.csv")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"test_global.csv nu a fost găsit în {experiments_dir}\n"
        f"Asigură-te că rulezi tavi_test_e2e.py cel puțin o dată."
    )

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Antrenare centralizată pe un split de nod din experiments_tavi."
    )
    parser.add_argument(
        "--train-csv", required=True,
        help="Calea către fișierul CSV de antrenare "
             "(ex. experiments_tavi/splits_noniid_extreme/node1_train.csv)"
    )
    parser.add_argument(
        "--val-csv", default=None,
        help="Calea către fișierul CSV de validare. "
             "Dacă nu e specificat, se derivă automat din --train-csv."
    )
    parser.add_argument(
        "--test-csv", default=None,
        help="Calea către test_global.csv. "
             "Dacă nu e specificat, se caută automat în directorul parinte."
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Directorul de output. "
             "Dacă nu e specificat, se derivă automat din --train-csv."
    )
    args = parser.parse_args()

    # Derivare căi
    train_csv  = args.train_csv
    val_csv    = args.val_csv    or derive_val_csv(train_csv)
    test_csv   = args.test_csv   or find_test_global(train_csv)
    output_dir = args.output_dir or derive_output_dir(train_csv)

    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  ANTRENARE CENTRALIZATĂ PE NOD INDIVIDUAL")
    print(f"{'='*60}")
    print(f"  Device:     {device}")
    print(f"  Train CSV:  {train_csv}")
    print(f"  Val CSV:    {val_csv}")
    print(f"  Test CSV:   {test_csv}")
    print(f"  Output:     {output_dir}")
    print(f"  K-Folds:    {K_FOLDS}")
    print(f"  Max epochs: {MAX_EPOCHS}  Patience: {PATIENCE}")
    print(f"  LR:         {LEARNING_RATE}  Batch: {BATCH_SIZE}")

    # Verificare fișiere
    for path, name in [(train_csv, "train"), (val_csv, "val"), (test_csv, "test")]:
        if not os.path.exists(path):
            print(f"\nEROARE: Fișierul {name} nu există: {path}")
            raise SystemExit(1)

    # Construiește dataset-uri
    train_dataset = CsvImageDataset(train_csv, PROJECT_ROOT, transform=train_transform)
    val_dataset   = CsvImageDataset(val_csv,   PROJECT_ROOT, transform=test_transform)
    test_dataset  = CsvImageDataset(test_csv,  PROJECT_ROOT, transform=test_transform)

    print(f"\n  Train: {len(train_dataset)} imagini")
    print(f"  Val:   {len(val_dataset)} imagini")
    print(f"  Test:  {len(test_dataset)} imagini (test_global)")

    n_normal    = sum(1 for _, l in train_dataset.samples if l == 0)
    n_pneumonia = sum(1 for _, l in train_dataset.samples if l == 1)
    print(f"  Train distribution: NORMAL={n_normal}, PNEUMONIA={n_pneumonia}")

    # Antrenare
    best_models, fold_f1s = train_kfold(train_dataset, val_dataset, output_dir)

    print(f"\n{'='*60}")
    print(f"  SUMAR ANTRENARE")
    for i, f1 in enumerate(fold_f1s):
        print(f"  Fold {i+1}: val F1 = {f1:.4f}")
    print(f"  Modele salvate: {len(best_models)}")

    if not best_models:
        print(f"\n⚠ Niciun model nu a depășit pragul F1={F1_THRESHOLD}.")
        print(f"  Salvez best fold oricum...")
        best_idx  = int(np.argmax(fold_f1s))
        best_f1   = fold_f1s[best_idx]
        skf       = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)
        full_labels = np.array([train_dataset.samples[i][1]
                                for i in range(len(train_dataset))])
        label_tensor  = torch.tensor(full_labels)
        class_counts  = torch.bincount(label_tensor)
        class_weights = (1.0 / class_counts.float())
        class_weights = (class_weights / class_weights.sum()).to(device)
        val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

        for i, (train_idx, _) in enumerate(
                skf.split(np.zeros(len(full_labels)), full_labels)):
            if i != best_idx:
                continue
            from torch.utils.data import Subset
            train_loader = DataLoader(Subset(train_dataset, train_idx),
                                      batch_size=BATCH_SIZE, shuffle=True)
            model     = get_model()
            optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
            criterion = nn.CrossEntropyLoss(weight=class_weights)
            best_state = None
            bf1 = 0
            for epoch in range(MAX_EPOCHS):
                model.train()
                for inputs, labels in train_loader:
                    inputs, labels = inputs.to(device), labels.to(device)
                    optimizer.zero_grad()
                    loss = criterion(model(inputs), labels)
                    loss.backward(); optimizer.step()
                m = evaluate(model, val_loader)
                if m['f1'] > bf1:
                    bf1 = m['f1']
                    best_state = {k: v.clone() for k, v in model.state_dict().items()}
            save_path = os.path.join(
                output_dir, f"{MODEL_NAME}_fold{best_idx}_f1{bf1:.4f}.pt"
            )
            torch.save(best_state, save_path)
            best_models.append(save_path)
            print(f"  ✓ Salvat: {save_path}")
            break

    # Evaluare pe test_global
    print(f"\n{'='*60}")
    print(f"  EVALUARE PE TEST_GLOBAL")
    results = evaluate_on_test(best_models, test_dataset, output_dir)

    # Copiază best model (după F2) ca fișiere finale
    import shutil
    best = max(results, key=lambda r: r['f2'])
    best_safe = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(best['path']))

    shutil.copy(
        os.path.join(output_dir, f"predictions_test_{best_safe}.csv"),
        os.path.join(output_dir, "predictions_test.csv")
    )
    shutil.copy(
        os.path.join(output_dir, f"confusion_matrix_{best_safe}.json"),
        os.path.join(output_dir, "confusion_matrix.json")
    )

    print(f"\n  Best model (F2={best['f2']:.4f}): {os.path.basename(best['path'])}")
    print(f"  ✓ predictions_test.csv")
    print(f"  ✓ confusion_matrix.json")
    print(f"\n✅ Gata! Rezultatele sunt în: {output_dir}")


if __name__ == "__main__":
    main()
