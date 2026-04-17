"""
Central FL Server - Orchestrates federated learning rounds.

Endpoints:
- POST /round/create - Create new FL round
- POST /round/{round_id}/join - Node joins round
- GET /round/{round_id}/plan - Get round training plan
- GET /model/global/{round_id} - Download global model
- POST /update/submit - Submit delta update from node
- POST /round/{round_id}/aggregate - Trigger aggregation
- GET /round/{round_id}/results - Get aggregated results
- GET /round/{round_id}/status - Get round status
- GET /health - Health check
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import sys
import base64
import io
import torch

# Add node_core to path
sys.path.insert(0, '/app/shared/python/node_core')

from node_core import FedAvgAggregator, get_model

app = FastAPI(
    title="Central FL Server",
    version="0.1.0",
    description="Federated Learning Central Orchestrator"
)

# CORS middleware - Allow requests from UIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3000",  # Dev mode
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
STORAGE_ROOT = os.getenv("CENTRAL_STORAGE", "/storage")
MIN_NODES = int(os.getenv("MIN_NODES", "2"))
OUTLIER_THRESHOLD = float(os.getenv("OUTLIER_THRESHOLD", "3.0"))

# Initialize aggregator
aggregator = FedAvgAggregator(
    storage_path=STORAGE_ROOT,
    min_nodes=MIN_NODES,
    outlier_threshold=OUTLIER_THRESHOLD
)

print(f"[Central] Initialized with storage: {STORAGE_ROOT}")
print(f"[Central] Min nodes: {MIN_NODES}, Outlier threshold: {OUTLIER_THRESHOLD}")


# ============================================================================
# Pydantic Schemas
# ============================================================================

class RoundCreateRequest(BaseModel):
    round_id: str
    model_name: str = "resnet18"
    num_classes: int = 2
    pretrained: bool = True
    hyperparameters: Dict = {
        "num_epochs": 5,
        "batch_size": 32,
        "learning_rate": 0.001,
        "optimizer": "adam"
    }


class NodeJoinRequest(BaseModel):
    node_id: str


class UpdateSubmitRequest(BaseModel):
    node_id: str
    round_id: str
    base_model_hash: str
    n_samples: int
    metrics: Dict[str, Any]  # Changed from Dict[str, float] to accept all metric types
    delta: str  # Base64 encoded delta state dict
    delta_hash: str


class HealthResponse(BaseModel):
    ok: bool
    service: str
    timestamp: str
    storage_path: str
    active_rounds: int


# ============================================================================
# Health Endpoint
# ============================================================================

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return {
        "ok": True,
        "service": "central-fl",
        "timestamp": datetime.utcnow().isoformat(),
        "storage_path": STORAGE_ROOT,
        "active_rounds": len(aggregator.rounds)
    }


# ============================================================================
# Round Management Endpoints
# ============================================================================

@app.post("/round/create")
def create_round(request: RoundCreateRequest):
    """
    Create a new federated learning round.
    
    Initializes a global model and prepares for node participation.
    """
    try:
        print(f"[Central] Creating round {request.round_id}...")
        
        # Initialize base model
        model = get_model(
            request.model_name,
            num_classes=request.num_classes,
            pretrained=request.pretrained
        )
        
        base_model_state = model.state_dict()
        
        # Create round in aggregator
        round_data = aggregator.create_round(
            round_id=request.round_id,
            model_name=request.model_name,
            base_model_state=base_model_state,
            hyperparameters=request.hyperparameters
        )
        
        return {
            "status": "success",
            "round_id": request.round_id,
            "model_name": request.model_name,
            "base_model_hash": round_data['base_model_hash'],
            "hyperparameters": request.hyperparameters,
            "message": f"Round {request.round_id} created successfully"
        }
        
    except Exception as e:
        print(f"[Central] ✗ Failed to create round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/round/{round_id}/join")
def join_round(round_id: str, request: NodeJoinRequest):
    """
    Register a node as participant in a round.
    """
    try:
        aggregator.register_participant(round_id, request.node_id)
        
        return {
            "status": "success",
            "round_id": round_id,
            "node_id": request.node_id,
            "message": f"Node {request.node_id} joined round {round_id}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/round/{round_id}/plan")
def get_round_plan(round_id: str):
    """
    Get training plan for a round.
    
    Returns hyperparameters and model information for nodes.
    """
    try:
        if round_id not in aggregator.rounds:
            raise HTTPException(status_code=404, detail=f"Round {round_id} not found")
        
        round_data = aggregator.rounds[round_id]
        
        return {
            "round_id": round_id,
            "model_name": round_data['model_name'],
            "base_model_hash": round_data['base_model_hash'],
            "hyperparameters": round_data['hyperparameters'],
            "participants": round_data['participants']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/round/{round_id}/status")
def get_round_status(round_id: str):
    """
    Get current status of a round.
    """
    try:
        if round_id not in aggregator.rounds:
            raise HTTPException(status_code=404, detail=f"Round {round_id} not found")
        
        round_data = aggregator.rounds[round_id]
        
        return {
            "round_id": round_id,
            "status": round_data['status'],
            "model_name": round_data['model_name'],
            "participants": round_data['participants'],
            "num_participants": len(round_data['participants']),
            "updates_received": len(round_data['updates']),
            "aggregated_metrics": round_data.get('aggregated_metrics'),
            "aggregated_model_hash": round_data.get('aggregated_model_hash')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Model Distribution Endpoint
# ============================================================================

@app.get("/model/global/{round_id}")
def get_global_model(round_id: str):
    """
    Download global model for a round.
    
    Returns base64-encoded model state dict and hash.
    """
    try:
        if round_id not in aggregator.rounds:
            raise HTTPException(status_code=404, detail=f"Round {round_id} not found")
        
        round_data = aggregator.rounds[round_id]
        
        # Determine which model to send
        if round_data['status'] == 'aggregated' and round_data.get('aggregated_model_path'):
            # Send aggregated model if available
            model_path = round_data['aggregated_model_path']
            model_hash = round_data['aggregated_model_hash']
        else:
            # Send base model
            model_path = round_data['base_model_path']
            model_hash = round_data['base_model_hash']
        
        # Load model
        state_dict = torch.load(model_path, map_location='cpu')
        
        # Serialize to base64
        buffer = io.BytesIO()
        torch.save(state_dict, buffer)
        state_dict_bytes = buffer.getvalue()
        state_dict_b64 = base64.b64encode(state_dict_bytes).decode('utf-8')
        
        print(f"[Central] Sending global model for round {round_id} to client")
        print(f"[Central]   - Model hash: {model_hash[:16]}...")
        print(f"[Central]   - Size: {len(state_dict_bytes) / 1024 / 1024:.2f} MB")
        
        return {
            "round_id": round_id,
            "model_name": round_data['model_name'],
            "hash": model_hash,
            "state_dict": state_dict_b64
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Central] ✗ Failed to send model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Update Collection Endpoint
# ============================================================================

@app.post("/update/submit")
def submit_update(request: UpdateSubmitRequest):
    """
    Receive delta update from a node.
    
    Validates and stores the update for aggregation.
    """
    try:
        print(f"[Central] Receiving update from {request.node_id} for round {request.round_id}...")
        
        # Decode delta
        delta_bytes = base64.b64decode(request.delta)
        delta = torch.load(io.BytesIO(delta_bytes), map_location='cpu')
        
        # Verify delta hash
        import hashlib
        computed_hash = hashlib.sha256(delta_bytes).hexdigest()
        if computed_hash != request.delta_hash:
            raise ValueError(
                f"Delta hash mismatch! Expected {request.delta_hash[:16]}..., "
                f"got {computed_hash[:16]}..."
            )
        
        # Collect update
        result = aggregator.collect_update(
            round_id=request.round_id,
            node_id=request.node_id,
            delta=delta,
            base_model_hash=request.base_model_hash,
            n_samples=request.n_samples,
            metrics=request.metrics
        )
        
        return {
            "status": "success",
            "message": f"Update from {request.node_id} accepted",
            **result
        }
        
    except ValueError as e:
        print(f"[Central] ✗ Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Central] ✗ Failed to process update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Aggregation Endpoint
# ============================================================================

@app.post("/round/{round_id}/aggregate")
def aggregate_round(round_id: str, validate: bool = True):
    """
    Trigger FedAvg aggregation for a round.
    
    Aggregates all collected updates and creates new global model.
    """
    try:
        print(f"[Central] Triggering aggregation for round {round_id}...")
        
        result = aggregator.aggregate_round(round_id, validate=validate)
        
        return {
            "status": "success",
            "message": f"Round {round_id} aggregated successfully",
            **result
        }
        
    except ValueError as e:
        print(f"[Central] ✗ Aggregation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Central] ✗ Aggregation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Results Endpoint
# ============================================================================

@app.get("/round/{round_id}/results")
def get_round_results(round_id: str):
    """
    Get aggregation results for a round.
    
    Returns aggregated metrics and model information.
    """
    try:
        results = aggregator.get_round_results(round_id)
        
        return {
            "status": "success",
            **results
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# List Rounds Endpoint
# ============================================================================

@app.get("/rounds/list")
def list_rounds():
    """
    List all rounds.
    """
    rounds_list = []
    
    for round_id, round_data in aggregator.rounds.items():
        rounds_list.append({
            "round_id": round_id,
            "model_name": round_data['model_name'],
            "status": round_data['status'],
            "num_participants": len(round_data['participants']),
            "num_updates": len(round_data['updates']),
            "aggregated_metrics": round_data.get('aggregated_metrics')
        })
    
    return {
        "total_rounds": len(rounds_list),
        "rounds": rounds_list
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
