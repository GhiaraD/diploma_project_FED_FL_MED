# Document de Cerințe: Experiment Logging and Visualization

## Introducere

Acest feature adaugă infrastructura completă de logging, colectare metrici și generare grafice pentru platforma Fed-Med-FL, cu scopul de a compara un model centralizat cu trei variante de Federated Learning (FedAvg, FedAvgM, FedProx) pe 5 noduri, pentru o lucrare de disertație.

Platforma clasifică imagini medicale Chest X-Ray (NORMAL vs PNEUMONIA) folosind EfficientNet-B0, Flower Framework, PyTorch, FastAPI și Celery. Experimentele trebuie să fie reproductibile, comparabile și ușor de prezentat în lucrare.

Implementarea acoperă 8 fișiere (2 noi, 6 modificate) și produce o structură de output standardizată sub `experiments/` și `results/`.

## Glosar

- **Experiment_Logger**: Componenta responsabilă cu scrierea fișierelor CSV și JSON de metrici în timpul antrenării.
- **Plot_Generator**: Scriptul `scripts/generate_plots.py` care produce toate graficele finale offline, după finalizarea experimentelor.
- **Data_Splitter**: Scriptul `scripts/prepare_experiment_data.py` care creează și salvează split-urile fixe de date.
- **FL_Strategy**: Clasa `FedMedStrategy` din `flower_strategy.py` care orchestrează rundele FL pe server.
- **FL_Client**: Clasa `FedMedClient` din `flower_client.py` care antrenează local pe fiecare nod.
- **Centralized_Notebook**: Fișierul `chest-x-ray-pneumonia-detection-with-deep-learning.ipynb` care rulează antrenarea centralizată.
- **test_global**: Subset fix hold-out de 15% din dataset, stratificat pe clasă, folosit exclusiv pentru evaluarea comparativă finală. Nu intră în niciun training.
- **train_pool**: Restul de 85% din dataset, folosit pentru antrenare (centralizat și FL).
- **run_id**: Identificator unic al unui experiment (ex. `centralized_effb0_run01`, `fl_fedavg_effb0_run01`).
- **Non-IID**: Distribuție non-identică și independentă a datelor între noduri, simulată prin distribuție Dirichlet cu α=2.0.
- **round_weights.pt**: Fișier PyTorch cu parametrii modelului global salvat după o rundă FL.
- **predictions_test.csv**: Fișier cu predicțiile modelului final pe test_global (filename, y_true, y_score).
- **confusion_matrix.json**: Fișier JSON cu matricea de confuzie la threshold fix 0.5 (TP, FP, TN, FN).
- **metrics_by_epoch.csv**: Fișier CSV cu metricile per epocă pentru antrenarea centralizată.
- **metrics_by_round.csv**: Fișier CSV cu metricile per rundă pentru antrenarea FL (la nivel central).
- **node_metrics_by_round.csv**: Fișier CSV cu metricile per rundă per nod FL.
- **run_config.json**: Fișier JSON cu configurația completă a unui experiment (hyperparametri, split info, timestamp).
- **AUC**: Area Under the ROC Curve — metrică principală de evaluare.
- **PR-AUC**: Area Under the Precision-Recall Curve — metrică secundară, robustă la dezechilibru de clase.
- **Sensitivity**: Recall pentru clasa PNEUMONIA (True Positive Rate).
- **Specificity**: True Negative Rate pentru clasa NORMAL.
- **delta_norm**: Norma L2 a diferenței dintre parametrii modelului local și modelul global (‖ΔW_i‖).
- **update_norm**: Norma L2 a update-ului agregat aplicat modelului global (‖ΔW_avg‖).
- **Dirichlet_α**: Parametrul distribuției Dirichlet folosit pentru simularea heterogenității datelor între noduri (α=2.0).

---

## Cerințe

### Cerința 1: Pregătirea Split-urilor Fixe de Date

**User Story:** Ca cercetător, vreau ca toate experimentele să folosească exact aceleași split-uri de date, astfel încât comparațiile dintre modelul centralizat și variantele FL să fie corecte și reproductibile.

#### Criterii de Acceptare

1. THE Data_Splitter SHALL crea un fișier `experiments/splits/test_global.csv` care conține exact 15% din totalul imaginilor din dataset, selectate prin eșantionare stratificată pe clasă (NORMAL și PNEUMONIA), cu seed fix.
2. THE Data_Splitter SHALL crea un fișier `experiments/splits/train_pool.csv` care conține restul de 85% din imagini, exclusiv față de test_global.csv, fără suprapunere.
3. WHEN Data_Splitter rulează distribuția non-IID, THE Data_Splitter SHALL împărți train_pool pe 5 noduri folosind distribuția Dirichlet cu α=2.0 și seed fix, producând fișierele `experiments/splits/node{1-5}_train.csv` și `experiments/splits/node{1-5}_val.csv` (split 80/20 per nod).
4. THE Data_Splitter SHALL salva un fișier `experiments/splits/data_distribution.json` care conține, pentru fiecare nod, numărul total de imagini, numărul de imagini NORMAL și numărul de imagini PNEUMONIA.
5. IF fișierele de split există deja în `experiments/splits/`, THEN THE Data_Splitter SHALL afișa un avertisment și SHALL opri execuția fără a suprascrie fișierele existente, cu excepția cazului în care este pasat explicit flag-ul `--force`.
6. THE Data_Splitter SHALL copia fișierul `test_global.csv` în directoarele `storage/central/`, `storage/node1/`, `storage/node2/`, `storage/node3/`, `storage/node4/` și `storage/node5/`, astfel încât fiecare componentă să aibă acces local la setul de test.
7. WHEN split-ul este finalizat, THE Data_Splitter SHALL afișa un sumar cu numărul de imagini per split și distribuția claselor, pentru verificare vizuală.

---

### Cerința 2: Logging Structurat pentru Antrenarea Centralizată

**User Story:** Ca cercetător, vreau ca notebook-ul de antrenare centralizată să logheze automat metricile per epocă și configurația experimentului, astfel încât să pot reproduce și compara rezultatele cu variantele FL.

#### Criterii de Acceptare

1. WHEN Centralized_Notebook pornește un experiment, THE Centralized_Notebook SHALL crea directorul `experiments/{run_id}/` și SHALL scrie fișierul `run_config.json` cu câmpurile: `run_id`, `timestamp`, `experiment_type` (valoarea `"centralized"`), `model_arch`, `pretrained`, `input_size`, `dataset_summary` (total imagini, num_normal, num_pneumonia, dimensiune test_global), `training_hyperparams` (epochs_max, early_stopping_patience, batch_size, lr, optimizer, scheduler, class_weights, augmentations), `thresholding_policy` (valoarea `"fixed_0.5"`).
2. WHEN Centralized_Notebook finalizează o epocă de antrenare, THE Experiment_Logger SHALL adăuga un rând în `experiments/{run_id}/metrics_by_epoch.csv` cu coloanele: `epoch`, `train_loss`, `val_loss`, `val_auc`, `val_f1`, `val_sensitivity`, `val_specificity`, `val_pr_auc`, `lr`, `time_epoch_sec`.
3. THE Centralized_Notebook SHALL folosi split-ul fix din `experiments/splits/train_pool.csv` pentru antrenare și validare (80/20 stratificat din train_pool), în locul split-ului original al notebook-ului.
4. WHEN Centralized_Notebook identifică cel mai bun model (după val_auc), THE Experiment_Logger SHALL salva în `experiments/{run_id}/artifacts/best_model/`: fișierul `weights.pt`, fișierul `model_hash.txt` (hash SHA-256 al weights), fișierul `predictions_test.csv` (coloane: `filename`, `y_true`, `y_score`) evaluat pe test_global, fișierul `confusion_matrix.json` (câmpurile: `threshold`, `TP`, `FP`, `TN`, `FN`) la threshold 0.5.
5. THE Centralized_Notebook SHALL folosi un seed fix (valoarea `42`) pentru toate operațiile cu caracter aleatoriu (inițializare model, augmentări, split-uri).
6. IF val_auc nu se îmbunătățește timp de `early_stopping_patience` epoci consecutive, THEN THE Centralized_Notebook SHALL opri antrenarea și SHALL loga în `run_config.json` câmpul `early_stopped_at_epoch` cu numărul epocii la care s-a oprit.

---

### Cerința 3: Evaluarea Modelului Global pe test_global după Fiecare Rundă FL

**User Story:** Ca cercetător, vreau ca serverul FL să evalueze modelul global pe test_global după fiecare rundă de agregare, astfel încât să pot trasa curbele AUC vs. rundă și F1 vs. rundă pentru comparație.

#### Criterii de Acceptare

1. WHEN FL_Strategy finalizează agregarea parametrilor într-o rundă, THE FL_Strategy SHALL evalua modelul global pe test_global și SHALL calcula metricile: `test_auc`, `test_f1`, `test_sensitivity`, `test_specificity`, `test_pr_auc`.
2. WHEN FL_Strategy finalizează o rundă, THE Experiment_Logger SHALL adăuga un rând în `experiments/{run_id}/central/metrics_by_round.csv` cu coloanele: `round`, `num_clients`, `aggregation_method`, `time_round_sec`, `update_norm`, `test_auc`, `test_f1`, `test_sensitivity`, `test_specificity`, `test_pr_auc`.
3. THE FL_Strategy SHALL salva parametrii modelului global după fiecare rundă în `experiments/{run_id}/central/global_models/round_{NNN}_weights.pt`, unde `{NNN}` este numărul rundei cu zero-padding la 3 cifre.
4. WHEN toate rundele FL sunt finalizate, THE FL_Strategy SHALL identifica runda cu cel mai mare `test_auc` și SHALL salva în `experiments/{run_id}/central/best_model/`: fișierul `weights.pt`, fișierul `model_hash.txt`, fișierul `predictions_test.csv` și fișierul `confusion_matrix.json` la threshold 0.5.
5. THE FL_Strategy SHALL crea directorul `experiments/{run_id}/` și SHALL scrie fișierul `run_config.json` la pornirea serverului, cu câmpurile: `run_id`, `timestamp`, `experiment_type` (valoarea `"federated"`), `aggregation_method`, `model_arch`, `num_rounds`, `local_epochs`, `min_fit_clients`, `batch_size`, `lr`, `optimizer`, `dataset_summary` (distribuția per nod din `data_distribution.json`), `thresholding_policy` (valoarea `"fixed_0.5"`).
6. IF evaluarea pe test_global eșuează pentru o rundă (ex. fișier lipsă, eroare de inferență), THEN THE FL_Strategy SHALL loga eroarea, SHALL continua cu runda următoare și SHALL scrie valori `null` pentru metricile de test în rândul corespunzător din CSV.

---

### Cerința 4: Logging per Nod în Antrenarea FL

**User Story:** Ca cercetător, vreau să colectez metricile de validare de la fiecare nod FL după fiecare rundă locală, astfel încât să pot analiza heterogenitatea datelor și convergența per nod.

#### Criterii de Acceptare

1. WHEN FL_Client finalizează antrenarea locală într-o rundă, THE Experiment_Logger SHALL adăuga un rând în `experiments/{run_id}/nodes/node{N}_metrics_by_round.csv` cu coloanele: `round`, `node_id`, `n_train_samples_used`, `val_auc`, `val_f1`, `val_sensitivity`, `val_specificity`, `val_pr_auc`, `local_train_time_sec`, `delta_norm`.
2. THE FL_Client SHALL calcula `delta_norm` ca norma L2 a diferenței dintre parametrii modelului local după antrenare și parametrii modelului global primit de la server (‖W_local − W_global‖).
3. THE FL_Client SHALL folosi split-ul fix din `experiments/splits/node{N}_train.csv` și `experiments/splits/node{N}_val.csv` în locul split-ului aleatoriu 80/20 existent.
4. THE FL_Client SHALL transmite metricile de validare (`val_auc`, `val_f1`, `val_sensitivity`, `val_specificity`, `val_pr_auc`, `local_train_time_sec`, `delta_norm`, `n_train_samples_used`) către server prin dicționarul de metrici returnat din metoda `fit()`.
5. IF fișierele de split pentru un nod nu există în `experiments/splits/`, THEN THE FL_Client SHALL loga o eroare clară cu calea așteptată și SHALL opri execuția task-ului Celery cu status `"failed"`.

---

### Cerința 5: Parametri Noi pentru run_id în API și Orchestrare

**User Story:** Ca cercetător, vreau să pot specifica un `run_id` explicit la pornirea unui experiment FL, astfel încât fișierele de output să fie organizate consistent și ușor de identificat.

#### Criterii de Acceptare

1. THE `POST /api/fl/start` endpoint SHALL accepta un parametru opțional `run_id` de tip string; WHEN `run_id` nu este furnizat, THE endpoint SHALL genera automat un `run_id` cu formatul `fl_{strategy}_{model}_run{NN}` unde `{NN}` este un număr secvențial bazat pe directoarele existente în `experiments/`.
2. THE `flower_server.py` SHALL accepta argumentul CLI `--run-id` și SHALL transmite valoarea `run_id` către `FL_Strategy` la inițializare.
3. THE `tasks.py` SHALL accepta parametrul `run_id` în `federated_training_task()` și SHALL transmite valoarea `run_id` către `start_flower_client()`.
4. THE `test_e2e_5nodes.py` SHALL genera un `run_id` unic per sesiune (format: `fl_{strategy}_effb0_run{NN}`) și SHALL transmite `run_id` la pornirea serverului Flower și la declanșarea antrenării pe noduri.
5. WHEN `test_e2e_5nodes.py` finalizează toate sesiunile, THE script SHALL verifica existența fișierelor `metrics_by_round.csv` și `run_config.json` pentru fiecare `run_id` generat și SHALL raporta în sumarul final dacă fișierele sunt prezente sau lipsesc.

---

### Cerința 6: Generarea Graficelor Comparative Finale

**User Story:** Ca cercetător, vreau să generez automat toate graficele necesare lucrării de disertație dintr-o singură comandă, astfel încât să pot reproduce vizualizările oricând după finalizarea experimentelor.

#### Criterii de Acceptare

1. THE Plot_Generator SHALL citi fișierele `metrics_by_epoch.csv` (centralizat) și `metrics_by_round.csv` (FL) din directoarele de experiment și SHALL produce fișierul `results/comparison_table.csv` și `results/comparison_table.md` cu coloanele: `model`, `AUC`, `F1`, `Sensitivity`, `Specificity`, `PR_AUC`, populate cu valorile de pe test_global pentru fiecare experiment.
2. THE Plot_Generator SHALL produce fișierul `results/auc_vs_round.png` care conține 3 curbe FL (FedAvg, FedAvgM, FedProx) și o linie orizontală reprezentând AUC-ul modelului centralizat pe test_global.
3. THE Plot_Generator SHALL produce fișierul `results/f1_vs_round.png` cu aceeași structură ca `auc_vs_round.png`, dar pentru metrica F1.
4. THE Plot_Generator SHALL produce fișierul `results/roc_curves.png` cu curbele ROC suprapuse pentru modelul centralizat și cel mai bun model FL (după test_auc), citind datele din `predictions_test.csv` al fiecărui experiment.
5. THE Plot_Generator SHALL produce fișierul `results/pr_curves.png` cu curbele Precision-Recall suprapuse, cu aceeași structură ca `roc_curves.png`.
6. THE Plot_Generator SHALL produce fișierul `results/confusion_matrices.png` cu un grid 2×2 (sau 1×4) de matrici de confuzie pentru cele 4 modele (centralizat + 3 FL), citind datele din `confusion_matrix.json` al fiecărui experiment.
7. THE Plot_Generator SHALL produce câte un fișier `results/per_node_auc_fedavg.png`, `results/per_node_auc_fedavgm.png` și `results/per_node_auc_fedprox.png`, fiecare conținând 5 curbe (câte una per nod) reprezentând `val_auc` vs. rundă, citind datele din `node{N}_metrics_by_round.csv`.
8. IF un fișier de input necesar lipsește (ex. `metrics_by_round.csv` pentru o strategie FL), THEN THE Plot_Generator SHALL afișa un avertisment explicit cu calea fișierului lipsă și SHALL continua generarea graficelor pentru care datele sunt disponibile, fără a opri execuția.
9. THE Plot_Generator SHALL accepta ca argumente CLI directoarele de experiment pentru fiecare run (ex. `--centralized experiments/centralized_effb0_run01 --fedavg experiments/fl_fedavg_effb0_run01 ...`) astfel încât să poată fi rulat cu orice combinație de experimente finalizate.

---

### Cerința 7: Structura de Output Standardizată

**User Story:** Ca cercetător, vreau ca toate fișierele de output să fie organizate într-o structură de directoare predictibilă și documentată, astfel încât să pot naviga și partaja rezultatele experimentelor fără ambiguitate.

#### Criterii de Acceptare

1. THE Experiment_Logger SHALL crea și menține structura de directoare pentru antrenarea centralizată conform schemei:
   ```
   experiments/
     {run_id}/
       run_config.json
       metrics_by_epoch.csv
       artifacts/best_model/
         weights.pt
         model_hash.txt
         predictions_test.csv
         confusion_matrix.json
         roc_curve.png
         pr_curve.png
         confusion_matrix.png
   ```
2. THE Experiment_Logger SHALL crea și menține structura de directoare pentru antrenarea FL conform schemei:
   ```
   experiments/
     {run_id}/
       run_config.json
       central/
         metrics_by_round.csv
         global_models/
           round_000_weights.pt
           ...
           round_029_weights.pt
         best_model/
           weights.pt
           model_hash.txt
           predictions_test.csv
           confusion_matrix.json
       nodes/
         node1_metrics_by_round.csv
         node2_metrics_by_round.csv
         node3_metrics_by_round.csv
         node4_metrics_by_round.csv
         node5_metrics_by_round.csv
   ```
3. THE Plot_Generator SHALL crea directorul `results/` și SHALL scrie toate graficele și tabelele comparative în acest director.
4. THE Experiment_Logger SHALL crea toate directoarele necesare cu `mkdir -p` (echivalent Python: `Path.mkdir(parents=True, exist_ok=True)`) înainte de prima scriere, fără a eșua dacă directoarele există deja.
5. WHEN un fișier CSV este creat pentru prima dată, THE Experiment_Logger SHALL scrie header-ul cu toate coloanele definite; WHEN un rând nou este adăugat la un CSV existent, THE Experiment_Logger SHALL adăuga rândul fără a rescrie header-ul.

---

### Cerința 8: Reproductibilitate și Integritate

**User Story:** Ca cercetător, vreau ca experimentele să fie reproductibile și verificabile, astfel încât rezultatele din lucrarea de disertație să poată fi validate independent.

#### Criterii de Acceptare

1. THE Data_Splitter SHALL folosi seed-ul fix `42` pentru toate operațiile cu caracter aleatoriu (eșantionare stratificată, distribuție Dirichlet), astfel încât rulările repetate ale scriptului să producă fișiere de split identice.
2. THE Centralized_Notebook SHALL folosi seed-ul fix `42` pentru `torch.manual_seed()`, `numpy.random.seed()` și `random.seed()` la începutul execuției.
3. THE FL_Strategy SHALL calcula hash-ul SHA-256 al fiecărui model salvat și SHALL scrie valoarea în fișierul `model_hash.txt` corespunzător, pentru verificarea integrității.
4. THE `run_config.json` SHALL conține câmpul `git_commit_hash` populat cu hash-ul commit-ului curent din repository (obținut prin `git rev-parse HEAD`); IF repository-ul nu este disponibil sau comanda eșuează, THEN câmpul SHALL conține valoarea `"unknown"`.
5. THE `predictions_test.csv` SHALL conține coloanele `filename`, `y_true` și `y_score` (probabilitatea pentru clasa PNEUMONIA), astfel încât curbele ROC și PR să poată fi recalculate independent din acest fișier.
6. THE `confusion_matrix.json` SHALL conține câmpurile `threshold` (valoarea `0.5`), `TP`, `FP`, `TN`, `FN`, `accuracy`, `sensitivity` și `specificity`, calculate pe test_global.
