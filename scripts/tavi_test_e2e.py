#!/usr/bin/env python3
"""
tavi_test_e2e.py — Comparație distribuții de date cu FedAvg fix.

Rulează 4 sesiuni FL consecutive, toate cu FedAvg, fiecare cu o
distribuție diferită a datelor pe noduri:

  1. IID strict          — noduri cu același număr de imagini și aceeași
                           proporție NORMAL/PNEUMONIA
  2. Non-IID extrem (α=0.1) — Dirichlet cu α foarte mic, fiecare nod
                               se specializează pe o clasă
  3. Dezechilibru 75% pneumonie — un nod concentrează 75% din cazurile
                                   de pneumonie, celelalte împart restul
  4. Dezechilibru cantitativ   — proporții egale per nod, dar un nod
                                  are ~3x mai multe imagini decât ceilalți

Rezultatele se salvează în experiments_tavi/ (nu în experiments/).
Split-urile pentru fiecare distribuție se generează automat înainte
de antrenare în experiments_tavi/splits_{distribution_name}/.

Utilizare:
  python scripts/tavi_test_e2e.py

  # Sau cu parametri custom:
  python scripts/tavi_test_e2e.py  # editează constantele de mai jos
"""
import csv
import json
import os
import requests
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit


# ============================================================================
# PARAMETRI DE ANTRENARE — modifică după nevoie
# ============================================================================

NUM_ROUNDS      = 30
NUM_EPOCHS      = 3
MODEL_NAME      = "efficientnet_b0"
BATCH_SIZE      = 16
LEARNING_RATE   = 0.0005
OPTIMIZER       = "adam"
AGGREGATION     = "fedavg"

# ============================================================================
# DATE ȘI INFRASTRUCTURĂ
# ============================================================================

DATASET_DIR     = "central_dataset/chest_xray"
TEST_GLOBAL_CSV = "experiments/splits/test_global.csv"   # test global comun
EXPERIMENTS_DIR = "experiments_tavi"                      # output folder
SEED            = 42
NUM_NODES       = 4
VAL_RATIO       = 0.2    # fracție validare din datele locale ale fiecărui nod
TEST_RATIO      = 0.15   # fracție test_global (folosit dacă nu există deja)

# ============================================================================
# NODURI ȘI CENTRAL
# ============================================================================

CENTRAL_URL = "http://localhost:8081"

NODES = [
    {"name": "node1", "url": "http://localhost:8001",
     "email": "admin@node1.fed-med-fl.com", "password": "AdminNode1@2026"},
    {"name": "node2", "url": "http://localhost:8002",
     "email": "admin@node2.fed-med-fl.com", "password": "AdminNode2@2026"},
    {"name": "node3", "url": "http://localhost:8003",
     "email": "admin@node3.fed-med-fl.com", "password": "AdminNode3@2026"},
    {"name": "node4", "url": "http://localhost:8004",
     "email": "admin@node4.fed-med-fl.com", "password": "AdminNode4@2026"},
]

ADMIN_CENTRAL = {
    "email": "admin@central.fed-med-fl.com",
    "password": "AdminCentral@2026",
}

# ============================================================================
# TIMEOUT-URI
# ============================================================================

TIMEOUT          = 30
POLL_INTERVAL    = 5
SERVER_INIT_WAIT = 45
SERVER_STOP_WAIT = 300   # mai mare — sesiunile durează mai mult

# ============================================================================
# DISTRIBUȚII — definesc cum se împart datele pe noduri
# ============================================================================
# Fiecare distribuție e un dict cu:
#   label       : numele afișat
#   split_name  : numele folderului de splits
#   description : descriere pentru summary
# Logica de generare e în funcțiile de mai jos.

DISTRIBUTIONS = [
    {
        "label":       "IID strict",
        "split_name":  "iid_strict",
        "description": "Fiecare nod primește același număr de imagini cu aceeași "
                       "proporție NORMAL/PNEUMONIA (distribuție ideală).",
    },
    {
        "label":       "Non-IID extrem (Dirichlet α=0.1)",
        "split_name":  "noniid_extreme",
        "description": "Distribuție Dirichlet cu α=0.1 — fiecare nod se specializează "
                       "aproape complet pe o singură clasă.",
    },
    {
        "label":       "Concentrare pneumonie (75% la node1)",
        "split_name":  "pneumonia_concentration",
        "description": "Node1 primește 75% din toate cazurile de pneumonie. "
                       "Celelalte 3 noduri împart restul de 25% plus toate cazurile NORMAL.",
    },
    {
        "label":       "Dezechilibru cantitativ (node1 = 3x)",
        "split_name":  "quantity_imbalance",
        "description": "Proporții NORMAL/PNEUMONIA egale per nod, dar node1 are "
                       "de ~3x mai multe imagini decât fiecare din celelalte noduri.",
    },
]


# ============================================================================
# Tipuri
# ============================================================================

Sample = Tuple[str, int]   # (filepath, label)


# ============================================================================
# Logging
# ============================================================================

def log(message: str, level: str = "INFO") -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {message}", flush=True)


def log_banner(text: str) -> None:
    log("=" * 80)
    log(text)
    log("=" * 80)


# ============================================================================
# Colectare imagini
# ============================================================================

def collect_images(dataset_dir: str) -> List[Sample]:
    """Parcurge dataset-ul și returnează toate imaginile ca (filepath, label)."""
    dataset_path = Path(dataset_dir).resolve()
    if not dataset_path.exists():
        log(f"Dataset nu există: {dataset_path}", "ERROR")
        sys.exit(1)

    root = Path.cwd()
    samples: List[Sample] = []
    extensions = {".jpeg", ".jpg", ".png"}

    for split_dir in sorted(dataset_path.iterdir()):
        if not split_dir.is_dir() or split_dir.name.startswith(("_", ".")):
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
                continue
            for img_file in sorted(class_dir.iterdir()):
                if img_file.suffix.lower() in extensions:
                    try:
                        filepath = str(img_file.resolve().relative_to(root))
                    except ValueError:
                        filepath = str(img_file.resolve())
                    samples.append((filepath, label))

    if not samples:
        log(f"Nu s-au găsit imagini în {dataset_path}", "ERROR")
        sys.exit(1)

    return samples


# ============================================================================
# Funcții utilitare split
# ============================================================================

def save_csv(rows: List[Sample], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
        writer.writeheader()
        for filepath, label in rows:
            writer.writerow({"filepath": filepath, "label": label})


def local_train_val_split(
    node_samples: List[Sample],
    val_ratio: float,
    seed: int,
    node_idx: int,
) -> Tuple[List[Sample], List[Sample]]:
    """Split stratificat train/val local per nod.
    Dacă un nod are prea puține sample-uri dintr-o clasă pentru split stratificat
    (cazul Non-IID extrem), face split simplu aleatoriu.
    """
    if len(node_samples) < 2:
        return node_samples, []

    labels = [l for _, l in node_samples]
    unique_labels = set(labels)

    # Split simplu dacă: o singură clasă SAU orice clasă are < 2 membri
    min_class_count = min(labels.count(l) for l in unique_labels)
    if len(unique_labels) < 2 or min_class_count < 2:
        rng = np.random.default_rng(seed + node_idx + 1000)
        indices = list(range(len(node_samples)))
        rng.shuffle(indices)
        split_idx = max(1, int(len(node_samples) * (1 - val_ratio)))
        train_idx = sorted(indices[:split_idx])
        val_idx   = sorted(indices[split_idx:])
        return ([node_samples[i] for i in train_idx],
                [node_samples[i] for i in val_idx])

    indices = list(range(len(node_samples)))
    splitter = StratifiedShuffleSplit(
        n_splits=1, test_size=val_ratio, random_state=seed + node_idx + 1000
    )
    train_idx, val_idx = next(splitter.split(indices, labels))
    return ([node_samples[i] for i in sorted(train_idx)],
            [node_samples[i] for i in sorted(val_idx)])


def save_splits(
    node_splits: List[List[Sample]],
    output_dir: Path,
    val_ratio: float,
    seed: int,
) -> None:
    """Salvează CSV-urile train/val pentru fiecare nod."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, node_samples in enumerate(node_splits):
        train, val = local_train_val_split(node_samples, val_ratio, seed, i)
        save_csv(train, str(output_dir / f"node{i+1}_train.csv"))
        save_csv(val,   str(output_dir / f"node{i+1}_val.csv"))
        normal     = sum(1 for _, l in node_samples if l == 0)
        pneumonia  = sum(1 for _, l in node_samples if l == 1)
        log(f"  node{i+1}: {len(node_samples)} total "
            f"(NORMAL={normal}, PNEUMONIA={pneumonia}) → "
            f"{len(train)} train, {len(val)} val")

    # Salvează și distribuția
    dist = {
        f"node{i+1}": {
            "total": len(s),
            "normal": sum(1 for _, l in s if l == 0),
            "pneumonia": sum(1 for _, l in s if l == 1),
        }
        for i, s in enumerate(node_splits)
    }
    with open(output_dir / "data_distribution.json", "w") as f:
        json.dump(dist, f, indent=2)


# ============================================================================
# Generatoare de distribuții
# ============================================================================

def _ensure_min_per_class(
    node_splits: List[List[Sample]],
    train_pool: List[Sample],
    min_samples: int = 10,
    seed: int = 42,
) -> List[List[Sample]]:
    """
    Garantează că fiecare nod are cel puțin `min_samples` din fiecare clasă.
    Dacă un nod are prea puțin dintr-o clasă, ia sample-uri de la nodurile
    cu surplus, fără a duplica date.

    Această funcție e apelată după orice generator de distribuție.
    """
    rng = np.random.default_rng(seed + 9999)

    # Grupează sample-urile din train_pool pe clase (pool de rezervă)
    pool_by_class: Dict[int, List[Sample]] = {0: [], 1: []}
    assigned = set()
    for node_samples in node_splits:
        for s in node_samples:
            assigned.add(s[0])  # filepath

    # Pool de rezervă = sample-uri din train_pool nefolosite încă
    reserve: Dict[int, List[Sample]] = {0: [], 1: []}
    for s in train_pool:
        if s[0] not in assigned:
            reserve[s[1]].append(s)
    for cls in reserve:
        rng.shuffle(reserve[cls])

    result = [list(node) for node in node_splits]

    for i, node_samples in enumerate(result):
        for cls in [0, 1]:
            cls_count = sum(1 for _, l in node_samples if l == cls)
            deficit = min_samples - cls_count
            if deficit <= 0:
                continue

            # Încearcă să ia din rezervă
            available = reserve[cls]
            take = min(deficit, len(available))
            if take > 0:
                result[i].extend(available[:take])
                reserve[cls] = available[take:]
                deficit -= take

            if deficit > 0:
                # Ia de la nodul cu cel mai mare surplus din acea clasă
                donor_idx = max(
                    (j for j in range(len(result)) if j != i),
                    key=lambda j: sum(1 for _, l in result[j] if l == cls),
                    default=None,
                )
                if donor_idx is not None:
                    donor_cls = [s for s in result[donor_idx] if s[1] == cls]
                    take2 = min(deficit, len(donor_cls) - min_samples)
                    if take2 > 0:
                        # Mută sample-uri de la donor la nodul curent
                        to_move = donor_cls[:take2]
                        result[i].extend(to_move)
                        move_set = {s[0] for s in to_move}
                        result[donor_idx] = [s for s in result[donor_idx]
                                             if s[0] not in move_set]

    return result

def gen_iid_strict(
    train_pool: List[Sample], num_nodes: int, seed: int
) -> List[List[Sample]]:
    """
    IID strict: fiecare nod primește exact aceeași proporție de clase
    și aproximativ același număr de imagini.
    """
    rng = np.random.default_rng(seed)

    normal    = [s for s in train_pool if s[1] == 0]
    pneumonia = [s for s in train_pool if s[1] == 1]

    normal_arr = list(normal)
    pneum_arr  = list(pneumonia)
    rng.shuffle(normal_arr)
    rng.shuffle(pneum_arr)

    nodes = [[] for _ in range(num_nodes)]
    for cls_list in [normal_arr, pneum_arr]:
        chunk = len(cls_list) // num_nodes
        for i in range(num_nodes):
            start = i * chunk
            end   = start + chunk if i < num_nodes - 1 else len(cls_list)
            nodes[i].extend(cls_list[start:end])

    return _ensure_min_per_class(nodes, train_pool, min_samples=50, seed=seed)


def gen_noniid_extreme(
    train_pool: List[Sample], num_nodes: int, alpha: float, seed: int
) -> List[List[Sample]]:
    """
    Non-IID extrem: distribuție Dirichlet cu α foarte mic (0.1).
    Fiecare nod se specializează aproape complet pe o clasă,
    dar garantăm cel puțin 10 sample-uri din fiecare clasă per nod.
    """
    rng = np.random.default_rng(seed)

    class_indices: Dict[int, List[int]] = {}
    for idx, (_, label) in enumerate(train_pool):
        class_indices.setdefault(label, []).append(idx)

    node_indices: List[List[int]] = [[] for _ in range(num_nodes)]

    for label, indices in class_indices.items():
        indices_arr = np.array(indices)
        rng_local = np.random.default_rng(seed + label)
        rng_local.shuffle(indices_arr)

        proportions = rng.dirichlet(alpha * np.ones(num_nodes))
        sizes = (proportions * len(indices_arr)).astype(int)
        diff = len(indices_arr) - sizes.sum()
        for i in range(abs(diff)):
            if diff > 0:
                sizes[i % num_nodes] += 1
            else:
                sizes[i % num_nodes] = max(0, sizes[i % num_nodes] - 1)

        start = 0
        for node_idx, size in enumerate(sizes):
            node_indices[node_idx].extend(indices_arr[start:start + size].tolist())
            start += size

    nodes = [[train_pool[i] for i in sorted(idxs)] for idxs in node_indices]
    return _ensure_min_per_class(nodes, train_pool, min_samples=50, seed=seed)


def gen_pneumonia_concentration(
    train_pool: List[Sample], num_nodes: int, seed: int,
    concentration_ratio: float = 0.75,
) -> List[List[Sample]]:
    """
    Concentrare pneumonie: node1 primește `concentration_ratio` (75%) din
    toate cazurile de pneumonie. Restul de pneumonii se împart egal între
    celelalte noduri. Cazurile NORMAL se împart egal între toate nodurile.
    """
    rng = np.random.default_rng(seed)

    normal    = [s for s in train_pool if s[1] == 0]
    pneumonia = [s for s in train_pool if s[1] == 1]

    normal_arr = list(normal)
    pneum_arr  = list(pneumonia)
    rng.shuffle(normal_arr)
    rng.shuffle(pneum_arr)

    nodes: List[List[Sample]] = [[] for _ in range(num_nodes)]

    n_pneum_node1 = int(len(pneum_arr) * concentration_ratio)
    nodes[0].extend(pneum_arr[:n_pneum_node1])
    remaining_pneum = pneum_arr[n_pneum_node1:]

    others = num_nodes - 1
    chunk_p = len(remaining_pneum) // others
    for i in range(1, num_nodes):
        start = (i - 1) * chunk_p
        end   = start + chunk_p if i < num_nodes - 1 else len(remaining_pneum)
        nodes[i].extend(remaining_pneum[start:end])

    chunk_n = len(normal_arr) // num_nodes
    for i in range(num_nodes):
        start = i * chunk_n
        end   = start + chunk_n if i < num_nodes - 1 else len(normal_arr)
        nodes[i].extend(normal_arr[start:end])

    return _ensure_min_per_class(nodes, train_pool, min_samples=50, seed=seed)


def gen_quantity_imbalance(
    train_pool: List[Sample], num_nodes: int, seed: int,
    imbalance_ratio: float = 3.0,
) -> List[List[Sample]]:
    """
    Dezechilibru cantitativ: proporții NORMAL/PNEUMONIA egale per nod,
    dar node1 are imbalance_ratio × mai multe imagini decât fiecare alt nod.
    """
    rng = np.random.default_rng(seed)

    normal    = [s for s in train_pool if s[1] == 0]
    pneumonia = [s for s in train_pool if s[1] == 1]

    normal_arr = list(normal)
    pneum_arr  = list(pneumonia)
    rng.shuffle(normal_arr)
    rng.shuffle(pneum_arr)

    weights = np.array([imbalance_ratio] + [1.0] * (num_nodes - 1))
    proportions = weights / weights.sum()

    nodes: List[List[Sample]] = [[] for _ in range(num_nodes)]

    for cls_list in [normal_arr, pneum_arr]:
        sizes = (proportions * len(cls_list)).astype(int)
        diff = len(cls_list) - sizes.sum()
        for i in range(abs(diff)):
            if diff > 0:
                sizes[i % num_nodes] += 1
            else:
                sizes[i % num_nodes] = max(0, sizes[i % num_nodes] - 1)

        start = 0
        for i, size in enumerate(sizes):
            nodes[i].extend(cls_list[start:start + size])
            start += size

    return _ensure_min_per_class(nodes, train_pool, min_samples=50, seed=seed)


# ============================================================================
# Generare splits pentru o distribuție
# ============================================================================

def generate_splits_for_distribution(
    dist: Dict,
    train_pool: List[Sample],
    base_output_dir: str,
) -> str:
    """
    Generează split-urile pentru o distribuție și returnează calea folderului.
    """
    split_dir = Path(base_output_dir) / f"splits_{dist['split_name']}"

    # Evită regenerarea dacă există deja
    if (split_dir / f"node1_train.csv").exists():
        log(f"  Split-uri existente pentru {dist['label']} — le refolosim")
        return str(split_dir)

    log(f"  Generare split-uri: {dist['label']}")

    split_name = dist["split_name"]
    if split_name == "iid_strict":
        node_splits = gen_iid_strict(train_pool, NUM_NODES, SEED)
    elif split_name == "noniid_extreme":
        node_splits = gen_noniid_extreme(train_pool, NUM_NODES, alpha=0.1, seed=SEED)
    elif split_name == "pneumonia_concentration":
        node_splits = gen_pneumonia_concentration(train_pool, NUM_NODES, SEED)
    elif split_name == "quantity_imbalance":
        node_splits = gen_quantity_imbalance(train_pool, NUM_NODES, SEED)
    else:
        log(f"Distribuție necunoscută: {split_name}", "ERROR")
        sys.exit(1)

    save_splits(node_splits, split_dir, VAL_RATIO, SEED)
    return str(split_dir)


# ============================================================================
# Stare internă autentificare
# ============================================================================

_tokens: Dict[str, str] = {}


# ============================================================================
# Service checks
# ============================================================================

def check_service(url: str, name: str, is_node: bool = False) -> bool:
    endpoint = "/api/health" if is_node else "/health"
    try:
        r = requests.get(f"{url}{endpoint}", timeout=TIMEOUT)
        if r.status_code == 200:
            log(f"✓ {name} disponibil")
            return True
        log(f"✗ {name} a returnat {r.status_code}", "ERROR")
    except Exception as e:
        log(f"✗ {name} inaccesibil: {e}", "ERROR")
    return False


def check_all_services() -> bool:
    results = [check_service(CENTRAL_URL, "Central", is_node=False)]
    for node in NODES:
        results.append(check_service(node["url"], node["name"], is_node=True))
    return all(results)


# ============================================================================
# Autentificare
# ============================================================================

def login(node: Dict) -> bool:
    try:
        r = requests.post(
            f"{node['url']}/api/auth/login",
            data={"username": node["email"], "password": node["password"]},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            token = r.json().get("access_token")
            if token:
                _tokens[node["name"]] = token
                log(f"✓ Login {node['name']}")
                return True
        log(f"✗ Login eșuat {node['name']}: {r.status_code}", "ERROR")
    except Exception as e:
        log(f"✗ Eroare login {node['name']}: {e}", "ERROR")
    return False


def login_central_on_node(node: Dict) -> bool:
    try:
        r = requests.post(
            f"{node['url']}/api/auth/login",
            data={"username": ADMIN_CENTRAL["email"], "password": ADMIN_CENTRAL["password"]},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            token = r.json().get("access_token")
            if token:
                _tokens[f"central_{node['name']}"] = token
                log(f"✓ Login admin_central pe {node['name']}")
                return True
        log(f"✗ Login admin_central eșuat pe {node['name']}: {r.status_code}", "ERROR")
    except Exception as e:
        log(f"✗ Eroare login admin_central pe {node['name']}: {e}", "ERROR")
    return False


def login_all() -> bool:
    log("Autentificare pe toate nodurile...")
    ok = all(login(node) for node in NODES)
    ok = ok and all(login_central_on_node(node) for node in NODES)
    return ok


def auth_headers(node_name: str) -> Dict[str, str]:
    token = _tokens.get(node_name)
    return {"Authorization": f"Bearer {token}"} if token else {}


def auth_headers_central(node_name: str) -> Dict[str, str]:
    token = _tokens.get(f"central_{node_name}")
    return {"Authorization": f"Bearer {token}"} if token else {}


# ============================================================================
# Dataset management
# ============================================================================

def get_active_dataset(node: Dict) -> Optional[str]:
    try:
        r = requests.get(
            f"{node['url']}/api/data/active",
            headers=auth_headers(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            active = r.json().get("active_dataset")
            if active:
                return active.get("dataset_id")
    except Exception:
        pass
    return None


def activate_first_dataset(node: Dict) -> bool:
    try:
        r = requests.get(
            f"{node['url']}/api/data/list",
            headers=auth_headers(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code != 200 or not r.json():
            log(f"✗ Niciun dataset pe {node['name']}", "ERROR")
            return False
        dataset_id = r.json()[0].get("dataset_id")
        activate = requests.post(
            f"{node['url']}/api/data/set-active/{dataset_id}",
            headers=auth_headers(node["name"]),
            timeout=TIMEOUT,
        )
        if activate.status_code == 200:
            log(f"✓ Dataset activat pe {node['name']}: {dataset_id}")
        return True
    except Exception as e:
        log(f"✗ Eroare activare dataset {node['name']}: {e}", "ERROR")
        return False


# ============================================================================
# Flower Server lifecycle
# ============================================================================

def is_flower_running() -> bool:
    try:
        r = requests.get(f"{CENTRAL_URL}/flower/status", timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json().get("flower_server_running", False)
    except Exception:
        pass
    return False


def wait_for_flower_to_stop(max_wait: int = SERVER_STOP_WAIT) -> bool:
    log(f"Aștept oprirea Flower Server (max {max_wait}s)...")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if not is_flower_running():
            log("✓ Flower Server oprit")
            return True
        time.sleep(5)
    log("⚠ Flower Server nu s-a oprit în timp util", "WARNING")
    return False


def force_stop_flower_server() -> bool:
    if not is_flower_running():
        return True
    log("Force-stop Flower Server...")
    try:
        r = requests.post(f"{CENTRAL_URL}/api/fl/stop", timeout=TIMEOUT)
        if r.status_code == 200:
            log("✓ Flower Server oprit forțat")
            # Așteptăm până la 15s ca portul să fie eliberat
            deadline = time.time() + 15
            while time.time() < deadline:
                time.sleep(2)
                if not is_flower_running():
                    log("✓ Port 8080 eliberat")
                    return True
            log("⚠ Portul 8080 nu s-a eliberat în 15s", "WARNING")
            return not is_flower_running()
    except Exception:
        pass
    deadline = time.time() + 10
    while time.time() < deadline:
        if not is_flower_running():
            return True
        time.sleep(2)
    log("⚠ Nu s-a putut opri Flower Server", "WARNING")
    return False


def start_flower_server(run_id: str, experiments_dir: str, test_global_csv: str) -> bool:
    log(f"Pornire Flower Server — strategy: {AGGREGATION.upper()}")
    params = {
        "num_rounds":            NUM_ROUNDS,
        "num_epochs":            NUM_EPOCHS,
        "model_name":            MODEL_NAME,
        "learning_rate":         LEARNING_RATE,
        "optimizer":             OPTIMIZER,
        "min_fit_clients":       NUM_NODES,
        "min_available_clients": NUM_NODES,
        "aggregation_strategy":  AGGREGATION,
        "run_id":                run_id,
        "experiments_dir":       experiments_dir,
        "test_global_csv":       test_global_csv,
    }
    try:
        r = requests.post(f"{CENTRAL_URL}/api/fl/start", params=params, timeout=TIMEOUT)
        if r.status_code == 200:
            result = r.json()
            if result.get("status") == "already_running":
                log("⚠ Flower Server deja rulează", "WARNING")
                return False
            log("✓ Flower Server pornit")
            log(f"  Aștept ca Flower Server să fie gata (max {SERVER_INIT_WAIT}s)...")
            start_wait = time.time()
            deadline = start_wait + SERVER_INIT_WAIT
            while time.time() < deadline:
                time.sleep(2)
                try:
                    status_r = requests.get(f"{CENTRAL_URL}/flower/status", timeout=5)
                    if status_r.status_code == 200 and status_r.json().get("flower_server_running"):
                        elapsed = time.time() - start_wait
                        log(f"  ✓ Flower Server gata după {elapsed:.0f}s")
                        time.sleep(3)
                        return True
                except Exception:
                    pass
            log(f"  ⚠ Flower Server nu a răspuns în {SERVER_INIT_WAIT}s, continuăm", "WARNING")
            return True
        log(f"✗ Start Flower eșuat: {r.status_code} — {r.text}", "ERROR")
    except Exception as e:
        log(f"✗ Eroare start Flower: {e}", "ERROR")
    return False


# ============================================================================
# Training
# ============================================================================

def start_training(node: Dict, dataset_id: str, splits_dir: str) -> Optional[str]:
    try:
        r = requests.post(
            f"{node['url']}/api/federated/train",
            params={
                "dataset_id": dataset_id,
                "model_name": MODEL_NAME,
                "batch_size": BATCH_SIZE,
                "splits_dir": splits_dir,
            },
            headers=auth_headers_central(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            job_id = r.json().get("job_id")
            log(f"✓ Training pornit pe {node['name']} — job_id: {job_id}")
            return job_id
        log(f"✗ Start training eșuat pe {node['name']}: {r.text}", "ERROR")
    except Exception as e:
        log(f"✗ Eroare start training {node['name']}: {e}", "ERROR")
    return None


def start_training_all(splits_dir: str) -> Optional[Dict[str, str]]:
    log("Pornire training federat pe toate nodurile...")
    job_ids: Dict[str, str] = {}
    for node in NODES:
        dataset_id = get_active_dataset(node)
        if not dataset_id:
            log(f"✗ Niciun dataset activ pe {node['name']}", "ERROR")
            return None
        job_id = start_training(node, dataset_id, splits_dir)
        if not job_id:
            return None
        job_ids[node["name"]] = job_id
    return job_ids


# ============================================================================
# Monitorizare
# ============================================================================

def get_job_status(node: Dict, job_id: str) -> Optional[str]:
    try:
        r = requests.get(
            f"{node['url']}/api/federated/status/{job_id}",
            headers=auth_headers_central(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json().get("status", "unknown")
    except Exception:
        pass
    return None


def monitor_training(job_ids: Dict[str, str]) -> bool:
    node_map = {node["name"]: node for node in NODES}
    start_time = time.time()
    consecutive_completed = 0
    consecutive_errors = 0
    REQUIRED_CONFIRMATIONS = 3
    MAX_ERRORS = 10

    while True:
        elapsed = time.time() - start_time
        statuses: Dict[str, str] = {}
        all_reachable = True

        for name, job_id in job_ids.items():
            status = get_job_status(node_map[name], job_id)
            if status is None:
                all_reachable = False
                statuses[name] = "?"
            else:
                statuses[name] = status

        status_str = " | ".join(f"{n}: {s}" for n, s in statuses.items())
        log(f"{status_str} | {elapsed:.0f}s")

        if not all_reachable:
            consecutive_errors += 1
            consecutive_completed = 0
            if consecutive_errors >= MAX_ERRORS:
                log("⚠ Prea multe răspunsuri lipsă — presupunem completat", "WARNING")
                return True
            time.sleep(POLL_INTERVAL)
            continue

        consecutive_errors = 0
        failed = [n for n, s in statuses.items() if s == "failed"]
        if failed:
            log(f"✗ Training eșuat pe: {', '.join(failed)}", "ERROR")
            return False

        if all(s == "completed" for s in statuses.values()):
            consecutive_completed += 1
            if consecutive_completed >= REQUIRED_CONFIRMATIONS:
                log(f"✓ Toate {len(job_ids)} noduri au completat!")
                return True
            log(f"  Confirmare... ({consecutive_completed}/{REQUIRED_CONFIRMATIONS})")
        else:
            consecutive_completed = 0

        time.sleep(POLL_INTERVAL)


# ============================================================================
# Generare run_id
# ============================================================================

def generate_run_id(dist_label: str, experiments_dir: str) -> str:
    """
    Generează run_id cu format: dist_{split_name}_run{NN}
    """
    # Normalizează label-ul pentru folder name
    clean = dist_label.lower()
    for ch in " ()=.α/":
        clean = clean.replace(ch, "_")
    while "__" in clean:
        clean = clean.replace("__", "_")
    clean = clean.strip("_")
    prefix = f"dist_{clean}_run"

    exp_dir = Path(experiments_dir)
    existing = []
    if exp_dir.exists():
        for d in exp_dir.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                existing.append(d.name)
    nn = len(existing) + 1
    return f"{prefix}{nn:02d}"


# ============================================================================
# Verificare outputs
# ============================================================================

def verify_outputs(run_id: str, experiments_dir: str) -> bool:
    exp_dir = Path(experiments_dir) / run_id
    required = (
        [exp_dir / "run_config.json", exp_dir / "central" / "metrics_by_round.csv"]
        + [exp_dir / "nodes" / f"node{i}_metrics_by_round.csv" for i in range(1, NUM_NODES + 1)]
    )
    missing = [str(f) for f in required if not f.exists()]
    for m in missing:
        log(f"  ⚠ Lipsă: {m}", "WARNING")
    return len(missing) == 0


# ============================================================================
# Runner per sesiune
# ============================================================================

def run_session(
    session_num: int,
    dist: Dict,
    splits_dir: str,
    experiments_dir: str,
    test_global_csv: str,
) -> Tuple[bool, str]:
    """Rulează o sesiune completă pentru o distribuție. Returnează (success, run_id)."""

    log_banner(
        f"SESIUNEA {session_num}/{len(DISTRIBUTIONS)}: {dist['label']}\n"
        f"  {dist['description']}"
    )

    # Path-ul intern Docker — experiments_tavi e montat la /experiments_tavi în containere
    abs_splits_dir = "/experiments_tavi/" + Path(splits_dir).name

    # 2. Generează run_id — folosim EXPERIMENTS_DIR local (host) pentru numărare
    run_id = generate_run_id(dist["label"], EXPERIMENTS_DIR)
    log(f"  run_id: {run_id}")

    # 3. Pornește Flower Server
    if not start_flower_server(run_id, experiments_dir, test_global_csv):
        log(f"✗ Sesiunea {session_num} anulată — Flower Server nu a pornit", "ERROR")
        return False, run_id

    log(f"  Aștept {SERVER_INIT_WAIT}s inițializare server...")
    time.sleep(SERVER_INIT_WAIT)

    # 4. Pornește training pe toate nodurile
    job_ids = start_training_all(abs_splits_dir)
    if not job_ids:
        log(f"✗ Sesiunea {session_num} anulată — training nu a pornit", "ERROR")
        return False, run_id

    # 5. Monitorizare
    success = monitor_training(job_ids)

    if success:
        log(f"✓ Sesiunea {session_num} ({dist['label']}) COMPLETATĂ")
    else:
        log(f"✗ Sesiunea {session_num} ({dist['label']}) EȘUATĂ", "ERROR")
        force_stop_flower_server()

    return success, run_id


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    log_banner(
        f"Fed-Med-FL — Comparație Distribuții de Date\n"
        f"  Strategie:  {AGGREGATION.upper()}\n"
        f"  Runde:      {NUM_ROUNDS}\n"
        f"  Epoci:      {NUM_EPOCHS}\n"
        f"  Batch:      {BATCH_SIZE}\n"
        f"  LR:         {LEARNING_RATE}\n"
        f"  Model:      {MODEL_NAME}\n"
        f"  Noduri:     {NUM_NODES}\n"
        f"  Output:     {EXPERIMENTS_DIR}"
    )
    for i, d in enumerate(DISTRIBUTIONS, 1):
        log(f"  {i}. {d['label']}")

    # ── Verificare servicii ─────────────────────────────────────────────────
    log("\n[SETUP 1] Verificare servicii...")
    if not check_all_services():
        log("✗ Nu toate serviciile sunt disponibile.", "ERROR")
        sys.exit(1)

    # ── Autentificare ───────────────────────────────────────────────────────
    log("\n[SETUP 2] Autentificare...")
    if not login_all():
        log("✗ Autentificare eșuată.", "ERROR")
        sys.exit(1)

    # ── Activare datasets ───────────────────────────────────────────────────
    log("\n[SETUP 3] Activare datasets...")
    if not all(activate_first_dataset(node) for node in NODES):
        log("✗ Activare dataset eșuată.", "ERROR")
        sys.exit(1)

    # ── Pregătire date comune ───────────────────────────────────────────────
    log("\n[SETUP 4] Colectare imagini din dataset...")
    all_samples = collect_images(DATASET_DIR)
    log(f"  Total: {len(all_samples)} "
        f"(NORMAL={sum(1 for _,l in all_samples if l==0)}, "
        f"PNEUMONIA={sum(1 for _,l in all_samples if l==1)})")

    # Verifică test_global existent
    test_global_path = Path(TEST_GLOBAL_CSV)
    if not test_global_path.exists():
        log(f"  WARN: {TEST_GLOBAL_CSV} nu există — generez din dataset", "WARNING")
        splitter = StratifiedShuffleSplit(n_splits=1, test_size=TEST_RATIO, random_state=SEED)
        labels = [l for _, l in all_samples]
        indices = list(range(len(all_samples)))
        train_idx, test_idx = next(splitter.split(indices, labels))
        test_global = [all_samples[i] for i in sorted(test_idx)]
        train_pool  = [all_samples[i] for i in sorted(train_idx)]
        Path(TEST_GLOBAL_CSV).parent.mkdir(parents=True, exist_ok=True)
        save_csv(test_global, TEST_GLOBAL_CSV)
        log(f"  ✓ test_global.csv generat: {len(test_global)} imagini")
    else:
        # Citește test_global și reconstruiește train_pool ca diferență
        with open(test_global_path, "r") as f:
            test_files = {row["filepath"] for row in csv.DictReader(f)}
        train_pool = [s for s in all_samples if s[0] not in test_files]
        log(f"  ✓ test_global existent: {len(test_files)} imagini")

    log(f"  train_pool: {len(train_pool)} imagini disponibile pentru noduri")

    # Asigură că test_global e accesibil în experiments_tavi
    Path(EXPERIMENTS_DIR).mkdir(parents=True, exist_ok=True)
    tavi_test_csv = str(Path(EXPERIMENTS_DIR) / "test_global.csv")
    if not Path(tavi_test_csv).exists():
        shutil.copy2(TEST_GLOBAL_CSV, tavi_test_csv)
        log(f"  ✓ Copiat test_global.csv în {tavi_test_csv}")

    # ── Generare TOATE split-urile înainte de orice antrenare ───────────────
    log("\n[SETUP 5] Generare split-uri pentru toate distribuțiile...")
    all_splits_dirs: Dict[str, str] = {}
    for dist in DISTRIBUTIONS:
        splits_dir = generate_splits_for_distribution(dist, train_pool, EXPERIMENTS_DIR)
        all_splits_dirs[dist["split_name"]] = splits_dir
        log(f"  ✓ {dist['label']} → {splits_dir}")
    log("  Toate split-urile sunt gata — antrenarea poate începe.")

    # ── Rulare sesiuni ──────────────────────────────────────────────────────

    results: Dict[str, Tuple[bool, str]] = {}

    for i, session in enumerate(DISTRIBUTIONS, 1):
        if i > 1:
            log(f"\nAștept oprirea Flower Server înainte de sesiunea {i}...")
            if not wait_for_flower_to_stop():
                log("⚠ Server nu s-a oprit — force stop...", "WARNING")
                force_stop_flower_server()

        success, run_id = run_session(
            i, session, all_splits_dirs[session["split_name"]],
            EXPERIMENTS_DIR, tavi_test_csv
        )
        results[session["label"]] = (success, run_id)

        if not success:
            log(f"\n⚠ Sesiunea {i} eșuată — continuăm cu restul", "WARNING")

    # ── Sumar final ─────────────────────────────────────────────────────────

    log_banner("REZULTATE FINALE")
    all_passed = True
    for label, (passed, run_id) in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        log(f"  {status}  —  {label} ({run_id})")
        if not passed:
            all_passed = False

    log_banner("VERIFICARE FIȘIERE OUTPUT")
    for label, (passed, run_id) in results.items():
        if passed:
            ok = verify_outputs(run_id, EXPERIMENTS_DIR)
            log(f"  {'✓ OK' if ok else '⚠ LIPSĂ'}  —  {label} ({run_id})")

    log_banner("COMANDĂ GENERATE PLOTS")
    run_ids = {DISTRIBUTIONS[i]["split_name"]: run_id
               for i, (label, (passed, run_id)) in enumerate(results.items()) if passed}
    if run_ids:
        cmd_parts = [".venv/bin/python scripts/generate_plots.py"]
        # Mapare split_name → argument generate_plots (folosim fedavg pt toate)
        for split_name, run_id in run_ids.items():
            # Adaugă ca --fedavg pentru primul, restul sunt afișate manual
            cmd_parts.append(f"    # {split_name}: {EXPERIMENTS_DIR}/{run_id}")
        log("  Rulează generate_plots separat pentru fiecare run_id de mai sus.")
        log("  (scriptul de plots compară strategii, nu distribuții —")
        log("   analizează metrics_by_round.csv direct sau extinde generate_plots.py)")
    log("")
    if all_passed:
        log("✓✓✓ TOATE SESIUNILE COMPLETATE ✓✓✓")
        sys.exit(0)
    else:
        log("✗✗✗ UNA SAU MAI MULTE SESIUNI AU EȘUAT ✗✗✗", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
