Prompt pentru agent AI: Plan de antrenare + loguri + structură fișiere (Centralizat vs FL cu 5 noduri)

Ești un asistent tehnic pentru un proiect de disertație: clasificarea imaginilor (Chest X-ray) în NORMAL vs PNEUMONIA, folosind EfficientNet-B0 ca punct de plecare, și comparând un model centralizat cu mai multe modele Federated Learning (FL) pe 5 noduri (toate 5 participă în fiecare rundă). Scopul este să obținem rezultate reproductibile, comparabile și ușor de prezentat în lucrare.

antrenarea centrala este integral in chest-x-ray-pneumonia-detection-with-deep-learning.ipynb

1) Date și split (obligatoriu)

Avem un dataset de ~5000 imagini JPEG: Acesta este in /central_dataset

~1300 NORMAL
~3800 PNEUMONIA

Trebuie să folosim un test global fix (hold-out) folosit identic pentru toate experimentele:

test_global: 15% din date (stratificat pe clasă), NU intră în niciun training (nici centralizat, nici FL), folosit numai pentru evaluarea comparativă finală și pentru “curbe vs runde”.
Restul 85% (train_pool) se folosește:
în centralizat: train/val stratificat (de ex. 80/20 din train_pool)
în FL: se împarte pe 5 noduri (non-IID), apoi fiecare nod își separă train_local și val_local (de ex. 80/20 din datele nodului).

Non-IID distribution (recomandat): creează distribuții diferite per nod (ex. noduri cu proporții diferite NORMAL/PNEUMONIA), dar păstrează totalul global din train_pool aproximativ consistent. Scop: să existe heterogenitate între noduri, astfel încât să fie relevantă comparația între metode FL.

2) Model și setări comune (obligatoriu)
Model: EfficientNet-B0, pretrained ImageNet.
Input: 224×224.
Loss: BCEWithLogitsLoss sau CrossEntropyLoss + class weights (avem imbalance).
Optimizator: AdamW sau Adam.
LR: 1e-4.
Batch size: 32 (sau 16 dacă nu încape).
Augmentări: basic (random horizontal flip, affine/rotation modest, normalization).
Seed fix pentru reproducibilitate.
3) Experimente de rulat (plan complet)
A) Baseline centralizat (1 run)
Date: train_pool împărțit în train/val (stratificat).
Training: 15–25 epoci cu early stopping (monitorizare AUC sau F1 pe val).
Evaluare finală: pe test_global (fix).
Salvează modelul “best” (după val metric).
B) Federated Learning (3 runs cu agregări diferite)

Folosim Flower pentru orchestrare, dar implementarea poate fi Flower standard + strategy custom.

Număr noduri: 5 (toate participă la fiecare rundă).
Rounds: 30 (dacă e lent, minim 20; preferat 30 pentru curbe relevante).
Local epochs per round: 1 (E=1 pentru stabilitate non-IID).
Batch size: 32.
LR local: 1e-4.
Update: delta weights (ΔW = W_local − W_global).
Agregare: comparăm 3 metode:
FedAvg (baseline FL)
FedAvgM (server momentum=0.9)
FedProx (mu=0.01) sau alternativ o strategie robustă dacă se cere strict “aggregation”; preferat FedProx pentru non-IID

Pentru fiecare metodă FL:

după fiecare rundă, centrul produce W_{t+1} și îl evaluează pe test_global (același test fix).
salvăm metricile per rundă + per nod.
4) Metrici obligatorii (colectare standard)

Pentru comparații în lucrare, colectăm:

AUC-ROC
F1
Sensitivity (Recall pentru PNEUMONIA)
Specificity
Recomandat în plus:
PR-AUC (mai robust pentru imbalance)
Confusion Matrix
ROC & PR curves

Trebuie să fie clar dacă pragul este:

fix 0.5, sau
ales pe val (explicat și aplicat consistent)
5) Ce loguri trebuie colectate (detaliat)
A) Per experiment (o singură dată)

Creează un run_config.json pentru fiecare experiment (centralizat sau FL) cu:

run_id, timestamp, git_commit_hash
experiment_type: centralized / federated
aggregation_method (pentru FL)
model_arch, pretrained, input_size
dataset_summary:
total_images, num_normal, num_pneumonia
test_global split (size + class counts)
pentru FL: distribuția pe noduri (num samples și class counts pe nod)
training_hyperparams:
epochs_max (centralizat), early stopping criteria
rounds, local_epochs, min_fit_clients=5, participation=5/5 (FL)
batch_size, lr, optimizer, scheduler, class weights, augmentations
thresholding_policy (0.5 sau optimal)
B) Centralizat – per epocă

metrics_by_epoch.csv cu coloane:

epoch
train_loss, val_loss
val_auc, val_f1, val_sensitivity, val_specificity, val_pr_auc
lr (opțional)
time_epoch_sec
C) FL – la centru (per rundă)

metrics_by_round.csv (centrul trebuie să logheze pentru fiecare rundă):

round
global_model_version / hash (W_t și W_{t+1})
num_clients_participated (mereu 5)
aggregation_method (fedavg/fedavgm/fedprox)
time_round_sec
update_norm (opțional: ||ΔW_avg||)
test_global metrics (obligatoriu):
test_auc, test_f1, test_sensitivity, test_specificity, test_pr_auc
D) FL – la fiecare nod (per rundă)

Pentru fiecare nod, node_metrics_by_round.csv:

round
node_id
n_train_samples_used
val_auc, val_f1, val_sensitivity, val_specificity, val_pr_auc
local_train_time_sec
delta_norm (opțional: ||ΔW_i||)
E) Pentru figurile finale ROC/PR/CM (pentru fiecare model final raportat)

Pe test_global, salvează:

predictions_test.csv:
sample_id / filename
y_true (0/1)
y_score (probabilitate pneumonie sau logit)
confusion_matrix.json:
threshold
TP, FP, TN, FN

Aceste fișiere permit reconstruirea ROC/PR curves și confusion matrix în mod reproducibil.

6) Structura de fișiere (obligatoriu)

Propune o structură standard sub experiments/:

experiments/
  centralized_effb0_run01/
    run_config.json
    metrics_by_epoch.csv
    artifacts/
      best_model/
        weights.pt
        model_hash.txt
        predictions_test.csv
        confusion_matrix.json
        roc_curve.png
        pr_curve.png
        confusion_matrix.png

  fl_fedavg_effb0_run01/
    run_config.json
    central/
      metrics_by_round.csv
      global_models/
        round_000_weights.pt
        round_001_weights.pt
        ...
      best_model/
        weights.pt
        model_hash.txt
        predictions_test.csv
        confusion_matrix.json
        roc_curve.png
        pr_curve.png
        confusion_matrix.png
    nodes/
      node1_metrics_by_round.csv
      node2_metrics_by_round.csv
      node3_metrics_by_round.csv
      node4_metrics_by_round.csv
      node5_metrics_by_round.csv

  fl_fedavgm_effb0_run01/
    ... (same structure)

  fl_fedprox_effb0_run01/
    ... (same structure)

Notă: “best_model” pentru FL poate fi:

best round după test_auc (pe test_global) pentru prezentare, sau
last round (consistent) + raportezi ambele (recomandat: best și last)
7) Grafice/tabele de produs (cerință finală)

Agentul trebuie să fie capabil să producă:

Tabel final comparativ (pe test_global):
Centralizat vs FedAvg vs FedAvgM vs FedProx
AUC, F1, Sens, Spec, PR-AUC
Grafice:
AUC vs round (3 curbe FL + linie orizontală centralizat)
F1 vs round
(opțional) Sens/Spec vs round
ROC/PR curves pentru centralizat vs best FL
Confusion matrix centralizat vs best FL
Grafic “per-nod”:
AUC_val_local vs round pentru cele 5 noduri (o figură per metodă FL sau una cu 5 linii)
8) Cerințe de implementare (ce trebuie să faci concret)
Creează cod care rulează antrenarea centralizată și loghează exact fișierele de mai sus.
Creează cod Flower server + clients pentru FL cu 5 noduri, toate participă la fiecare rundă, și loghează:
metrics_by_round la centru (inclusiv evaluare pe test_global)
node_metrics_by_round la fiecare nod
salvarea weights per rundă sau măcar periodic (ex. la fiecare 5 runde) + “best_model”
Asigură reproducibilitate:
seed-uri fixe
split-uri fixe salvate ca fișiere (ex. liste de sample_id pentru test/train/val per nod)
9) Output cerut de la tine

În răspunsul tău:

confirmă planul
propune exact cum să faci split-ul non-IID pe 5 noduri (un exemplu concret)
oferă implementare (cod) sau pași concreți pentru logging și structura de fișiere
nu inventa metrici/fișiere suplimentare decât dacă sunt justificate