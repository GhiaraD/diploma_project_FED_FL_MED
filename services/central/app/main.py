"""
Central FL Server - Hybrid Architecture

This server provides:
1. Management API (FastAPI) - For UI and round management
2. Flower Server - For actual FL orchestration (started separately)

The Management API can trigger Flower rounds and query status.
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import sys
import subprocess
import signal

# Add node_core to path
sys.path.insert(0, '/app/shared/python/node_core')

from node_core import get_model

app = FastAPI(
    title="Central FL Server - Management API",
    version="0.2.0",
    description="Federated Learning Central Orchestrator with Flower"
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
USE_FLOWER = os.getenv("USE_FLOWER", "true").lower() == "true"

# Flower server process (if running)
flower_server_process = None

print(f"[Central] Storage: {STORAGE_ROOT}")
print(f"[Central] Using Flower: {USE_FLOWER}")

# Track rounds (simple in-memory for now)
rounds_db = {}


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
    using_flower: bool
    flower_server_running: bool


# ============================================================================
# Health Endpoint
# ============================================================================

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    global flower_server_process
    
    flower_running = False
    if flower_server_process:
        flower_running = flower_server_process.poll() is None
    
    return {
        "ok": True,
        "service": "central-fl-management",
        "timestamp": datetime.utcnow().isoformat(),
        "storage_path": STORAGE_ROOT,
        "using_flower": USE_FLOWER,
        "flower_server_running": flower_running
    }


# ============================================================================
# Round Management Endpoints
# ============================================================================

@app.post("/round/create")
def create_round(request: RoundCreateRequest):
    """
    Create a new federated learning round.
    
    With Flower: This starts a Flower server in the background.
    """
    try:
        print(f"[Central] Creating round {request.round_id}...")
        
        if USE_FLOWER:
            # Start Flower server for this round
            global flower_server_process
            
            # Store round metadata
            rounds_db[request.round_id] = {
                "round_id": request.round_id,
                "model_name": request.model_name,
                "num_classes": request.num_classes,
                "hyperparameters": request.hyperparameters,
                "status": "created",
                "created_at": datetime.utcnow().isoformat()
            }
            
            print(f"[Central] ✓ Round {request.round_id} created (Flower mode)")
            print(f"[Central] Start Flower server manually or via docker-compose")
            
            return {
                "status": "success",
                "round_id": request.round_id,
                "model_name": request.model_name,
                "hyperparameters": request.hyperparameters,
                "message": f"Round {request.round_id} created. Start Flower server to begin.",
                "note": "Using Flower framework"
            }
        else:
            # Legacy mode (not implemented in this migration)
            raise HTTPException(
                status_code=501,
                detail="Legacy FL mode not available. Set USE_FLOWER=true"
            )
        
    except Exception as e:
        print(f"[Central] ✗ Failed to create round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/round/{round_id}/join")
def join_round(round_id: str, request: NodeJoinRequest):
    """
    Register a node as participant in a round.
    
    With Flower: This is informational only.
    """
    print(f"[Central] Node {request.node_id} will join round {round_id}")
    
    return {
        "status": "success",
        "round_id": round_id,
        "node_id": request.node_id,
        "message": f"Node {request.node_id} registered for round {round_id}",
        "note": "Using Flower - actual connection happens when client starts"
    }


@app.get("/round/{round_id}/plan")
def get_round_plan(round_id: str):
    """
    Get training plan for a round.
    """
    if round_id not in rounds_db:
        raise HTTPException(status_code=404, detail=f"Round {round_id} not found")
    
    round_data = rounds_db[round_id]
    
    return {
        "round_id": round_id,
        "model_name": round_data['model_name'],
        "hyperparameters": round_data['hyperparameters'],
        "note": "Using Flower framework"
    }


@app.get("/round/{round_id}/status")
def get_round_status(round_id: str):
    """
    Get current status of a round.
    """
    if round_id not in rounds_db:
        raise HTTPException(status_code=404, detail=f"Round {round_id} not found")
    
    round_data = rounds_db[round_id]
    
    return {
        "round_id": round_id,
        "status": round_data['status'],
        "model_name": round_data['model_name'],
        "note": "Using Flower - check Flower server logs for detailed status"
    }


# ============================================================================
# List Rounds Endpoint
# ============================================================================

@app.get("/rounds/list")
def list_rounds():
    """
    List all rounds.
    """
    rounds_list = []
    
    for round_id, round_data in rounds_db.items():
        rounds_list.append({
            "round_id": round_id,
            "model_name": round_data['model_name'],
            "status": round_data['status'],
            "created_at": round_data['created_at']
        })
    
    return {
        "total_rounds": len(rounds_list),
        "rounds": rounds_list,
        "note": "Using Flower framework"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8081"))  # Changed to 8081 (8080 for Flower gRPC)
    uvicorn.run(app, host="0.0.0.0", port=port)
