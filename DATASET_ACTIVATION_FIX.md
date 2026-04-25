# Dataset Activation Button Fix

## Problem
The "Activate Dataset" button in the Datasets page UI was not working because the `is_active` field was missing from the API response.

## Root Cause
The `DatasetInfo` Pydantic schema in `services/node/api/app/schemas.py` did not include the `is_active` field, even though:
- The database had the `is_active` column
- The API endpoint was returning it in the dict
- FastAPI was filtering it out during response validation

## Solution

### 1. Updated Schema
Added `is_active` field to the `DatasetInfo` schema:

```python
class DatasetInfo(BaseModel):
    dataset_id: str
    name: str
    split: str
    num_samples: int
    num_normal: int
    num_pneumonia: int
    is_active: bool = False  # Added this field
    created_at: str
```

### 2. Rebuilt Containers
Since the code is built into the Docker images (not mounted as volumes), we needed to rebuild all node API containers:

```bash
# Rebuild images
docker build -t diploma_project_fed_fl_med-node1-api -f ./services/node/api/Dockerfile .
docker build -t diploma_project_fed_fl_med-node2-api -f ./services/node/api/Dockerfile .
docker build -t diploma_project_fed_fl_med-node3-api -f ./services/node/api/Dockerfile .

# Restart containers
docker restart diploma_project_fed_fl_med-node1-api-1
docker restart diploma_project_fed_fl_med-node2-api-1
docker restart diploma_project_fed_fl_med-node3-api-1
```

## Verification

### API Response Now Includes is_active
```bash
curl http://localhost:8001/api/data/list
```

Response:
```json
[
    {
        "dataset_id": "dataset_train_4c7b250c",
        "name": "train123",
        "split": "train",
        "num_samples": 1738,
        "num_normal": 447,
        "num_pneumonia": 1291,
        "is_active": true,  // ✅ Now present
        "created_at": "2026-04-24T21:40:04.128282"
    }
]
```

### Activation Works
```bash
# Set dataset as active
curl -X POST http://localhost:8001/api/data/set-active/dataset_train_d2d88576

# Response
{
    "status": "success",
    "dataset_id": "dataset_train_d2d88576",
    "message": "Dataset Node2 Training Dataset set as active"
}
```

### Multiple Datasets Test
Created two datasets and verified activation switches correctly:
- Dataset 1: "train123" 
- Dataset 2: "Node2 Training Dataset"

Activation correctly:
- Sets selected dataset `is_active=true`
- Sets all other datasets `is_active=false`
- Only one dataset can be active at a time

## Files Modified
- `services/node/api/app/schemas.py` - Added `is_active` field to `DatasetInfo` schema

## Status
✅ **FIXED** - The activate dataset button now works correctly in the UI.

## Testing
All three nodes (Node1, Node2, Node3) have been updated and tested:
- ✅ Node1 (port 8001) - Working
- ✅ Node2 (port 8002) - Working  
- ✅ Node3 (port 8003) - Working

The UI can now:
1. Display which dataset is active (green chip)
2. Click "Activate" button on inactive datasets
3. Switch active dataset successfully
4. See the active dataset highlighted in the table
