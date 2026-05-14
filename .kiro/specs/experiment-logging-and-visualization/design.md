# Document de Design Tehnic: Experiment Logging and Visualization

## Prezentare Generală

Acest document descrie arhitectura tehnică pentru adăugarea infrastructurii complete de logging, colectare metrici și generare grafice în platforma Fed-Med-FL. Scopul este compararea unui model centralizat cu trei variante FL (FedAvg, FedAvgM, FedProx) pe 5 noduri, pentru o lucrare de disertație despre clasificarea imaginilor Chest X-Ray (NORMAL vs PNEUMONIA) cu EfficientNet-B0.

### Decizii de design fixate

- **Threshold**: fix 0.5 pentru tabelul comparativ; threshold optim pe val raportat ca referință
- **Non-IID**: distribuție Dirichlet α=2.0, seed 42
- **test_global**: 15% stratificat din dataset total, copiat în `storage/central` și `storage/node{1-5}`
- **Evaluare test_global**: în `FL_Strategy.aggregate_fit()`, pe central, după fiecare rundă
- **Weights salvate**: la fiecare rundă FL
- **Notebook centralizat**: rămâne `.ipynb`

### Fișiere implicate (ordine de implementare)

| # | Fișier | Tip |
|---|--------|-----|
| 1 | `scripts/prepare_experiment_data.py` | NOU |
| 2 | `shared/python/node_core/node_core/flower_strategy.py` | MODIFICAT |
| 3 | `services/node/worker/app/flower_client.py` | MODIFICAT |
| 4 | `services/central/app/flower_server.py` | MODIFICAT minor |
| 5 | `services/central/app/main.py` | MODIFICAT minor |
| 6 | `services/node/api/app/tasks.py` | MODIFICAT minor |
| 7 | `chest-x-ray-pneumonia-detection-with-deep-learning.ipynb` | MODIFICAT |
| 8 | `scripts/test_e2e_5nodes.py` | MODIFICAT |
| 9 | `scripts/generate_plots.py` | NOU |


---

## Arhitectură

### Flux de date general

```
central_dataset/chest_xray/
        |
        v
scripts/prepare_experiment_data.py
        |
        +---> experiments/splits/
        |       test_global.csv        (15%, stratificat, seed=42)
        |       train_pool.csv         (85%)
        |       node{1-5}_train.csv    (Dirichlet α=2.0)
        |       node{1-5}_val.csv      (20% din fiecare nod)
        |       data_distribution.json
        |
        +---> storage/central/test_global.csv
              storage/node{1-5}/test_global.csv

Antrenare centralizată (notebook):
        train_pool.csv
              |
              v
        80/20 stratificat
              |
        EfficientNet-B0 training (seed=42)
              |
        experiments/centralized_effb0_run01/
              run_config.json
              metrics_by_epoch.csv
              artifacts/best_model/
                weights.pt, model_hash.txt
                predictions_test.csv, confusion_matrix.json

Antrenare FL (Flower, 3 strategii):
        node{N}_train.csv + node{N}_val.csv
              |
        FedMedClient.fit() [per nod, per rundă]
              |
        FedMedStrategy.aggregate_fit() [central]
              |
        evaluare pe test_global [central, per rundă]
              |
        experiments/fl_{strategy}_effb0_run01/
              run_config.json
              central/
                metrics_by_round.csv
                global_models/round_NNN_weights.pt
                best_model/
              nodes/
                node{N}_metrics_by_round.csv

Post-procesare:
        experiments/ + results/
              |
        scripts/generate_plots.py
              |
        results/
              comparison_table.csv, comparison_table.md
              auc_vs_round.png, f1_vs_round.png
              roc_curves.png, pr_curves.png
              confusion_matrices.png
              per_node_auc_{strategy}.png (x3)
```

### Componente principale

```
+---------------------------+     +---------------------------+
|   ExperimentLogger        |     |   DataSplitter            |
|   (nou, shared)           |     |   (prepare_experiment_    |
|                           |     |    data.py)               |
|  write_run_config()       |     |                           |
|  append_epoch_metrics()   |     |  stratified_split()       |
|  append_round_metrics()   |     |  dirichlet_split()        |
|  append_node_metrics()    |     |  copy_test_global()       |
|  save_best_model()        |     |  save_distribution()      |
|  save_predictions()       |     +---------------------------+
|  save_confusion_matrix()  |
+---------------------------+
          |
          | folosit de:
          v
+------------------+  +------------------+  +------------------+
| FedMedStrategy   |  | FedMedClient     |  | Centralized      |
| (flower_strategy)|  | (flower_client)  |  | Notebook         |
|                  |  |                  |  |                  |
| aggregate_fit()  |  | fit()            |  | train loop       |
| eval_test_global |  | _load_fixed_data |  | per-epoch log    |
| save_round_model |  | calc_delta_norm  |  | best model save  |
+------------------+  +------------------+  +------------------+
          |
          v
+---------------------------+
|   PlotGenerator           |
|   (generate_plots.py)     |
|                           |
|  comparison_table()       |
|  auc_vs_round()           |
|  roc_pr_curves()          |
|  confusion_matrices()     |
|  per_node_auc()           |
+---------------------------+
```


---

## Componente și Interfețe

### 1. `ExperimentLogger` (clasă nouă, shared)

**Locație**: `shared/python/node_core/node_core/experiment_logger.py`

Această clasă centralizează toată logica de scriere a fișierelor de metrici. Este folosită de `FedMedStrategy`, `FedMedClient` și notebook.

```python
class ExperimentLogger:
    def __init__(self, run_dir: str):
        """
        Args:
            run_dir: calea către directorul experimentului
                     ex: "experiments/fl_fedavg_effb0_run01"
        """

    def write_run_config(self, config: dict) -> None:
        """
        Scrie run_config.json în run_dir/.
        Adaugă automat câmpul 'git_commit_hash' (git rev-parse HEAD).
        Dacă git nu e disponibil, câmpul devine "unknown".
        Suprascrie dacă există deja.
        """

    def append_epoch_metrics(self, metrics: EpochMetrics) -> None:
        """
        Adaugă un rând în run_dir/metrics_by_epoch.csv.
        Creează fișierul cu header dacă nu există.
        """

    def append_round_metrics(self, metrics: RoundMetrics) -> None:
        """
        Adaugă un rând în run_dir/central/metrics_by_round.csv.
        Creează fișierul cu header dacă nu există.
        """

    def append_node_metrics(self, metrics: NodeRoundMetrics) -> None:
        """
        Adaugă un rând în run_dir/nodes/node{N}_metrics_by_round.csv.
        Creează fișierul cu header dacă nu există.
        """

    def save_best_model(
        self,
        model: nn.Module,
        model_name: str,
        subdir: str = "artifacts/best_model"
    ) -> None:
        """
        Salvează weights.pt și model_hash.txt în run_dir/subdir/.
        subdir poate fi "artifacts/best_model" (centralizat)
        sau "central/best_model" (FL).
        """

    def save_predictions(
        self,
        filenames: List[str],
        y_true: List[int],
        y_score: List[float],
        subdir: str = "artifacts/best_model"
    ) -> None:
        """
        Scrie predictions_test.csv cu coloanele: filename, y_true, y_score.
        """

    def save_confusion_matrix(
        self,
        y_true: List[int],
        y_score: List[float],
        threshold: float = 0.5,
        subdir: str = "artifacts/best_model"
    ) -> None:
        """
        Calculează și scrie confusion_matrix.json cu câmpurile:
        threshold, TP, FP, TN, FN, accuracy, sensitivity, specificity.
        """

    def save_round_weights(
        self,
        parameters: List[np.ndarray],
        model: nn.Module,
        round_num: int
    ) -> None:
        """
        Salvează run_dir/central/global_models/round_{NNN}_weights.pt
        unde NNN = f"{round_num:03d}".
        """

    def get_best_round(self) -> Optional[int]:
        """
        Citește metrics_by_round.csv și returnează runda cu test_auc maxim.
        Returnează None dacă fișierul nu există sau e gol.
        """
```

**Structuri de date**:

```python
@dataclass
class EpochMetrics:
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
    round: int
    num_clients: int
    aggregation_method: str
    time_round_sec: float
    update_norm: float
    test_auc: Optional[float]      # None dacă evaluarea a eșuat
    test_f1: Optional[float]
    test_sensitivity: Optional[float]
    test_specificity: Optional[float]
    test_pr_auc: Optional[float]

@dataclass
class NodeRoundMetrics:
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
```


### 2. `scripts/prepare_experiment_data.py` (fișier nou)

**Semnătură CLI**:
```
python scripts/prepare_experiment_data.py \
    --dataset-dir central_dataset/chest_xray \
    --output-dir experiments/splits \
    --storage-dir storage \
    --test-ratio 0.15 \
    --num-nodes 5 \
    --dirichlet-alpha 2.0 \
    --seed 42 \
    [--force]
```

**Funcții interne**:

```python
def stratified_split(
    all_files: List[Tuple[str, int]],   # (filepath, label)
    test_ratio: float,
    seed: int
) -> Tuple[List, List]:
    """
    Returnează (test_global, train_pool) prin StratifiedShuffleSplit.
    Garantează că proporția claselor în test_global ≈ proporția globală.
    """

def dirichlet_split(
    train_pool: List[Tuple[str, int]],
    num_nodes: int,
    alpha: float,
    seed: int
) -> List[List[Tuple[str, int]]]:
    """
    Împarte train_pool pe num_nodes noduri folosind distribuția Dirichlet.
    Algoritmul:
      1. Separă indicii pe clasă: indices_per_class[c] = [i for i,(_,l) in enumerate(train_pool) if l==c]
      2. Pentru fiecare clasă c, trage proporții din Dirichlet(alpha * ones(num_nodes))
      3. Alocă indicii proporțional fiecărui nod
      4. Concatenează alocările per nod
    Returnează lista de liste, una per nod.
    """

def save_csv(rows: List[Tuple[str, int]], path: str) -> None:
    """Scrie CSV cu coloanele: filepath, label (0=NORMAL, 1=PNEUMONIA)."""

def save_distribution_json(
    node_splits: List[List[Tuple[str, int]]],
    path: str
) -> None:
    """
    Scrie data_distribution.json cu structura:
    {
      "node1": {"total": N, "normal": n, "pneumonia": p},
      ...
    }
    """

def copy_test_global(
    test_csv_path: str,
    storage_dir: str,
    num_nodes: int
) -> None:
    """Copiază test_global.csv în storage/central/ și storage/node{1-N}/."""
```

**Logica de protecție la suprascriere**:
```python
if any(split_file.exists() for split_file in expected_files):
    if not args.force:
        print("WARN: Split files already exist. Use --force to overwrite.")
        sys.exit(0)
```

### 3. Modificări în `flower_strategy.py`

**Parametri noi în `FedMedStrategy.__init__()`**:

```python
def __init__(
    self,
    # ... parametri existenți ...
    run_id: str = None,                    # NOU: ex. "fl_fedavg_effb0_run01"
    experiments_dir: str = "experiments",  # NOU: directorul rădăcină
    test_global_csv: str = None,           # NOU: calea către test_global.csv
    aggregation_method: str = "fedavg",    # NOU: pentru logging
    **kwargs
):
```

**Modificări în `aggregate_fit()`**:

```python
def aggregate_fit(self, server_round, results, failures):
    round_start = time.time()

    # ... logica existentă de agregare ...

    aggregated_parameters, aggregated_metrics = super().aggregate_fit(...)

    if aggregated_parameters is not None:
        # 1. Salvare weights per rundă (logica existentă, dar în calea nouă)
        self._save_round_weights(parameters_list, server_round)

        # 2. Evaluare pe test_global (NOU)
        test_metrics = self._evaluate_on_test_global(parameters_list)

        # 3. Calculare update_norm (NOU)
        update_norm = self._compute_update_norm(parameters_list)

        # 4. Logging în metrics_by_round.csv (NOU)
        round_metrics = RoundMetrics(
            round=server_round,
            num_clients=len(results),
            aggregation_method=self.aggregation_method,
            time_round_sec=time.time() - round_start,
            update_norm=update_norm,
            **test_metrics  # test_auc, test_f1, etc. sau None dacă a eșuat
        )
        self.logger.append_round_metrics(round_metrics)

        # 5. Logging metrici per nod (NOU)
        for client, fit_res in results:
            self._log_node_metrics(client, fit_res, server_round)

    return aggregated_parameters, aggregated_metrics
```

**Metode noi în `FedMedStrategy`**:

```python
def _evaluate_on_test_global(
    self,
    parameters: List[np.ndarray]
) -> dict:
    """
    Încarcă test_global.csv, rulează inferența cu parametrii dați,
    returnează dict cu: test_auc, test_f1, test_sensitivity,
    test_specificity, test_pr_auc.
    Dacă evaluarea eșuează, loghează eroarea și returnează
    {test_auc: None, test_f1: None, ...}.

    Algoritmul:
      1. Încarcă parametrii în self.model
      2. Citește test_global.csv → listă de (filepath, label)
      3. Creează un DataLoader cu get_val_transforms()
      4. Rulează inferența → y_true, y_score (softmax[:, 1])
      5. Calculează metrici cu compute_metrics() și compute_roc_curve()
      6. Calculează PR-AUC cu sklearn.metrics.average_precision_score
    """

def _compute_update_norm(
    self,
    new_parameters: List[np.ndarray]
) -> float:
    """
    Calculează ||W_new - W_old||_2 față de parametrii din runda anterioară.
    La prima rundă, returnează 0.0.
    """

def _log_node_metrics(
    self,
    client,
    fit_res: fl.common.FitRes,
    server_round: int
) -> None:
    """
    Extrage metricile din fit_res.metrics și le scrie în
    nodes/node{N}_metrics_by_round.csv prin self.logger.
    Câmpurile așteptate în metrics: val_auc, val_f1, val_sensitivity,
    val_specificity, val_pr_auc, local_train_time_sec, delta_norm,
    n_train_samples_used.
    """

def _finalize_best_model(self) -> None:
    """
    Apelat după ultima rundă (în aggregate_fit când server_round == num_rounds).
    Citește metrics_by_round.csv, găsește runda cu test_auc maxim,
    copiază round_{NNN}_weights.pt în central/best_model/weights.pt,
    salvează model_hash.txt, predictions_test.csv, confusion_matrix.json.
    """
```


### 4. Modificări în `flower_client.py`

**Parametri noi în `FedMedClient.__init__()`**:

```python
def __init__(
    self,
    # ... parametri existenți ...
    run_id: str = None,                    # NOU
    experiments_dir: str = "experiments",  # NOU
    splits_dir: str = "experiments/splits", # NOU
    **kwargs
):
```

**Modificări în `_load_data()`**:

```python
def _load_data(self):
    """
    MODIFICAT: Înlocuiește random_split 80/20 cu split-urile fixe.

    Dacă splits_dir și run_id sunt setate:
      - Citește experiments/splits/node{N}_train.csv
      - Citește experiments/splits/node{N}_val.csv
      - Creează CsvDataset (dataset custom care citește din CSV)
    Altfel (fallback pentru compatibilitate):
      - Comportamentul existent cu random_split 80/20
    """
```

**Clasă nouă `CsvDataset`** (în același fișier sau în `data_utils.py`):

```python
class CsvDataset(Dataset):
    """
    Dataset care citește lista de fișiere dintr-un CSV.
    CSV format: filepath, label
    """
    def __init__(self, csv_path: str, transform=None):
        self.samples = pd.read_csv(csv_path)  # coloane: filepath, label
        self.transform = transform

    def __len__(self): return len(self.samples)

    def __getitem__(self, idx):
        row = self.samples.iloc[idx]
        img = Image.open(row['filepath']).convert('RGB')
        if self.transform:
            img = self.transform(img)
        return img, int(row['label'])
```

**Modificări în `fit()`**:

```python
def fit(self, parameters, config):
    fit_start = time.time()
    global_parameters = [p.copy() for p in parameters]  # NOU: copie pentru delta_norm

    # ... logica existentă de antrenare ...

    # NOU: calculare delta_norm
    local_parameters = self.get_parameters({})
    delta_norm = self._compute_delta_norm(local_parameters, global_parameters)

    # NOU: metrici extinse în dicționarul returnat
    metrics.update({
        "val_auc": float(eval_metrics.get('auc', 0)),
        "val_f1": float(eval_metrics.get('f1', 0)),
        "val_sensitivity": float(eval_metrics.get('sensitivity', 0)),
        "val_specificity": float(eval_metrics.get('specificity', 0)),
        "val_pr_auc": float(eval_metrics.get('pr_auc', 0)),
        "local_train_time_sec": float(time.time() - fit_start),
        "delta_norm": float(delta_norm),
        "n_train_samples_used": len(self.train_loader.dataset),
    })

    return updated_parameters, num_samples, metrics
```

**Metodă nouă**:

```python
def _compute_delta_norm(
    self,
    local_params: List[np.ndarray],
    global_params: List[np.ndarray]
) -> float:
    """
    Calculează ||W_local - W_global||_2.
    delta = concatenare(local_params) - concatenare(global_params)
    return np.linalg.norm(delta)
    """
```

**Modificare în `start_flower_client()`**:

```python
def start_flower_client(
    # ... parametri existenți ...
    run_id: str = None,                    # NOU
    experiments_dir: str = "experiments",  # NOU
    splits_dir: str = "experiments/splits", # NOU
):
```

### 5. Modificări minore în `flower_server.py`

**Parametri noi în `start_flower_server()`**:

```python
def start_flower_server(
    # ... parametri existenți ...
    run_id: str = None,                    # NOU
    experiments_dir: str = "experiments",  # NOU
    test_global_csv: str = None,           # NOU
):
```

**Argument CLI nou în `main()`**:

```python
parser.add_argument("--run-id", type=str, default=None)
parser.add_argument("--experiments-dir", type=str, default="experiments")
parser.add_argument("--test-global-csv", type=str, default=None)
```

### 6. Modificări minore în `main.py` (central)

**Parametru nou în `POST /api/fl/start`**:

```python
@app.post("/api/fl/start")
def start_fl_server(
    # ... parametri existenți ...
    run_id: Optional[str] = None,          # NOU
):
    # Generare automată dacă lipsește:
    if run_id is None:
        run_id = _generate_run_id(aggregation_strategy, model_name)

    # Adăugat în cmd list:
    cmd += ["--run-id", run_id]
```

**Funcție nouă**:

```python
def _generate_run_id(strategy: str, model_name: str) -> str:
    """
    Generează run_id cu format: fl_{strategy}_{model}_run{NN}
    NN = numărul de directoare existente cu același prefix + 1.
    Ex: dacă există fl_fedavg_effb0_run01, generează fl_fedavg_effb0_run02.
    """
```

### 7. Modificări minore în `tasks.py`

**Parametru nou în `federated_training_task()`**:

```python
@celery_app.task(name="federated_training")
def federated_training_task(
    job_id: str,
    dataset_id: str,
    model_name: str = "efficientnet_b0",
    batch_size: int = 32,
    run_id: str = None,                    # NOU
    experiments_dir: str = "experiments",  # NOU
    splits_dir: str = "experiments/splits", # NOU
):
```

Transmite `run_id`, `experiments_dir`, `splits_dir` la `start_flower_client()`.

### 8. Modificări în `test_e2e_5nodes.py`

**Constante noi**:

```python
EXPERIMENTS_DIR = "experiments"
SPLITS_DIR = "experiments/splits"
```

**Modificare în `run_session()`**:

```python
def run_session(session_num: int, session: Dict) -> Tuple[bool, str]:
    """Returnează (success, run_id) în loc de bool."""
    strategy = session["aggregation_strategy"]
    run_id = _generate_run_id(strategy, MODEL_NAME, EXPERIMENTS_DIR)

    # Transmite run_id la start_flower_server()
    params["run_id"] = run_id

    # Transmite run_id la start_training() pe fiecare nod
    # (prin parametrul nou al endpoint-ului /api/federated/train)
```

**Verificare finală**:

```python
def verify_experiment_outputs(run_id: str) -> bool:
    """
    Verifică existența fișierelor obligatorii:
    - experiments/{run_id}/run_config.json
    - experiments/{run_id}/central/metrics_by_round.csv
    - experiments/{run_id}/nodes/node{1-5}_metrics_by_round.csv
    Returnează True dacă toate există.
    """
```

**Modificare în `main()`**:

```python
# La final, după toate sesiunile:
log_banner("VERIFICARE FIȘIERE OUTPUT")
for label, (success, run_id) in results.items():
    if success:
        files_ok = verify_experiment_outputs(run_id)
        status = "✓ FIȘIERE OK" if files_ok else "⚠ FIȘIERE LIPSĂ"
        log(f"  {status}  —  {label} ({run_id})")
```

### 9. `scripts/generate_plots.py` (fișier nou)

**Semnătură CLI**:

```
python scripts/generate_plots.py \
    --centralized experiments/centralized_effb0_run01 \
    --fedavg experiments/fl_fedavg_effb0_run01 \
    --fedavgm experiments/fl_fedavgm_effb0_run01 \
    --fedprox experiments/fl_fedprox_effb0_run01 \
    --output-dir results
```

**Funcții principale**:

```python
def generate_comparison_table(
    experiments: Dict[str, str],  # {"centralized": path, "fedavg": path, ...}
    output_dir: str
) -> None:
    """
    Citește predictions_test.csv din best_model/ al fiecărui experiment.
    Calculează AUC, F1, Sensitivity, Specificity, PR-AUC la threshold 0.5.
    Scrie results/comparison_table.csv și results/comparison_table.md.
    """

def plot_metric_vs_round(
    fl_experiments: Dict[str, str],
    centralized_value: float,
    metric: str,                   # "test_auc" sau "test_f1"
    output_path: str
) -> None:
    """
    Citește metrics_by_round.csv pentru fiecare strategie FL.
    Trasează 3 curbe FL + linie orizontală pentru centralizat.
    Salvează PNG.
    """

def plot_roc_pr_curves(
    experiments: Dict[str, str],
    output_dir: str
) -> None:
    """
    Citește predictions_test.csv din fiecare experiment.
    Trasează ROC curves suprapuse → roc_curves.png.
    Trasează PR curves suprapuse → pr_curves.png.
    """

def plot_confusion_matrices(
    experiments: Dict[str, str],
    output_dir: str
) -> None:
    """
    Citește confusion_matrix.json din fiecare experiment.
    Trasează grid 1x4 de heatmap-uri → confusion_matrices.png.
    """

def plot_per_node_auc(
    fl_experiment_path: str,
    strategy_name: str,
    output_dir: str
) -> None:
    """
    Citește nodes/node{1-5}_metrics_by_round.csv.
    Trasează 5 curbe val_auc vs round → per_node_auc_{strategy}.png.
    """
```


---

## Modele de Date

### Structura fișierelor CSV

**`experiments/splits/test_global.csv`** și **`train_pool.csv`**:
```
filepath,label
central_dataset/chest_xray/train/NORMAL/IM-0001-0001.jpeg,0
central_dataset/chest_xray/train/PNEUMONIA/person1_bacteria_1.jpeg,1
```

**`experiments/splits/node{N}_train.csv`** și **`node{N}_val.csv`**:
```
filepath,label
central_dataset/chest_xray/train/NORMAL/IM-0005-0001.jpeg,0
```

**`experiments/splits/data_distribution.json`**:
```json
{
  "total": 5216,
  "test_global": {"total": 782, "normal": 195, "pneumonia": 587},
  "train_pool": {"total": 4434, "normal": 1105, "pneumonia": 3329},
  "nodes": {
    "node1": {"total": 886, "normal": 55, "pneumonia": 831},
    "node2": {"total": 887, "normal": 442, "pneumonia": 445},
    "node3": {"total": 886, "normal": 331, "pneumonia": 555},
    "node4": {"total": 887, "normal": 167, "pneumonia": 720},
    "node5": {"total": 888, "normal": 110, "pneumonia": 778}
  }
}
```

**`experiments/{run_id}/run_config.json`** (centralizat):
```json
{
  "run_id": "centralized_effb0_run01",
  "timestamp": "2025-01-15T10:30:00",
  "git_commit_hash": "a1b2c3d4...",
  "experiment_type": "centralized",
  "model_arch": "efficientnet_b0",
  "pretrained": true,
  "input_size": 224,
  "dataset_summary": {
    "total_images": 5216,
    "num_normal": 1300,
    "num_pneumonia": 3916,
    "test_global_size": 782,
    "test_global_normal": 195,
    "test_global_pneumonia": 587
  },
  "training_hyperparams": {
    "epochs_max": 25,
    "early_stopping_patience": 5,
    "batch_size": 32,
    "lr": 0.0001,
    "optimizer": "adamw",
    "scheduler": "cosine",
    "class_weights": [1.0, 3.01],
    "augmentations": ["random_horizontal_flip", "random_rotation_10", "color_jitter"]
  },
  "thresholding_policy": "fixed_0.5",
  "early_stopped_at_epoch": null
}
```

**`experiments/{run_id}/run_config.json`** (FL):
```json
{
  "run_id": "fl_fedavg_effb0_run01",
  "timestamp": "2025-01-15T12:00:00",
  "git_commit_hash": "a1b2c3d4...",
  "experiment_type": "federated",
  "aggregation_method": "fedavg",
  "model_arch": "efficientnet_b0",
  "num_rounds": 30,
  "local_epochs": 1,
  "min_fit_clients": 5,
  "batch_size": 32,
  "lr": 0.0001,
  "optimizer": "adam",
  "dataset_summary": {
    "node1": {"total": 886, "normal": 55, "pneumonia": 831},
    "node2": {"total": 887, "normal": 442, "pneumonia": 445},
    "node3": {"total": 886, "normal": 331, "pneumonia": 555},
    "node4": {"total": 887, "normal": 167, "pneumonia": 720},
    "node5": {"total": 888, "normal": 110, "pneumonia": 778}
  },
  "thresholding_policy": "fixed_0.5"
}
```

**`metrics_by_epoch.csv`**:
```
epoch,train_loss,val_loss,val_auc,val_f1,val_sensitivity,val_specificity,val_pr_auc,lr,time_epoch_sec
1,0.4521,0.3812,0.8934,0.8712,0.9123,0.7845,0.9012,0.0001,45.3
```

**`metrics_by_round.csv`**:
```
round,num_clients,aggregation_method,time_round_sec,update_norm,test_auc,test_f1,test_sensitivity,test_specificity,test_pr_auc
1,5,fedavg,123.4,0.0234,0.8712,0.8534,0.9012,0.7623,0.8934
```

**`node{N}_metrics_by_round.csv`**:
```
round,node_id,n_train_samples_used,val_auc,val_f1,val_sensitivity,val_specificity,val_pr_auc,local_train_time_sec,delta_norm
1,node1,708,0.8234,0.8012,0.8712,0.7234,0.8456,45.2,0.0123
```

**`predictions_test.csv`**:
```
filename,y_true,y_score
IM-0001-0001.jpeg,0,0.1234
person1_bacteria_1.jpeg,1,0.8912
```

**`confusion_matrix.json`**:
```json
{
  "threshold": 0.5,
  "TP": 560,
  "FP": 45,
  "TN": 150,
  "FN": 27,
  "accuracy": 0.9156,
  "sensitivity": 0.9540,
  "specificity": 0.7692
}
```


---

## Proprietăți de Corectitudine

*O proprietate este o caracteristică sau un comportament care trebuie să fie adevărat pentru toate execuțiile valide ale unui sistem — în esență, o afirmație formală despre ce trebuie să facă sistemul. Proprietățile servesc ca punte între specificațiile lizibile de om și garanțiile de corectitudine verificabile automat.*

### Property 1: Partiționare completă și disjunctă a dataset-ului

*Pentru orice* dataset de imagini, split-ul produs de `Data_Splitter` trebuie să satisfacă simultan:
- `|test_global| + |train_pool| = |total|`
- `test_global ∩ train_pool = ∅`
- `|test_global| / |total| ≈ 0.15` (±1 imagine din cauza rotunjirii)

**Validează: Cerințele 1.1, 1.2**

### Property 2: Partiționare completă și disjunctă a nodurilor FL

*Pentru orice* `train_pool` și orice număr de noduri N, split-ul Dirichlet trebuie să satisfacă:
- `union(node1, ..., nodeN) = train_pool`
- `node_i ∩ node_j = ∅` pentru orice `i ≠ j`
- `sum(|node_i|) = |train_pool|`

**Validează: Cerința 1.3**

### Property 3: Reproductibilitate a split-urilor cu seed fix

*Pentru orice* dataset de intrare, rulând `Data_Splitter` de două ori cu același seed (42), fișierele CSV produse trebuie să fie identice linie cu linie.

**Validează: Cerințele 1.1, 1.3, 8.1, 8.2**

### Property 4: Round-trip CSV pentru metrici

*Pentru orice* set de metrici valide (valori float în intervalele corecte), scriind metricile în CSV cu `ExperimentLogger` și citindu-le înapoi, valorile trebuie să fie identice (cu precizie float32).

Această proprietate se aplică pentru toate cele trei tipuri de CSV:
- `metrics_by_epoch.csv` (câmpurile `EpochMetrics`)
- `metrics_by_round.csv` (câmpurile `RoundMetrics`)
- `node{N}_metrics_by_round.csv` (câmpurile `NodeRoundMetrics`)

**Validează: Cerințele 2.2, 3.2, 4.1**

### Property 5: Corectitudinea calculului `delta_norm`

*Pentru orice* pereche de liste de parametri `(W_local, W_global)`, `delta_norm` calculat de `FedMedClient._compute_delta_norm()` trebuie să fie egal cu `np.linalg.norm(np.concatenate([l.flatten() - g.flatten() for l, g in zip(W_local, W_global)]))`.

**Validează: Cerința 4.2**

### Property 6: Structura completă a `run_config.json`

*Pentru orice* configurație de experiment (centralizat sau FL), `run_config.json` produs de `ExperimentLogger.write_run_config()` trebuie să conțină toate câmpurile obligatorii definite în cerințe (2.1 pentru centralizat, 3.5 pentru FL).

**Validează: Cerințele 2.1, 3.5**

### Property 7: Selecția corectă a best round

*Pentru orice* secvență de valori `test_auc` per rundă, `ExperimentLogger.get_best_round()` trebuie să returneze indexul rundei cu valoarea maximă. Dacă există mai multe runde cu același AUC maxim, returnează prima.

**Validează: Cerința 3.4**

### Property 8: Structura și intervalele `predictions_test.csv`

*Pentru orice* set de predicții pe `test_global`, `predictions_test.csv` produs trebuie să satisfacă:
- Conține exact coloanele `filename`, `y_true`, `y_score`
- `y_true ∈ {0, 1}` pentru fiecare rând
- `y_score ∈ [0.0, 1.0]` pentru fiecare rând
- Numărul de rânduri = dimensiunea `test_global`

**Validează: Cerința 8.5**

### Property 9: Corectitudinea matematică a `confusion_matrix.json`

*Pentru orice* set de predicții binare la threshold 0.5, `confusion_matrix.json` produs trebuie să satisfacă:
- `TP + FP + TN + FN = |test_global|`
- `accuracy = (TP + TN) / (TP + FP + TN + FN)`
- `sensitivity = TP / (TP + FN)` (când `TP + FN > 0`)
- `specificity = TN / (TN + FP)` (când `TN + FP > 0`)

**Validează: Cerința 8.6**

### Property 10: Integritatea hash-ului modelului

*Pentru orice* `state_dict` de model, hash-ul SHA-256 calculat de `ExperimentLogger.save_best_model()` și scris în `model_hash.txt` trebuie să fie identic cu hash-ul calculat independent din același `state_dict`.

**Validează: Cerința 8.3**

### Property 11: Header CSV scris o singură dată

*Pentru orice* secvență de N apeluri `append_*_metrics()` pe același fișier CSV, fișierul rezultat trebuie să conțină exact un rând de header și exact N rânduri de date (fără duplicate de header).

**Validează: Cerința 7.5**


---

## Tratarea Erorilor

### Erori în `prepare_experiment_data.py`

| Situație | Comportament |
|----------|-------------|
| `--dataset-dir` nu există | `sys.exit(1)` cu mesaj clar |
| Split-urile există deja, fără `--force` | Avertisment + `sys.exit(0)` (nu eroare) |
| Eroare la copiere în `storage/` | Avertisment, continuă (nu e critic) |
| Dataset gol sau prea mic pentru 15% | `sys.exit(1)` cu mesaj |

### Erori în `FedMedStrategy`

| Situație | Comportament |
|----------|-------------|
| `test_global_csv` lipsă sau corupt | Loghează eroarea, scrie `null` în CSV, continuă runda |
| Eroare de inferență pe test_global | Idem — nu oprește antrenarea FL |
| Eroare la salvarea `round_{NNN}_weights.pt` | Loghează eroarea, continuă (pierde weights pentru runda respectivă) |
| `run_id` nu e furnizat | Generează automat: `fl_{strategy}_{model}_run01` |

### Erori în `FedMedClient`

| Situație | Comportament |
|----------|-------------|
| `node{N}_train.csv` sau `node{N}_val.csv` lipsă | Ridică `FileNotFoundError` cu calea așteptată; task Celery → status `"failed"` |
| Eroare la calculul `delta_norm` | Loghează, transmite `delta_norm=0.0` |
| Metrici lipsă în `eval_metrics` | Folosește `0.0` ca valoare implicită |

### Erori în `generate_plots.py`

| Situație | Comportament |
|----------|-------------|
| Fișier de input lipsă | Avertisment cu calea exactă, continuă cu graficele disponibile |
| `predictions_test.csv` corupt | Avertisment, sare graficul respectiv |
| Directorul `results/` nu există | Creat automat cu `mkdir -p` |

---

## Strategie de Testare

### Abordare duală

Testele sunt organizate în două categorii complementare:

1. **Teste unitare** — verifică exemple specifice, cazuri limită și condiții de eroare
2. **Teste bazate pe proprietăți** — verifică proprietăți universale pe input-uri generate aleatoriu

### Bibliotecă pentru property-based testing

**Hypothesis** (Python) — biblioteca standard pentru PBT în ecosistemul Python.

```python
# Instalare
pip install hypothesis

# Configurare minimă per test
from hypothesis import given, settings
from hypothesis import strategies as st

@given(st.lists(st.floats(0, 1), min_size=10, max_size=1000))
@settings(max_examples=100)
def test_property_name(data):
    ...
```

Fiecare test de proprietate rulează **minimum 100 de iterații** cu input-uri generate aleatoriu.

### Teste unitare (exemple specifice)

```python
# tests/test_experiment_logger.py

def test_write_run_config_creates_file():
    """Verifică că run_config.json este creat cu câmpurile obligatorii."""

def test_append_epoch_metrics_creates_header_once():
    """Verifică că header-ul CSV este scris o singură dată la N apeluri."""

def test_early_stopping_logs_epoch():
    """Verifică că early_stopped_at_epoch este logat corect."""

def test_missing_split_files_raises_error():
    """Verifică că FedMedClient ridică FileNotFoundError cu mesaj clar."""

def test_generate_run_id_sequential():
    """Verifică că run_id generat automat este secvențial față de directoarele existente."""
```

### Teste bazate pe proprietăți

Fiecare proprietate din secțiunea anterioară corespunde unui test PBT.

```python
# tests/test_properties.py
# Feature: experiment-logging-and-visualization

# Feature: experiment-logging-and-visualization, Property 1: dataset split completeness
@given(
    total_size=st.integers(min_value=20, max_value=10000),
    normal_ratio=st.floats(min_value=0.1, max_value=0.9)
)
@settings(max_examples=100)
def test_split_completeness_and_disjointness(total_size, normal_ratio):
    """Property 1: test_global + train_pool = total, fără suprapunere."""
    ...

# Feature: experiment-logging-and-visualization, Property 2: node split completeness
@given(
    train_pool_size=st.integers(min_value=50, max_value=5000),
    num_nodes=st.integers(min_value=2, max_value=10)
)
@settings(max_examples=100)
def test_node_split_completeness(train_pool_size, num_nodes):
    """Property 2: union(nodes) = train_pool, fără suprapuneri."""
    ...

# Feature: experiment-logging-and-visualization, Property 3: reproducibility
@given(total_size=st.integers(min_value=20, max_value=1000))
@settings(max_examples=100)
def test_split_reproducibility(total_size):
    """Property 3: două rulări cu seed=42 produc rezultate identice."""
    ...

# Feature: experiment-logging-and-visualization, Property 4: CSV round-trip
@given(
    epoch=st.integers(min_value=1, max_value=100),
    train_loss=st.floats(min_value=0.0, max_value=10.0, allow_nan=False),
    val_auc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
    # ... restul câmpurilor
)
@settings(max_examples=100)
def test_epoch_metrics_csv_roundtrip(epoch, train_loss, val_auc, ...):
    """Property 4: metrici scrise în CSV și citite înapoi sunt identice."""
    ...

# Feature: experiment-logging-and-visualization, Property 5: delta_norm correctness
@given(
    param_shapes=st.lists(
        st.tuples(st.integers(1, 100), st.integers(1, 100)),
        min_size=1, max_size=10
    )
)
@settings(max_examples=100)
def test_delta_norm_correctness(param_shapes):
    """Property 5: delta_norm = ||W_local - W_global||_2."""
    ...

# Feature: experiment-logging-and-visualization, Property 7: best round selection
@given(
    auc_values=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        min_size=1, max_size=50
    )
)
@settings(max_examples=100)
def test_best_round_selection(auc_values):
    """Property 7: get_best_round() returnează indexul AUC maxim."""
    ...

# Feature: experiment-logging-and-visualization, Property 8: predictions CSV structure
@given(
    n_samples=st.integers(min_value=1, max_value=1000),
    y_true=st.lists(st.integers(0, 1), min_size=1, max_size=1000),
    y_score=st.lists(st.floats(0.0, 1.0, allow_nan=False), min_size=1, max_size=1000)
)
@settings(max_examples=100)
def test_predictions_csv_structure(n_samples, y_true, y_score):
    """Property 8: predictions_test.csv are structura și intervalele corecte."""
    ...

# Feature: experiment-logging-and-visualization, Property 9: confusion matrix math
@given(
    y_true=st.lists(st.integers(0, 1), min_size=2, max_size=1000),
    y_score=st.lists(st.floats(0.0, 1.0, allow_nan=False), min_size=2, max_size=1000)
)
@settings(max_examples=100)
def test_confusion_matrix_math(y_true, y_score):
    """Property 9: TP+FP+TN+FN=total, accuracy/sensitivity/specificity corecte."""
    ...

# Feature: experiment-logging-and-visualization, Property 10: model hash integrity
@given(
    layer_shapes=st.lists(
        st.integers(min_value=1, max_value=1000),
        min_size=1, max_size=20
    )
)
@settings(max_examples=100)
def test_model_hash_integrity(layer_shapes):
    """Property 10: hash scris în fișier = hash calculat independent."""
    ...

# Feature: experiment-logging-and-visualization, Property 11: CSV header written once
@given(n_rows=st.integers(min_value=1, max_value=100))
@settings(max_examples=100)
def test_csv_header_written_once(n_rows):
    """Property 11: N apeluri append → 1 header + N rânduri de date."""
    ...
```

### Teste de integrare (exemple)

```python
# tests/test_integration.py

def test_prepare_experiment_data_end_to_end():
    """Rulează scriptul pe un dataset mic și verifică toate fișierele produse."""

def test_fl_strategy_evaluates_test_global():
    """Verifică că FedMedStrategy evaluează pe test_global după fiecare rundă."""

def test_generate_plots_with_synthetic_data():
    """Verifică că generate_plots.py produce toate fișierele PNG așteptate."""
```

