# Inference Functionality - Complete Fix

## Date: 2026-04-19

## Issues Fixed

### Issue 1: PyTorch Model Loading Error
**Error**: `Weights only load failed. Re-running torch.load with weights_only set to False will likely succeed`

**Root Cause**: PyTorch 2.6+ changed the default behavior of `torch.load()` to `weights_only=True` for security reasons. Models saved with numpy arrays or custom objects fail to load.

**Solution**: Added `weights_only=False` parameter to `torch.load()` in `shared/python/node_core/node_core/ml_models.py`:

```python
def load_model(model_name: str, path: str, device: str = 'cpu') -> tuple:
    # PyTorch 2.6+ requires weights_only=False for models with numpy arrays
    # This is safe for our own trained models
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    # ... rest of the code
```

**Files Modified**:
- `shared/python/node_core/node_core/ml_models.py`

---

### Issue 2: Grad-CAM Dimension Mismatch
**Error**: `ValueError: operands could not be broadcast together with shapes (7,7,3) (1434,1810,3)`

**Root Cause**: The Grad-CAM heatmap has the dimensions of the final convolutional layer's feature map (7x7 for ResNet18), but the original image has full resolution (e.g., 1434x1810). When overlaying, the dimensions must match.

**Solution**: Resize the heatmap to match the original image dimensions before creating the overlay in `services/node/api/app/tasks.py`:

```python
# Generate heatmap and resize to match original image dimensions
heatmap, _ = gradcam.generate(img_tensor, device=settings.DEVICE)

# Resize heatmap to match original image size (H, W)
import cv2
heatmap_resized = cv2.resize(heatmap, (img_np.shape[1], img_np.shape[0]))

# Save overlay with resized heatmap
save_gradcam_overlay(img_np, heatmap_resized, overlay_path)
```

**Files Modified**:
- `services/node/api/app/tasks.py` (in `run_inference_task` function)

---

## Testing

### Test Results

**Test Image**: `/storage/datasets/dataset_train_477f2544/train/NORMAL/IM-0119-0001.jpeg`

**Result**:
```json
{
    "job_id": "infer_acc04cb9",
    "status": "completed",
    "results": [
        {
            "result_id": "infer_acc04cb9_0",
            "image_path": "/storage/datasets/dataset_train_477f2544/train/NORMAL/IM-0119-0001.jpeg",
            "predicted_class": 0,
            "confidence": 0.9978002905845642,
            "probabilities": [0.9978002905845642, 0.0021996325813233852],
            "gradcam_path": "/storage/results/inference/infer_acc04cb9_0_gradcam.png"
        }
    ]
}
```

✓ Image correctly classified as NORMAL (class 0) with 99.78% confidence
✓ Grad-CAM visualization generated successfully

### Test Scripts

**Quick Test**:
```bash
make test-inference
```

**Complete Test** (tests NORMAL, PNEUMONIA, and batch inference):
```bash
./scripts/test_inference_complete.sh
```

---

## Deployment Steps

1. **Rebuild node workers** (applies to all nodes):
```bash
docker compose build node1-worker node2-worker node3-worker
```

2. **Restart workers**:
```bash
docker compose up -d node1-worker node2-worker node3-worker
```

3. **Verify**:
```bash
docker compose logs node1-worker --tail 50
```

---

## API Usage

### On-Premise Inference (Recommended)

Images remain in their original location on the hospital filesystem:

```bash
curl -X POST http://localhost:8001/api/infer \
  -H "Content-Type: application/json" \
  -d '{
    "image_paths": [
      "/storage/datasets/dataset_train_477f2544/train/NORMAL/IM-0119-0001.jpeg"
    ],
    "generate_gradcam": true
  }'
```

### Browse Available Images

```bash
curl "http://localhost:8001/api/infer/browse?directory=/storage/datasets"
```

### Get Results

```bash
curl http://localhost:8001/api/infer/results/{job_id}
```

---

## UI Access

- **Node 1 UI**: http://localhost:3001/inference
- **Node 2 UI**: http://localhost:3002/inference
- **Node 3 UI**: http://localhost:3003/inference

The UI provides a file browser to select images from the hospital filesystem without uploading them.

---

## Status

✅ **COMPLETE** - Inference functionality fully operational
- Model loading works with PyTorch 2.6+
- Grad-CAM visualization generates correctly
- On-premise workflow preserves data security
- Both API and UI interfaces functional
