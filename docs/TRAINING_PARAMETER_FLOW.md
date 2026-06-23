# Training Parameter Flow — Fed-Med-FL

**Data**: Mai 2026  
**Scop**: Documentează cum ajung parametrii de antrenare de la sursă până la training loop, urmărind fiecare pas prin cod.

---

## Rezumat

Parametrii de antrenare au **două surse** și **două căi** distincte:

| Cale | Sursă | Parametri |
|------|-------|-----------|
| **Federated (Flower)** | Central Server | `num_rounds`, `num_epochs`, `learning_rate`, `optimizer`, `model_name`, `min_fit_clients`, `min_available_clients` |
| **Federated (Flower)** | Fiecare nod | `batch_size` |
| **Local Training** | Node API request | toți parametrii direct |

---

## Cale 1: Federated Learning (Flower)

### 1.1 Sursa parametrilor — `docker-compose.yml`

Parametrii de bază sunt definiți ca variabile de mediu pe containerul `central`:

```yaml
# docker-compose.yml → central service
NUM_ROUNDS: 2
NUM_EPOCHS: 2
LEARNING_RATE: 0.001
OPTIMIZER: adam
MODEL_NAME: efficientnet_b0
MIN_FIT_CLIENTS: 2
MIN_AVAILABLE_CLIENTS: 3
```

`batch_size` este definit pe fiecare container worker (per-nod):

```yaml
# docker-compose.yml → node1-worker, node2-worker, node3-worker
BATCH_SIZE: 32   # fiecare nod poate avea valoare diferită
```

---

### 1.2 Intrarea prin API — `central/app/main.py`

Endpoint-ul `POST /api/fl/start` permite suprascrierea parametrilor din `docker-compose.yml` la fiecare sesiune de antrenare:

```python
# central/app/main.py
@app.post("/api/fl/start")
def start_fl_server(
    num_rounds: int = 2,
    num_epochs: int = 2,
    model_name: str = "efficientnet_b0",
    learning_rate: float = 0.001,
    optimizer: str = "adam",
    min_fit_clients: int = 2,
    min_available_clients: int = 2,
):
```

Parametrii primiți sunt pasați ca argumente CLI unui subprocess:

```python
cmd = [
    sys.executable, "-m", "app.flower_server",
    "--num-rounds", str(num_rounds),
    "--num-epochs", str(num_epochs),
    "--model-name", model_name,
    "--learning-rate", str(learning_rate),
    "--optimizer", optimizer,
    "--min-fit-clients", str(min_fit_clients),
    "--min-available-clients", str(min_available_clients),
    "--storage-path", STORAGE_ROOT,
    # + SSL/certificate params din env vars
]
subprocess.Popen(cmd, ...)
```

**Notă**: `batch_size` nu este acceptat de `/api/fl/start` — este exclusiv per-nod.

---

### 1.3 Flower Server — `central/app/flower_server.py`

`main()` parsează argumentele CLI (cu fallback pe env vars):

```python
# flower_server.py::main()
num_rounds = args.num_rounds if args.num_rounds is not None else int(os.getenv("NUM_ROUNDS", "5"))
num_epochs = args.num_epochs if args.num_epochs is not None else int(os.getenv("NUM_EPOCHS", "2"))
learning_rate = args.learning_rate if ... else float(os.getenv("LEARNING_RATE", "0.001"))
optimizer = args.optimizer if ... else os.getenv("OPTIMIZER", "adam")
model_name = args.model_name if ... else os.getenv("MODEL_NAME", "resnet18")
min_fit_clients = args.min_fit_clients if ... else int(os.getenv("MIN_FIT_CLIENTS", "1"))
min_available_clients = args.min_available_clients if ... else int(os.getenv("MIN_AVAILABLE_CLIENTS", "3"))
```

Apoi apelează `start_flower_server()` cu toți parametrii, care la rândul lui apelează `create_fedmed_strategy()`:

```python
# flower_server.py::start_flower_server()
strategy = create_fedmed_strategy(
    model_name=model_name,
    num_epochs=num_epochs,
    learning_rate=learning_rate,
    optimizer=optimizer,
    min_fit_clients=min_fit_clients,
    min_available_clients=min_available_clients,
    ...
)
config = fl.server.ServerConfig(num_rounds=num_rounds)
fl.server.start_server(config=config, strategy=strategy, ...)
```

---

### 1.4 Strategy — `node_core/flower_strategy.py`

`FedMedStrategy` stochează parametrii de antrenare pe instanță:

```python
# flower_strategy.py::FedMedStrategy.__init__()
self.num_epochs = num_epochs        # stocat
self.learning_rate = learning_rate  # stocat
self.optimizer = optimizer          # stocat
self.model_name = model_name        # stocat
```

La fiecare rundă, `configure_fit()` construiește un dict de configurare și îl trimite fiecărui client prin protocolul gRPC Flower:

```python
# flower_strategy.py::FedMedStrategy.configure_fit()
new_config = {
    "server_round": server_round,   # numărul rundei curente
    "num_epochs": self.num_epochs,  # ← trimis la client
    "learning_rate": self.learning_rate,  # ← trimis la client
    "optimizer": self.optimizer,    # ← trimis la client
}
new_fit_ins = fl.common.FitIns(fit_ins.parameters, new_config)
```

**Acesta este momentul în care parametrii trec de la server la client** — prin `FitIns.config`, un dict serializat în mesajul gRPC.

---

### 1.5 Flower Client — `flower_client.py`

#### Inițializare (înainte de conectare la server)

`start_flower_client()` este apelat din `tasks.py` cu parametrii per-nod:

```python
# flower_client.py::start_flower_client()
client = FedMedClient(
    node_id=node_id,
    model_name=model_name,   # ← din tasks.py (din API request)
    batch_size=batch_size,   # ← din tasks.py (din API request sau env var)
    dataset_path=dataset_path,
    device=device,
    ...
)
```

`batch_size` este folosit imediat la încărcarea datelor, **înainte** ca serverul să trimită orice configurare:

```python
# flower_client.py::FedMedClient._load_data()
train_loader, val_loader = create_dataloaders(
    train_dataset, val_dataset,
    batch_size=self.batch_size,  # ← setat la init, nu vine de la server
    num_workers=0
)
```

#### La fiecare rundă (după conectare)

`fit()` primește `config` de la server prin Flower:

```python
# flower_client.py::FedMedClient.fit()
def fit(self, parameters, config):
    # Parametrii vin din configure_fit() al serverului
    num_epochs    = config.get("num_epochs", 5)       # default dacă serverul nu trimite
    learning_rate = config.get("learning_rate", 0.001)
    optimizer_name = config.get("optimizer", "adam")
    current_round = config.get("server_round", "?")

    # Folosiți în training
    optimizer = get_optimizer(self.model, optimizer_name, lr=learning_rate)
    scheduler = get_scheduler(optimizer, 'cosine', num_epochs=num_epochs)
    history = train_model(..., num_epochs=num_epochs, ...)
```

---

### 1.6 Calea nodului — `tasks.py` și `main.py`

Când un utilizator apelează `POST /api/federated/train`, parametrii per-nod sunt pasați astfel:

```
POST /api/federated/train?dataset_id=...&model_name=efficientnet_b0&batch_size=16
    ↓
node/api/app/main.py::start_federated_training()
    ↓
federated_training_task.delay(job_id, dataset_id, model_name, batch_size)
    ↓
tasks.py::federated_training_task()
    ↓
start_flower_client(
    server_address=settings.FLOWER_SERVER,
    model_name=model_name,   # din API request
    batch_size=batch_size,   # din API request
    session_id=job_id,
    ...
)
```

---

## Cale 2: Local Training

Local training nu folosește Flower. Toți parametrii vin direct din request-ul API:

```
POST /api/train/local
Body: { dataset_id, model_name, num_epochs, batch_size, learning_rate, optimizer }
    ↓
node/api/app/main.py::start_local_training()
    ↓
train_local_model_task.delay(job_id, dataset_id, model_name, num_epochs, batch_size, learning_rate)
    ↓
tasks.py::train_local_model_task()
    ├─ create_dataloaders(..., batch_size=batch_size)
    ├─ get_optimizer(model, 'adam', lr=learning_rate)  ← optimizer hardcodat 'adam'
    └─ train_model(..., num_epochs=num_epochs)
```

**Notă**: `optimizer` este hardcodat ca `'adam'` în `train_local_model_task` — nu poate fi schimbat din API.

---

## Diagrama completă a fluxului

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SURSE DE PARAMETRI                               │
│                                                                     │
│  docker-compose.yml          POST /api/fl/start                    │
│  (valori implicite)          (suprascrie per sesiune)              │
│         │                           │                              │
│         └──────────────┬────────────┘                              │
│                        ↓                                           │
│              central/app/main.py                                   │
│              start_fl_server()                                     │
│                        │                                           │
│                        │ subprocess CLI args                       │
│                        ↓                                           │
│              central/app/flower_server.py                          │
│              start_flower_server()                                 │
│                        │                                           │
│                        ↓                                           │
│              node_core/flower_strategy.py                          │
│              FedMedStrategy.__init__()                             │
│              stochează: num_epochs, lr, optimizer, model_name      │
│                        │                                           │
│              ┌─────────┴──────────────────────┐                   │
│              │  La fiecare rundă FL:           │                   │
│              │  configure_fit() → FitIns.config│                   │
│              │  trimite: num_epochs, lr,       │                   │
│              │           optimizer, round_num  │                   │
│              └─────────┬──────────────────────┘                   │
│                        │ gRPC (Flower protocol)                    │
│                        ↓                                           │
│              flower_client.py                                      │
│              FedMedClient.fit(parameters, config)                  │
│              citește: num_epochs, lr, optimizer din config         │
│                        │                                           │
│                        ↓                                           │
│              train_model() / _train_with_dp()                      │
│                                                                    │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                                                    │
│  POST /api/federated/train?batch_size=16                           │
│         │                                                          │
│         ↓                                                          │
│  node/api/app/main.py → tasks.py → start_flower_client()          │
│  FedMedClient.__init__(batch_size=16)                              │
│  _load_data() → create_dataloaders(batch_size=16)                  │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Matricea de control a parametrilor

| Parametru | Cine îl controlează | Cum ajunge la training | Poate fi schimbat fără restart? |
|-----------|--------------------|-----------------------|--------------------------------|
| `num_rounds` | Central Server | env → CLI → `ServerConfig` | ✅ Da, prin `/api/fl/start` |
| `num_epochs` | Central Server | env → CLI → `configure_fit()` → `fit()` | ✅ Da, prin `/api/fl/start` |
| `learning_rate` | Central Server | env → CLI → `configure_fit()` → `fit()` | ✅ Da, prin `/api/fl/start` |
| `optimizer` | Central Server | env → CLI → `configure_fit()` → `fit()` | ✅ Da, prin `/api/fl/start` |
| `model_name` | Central Server | env → CLI → `FedMedStrategy` → `initialize_parameters()` | ✅ Da, prin `/api/fl/start` |
| `min_fit_clients` | Central Server | env → CLI → `FedMedStrategy` (FedAvg param) | ✅ Da, prin `/api/fl/start` |
| `min_available_clients` | Central Server | env → CLI → `FedMedStrategy` (FedAvg param) | ✅ Da, prin `/api/fl/start` |
| `batch_size` | Fiecare nod | API request → `tasks.py` → `FedMedClient.__init__()` → `create_dataloaders()` | ✅ Da, prin `/api/federated/train?batch_size=X` |

---

## Probleme cunoscute și limitări

### 1. `batch_size` în DP training este hardcodat

În `_train_with_dp()`, `max_physical_batch_size` este hardcodat la 32, indiferent de `batch_size` primit:

```python
# flower_client.py::_train_with_dp()
with BatchMemoryManager(
    data_loader=train_loader,
    max_physical_batch_size=32,  # ← hardcodat, nu folosește self.batch_size
    optimizer=optimizer
)
```

### 2. `optimizer` hardcodat în local training

`train_local_model_task` ignoră parametrul `optimizer` din request și folosește întotdeauna `'adam'`:

```python
# tasks.py::train_local_model_task()
optimizer = get_optimizer(model, 'adam', lr=learning_rate)  # ← hardcodat
```

### 3. `model_name` are două surse independente

Serverul Flower pornește cu `model_name` din `/api/fl/start`, iar clientul primește `model_name` din `/api/federated/train`. Dacă cele două diferă, serverul inițializează modelul global cu o arhitectură, iar clientul antrenează cu alta — incompatibilitate garantată.

**Recomandare**: Clientul ar trebui să citească `model_name` din config-ul trimis de server prin `configure_fit()`, nu din parametrul API.

### 4. Parametrii de antrenare nu sunt validați cross-service

Nu există nicio verificare că `model_name` din `/api/fl/start` și `model_name` din `/api/federated/train` sunt identice. Această validare trebuie făcută manual de utilizator.

---

## Cum să schimbi parametrii pentru o sesiune nouă

```bash
# Pornești serverul Flower cu parametrii doriți
curl -X POST "http://localhost:8081/api/fl/start" \
  -G \
  -d "num_rounds=5" \
  -d "num_epochs=3" \
  -d "model_name=resnet18" \
  -d "learning_rate=0.0005" \
  -d "optimizer=adam" \
  -d "min_fit_clients=2"

# Pornești training pe fiecare nod cu batch_size dorit
curl -X POST "http://localhost:8001/api/federated/train" \
  -G \
  -d "dataset_id=dataset_train_abc123" \
  -d "model_name=resnet18" \
  -d "batch_size=16" \
  -H "Authorization: Bearer $TOKEN"
```

---

*Document generat: Mai 2026*  
*Fișiere analizate: `docker-compose.yml`, `central/app/main.py`, `central/app/flower_server.py`, `node_core/flower_strategy.py`, `worker/app/flower_client.py`, `node/api/app/main.py`, `node/api/app/tasks.py`*
