# Fix pentru Agregarea Metricilor când n_samples=0

## Problema

În timpul testării FL workflow-ului, am descoperit o problemă în `FedAvgAggregator.aggregate_round()`:

**Eroare**: `ZeroDivisionError` când toate nodurile trimit `n_samples=0`

**Cauză**: Codul calcula weighted average folosind:
```python
total_samples = sum(u['n_samples'] for u in updates)  # = 0
weights = [u['n_samples'] / total_samples for u in updates]  # Division by zero!
```

## Soluția

Am modificat codul în `shared/python/node_core/node_core/fl_aggregator.py` (liniile 382-397):

```python
# Aggregate metrics
updates = round_data['updates']
total_samples = sum(u['n_samples'] for u in updates)

aggregated_metrics = {}

# Weighted average of metrics
for metric_name in ['accuracy', 'f1', 'auc', 'precision', 'recall']:
    values = [u['metrics'].get(metric_name, 0) for u in updates]
    
    # If total_samples is 0, use equal weights (simple average)
    if total_samples > 0:
        weights = [u['n_samples'] / total_samples for u in updates]
    else:
        weights = [1.0 / len(updates) for _ in updates]
    
    if any(v > 0 for v in values):
        aggregated_metrics[metric_name] = sum(v * w for v, w in zip(values, weights))
```

## Comportament

### Cazul 1: total_samples > 0 (Normal)
- **Weighted average**: Nodurile cu mai multe sample-uri au mai multă influență
- **Formula**: `metric_avg = Σ(n_i/Σn_i) * metric_i`
- **Exemplu**: 
  - Node1: 1000 samples, acc=0.95
  - Node2: 500 samples, acc=0.90
  - Result: `acc_avg = (1000/1500)*0.95 + (500/1500)*0.90 = 0.9333`

### Cazul 2: total_samples = 0 (Edge case)
- **Simple average**: Toate nodurile au aceeași influență
- **Formula**: `metric_avg = Σ(metric_i) / n_nodes`
- **Exemplu**:
  - Node1: 0 samples, acc=0.9770
  - Node2: 0 samples, acc=0.9856
  - Node3: 0 samples, acc=0.9655
  - Result: `acc_avg = (0.9770 + 0.9856 + 0.9655) / 3 = 0.9760`

## De ce apare n_samples=0?

În implementarea curentă, `n_samples` este setat la 0 în `fl_client.py` pentru că:

1. **Bug în compute_metrics()**: Nu returnează numărul de sample-uri
2. **Workaround temporar**: Setăm `n_samples=0` până fixăm compute_metrics()

## Verificare

Din logurile de training pentru `R-SUCCESS-1`:

**Node1**:
```
n_samples: 0
metrics: {
  'accuracy': 0.9770114942528736,
  'f1': 0.985239852398524,
  'auc': 0.9925373134328358
}
```

**Node2**:
```
n_samples: 0
metrics: {
  'accuracy': 0.985632183908046,
  'f1': 0.9905123339658444,
  'auc': 0.9986132856184299
}
```

**Node3**:
```
n_samples: 0
metrics: {
  'accuracy': 0.9655172413793104,
  'f1': 0.9766536964980544,
  'auc': 0.9962384259259259
}
```

**Expected aggregated metrics (simple average)**:
```
accuracy:  (0.9770 + 0.9856 + 0.9655) / 3 = 0.9760
f1:        (0.9852 + 0.9905 + 0.9767) / 3 = 0.9841
auc:       (0.9925 + 0.9986 + 0.9962) / 3 = 0.9958
```

## Status

✅ **Fix aplicat** în `fl_aggregator.py`  
✅ **Central rebuild-uit** cu fix-ul  
⏳ **Testare end-to-end** - Necesită rulare completă a workflow-ului

## Next Steps

1. **Testare completă**: Rulează un FL round complet pentru a verifica agregarea
2. **Fix n_samples**: Modifică `compute_metrics()` să returneze numărul real de sample-uri
3. **Update fl_client.py**: Folosește `n_samples` real în loc de 0

## Fișiere Modificate

- `shared/python/node_core/node_core/fl_aggregator.py` (liniile 382-397)
- `services/central/` (rebuild necesar)

## Data Fix-ului

**2026-04-17** - Fix aplicat și documentat
