# Node Core

Shared Python library for Federated Learning medical imaging platform.

## Features

### ML Core
- **ML Models**: Pre-configured architectures (ResNet18, DenseNet121, EfficientNet-B0)
- **Training**: Complete training loops with early stopping, schedulers
- **Inference**: Single/batch prediction with Grad-CAM visualization
- **Metrics**: Comprehensive evaluation (accuracy, F1, AUC, confusion matrix)
- **Data Utils**: Dataset loading, augmentation, stratified K-fold splits

### Federated Learning ⭐ NEW
- **FL Client**: Delta computation, model pulling/pushing
- **FL Aggregator**: FedAvg aggregation with outlier detection
- **FL Utils**: Delta operations, DP support, metrics aggregation
- **Communication**: HTTP REST API with hash verification

## Installation

```bash
cd shared/python/node_core
pip install -e .
```

## Quick Start

### Federated Learning Round

```python
from node_core import FederatedClient, get_model, train_model

# Initialize FL client
client = FederatedClient(
    node_id='node1',
    central_url='http://central:8080'
)

# Pull global model
global_state, base_hash = client.pull_global_model(round_id='R-1')

# Load and train
model = get_model('resnet18', num_classes=2)
model.load_state_dict(global_state)
history = train_model(model, train_loader, val_loader, ...)

# Compute delta
global_model = get_model('resnet18', num_classes=2)
global_model.load_state_dict(global_state)
delta = client.compute_delta(model, global_model)

# Push update
client.push_update(
    delta=delta,
    round_id='R-1',
    base_model_hash=base_hash,
    n_samples=1000,
    metrics={'accuracy': 0.92, 'f1': 0.90}
)
```

### Central Aggregation

```python
from node_core import FedAvgAggregator, get_model

# Initialize aggregator
aggregator = FedAvgAggregator(storage_path='./storage/central')

# Create round
base_model = get_model('resnet18', num_classes=2)
aggregator.create_round(
    round_id='R-1',
    model_name='resnet18',
    base_model_state=base_model.state_dict(),
    hyperparameters={'lr': 0.001, 'epochs': 5}
)

# Collect updates from nodes...
# (nodes push their deltas)

# Aggregate
result = aggregator.aggregate_round('R-1')
print(f"New model: {result['new_model_path']}")
print(f"Metrics: {result['aggregated_metrics']}")
```

### Run Inference with Grad-CAM

```python
from node_core import (
    load_model, predict_single_image,
    GradCAM, get_final_conv_layer,
    save_gradcam_overlay
)
from PIL import Image
from torchvision import transforms

# Load model
model, metadata = load_model('resnet18', 'model.pt', device='cuda')

# Prepare image
image = Image.open('xray.jpg')
transform = get_val_transforms()
img_tensor = transform(image)

# Predict
pred_class, confidence, probs = predict_single_image(model, img_tensor, 'cuda')
print(f"Prediction: {pred_class}, Confidence: {confidence:.2%}")

# Generate Grad-CAM
target_layer = get_final_conv_layer(model, 'resnet18')
gradcam = GradCAM(model, target_layer)
heatmap, _ = gradcam.generate(img_tensor, device='cuda')

# Save overlay
save_gradcam_overlay(image, heatmap, 'gradcam_overlay.png')
```

### Compute Metrics

```python
from node_core import compute_metrics, format_metrics_for_display

y_true = [0, 1, 1, 0, 1]
y_pred = [0, 1, 0, 0, 1]
y_probs = [0.1, 0.9, 0.4, 0.2, 0.8]

metrics = compute_metrics(y_true, y_pred, y_probs)
print(format_metrics_for_display(metrics))
```

## Module Structure

```
node_core/
├── __init__.py           # Main exports
├── ml_models.py          # Model architectures
├── ml_training.py        # Training loops
├── ml_inference.py       # Inference + Grad-CAM
├── ml_metrics.py         # Evaluation metrics
├── data_utils.py         # Dataset utilities
├── fl_client.py          # ⭐ FL client for nodes
├── fl_aggregator.py      # ⭐ FedAvg aggregator
├── fl_utils.py           # ⭐ FL utilities
└── utils_hash.py         # Model hashing
```

## Examples

- `examples/train_example.py` - Complete training pipeline
- `examples/inference_example.py` - Inference with Grad-CAM
- `examples/fl_simulation.py` - ⭐ Complete FL round simulation

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_ml_models.py -v
pytest tests/test_fl_core.py -v

# Run FL simulation
python examples/fl_simulation.py
```

## Requirements

- Python >= 3.8
- PyTorch >= 2.0.0
- torchvision >= 0.15.0
- scikit-learn >= 1.0.0
- OpenCV >= 4.5.0
- requests >= 2.28.0

## Federated Learning Algorithm

**FedAvg Implementation**:

1. **Delta Computation** (on each node):
   ```
   ΔW_i = W_local_i - W_global
   ```

2. **Weighted Aggregation** (on central):
   ```
   w_i = n_i / Σn_i
   ΔW_avg = Σ(w_i * ΔW_i)
   ```

3. **Global Update**:
   ```
   W_{t+1} = W_t + ΔW_avg
   ```

## Documentation

- [Phase 1: ML Modularization](../../docs/PHASE1_COMPLETE.md)
- [Phase 2: FL Core](../../docs/PHASE2_COMPLETE.md)
- [Implementation Status](../../IMPLEMENTATION_STATUS.md)

## License

MIT
