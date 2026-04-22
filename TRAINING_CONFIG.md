# Configurare Parametri de Antrenare

## Unde se setează numărul de epoci și alți hiperparametri

### 1. Variabile de mediu (docker-compose.yml)

Poți seta parametrii prin variabile de mediu în `docker-compose.yml`:

```yaml
services:
  central:
    environment:
      - NUM_ROUNDS=2              # Număr de runde FL
      - NUM_EPOCHS=5              # Epoci per rundă
      - LEARNING_RATE=0.001       # Learning rate
      - OPTIMIZER=adam            # Optimizer (adam, sgd, adamw)
      - MIN_FIT_CLIENTS=2         # Clienți per rundă
      - MIN_AVAILABLE_CLIENTS=3   # Clienți disponibili
      - FRACTION_FIT=0.66         # Fracțiune clienți (0.66 = 2/3)
      - MODEL_NAME=efficientnet_b0
```

### 2. Valori default în cod

Dacă nu setezi variabilele de mediu, se folosesc valorile default:

**În `flower_server.py`:**
- `num_epochs = 5` (epoci per rundă)
- `learning_rate = 0.001`
- `optimizer = "adam"`
- `num_rounds = 5` (runde FL)
- `min_fit_clients = 1` (antrenare secvențială)

**În `flower_client.py`:**
- `num_epochs = 5` (fallback dacă serverul nu trimite config)
- `learning_rate = 0.001`
- `optimizer = "adam"`

### 3. Fluxul de configurare

```
docker-compose.yml (env vars)
         ↓
flower_server.py (main())
         ↓
create_fedmed_strategy()
         ↓
FedMedStrategy.__init__()
         ↓
FedMedStrategy.configure_fit()
         ↓
FitIns(parameters, config={
    "num_epochs": 5,
    "learning_rate": 0.001,
    "optimizer": "adam"
})
         ↓
Flower gRPC → Client
         ↓
FedMedClient.fit(parameters, config)
         ↓
train_model(num_epochs=config["num_epochs"])
```

## Exemple de configurare

### Antrenare rapidă (2 epoci, 2 runde)
```bash
export NUM_ROUNDS=2
export NUM_EPOCHS=2
export MIN_FIT_CLIENTS=2
export FRACTION_FIT=0.66
```

### Antrenare intensivă (10 epoci, 5 runde)
```bash
export NUM_ROUNDS=5
export NUM_EPOCHS=10
export LEARNING_RATE=0.0001
export MIN_FIT_CLIENTS=1  # Secvențial
```

### Antrenare cu toți clienții (3 noduri simultan)
```bash
export NUM_ROUNDS=3
export NUM_EPOCHS=5
export MIN_FIT_CLIENTS=3
export FRACTION_FIT=1.0
```

## Verificare configurație

După pornirea serverului Flower, vei vedea în log:

```
======================================================================
FED-MED-FL FLOWER SERVER
======================================================================
Server address: 0.0.0.0:8080
Number of rounds: 2
Minimum clients: 2
Min fit clients per round: 2
Min available clients: 3
Model: efficientnet_b0
Storage: /storage
Training: 5 epochs, lr=0.001, optimizer=adam
======================================================================
```

## Note importante

1. **Număr de epoci** = epoci per rundă (nu total)
   - 2 runde × 5 epoci = 10 epoci totale per client

2. **Selecția clienților** se face prin:
   - `min_fit_clients` = minim clienți
   - `fraction_fit` = fracțiune din clienți disponibili
   - Formula: `max(min_fit_clients, int(fraction_fit × available))`

3. **Pentru exact 2 clienți din 3**:
   - `MIN_FIT_CLIENTS=2`
   - `FRACTION_FIT=0.66` (sau mai mic)
   - Rezultat: `max(2, int(0.66 × 3)) = max(2, 1) = 2`

4. **Pentru toți clienții**:
   - `MIN_FIT_CLIENTS=3`
   - `FRACTION_FIT=1.0`
   - Rezultat: `max(3, int(1.0 × 3)) = 3`
