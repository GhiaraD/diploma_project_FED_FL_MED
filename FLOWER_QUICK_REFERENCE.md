# Flower Framework - Quick Reference

**Fed-Med-FL Project** | Version 0.2.0

---

## 🚀 Quick Start

### Option 1: Simulation (Fastest)
```bash
python3 shared/python/node_core/examples/flower_simulation.py \
  --clients 3 --rounds 3 --epochs 2
```

### Option 2: Docker (Production)
```bash
# 1. Rebuild
docker compose build

# 2. Start
docker compose up -d

# 3. Upload datasets (via UI)
# http://localhost:3001, 3002, 3003

# 4. Start Flower server
docker compose exec central python -m app.flower_server

# 5. Start clients (in separate terminals)
curl -X POST "http://localhost:8001/api/federated/train/R-1?dataset_id=<ID>"
curl -X POST "http://localhost:8002/api/federated/train/R-1?dataset_id=<ID>"
curl -X POST "http://localhost:8003/api/federated/train/R-1?dataset_id=<ID>"
```

---

## 📁 Key Files

### Flower Components
```
shared/python/node_core/node_core/
├── flower_strategy.py      # Custom FedAvg strategy
└── __init__.py             # Exports

services/central/app/
└── flower_server.py        # Flower gRPC server

services/node/worker/app/
└── flower_client.py        # Flower NumPy client

services/node/api/app/
└── tasks.py                # Celery task integration
```

### Tests & Examples
```
shared/python/node_core/
├── tests/
│   └── test_flower_strategy.py    # Unit tests
└── examples/
    └── flower_simulation.py       # Simulation

scripts/
└── test_flower_workflow.sh        # Integration test
```

### Documentation
```
docs/
├── FLOWER_MIGRATION_PLAN.md       # Migration plan
├── FLOWER_MIGRATION_PROGRESS.md   # Progress tracker
├── FLOWER_MIGRATION_COMPLETE.md   # Final summary
├── PHASE4_COMPLETE.md             # Testing phase
├── PHASE4_TEST_RESULTS.md         # Test results
└── PHASE5_COMPLETE.md             # Documentation phase

FLOWER_MIGRATION_SUMMARY.md        # Quick summary
FLOWER_QUICK_REFERENCE.md          # This file
```

---

## 🔧 Configuration

### Environment Variables (docker-compose.yml)

**Central**:
```yaml
FLOWER_SERVER_ADDRESS: 0.0.0.0:8080
NUM_ROUNDS: 5
MIN_CLIENTS: 2
MODEL_NAME: resnet18
NUM_CLASSES: 2
```

**Nodes**:
```yaml
FLOWER_SERVER: central:8080
NODE_ID: node1
DEVICE: cpu
```

### Ports
```
8080 - Flower gRPC (Central)
8081 - Management API (Central)
8001 - Node1 API
8002 - Node2 API
8003 - Node3 API
3001 - Node1 UI
3002 - Node2 UI
3003 - Node3 UI
```

---

## 🧪 Testing

### Unit Tests
```bash
# Requires pytest
pytest shared/python/node_core/tests/test_flower_strategy.py -v
```

### Simulation
```bash
# Quick test (2 clients, 2 rounds)
python3 shared/python/node_core/examples/flower_simulation.py \
  --clients 2 --rounds 2 --epochs 1

# Full test (3 clients, 3 rounds)
python3 shared/python/node_core/examples/flower_simulation.py \
  --clients 3 --rounds 3 --epochs 2
```

### Integration
```bash
# Start services first
docker compose up -d

# Run test script
bash scripts/test_flower_workflow.sh
```

---

## 📊 Monitoring

### Flower Server Logs
```bash
# If running in Docker
docker compose logs -f central

# If running manually
# Watch terminal where flower_server.py is running
```

### Node Worker Logs
```bash
docker compose logs -f node1-worker
docker compose logs -f node2-worker
docker compose logs -f node3-worker
```

### Check Saved Models
```bash
ls -la storage/central/models/
# Should see: global_R-0.pt, global_R-1.pt, global_R-2.pt, ...
```

---

## 🔍 Troubleshooting

### Server won't start
```bash
# Check logs
docker compose logs central

# Verify port not in use
lsof -i :8080

# Restart
docker compose restart central
```

### Client can't connect
```bash
# Check server is running
curl http://localhost:8081/health

# Check Flower server logs
docker compose logs -f central

# Verify network
docker compose exec node1-worker ping central
```

### Training fails
```bash
# Check worker logs
docker compose logs -f node1-worker

# Verify dataset exists
curl http://localhost:8001/api/data/list

# Check storage
ls -la storage/node1/datasets/
```

### OOM in simulation
```bash
# Reduce clients or use smaller model
python3 shared/python/node_core/examples/flower_simulation.py \
  --clients 2 --rounds 2 --model resnet18
```

---

## 📚 Resources

### Internal
- **Migration Plan**: `docs/FLOWER_MIGRATION_PLAN.md`
- **Quick Start**: `docs/QUICK_START.md`
- **Main README**: `README.md`

### External
- **Flower Docs**: https://flower.dev/docs/
- **Flower GitHub**: https://github.com/adap/flower
- **Flower Examples**: https://github.com/adap/flower/tree/main/examples
- **Flower Slack**: https://flower.dev/join-slack

---

## 💡 Tips

### Development
- Use simulation for rapid testing
- Check Flower server logs for debugging
- Monitor model sizes in storage/

### Production
- Rebuild Docker images after code changes
- Use real datasets for testing
- Monitor memory usage
- Set appropriate timeouts

### Performance
- gRPC is faster than HTTP REST
- Use GPU if available (set DEVICE=cuda)
- Adjust batch size based on memory
- Monitor network bandwidth

---

## 🎯 Common Tasks

### Add New Strategy
```python
# In flower_strategy.py
class MyCustomStrategy(fl.server.strategy.FedAvg):
    def aggregate_fit(self, ...):
        # Custom aggregation logic
        pass
```

### Change Model
```python
# In flower_server.py or environment
MODEL_NAME=densenet121  # or efficientnet_b0
```

### Adjust Rounds
```python
# In flower_server.py or environment
NUM_ROUNDS=10
MIN_CLIENTS=3
```

### Enable TLS
```python
# In flower_server.py
fl.server.start_server(
    server_address="0.0.0.0:8080",
    config=config,
    strategy=strategy,
    certificates=(
        Path("certificates/ca.crt").read_bytes(),
        Path("certificates/server.pem").read_bytes(),
        Path("certificates/server.key").read_bytes(),
    ),
)
```

---

## ✅ Checklist

### Before Deployment
- [ ] Rebuild Docker images
- [ ] Test with real datasets
- [ ] Verify all services start
- [ ] Check Flower server connects
- [ ] Test full FL round
- [ ] Verify models saved
- [ ] Check logs for errors

### After Deployment
- [ ] Monitor server logs
- [ ] Check model convergence
- [ ] Verify storage usage
- [ ] Test UI functionality
- [ ] Document any issues

---

**Version**: 0.2.0  
**Date**: 2026-04-20  
**Status**: Production Ready
