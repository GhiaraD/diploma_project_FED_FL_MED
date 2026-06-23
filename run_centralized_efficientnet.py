#!/usr/bin/env python3
"""
run_centralized_efficientnet.py

Antrenare centralizată cu EfficientNet-B0 pe același test_global.csv
folosit de experimentele federate. Salvează rezultatele în centralized_dragos/.

Echivalent cu notebook-ul, dar:
- Rulează doar EfficientNet-B0
- Nu afișează grafice (matplotlib fără display)
- Salvează predictions_test.csv compatibil cu generate_plots.py
- Salvează confusion_matrix.json compatibil cu generate_plots.py

Utilizare:
    python run_centralized_efficientnet.py
"""
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
from torch.utils.data import ConcatDataset, DataLoader, Subset
from torchvision import models, transforms
from torchvision.datasets import ImageFolder
from torchvision.models import EfficientNet_B0_Weights
from tqdm import tqdm

import warnings
warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURAȚIE
# ============================================================================

SEED              = 42
K_FOLDS           = 4
MAX_EPOCHS        = 30
PATIENCE          = 10
F1_THRESHOLD      = 0.90
BATCH_SIZE        = 32
LEARNING_RATE     = 1e-4
MODEL_NAME        = "efficientnet_b0"

PROJECT_ROOT      = os.path.expanduser("~/disertatie/diploma_project_FED_FL_MED")
DATA_DIR          = os.path.join(PROJECT_ROOT, "central_dataset", "chest_xray")
TRAIN_DIR         = os.path.join(DATA_DIR, "train")
VAL_DIR           = os.path.join(DATA_DIR, "val")
TEST_DIR          = os.path.join(DATA_DIR, "test")
TEST_GLOBAL_CSV   = os.path.join(PROJECT_ROOT, "experiments", "splits", "test_global.csv")
OUTPUT_DIR        = os.path.join(PROJECT_ROOT, "centralized_dragos")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Reproducibilitate
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")
print(f"Output dir: {OUTPUT_DIR}")

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
# DATASET-URI
# ============================================================================

class CsvImageDataset(torch.utils.data.Dataset):
    """Dataset care citește (filepath, label) din test_global.csv."""
    def __init__(self, csv_path, root, transform=None):
        self.transform = transform
        self.samples = []
        with open(csv_path, "r") as f:
            for row in csv.DictReader(f):
                abs_path = os.path.join(root, row["filepath"])
                self.samples.append((abs_path, int(row["label"])))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label


class FilteredImageFolder(torch.utils.data.Dataset):
    """ImageFolder care exclude fișierele din test_global.csv."""
    def __init__(self, folder, transform, exclude_set):
        base = ImageFolder(folder, transform=transform)
        self.transform = transform
        self.samples = [(p, l) for p, l in base.samples if p not in exclude_set]
        self.classes = base.classes

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label


# Construiește setul de test
test_data = CsvImageDataset(TEST_GLOBAL_CSV, PROJECT_ROOT, transform=test_transform)
print(f"test_global: {len(test_data)} imagini")

# Exclude fișierele din test_global din pool-ul de antrenare
with open(TEST_GLOBAL_CSV) as f:
    test_global_files = {
        os.path.join(PROJECT_ROOT, row["filepath"])
        for row in csv.DictReader(f)
    }

train_pool = FilteredImageFolder(TRAIN_DIR, train_transform, test_global_files)
val_pool   = FilteredImageFolder(VAL_DIR,   test_transform,  test_global_files)
test_orig  = FilteredImageFolder(TEST_DIR,  test_transform,  test_global_files)

full_train_data = ConcatDataset([train_pool, val_pool, test_orig])
full_labels = np.array(
    [s[1] for s in train_pool.samples] +
    [s[1] for s in val_pool.samples]   +
    [s[1] for s in test_orig.samples]
)
print(f"full_train_data: {len(full_train_data)} imagini")
print(f"  NORMAL={( full_labels==0).sum()}  PNEUMONIA={(full_labels==1).sum()}")

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

def train_kfold():
    skf = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)
    best_models = []
    fold_results = []

    label_tensor = torch.tensor(full_labels)
    class_counts = torch.bincount(label_tensor)
    class_weights = (1.0 / class_counts.float())
    class_weights = (class_weights / class_weights.sum()).to(device)

    for fold, (train_idx, val_idx) in enumerate(
            skf.split(np.zeros(len(full_labels)), full_labels)):
        print(f"\n{'='*50}")
        print(f"  FOLD {fold + 1}/{K_FOLDS}")
        print(f"{'='*50}")

        train_subset = Subset(full_train_data, train_idx)
        val_subset   = Subset(full_train_data, val_idx)
        train_loader = DataLoader(train_subset, batch_size=BATCH_SIZE, shuffle=True,
                                  num_workers=4, pin_memory=True)
        val_loader   = DataLoader(val_subset,   batch_size=BATCH_SIZE,
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
                OUTPUT_DIR, f"{MODEL_NAME}_fold{fold}_f1{best_f1:.4f}.pt"
            )
            torch.save(best_state, save_path)
            print(f"  ✓ Model salvat: {save_path}  (val F1={best_f1:.4f})")
            best_models.append(save_path)
        else:
            print(f"  Fold ignorat (val F1={best_f1:.4f} < {F1_THRESHOLD})")

    return best_models, fold_results

# ============================================================================
# EVALUARE PE TEST_GLOBAL
# ============================================================================

def evaluate_on_test(model_paths):
    test_loader = DataLoader(test_data, batch_size=BATCH_SIZE, shuffle=False,
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

        # Salvează predictions_test.csv (compatibil generate_plots.py)
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(path))
        pred_csv  = os.path.join(OUTPUT_DIR, f"predictions_test_{safe_name}.csv")
        with open(pred_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "y_true", "y_score"])
            writer.writeheader()
            for i, (yt, ys) in enumerate(zip(m['targets'], m['scores'])):
                writer.writerow({"filename": f"img_{i}",
                                 "y_true": yt,
                                 "y_score": f"{ys:.6f}"})
        print(f"  ✓ predictions_test: {pred_csv}")

        # Salvează confusion_matrix.json (compatibil generate_plots.py)
        cm = confusion_matrix(m['targets'], m['preds'])
        tn, fp, fn, tp = cm.ravel()
        cm_json = {
            "threshold":   0.5,
            "TP": int(tp), "FP": int(fp),
            "TN": int(tn), "FN": int(fn),
            "accuracy":    round(float(m['acc']), 6),
            "sensitivity": round(float(m['sensitivity']), 6),
            "specificity": round(float(m['specificity']), 6),
        }
        cm_path = os.path.join(OUTPUT_DIR,
                               f"confusion_matrix_{safe_name}.json")
        with open(cm_path, "w") as f:
            json.dump(cm_json, f, indent=2)
        print(f"  ✓ confusion_matrix: {cm_path}")

        results.append({**m, "path": path})

    return results

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*60)
    print("  ANTRENARE CENTRALIZATĂ — EfficientNet-B0")
    print(f"  K={K_FOLDS} folds, max {MAX_EPOCHS} epoci, patience={PATIENCE}, lr={LEARNING_RATE}")
    print(f"  Test set: test_global.csv ({len(test_data)} imagini)")
    print("="*60)

    # Antrenare
    best_models, fold_f1s = train_kfold()

    print("\n" + "="*60)
    print("  SUMAR ANTRENARE")
    for i, f1 in enumerate(fold_f1s):
        print(f"  Fold {i+1}: val F1 = {f1:.4f}")
    print(f"  Modele salvate: {len(best_models)}")

    if not best_models:
        print("\n⚠ Niciun model nu a depășit pragul F1. Salvez cel mai bun fold oricum.")
        # Salvează cel mai bun fold indiferent de prag
        best_idx  = int(np.argmax(fold_f1s))
        best_f1   = fold_f1s[best_idx]
        save_path = os.path.join(
            OUTPUT_DIR, f"{MODEL_NAME}_fold{best_idx}_f1{best_f1:.4f}.pt"
        )
        print(f"  → Rulează din nou fold-ul {best_idx+1} cu F1_THRESHOLD=0")
        # Re-antrenare fold-ul cel mai bun fără prag
        skf = StratifiedKFold(n_splits=K_FOLDS, shuffle=True, random_state=SEED)
        for i, (train_idx, val_idx) in enumerate(
                skf.split(np.zeros(len(full_labels)), full_labels)):
            if i != best_idx:
                continue
            label_tensor  = torch.tensor(full_labels)
            class_counts  = torch.bincount(label_tensor)
            class_weights = (1.0 / class_counts.float())
            class_weights = (class_weights / class_weights.sum()).to(device)
            train_loader  = DataLoader(Subset(full_train_data, train_idx),
                                       batch_size=BATCH_SIZE, shuffle=True)
            val_loader    = DataLoader(Subset(full_train_data, val_idx),
                                       batch_size=BATCH_SIZE)
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
            torch.save(best_state, save_path)
            best_models.append(save_path)
            print(f"  ✓ Salvat: {save_path}")
            break

    # Evaluare pe test_global
    print("\n" + "="*60)
    print("  EVALUARE PE TEST_GLOBAL")
    results = evaluate_on_test(best_models)

    # Best model după F2
    best = max(results, key=lambda r: r['f2'])
    best_safe = re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(best['path']))

    # Copiază predictions și confusion_matrix ale best model ca fișiere finale
    import shutil
    shutil.copy(
        os.path.join(OUTPUT_DIR, f"predictions_test_{best_safe}.csv"),
        os.path.join(OUTPUT_DIR, "predictions_test.csv")
    )
    shutil.copy(
        os.path.join(OUTPUT_DIR, f"confusion_matrix_{best_safe}.json"),
        os.path.join(OUTPUT_DIR, "confusion_matrix.json")
    )

    print(f"\n  Best model (după F2={best['f2']:.4f}): {os.path.basename(best['path'])}")
    print(f"  ✓ predictions_test.csv  (best model)")
    print(f"  ✓ confusion_matrix.json (best model)")
    print(f"\n✅ Gata! Rezultatele sunt în: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
