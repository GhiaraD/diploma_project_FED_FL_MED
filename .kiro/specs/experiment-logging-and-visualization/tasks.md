# Plan de Implementare: Experiment Logging and Visualization

## Prezentare Generală

Implementarea adaugă infrastructura completă de logging, colectare metrici și generare grafice pentru compararea unui model centralizat cu trei variante FL (FedAvg, FedAvgM, FedProx) pe 5 noduri. Limbaj: **Python**.

Ordinea de implementare urmează dependențele: `ExperimentLogger` (shared) → `prepare_experiment_data.py` → `flower_strategy.py` → `flower_client.py` → modificări minore în server/API → notebook → `test_e2e_5nodes.py` → `generate_plots.py` → teste PBT.

## Tasks

- [x] 1. Creează clasa `ExperimentLogger` în `shared/python/node_core/node_core/experiment_logger.py`
  - Definește dataclasses-urile `EpochMetrics`, `RoundMetrics`, `NodeRoundMetrics` cu câmpurile exacte din design
  - Implementează `__init__(self, run_dir: str)` care stochează calea și creează directoarele necesare cu `Path.mkdir(parents=True, exist_ok=True)`
  - Implementează `write_run_config(config: dict)` — scrie `run_config.json`, adaugă automat `git_commit_hash` via `git rev-parse HEAD` (fallback `"unknown"`)
  - Implementează `append_epoch_metrics(metrics: EpochMetrics)` — scrie/adaugă în `metrics_by_epoch.csv`; header scris o singură dată la creare
  - Implementează `append_round_metrics(metrics: RoundMetrics)` — scrie/adaugă în `central/metrics_by_round.csv`; suportă valori `None` (scrise ca string gol în CSV)
  - Implementează `append_node_metrics(metrics: NodeRoundMetrics)` — scrie/adaugă în `nodes/node{N}_metrics_by_round.csv`
  - Implementează `save_best_model(model, model_name, subdir)` — salvează `weights.pt` și `model_hash.txt` (SHA-256) în `run_dir/subdir/`
  - Implementează `save_predictions(filenames, y_true, y_score, subdir)` — scrie `predictions_test.csv` cu coloanele `filename`, `y_true`, `y_score`
  - Implementează `save_confusion_matrix(y_true, y_score, threshold, subdir)` — calculează și scrie `confusion_matrix.json` cu câmpurile `threshold`, `TP`, `FP`, `TN`, `FN`, `accuracy`, `sensitivity`, `specificity`
  - Implementează `save_round_weights(parameters, model, round_num)` — salvează `central/global_models/round_{NNN}_weights.pt`
  - Implementează `get_best_round()` — citește `central/metrics_by_round.csv`, returnează runda cu `test_auc` maxim (prima dacă există egalitate); returnează `None` dacă fișierul lipsește sau e gol
  - Exportă `ExperimentLogger` și dataclasses-urile din `shared/python/node_core/node_core/__init__.py`
  - _Cerințe: 2.2, 3.2, 3.3, 3.4, 4.1, 7.1, 7.2, 7.4, 7.5, 8.3, 8.5, 8.6_

  - [x]* 1.1 Scrie teste unitare pentru `ExperimentLogger`
    - `test_write_run_config_creates_file` — verifică că `run_config.json` este creat cu câmpurile obligatorii
    - `test_append_epoch_metrics_creates_header_once` — N apeluri → 1 header + N rânduri
    - `test_append_round_metrics_with_none_values` — valorile `None` sunt scrise corect
    - `test_get_best_round_returns_max_auc` — returnează indexul corect
    - `test_save_confusion_matrix_fields` — verifică câmpurile JSON produse
    - _Cerințe: 2.2, 3.2, 3.4, 7.5, 8.6_

  - [x]* 1.2 Scrie test de proprietate: Property 4 — Round-trip CSV pentru metrici
    - **Property 4: Round-trip CSV pentru metrici**
    - Generează `EpochMetrics`, `RoundMetrics`, `NodeRoundMetrics` cu valori aleatorii valide
    - Scrie în CSV cu `ExperimentLogger`, citește înapoi, verifică egalitatea valorilor (precizie float32)
    - **Validează: Cerințele 2.2, 3.2, 4.1**

  - [x]* 1.3 Scrie test de proprietate: Property 6 — Structura completă a `run_config.json`
    - **Property 6: Structura completă a `run_config.json`**
    - Generează configurații arbitrare (centralizat și FL), verifică că toate câmpurile obligatorii sunt prezente
    - **Validează: Cerințele 2.1, 3.5**

  - [x]* 1.4 Scrie test de proprietate: Property 7 — Selecția corectă a best round
    - **Property 7: Selecția corectă a best round**
    - Generează secvențe arbitrare de valori `test_auc`, verifică că `get_best_round()` returnează indexul maximului
    - **Validează: Cerința 3.4**

  - [x]* 1.5 Scrie test de proprietate: Property 8 — Structura și intervalele `predictions_test.csv`
    - **Property 8: Structura și intervalele `predictions_test.csv`**
    - Verifică că fișierul produs conține exact coloanele `filename`, `y_true`, `y_score`, cu `y_true ∈ {0,1}` și `y_score ∈ [0.0, 1.0]`
    - **Validează: Cerința 8.5**

  - [x]* 1.6 Scrie test de proprietate: Property 9 — Corectitudinea matematică a `confusion_matrix.json`
    - **Property 9: Corectitudinea matematică a `confusion_matrix.json`**
    - Verifică că `TP+FP+TN+FN = total`, `accuracy`, `sensitivity`, `specificity` sunt calculate corect
    - **Validează: Cerința 8.6**

  - [x]* 1.7 Scrie test de proprietate: Property 10 — Integritatea hash-ului modelului
    - **Property 10: Integritatea hash-ului modelului**
    - Verifică că hash-ul SHA-256 scris în `model_hash.txt` este identic cu hash-ul calculat independent
    - **Validează: Cerința 8.3**

  - [x]* 1.8 Scrie test de proprietate: Property 11 — Header CSV scris o singură dată
    - **Property 11: Header CSV scris o singură dată**
    - N apeluri `append_*_metrics()` → fișierul conține exact 1 header + N rânduri de date
    - **Validează: Cerința 7.5**

- [x] 2. Creează `scripts/prepare_experiment_data.py`
  - Implementează `stratified_split(all_files, test_ratio, seed)` folosind `StratifiedShuffleSplit` din sklearn; returnează `(test_global, train_pool)`
  - Implementează `dirichlet_split(train_pool, num_nodes, alpha, seed)` — distribuție Dirichlet cu `alpha=2.0`, seed fix; returnează lista de liste per nod
  - Implementează `save_csv(rows, path)` — scrie CSV cu coloanele `filepath`, `label` (0=NORMAL, 1=PNEUMONIA)
  - Implementează `save_distribution_json(node_splits, path)` — scrie `data_distribution.json` cu structura `{node1: {total, normal, pneumonia}, ...}` plus `total`, `test_global`, `train_pool`
  - Implementează `copy_test_global(test_csv_path, storage_dir, num_nodes)` — copiază în `storage/central/` și `storage/node{1-N}/`
  - Implementează logica CLI cu `argparse`: `--dataset-dir`, `--output-dir`, `--storage-dir`, `--test-ratio`, `--num-nodes`, `--dirichlet-alpha`, `--seed`, `--force`
  - Implementează protecția la suprascriere: dacă fișierele există și `--force` nu e pasat, afișează avertisment și iese cu `sys.exit(0)`
  - Afișează sumar cu numărul de imagini per split și distribuția claselor la final
  - _Cerințe: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 8.1_

  - [x]* 2.1 Scrie test de proprietate: Property 1 — Partiționare completă și disjunctă a dataset-ului
    - **Property 1: Partiționare completă și disjunctă a dataset-ului**
    - Verifică că `|test_global| + |train_pool| = |total|`, `test_global ∩ train_pool = ∅`, `|test_global| / |total| ≈ 0.15`
    - **Validează: Cerințele 1.1, 1.2**

  - [x]* 2.2 Scrie test de proprietate: Property 2 — Partiționare completă și disjunctă a nodurilor FL
    - **Property 2: Partiționare completă și disjunctă a nodurilor FL**
    - Verifică că `union(node1..nodeN) = train_pool`, `node_i ∩ node_j = ∅`, `sum(|node_i|) = |train_pool|`
    - **Validează: Cerința 1.3**

  - [x]* 2.3 Scrie test de proprietate: Property 3 — Reproductibilitate a split-urilor cu seed fix
    - **Property 3: Reproductibilitate a split-urilor cu seed fix**
    - Rulează `stratified_split` și `dirichlet_split` de două ori cu seed=42, verifică că rezultatele sunt identice
    - **Validează: Cerințele 1.1, 1.3, 8.1**

- [x] 3. Checkpoint — Verificare componente de bază
  - Asigură-te că `ExperimentLogger` importă corect din `node_core` și că `prepare_experiment_data.py` rulează fără erori pe un dataset mic de test.
  - Asigură-te că toate testele de la task-urile 1 și 2 trec.

- [x] 4. Modifică `shared/python/node_core/node_core/flower_strategy.py`
  - Adaugă parametrii noi în `FedMedStrategy.__init__()`: `run_id`, `experiments_dir`, `test_global_csv`, `aggregation_method`
  - Inițializează `self.logger = ExperimentLogger(run_dir)` în `__init__()` dacă `run_id` este furnizat; dacă nu, generează automat `fl_{strategy}_{model}_run01`
  - Apelează `self.logger.write_run_config(config)` la sfârșitul `__init__()` cu câmpurile definite în cerința 3.5
  - Implementează `_evaluate_on_test_global(parameters)` — încarcă `test_global_csv`, rulează inferența cu `get_val_transforms()`, calculează `test_auc`, `test_f1`, `test_sensitivity`, `test_specificity`, `test_pr_auc`; la eroare loghează și returnează dict cu valori `None`
  - Implementează `_compute_update_norm(new_parameters)` — calculează `||W_new - W_old||_2` față de runda anterioară; returnează `0.0` la prima rundă
  - Implementează `_log_node_metrics(client, fit_res, server_round)` — extrage câmpurile `val_auc`, `val_f1`, `val_sensitivity`, `val_specificity`, `val_pr_auc`, `local_train_time_sec`, `delta_norm`, `n_train_samples_used` din `fit_res.metrics` și apelează `self.logger.append_node_metrics()`
  - Implementează `_finalize_best_model()` — citește `metrics_by_round.csv`, găsește runda cu `test_auc` maxim, copiază weights, salvează `model_hash.txt`, `predictions_test.csv`, `confusion_matrix.json`
  - Modifică `aggregate_fit()` pentru a apela în ordine: `_save_round_weights()` (în calea nouă `central/global_models/`), `_evaluate_on_test_global()`, `_compute_update_norm()`, `logger.append_round_metrics()`, `_log_node_metrics()` pentru fiecare client; apelează `_finalize_best_model()` la ultima rundă
  - Transmite `run_id`, `experiments_dir`, `test_global_csv`, `aggregation_method` prin `create_fedmed_strategy()` și prin `flower_server.py`
  - _Cerințe: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 7.2_

  - [ ]* 4.1 Scrie test de integrare pentru `FedMedStrategy` cu date sintetice
    - Verifică că `_evaluate_on_test_global()` returnează dict cu cheile corecte
    - Verifică că `_compute_update_norm()` returnează `0.0` la prima rundă și o valoare pozitivă ulterior
    - Verifică că `_log_node_metrics()` apelează `logger.append_node_metrics()` cu câmpurile corecte
    - _Cerințe: 3.1, 3.2, 4.1_

- [x] 5. Modifică `services/node/worker/app/flower_client.py`
  - Adaugă clasa `CsvDataset(Dataset)` în același fișier (sau în `data_utils.py`): citește CSV cu coloanele `filepath`, `label`; aplică `transform`; returnează `(img, label)`
  - Adaugă parametrii noi în `FedMedClient.__init__()`: `run_id`, `experiments_dir`, `splits_dir`
  - Modifică `_load_data()`: dacă `splits_dir` și `node_id` sunt setate, citește `node{N}_train.csv` și `node{N}_val.csv` și creează `CsvDataset`; dacă fișierele lipsesc, ridică `FileNotFoundError` cu calea așteptată; altfel, fallback la comportamentul existent cu `random_split`
  - Implementează `_compute_delta_norm(local_params, global_params)` — calculează `||W_local - W_global||_2` prin concatenarea și aplatizarea parametrilor
  - Modifică `fit()`: salvează o copie a `parameters` la intrare ca `global_parameters`; după antrenare calculează `delta_norm`; adaugă în dicționarul de metrici returnat câmpurile `val_auc`, `val_f1`, `val_sensitivity`, `val_specificity`, `val_pr_auc`, `local_train_time_sec`, `delta_norm`, `n_train_samples_used`
  - Adaugă parametrii noi în `start_flower_client()`: `run_id`, `experiments_dir`, `splits_dir`; transmite-i la `FedMedClient`
  - _Cerințe: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x]* 5.1 Scrie test de proprietate: Property 5 — Corectitudinea calculului `delta_norm`
    - **Property 5: Corectitudinea calculului `delta_norm`**
    - Verifică că `_compute_delta_norm(W_local, W_global) == np.linalg.norm(np.concatenate([l.flatten() - g.flatten() for l, g in zip(W_local, W_global)]))`
    - **Validează: Cerința 4.2**

  - [x]* 5.2 Scrie test unitar pentru `CsvDataset` și fallback-ul `_load_data()`
    - Verifică că `CsvDataset` citește corect din CSV și aplică transformările
    - Verifică că `_load_data()` ridică `FileNotFoundError` cu mesaj clar când fișierele de split lipsesc
    - _Cerințe: 4.3, 4.5_

- [x] 6. Checkpoint — Verificare integrare client-server
  - Asigură-te că toate testele de la task-urile 4 și 5 trec.
  - Verifică că `FedMedClient` cu `splits_dir` setat citește corect din CSV-urile de split.

- [x] 7. Modificări minore în `services/central/app/flower_server.py`
  - Adaugă parametrii `run_id`, `experiments_dir`, `test_global_csv` în `start_flower_server()`
  - Transmite acești parametri la `create_fedmed_strategy()`
  - Adaugă argumentele CLI `--run-id`, `--experiments-dir`, `--test-global-csv` în `main()`
  - _Cerințe: 5.2_

- [x] 8. Modificări minore în `services/central/app/main.py`
  - Adaugă parametrul opțional `run_id: Optional[str] = None` în `POST /api/fl/start`
  - Implementează `_generate_run_id(strategy, model_name)` — format `fl_{strategy}_{model}_run{NN}`, `NN` bazat pe directoarele existente în `experiments/`
  - Dacă `run_id` lipsește, generează automat cu `_generate_run_id()`
  - Adaugă `--run-id`, `--experiments-dir`, `--test-global-csv` în comanda `cmd` transmisă subprocess-ului `flower_server.py`
  - _Cerințe: 5.1_

  - [ ]* 8.1 Scrie test unitar pentru `_generate_run_id()`
    - Verifică că `run_id` generat este secvențial față de directoarele existente
    - _Cerința: 5.1_

- [x] 9. Modificări minore în `services/node/api/app/tasks.py`
  - Adaugă parametrii `run_id`, `experiments_dir`, `splits_dir` în `federated_training_task()`
  - Transmite acești parametri la `start_flower_client()`
  - _Cerința: 5.3_

- [ ] 10. Modifică `chest-x-ray-pneumonia-detection-with-deep-learning.ipynb`
  - Adaugă celulă de configurare la început: `run_id`, `experiments_dir`, seed fix `42` pentru `torch.manual_seed()`, `numpy.random.seed()`, `random.seed()`
  - Înlocuiește split-ul original cu citirea din `experiments/splits/train_pool.csv`; aplică split 80/20 stratificat din `train_pool`
  - Inițializează `ExperimentLogger(run_dir)` și apelează `logger.write_run_config(config)` cu câmpurile din cerința 2.1
  - Adaugă apel `logger.append_epoch_metrics(EpochMetrics(...))` la finalul fiecărei epoci de antrenare
  - Adaugă logică de early stopping: dacă `val_auc` nu se îmbunătățește timp de `early_stopping_patience` epoci, oprește antrenarea și loghează `early_stopped_at_epoch` în `run_config.json`
  - La identificarea celui mai bun model (după `val_auc`), apelează `logger.save_best_model()`, `logger.save_predictions()`, `logger.save_confusion_matrix()` cu evaluare pe `test_global`
  - _Cerințe: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 8.2_

- [x] 11. Modifică `scripts/test_e2e_5nodes.py`
  - Adaugă constantele `EXPERIMENTS_DIR = "experiments"` și `SPLITS_DIR = "experiments/splits"`
  - Implementează `_generate_run_id(strategy, model_name, experiments_dir)` — același format ca în `main.py`
  - Modifică `run_session()` pentru a genera `run_id` și a-l transmite la `start_flower_server()` (prin parametrul `run_id` al endpoint-ului) și la `start_training()` pe fiecare nod (prin parametrul `run_id` al endpoint-ului `/api/federated/train`)
  - Modifică `run_session()` să returneze `(bool, run_id)` în loc de `bool`
  - Implementează `verify_experiment_outputs(run_id)` — verifică existența `run_config.json`, `central/metrics_by_round.csv`, `nodes/node{1-5}_metrics_by_round.csv`; returnează `True` dacă toate există
  - Modifică `main()` pentru a apela `verify_experiment_outputs()` după fiecare sesiune reușită și a raporta în sumarul final dacă fișierele sunt prezente sau lipsesc
  - _Cerințe: 5.4, 5.5_

- [x] 12. Creează `scripts/generate_plots.py`
  - Implementează `generate_comparison_table(experiments, output_dir)` — citește `predictions_test.csv` din `best_model/` al fiecărui experiment, calculează AUC, F1, Sensitivity, Specificity, PR-AUC la threshold 0.5, scrie `results/comparison_table.csv` și `results/comparison_table.md`
  - Implementează `plot_metric_vs_round(fl_experiments, centralized_value, metric, output_path)` — citește `central/metrics_by_round.csv` pentru fiecare strategie FL, trasează 3 curbe FL + linie orizontală pentru centralizat, salvează PNG
  - Apelează `plot_metric_vs_round` pentru `test_auc` → `results/auc_vs_round.png` și pentru `test_f1` → `results/f1_vs_round.png`
  - Implementează `plot_roc_pr_curves(experiments, output_dir)` — citește `predictions_test.csv` din fiecare experiment, trasează ROC curves suprapuse → `results/roc_curves.png` și PR curves → `results/pr_curves.png`
  - Implementează `plot_confusion_matrices(experiments, output_dir)` — citește `confusion_matrix.json` din fiecare experiment, trasează grid 1×4 de heatmap-uri → `results/confusion_matrices.png`
  - Implementează `plot_per_node_auc(fl_experiment_path, strategy_name, output_dir)` — citește `nodes/node{1-5}_metrics_by_round.csv`, trasează 5 curbe `val_auc` vs. rundă → `results/per_node_auc_{strategy}.png`; apelează pentru fiecare din cele 3 strategii FL
  - Implementează logica CLI cu `argparse`: `--centralized`, `--fedavg`, `--fedavgm`, `--fedprox`, `--output-dir`
  - La fișier de input lipsă: afișează avertisment cu calea exactă și continuă cu graficele disponibile (nu oprește execuția)
  - Creează `results/` automat cu `Path.mkdir(parents=True, exist_ok=True)`
  - _Cerințe: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7.3_

  - [ ]* 12.1 Scrie test de integrare pentru `generate_plots.py` cu date sintetice
    - Creează fișiere CSV/JSON sintetice în directoare temporare
    - Verifică că toate fișierele PNG și CSV așteptate sunt produse
    - Verifică că scriptul nu se oprește când un fișier de input lipsește
    - _Cerințe: 6.1–6.9_

- [x] 13. Checkpoint final — Verificare completă
  - Asigură-te că toate testele unitare și de proprietate trec.
  - Rulează `python scripts/prepare_experiment_data.py --help` și verifică că CLI-ul funcționează.
  - Rulează `python scripts/generate_plots.py --help` și verifică că CLI-ul funcționează.
  - Verifică că `ExperimentLogger` este exportat corect din `node_core`.

## Note

- Task-urile marcate cu `*` sunt opționale și pot fi sărite pentru un MVP mai rapid
- Fiecare task referențiază cerințele specifice pentru trasabilitate
- Checkpoints-urile asigură validarea incrementală înainte de a continua
- Testele PBT folosesc biblioteca **Hypothesis** (`pip install hypothesis`)
- Toate testele PBT rulează minimum 100 de iterații (`@settings(max_examples=100)`)
- Testele unitare și PBT sunt complementare — nu se exclud reciproc
