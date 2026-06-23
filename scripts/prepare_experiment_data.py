#!/usr/bin/env python3
"""
prepare_experiment_data.py — Pregătire split-uri fixe pentru experimentele Fed-Med-FL.

Produce:
  experiments/splits/
    test_global.csv          (15% stratificat, seed fix)
    train_pool.csv           (85%)
    node{1-N}_train.csv      (distribuție Dirichlet α=2.0)
    node{1-N}_val.csv        (20% din fiecare nod)
    data_distribution.json   (statistici per nod)

  storage/central/test_global.csv
  storage/node{1-N}/test_global.csv

Utilizare:
  python scripts/prepare_experiment_data.py \\
      --dataset-dir central_dataset/chest_xray \\
      --output-dir experiments/splits \\
      --storage-dir storage \\
      --test-ratio 0.15 \\
      --num-nodes 5 \\
      --dirichlet-alpha 2.0 \\
      --seed 42

  # Suprascrie split-uri existente:
  python scripts/prepare_experiment_data.py ... --force
"""
import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit


# ============================================================================
# Tipuri
# ============================================================================

Sample = Tuple[str, int]   # (filepath, label)  label: 0=NORMAL, 1=PNEUMONIA


# ============================================================================
# Colectare imagini din dataset
# ============================================================================

def collect_images(dataset_dir: str, project_root: str = None) -> List[Sample]:
    """
    Parcurge structura dataset-ului chest_xray și colectează toate imaginile.

    Structura așteptată:
        dataset_dir/
            train/NORMAL/*.jpeg
            train/PNEUMONIA/*.jpeg
            test/NORMAL/*.jpeg
            test/PNEUMONIA/*.jpeg
            val/NORMAL/*.jpeg
            val/PNEUMONIA/*.jpeg

    Toate split-urile originale (train/test/val) sunt combinate într-un
    singur pool, din care vom face propriile split-uri fixe.

    Args:
        dataset_dir: directorul dataset-ului
        project_root: dacă e furnizat, path-urile salvate în CSV vor fi
                      relative față de project_root (pentru compatibilitate Docker).
                      Dacă e None, se salvează path-uri absolute.

    Returns:
        Lista de (filepath, label) sortată pentru determinism.
        filepath este relativ față de project_root dacă acesta e furnizat.
    """
    dataset_path = Path(dataset_dir).resolve()
    if not dataset_path.exists():
        print(f"EROARE: Directorul dataset nu există: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    if project_root:
        root = Path(project_root).resolve()
    else:
        root = None

    samples: List[Sample] = []
    extensions = {".jpeg", ".jpg", ".png"}

    for split_dir in sorted(dataset_path.iterdir()):
        if not split_dir.is_dir():
            continue
        # Ignoră directoarele __MACOSX și ascunse
        if split_dir.name.startswith("_") or split_dir.name.startswith("."):
            continue

        for class_dir in sorted(split_dir.iterdir()):
            if not class_dir.is_dir():
                continue
            name_upper = class_dir.name.upper()
            if name_upper == "NORMAL":
                label = 0
            elif name_upper == "PNEUMONIA":
                label = 1
            else:
                continue  # ignoră directoare necunoscute

            for img_file in sorted(class_dir.iterdir()):
                if img_file.suffix.lower() in extensions:
                    if root:
                        # Path relativ față de project_root — funcționează în Docker
                        try:
                            filepath = str(img_file.resolve().relative_to(root))
                        except ValueError:
                            # Dacă nu e sub root, folosim path absolut
                            filepath = str(img_file.resolve())
                    else:
                        filepath = str(img_file.resolve())
                    samples.append((filepath, label))

    if not samples:
        print(f"EROARE: Nu s-au găsit imagini în {dataset_path}", file=sys.stderr)
        sys.exit(1)

    return samples


# ============================================================================
# Split stratificat
# ============================================================================

def stratified_split(
    all_files: List[Sample],
    test_ratio: float,
    seed: int,
) -> Tuple[List[Sample], List[Sample]]:
    """
    Împarte dataset-ul în test_global și train_pool prin eșantionare stratificată.

    Args:
        all_files: lista de (filepath, label)
        test_ratio: fracția pentru test_global (ex. 0.15)
        seed: seed pentru reproducibilitate

    Returns:
        (test_global, train_pool) — ambele liste de (filepath, label)
    """
    labels = [label for _, label in all_files]
    indices = list(range(len(all_files)))

    splitter = StratifiedShuffleSplit(n_splits=1, test_size=test_ratio, random_state=seed)
    train_idx, test_idx = next(splitter.split(indices, labels))

    test_global = [all_files[i] for i in sorted(test_idx)]
    train_pool = [all_files[i] for i in sorted(train_idx)]

    return test_global, train_pool


# ============================================================================
# Split Dirichlet pentru noduri FL
# ============================================================================

def dirichlet_split(
    train_pool: List[Sample],
    num_nodes: int,
    alpha: float,
    seed: int,
) -> List[List[Sample]]:
    """
    Împarte train_pool pe num_nodes noduri folosind distribuția Dirichlet.

    Algoritmul:
      1. Separă indicii pe clasă
      2. Pentru fiecare clasă, trage proporții din Dirichlet(alpha * ones(num_nodes))
      3. Alocă indicii proporțional fiecărui nod
      4. Concatenează alocările per nod și amestecă

    Args:
        train_pool: lista de (filepath, label)
        num_nodes: numărul de noduri
        alpha: parametrul Dirichlet (2.0 = heterogenitate moderată, suficient pentru ambele clase)
        seed: seed pentru reproducibilitate

    Returns:
        Lista de num_nodes liste, fiecare cu (filepath, label)
    """
    rng = np.random.default_rng(seed)

    # Grupează indicii pe clasă
    class_indices: dict = {}
    for idx, (_, label) in enumerate(train_pool):
        class_indices.setdefault(label, []).append(idx)

    # Alocare per nod
    node_indices: List[List[int]] = [[] for _ in range(num_nodes)]

    for label, indices in class_indices.items():
        # Amestecă indicii clasei cu seed deterministic
        indices_arr = np.array(indices)
        rng_local = np.random.default_rng(seed + label)
        rng_local.shuffle(indices_arr)

        # Trage proporții Dirichlet
        proportions = rng.dirichlet(alpha * np.ones(num_nodes))

        # Calculează dimensiunile per nod (cu rotunjire)
        sizes = (proportions * len(indices_arr)).astype(int)
        # Ajustează pentru a acoperi exact toți indicii
        diff = len(indices_arr) - sizes.sum()
        for i in range(abs(diff)):
            if diff > 0:
                sizes[i % num_nodes] += 1
            else:
                sizes[i % num_nodes] = max(0, sizes[i % num_nodes] - 1)

        # Alocă indicii
        start = 0
        for node_idx, size in enumerate(sizes):
            node_indices[node_idx].extend(indices_arr[start:start + size].tolist())
            start += size

    # Construiește listele de samples per nod
    node_splits: List[List[Sample]] = []
    for node_idx in range(num_nodes):
        node_samples = [train_pool[i] for i in sorted(node_indices[node_idx])]
        node_splits.append(node_samples)

    return node_splits


# ============================================================================
# Split local per nod (train/val 80/20)
# ============================================================================

def local_train_val_split(
    node_samples: List[Sample],
    val_ratio: float,
    seed: int,
    node_idx: int,
) -> Tuple[List[Sample], List[Sample]]:
    """
    Împarte datele unui nod în train_local și val_local (stratificat).

    Args:
        node_samples: lista de (filepath, label) pentru nodul respectiv
        val_ratio: fracția pentru validare (ex. 0.2)
        seed: seed de bază
        node_idx: indexul nodului (pentru seed unic per nod)

    Returns:
        (train_local, val_local)
    """
    if len(node_samples) < 2:
        return node_samples, []

    labels = [label for _, label in node_samples]
    unique_labels = set(labels)

    # Dacă nodul are o singură clasă, nu putem face split stratificat
    if len(unique_labels) < 2:
        split_idx = max(1, int(len(node_samples) * (1 - val_ratio)))
        return node_samples[:split_idx], node_samples[split_idx:]

    indices = list(range(len(node_samples)))
    splitter = StratifiedShuffleSplit(
        n_splits=1,
        test_size=val_ratio,
        random_state=seed + node_idx + 1000,
    )
    train_idx, val_idx = next(splitter.split(indices, labels))

    train_local = [node_samples[i] for i in sorted(train_idx)]
    val_local = [node_samples[i] for i in sorted(val_idx)]

    return train_local, val_local


# ============================================================================
# Salvare CSV și JSON
# ============================================================================

def save_csv(rows: List[Sample], path: str) -> None:
    """Scrie CSV cu coloanele: filepath, label (0=NORMAL, 1=PNEUMONIA)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
        writer.writeheader()
        for filepath, label in rows:
            writer.writerow({"filepath": filepath, "label": label})


def save_distribution_json(
    test_global: List[Sample],
    train_pool: List[Sample],
    node_splits: List[List[Sample]],
    path: str,
) -> None:
    """
    Scrie data_distribution.json cu statistici per split și per nod.

    Structura:
    {
      "total": N,
      "test_global": {"total": N, "normal": n, "pneumonia": p},
      "train_pool": {"total": N, "normal": n, "pneumonia": p},
      "nodes": {
        "node1": {"total": N, "normal": n, "pneumonia": p},
        ...
      }
    }
    """
    def stats(samples: List[Sample]) -> dict:
        normal = sum(1 for _, l in samples if l == 0)
        pneumonia = sum(1 for _, l in samples if l == 1)
        return {"total": len(samples), "normal": normal, "pneumonia": pneumonia}

    all_samples = test_global + train_pool
    distribution = {
        "total": len(all_samples),
        "test_global": stats(test_global),
        "train_pool": stats(train_pool),
        "nodes": {
            f"node{i + 1}": stats(node_splits[i])
            for i in range(len(node_splits))
        },
    }

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(distribution, f, indent=2)


# ============================================================================
# Copiere test_global în storage
# ============================================================================

def copy_test_global(
    test_csv_path: str,
    storage_dir: str,
    num_nodes: int,
) -> None:
    """
    Copiază test_global.csv în storage/central/ și storage/node{1-N}/.

    Dacă directoarele nu există, le creează.
    Erorile de copiere sunt logate ca avertismente (nu opresc execuția).
    """
    src = Path(test_csv_path)
    if not src.exists():
        print(f"  WARN: test_global.csv nu există la {src}, nu se copiază în storage.")
        return

    destinations = [Path(storage_dir) / "central"] + [
        Path(storage_dir) / f"node{i + 1}" for i in range(num_nodes)
    ]

    for dest_dir in destinations:
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_dir / "test_global.csv")
            print(f"  ✓ Copiat în {dest_dir}/test_global.csv")
        except Exception as e:
            print(f"  WARN: Nu s-a putut copia în {dest_dir}: {e}")


# ============================================================================
# Sumar
# ============================================================================

def print_summary(
    test_global: List[Sample],
    train_pool: List[Sample],
    node_splits: List[List[Sample]],
    node_train_splits: List[List[Sample]],
    node_val_splits: List[List[Sample]],
) -> None:
    """Afișează un sumar al distribuției datelor."""
    total = len(test_global) + len(train_pool)

    print("\n" + "=" * 60)
    print("SUMAR DISTRIBUȚIE DATE")
    print("=" * 60)
    print(f"Total imagini:    {total}")
    print(f"  test_global:    {len(test_global):5d}  "
          f"({len(test_global)/total*100:.1f}%)  "
          f"NORMAL={sum(1 for _,l in test_global if l==0)}  "
          f"PNEUMONIA={sum(1 for _,l in test_global if l==1)}")
    print(f"  train_pool:     {len(train_pool):5d}  "
          f"({len(train_pool)/total*100:.1f}%)  "
          f"NORMAL={sum(1 for _,l in train_pool if l==0)}  "
          f"PNEUMONIA={sum(1 for _,l in train_pool if l==1)}")

    print(f"\nDistribuție noduri (Dirichlet α):")
    print(f"  {'Nod':<8} {'Total':>6} {'NORMAL':>8} {'PNEUMONIA':>10} "
          f"{'Train':>7} {'Val':>5}")
    print(f"  {'-'*50}")
    for i, (node_all, node_train, node_val) in enumerate(
        zip(node_splits, node_train_splits, node_val_splits)
    ):
        normal = sum(1 for _, l in node_all if l == 0)
        pneumonia = sum(1 for _, l in node_all if l == 1)
        print(f"  node{i+1:<4} {len(node_all):>6} {normal:>8} {pneumonia:>10} "
              f"{len(node_train):>7} {len(node_val):>5}")
    print("=" * 60)


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pregătire split-uri fixe pentru experimentele Fed-Med-FL."
    )
    parser.add_argument(
        "--dataset-dir",
        default="central_dataset/chest_xray",
        help="Directorul rădăcină al dataset-ului chest_xray (default: central_dataset/chest_xray)",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/splits",
        help="Directorul de output pentru fișierele CSV (default: experiments/splits)",
    )
    parser.add_argument(
        "--storage-dir",
        default="storage",
        help="Directorul storage pentru copiere test_global.csv (default: storage)",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="Fracția pentru test_global (default: 0.15)",
    )
    parser.add_argument(
        "--num-nodes",
        type=int,
        default=5,
        help="Numărul de noduri FL (default: 5)",
    )
    parser.add_argument(
        "--dirichlet-alpha",
        type=float,
        default=2.0,
        help="Parametrul α pentru distribuția Dirichlet (default: 2.0)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.2,
        help="Fracția de validare per nod din datele locale (default: 0.2)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed pentru reproducibilitate (default: 42)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Suprascrie fișierele de split existente",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help=(
            "Rădăcina proiectului față de care se calculează path-urile relative "
            "în CSV-uri (recomandat: directorul curent). "
            "Dacă nu e specificat, se folosesc path-uri absolute."
        ),
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # ── Protecție la suprascriere ──────────────────────────────────────────
    expected_files = (
        [output_dir / "test_global.csv", output_dir / "train_pool.csv"]
        + [output_dir / f"node{i+1}_train.csv" for i in range(args.num_nodes)]
        + [output_dir / f"node{i+1}_val.csv" for i in range(args.num_nodes)]
    )

    if any(f.exists() for f in expected_files):
        if not args.force:
            print("WARN: Fișierele de split există deja.")
            print("      Folosește --force pentru a le suprascrie.")
            sys.exit(0)
        else:
            print("INFO: --force activ, se suprascriu fișierele existente.")

    # ── Colectare imagini ──────────────────────────────────────────────────
    print(f"\nColectare imagini din: {args.dataset_dir}")
    # Dacă --project-root nu e specificat, folosim directorul curent ca root
    project_root = args.project_root or str(Path.cwd())
    print(f"  Path-uri relative față de: {project_root}")
    all_samples = collect_images(args.dataset_dir, project_root=project_root)
    print(f"  Total imagini găsite: {len(all_samples)}")
    print(f"  NORMAL:    {sum(1 for _, l in all_samples if l == 0)}")
    print(f"  PNEUMONIA: {sum(1 for _, l in all_samples if l == 1)}")

    if len(all_samples) < 20:
        print("EROARE: Dataset prea mic (< 20 imagini).", file=sys.stderr)
        sys.exit(1)

    # ── Split stratificat test_global / train_pool ─────────────────────────
    print(f"\nSplit stratificat (test_ratio={args.test_ratio}, seed={args.seed})...")
    test_global, train_pool = stratified_split(all_samples, args.test_ratio, args.seed)
    print(f"  test_global: {len(test_global)} imagini")
    print(f"  train_pool:  {len(train_pool)} imagini")

    # ── Split Dirichlet pe noduri ──────────────────────────────────────────
    print(f"\nSplit Dirichlet (α={args.dirichlet_alpha}, {args.num_nodes} noduri)...")
    node_splits = dirichlet_split(
        train_pool, args.num_nodes, args.dirichlet_alpha, args.seed
    )

    # ── Split local train/val per nod ──────────────────────────────────────
    print(f"\nSplit local train/val per nod (val_ratio={args.val_ratio})...")
    node_train_splits: List[List[Sample]] = []
    node_val_splits: List[List[Sample]] = []
    for i, node_samples in enumerate(node_splits):
        train_local, val_local = local_train_val_split(
            node_samples, args.val_ratio, args.seed, i
        )
        node_train_splits.append(train_local)
        node_val_splits.append(val_local)
        print(f"  node{i+1}: {len(node_samples)} total → "
              f"{len(train_local)} train, {len(val_local)} val")

    # ── Salvare CSV-uri ────────────────────────────────────────────────────
    print(f"\nSalvare fișiere în {output_dir}/...")
    output_dir.mkdir(parents=True, exist_ok=True)

    save_csv(test_global, str(output_dir / "test_global.csv"))
    print(f"  ✓ test_global.csv ({len(test_global)} rânduri)")

    save_csv(train_pool, str(output_dir / "train_pool.csv"))
    print(f"  ✓ train_pool.csv ({len(train_pool)} rânduri)")

    for i in range(args.num_nodes):
        train_path = str(output_dir / f"node{i+1}_train.csv")
        val_path = str(output_dir / f"node{i+1}_val.csv")
        save_csv(node_train_splits[i], train_path)
        save_csv(node_val_splits[i], val_path)
        print(f"  ✓ node{i+1}_train.csv ({len(node_train_splits[i])} rânduri)")
        print(f"  ✓ node{i+1}_val.csv ({len(node_val_splits[i])} rânduri)")

    # ── Salvare data_distribution.json ────────────────────────────────────
    dist_path = str(output_dir / "data_distribution.json")
    save_distribution_json(test_global, train_pool, node_splits, dist_path)
    print(f"  ✓ data_distribution.json")

    # ── Copiere test_global în storage ────────────────────────────────────
    print(f"\nCopiere test_global.csv în {args.storage_dir}/...")
    copy_test_global(
        str(output_dir / "test_global.csv"),
        args.storage_dir,
        args.num_nodes,
    )

    # ── Sumar final ────────────────────────────────────────────────────────
    print_summary(test_global, train_pool, node_splits, node_train_splits, node_val_splits)
    print("\n✅ Pregătire date completă!")


if __name__ == "__main__":
    main()
