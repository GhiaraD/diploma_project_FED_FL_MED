"""
Central FL Server - Hybrid Architecture

This server provides:
1. Management API (FastAPI) - For UI and round management
2. Flower Server - For actual FL orchestration (started separately)

The Management API can trigger Flower rounds and query status.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime
import os
import sys
import subprocess
from pathlib import Path

# Add node_core to path
sys.path.insert(0, '/app/shared/python/node_core')

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

print(f"[Central] Storage: {STORAGE_ROOT}")
print(f"[Central] Using Flower: {USE_FLOWER}")


# ============================================================================
# Pydantic Schemas
# ============================================================================

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

FLOWER_PORT = 8080

FLOWER_PATTERNS = [
    'flower_server.py',
    'app.flower_server',
    'flwr.server',
    'python -m flwr',
    'python3 -m flwr',
    'start_flower_server',
]


def _get_flower_process_info() -> Optional[Dict]:
    """
    Check if Flower Server is running by verifying both port and process.

    Returns:
        Dict with 'pid' and 'command' if Flower is running,
        None if not running,
        {'port_open': True} if port is open but process can't be verified (lsof/ps unavailable).
    """
    import socket

    # Step 1: Check if port is open
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("0.0.0.0", FLOWER_PORT))
        sock.close()
        if result != 0:
            return None
    except Exception:
        return None

    # Step 2: Verify it's actually Flower Server
    try:
        result = subprocess.run(
            ['lsof', '-i', f':{FLOWER_PORT}', '-t'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        pid = result.stdout.strip().split('\n')[0]

        result = subprocess.run(
            ['ps', '-p', pid, '-o', 'cmd='],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            return None

        cmdline = result.stdout.strip()
        if not any(p in cmdline.lower() for p in FLOWER_PATTERNS):
            return None

        return {'pid': int(pid), 'command': cmdline}

    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        # lsof or ps not available — port is open, assume it's Flower
        return {'port_open': True}
    except Exception:
        return {'port_open': True}


def check_flower_server_running() -> bool:
    """Return True if Flower Server is running."""
    return _get_flower_process_info() is not None


def _generate_run_id(strategy: str, model_name: str, experiments_dir: str = "experiments") -> str:
    """
    Generează run_id cu format: fl_{strategy}_{model}_run{NN}
    NN = numărul de directoare existente cu același prefix + 1.
    Ex: dacă există fl_fedavg_effb0_run01, generează fl_fedavg_effb0_run02.
    """
    # Normalizează model_name (elimină caractere speciale)
    model_clean = model_name.replace("-", "_").replace(".", "_")
    prefix = f"fl_{strategy}_{model_clean}_run"

    exp_dir = Path(experiments_dir)
    existing = []
    if exp_dir.exists():
        for d in exp_dir.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                existing.append(d.name)

    nn = len(existing) + 1
    return f"{prefix}{nn:02d}"


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    flower_running = check_flower_server_running()
    
    return {
        "ok": True,
        "service": "central-fl-management",
        "timestamp": datetime.utcnow().isoformat(),
        "storage_path": STORAGE_ROOT,
        "using_flower": USE_FLOWER,
        "flower_server_running": flower_running
    }


@app.get("/flower/status")
def get_flower_status():
    """
    Get Flower Server status with process information.

    Returns detailed information about Flower Server availability and process.
    """
    process_info = _get_flower_process_info()
    flower_running = process_info is not None

    response = {
        "flower_server_running": flower_running,
        "flower_server_address": f"0.0.0.0:{FLOWER_PORT}",
        "protocol": "gRPC",
        "ssl_enabled": os.getenv("FLOWER_ENABLE_SSL", "true").lower() == "true",
        "status": "running" if flower_running else "stopped",
    }

    if flower_running:
        if process_info.get('pid'):
            response["process"] = process_info
            response["message"] = f"Flower Server is running (PID: {process_info['pid']})"
        else:
            response["message"] = "Flower Server is running and accepting connections"
    else:
        response["message"] = "Flower Server is not running. Start it with: POST /api/fl/start"

    return response


@app.post("/api/fl/stop")
def stop_fl_server():
    """
    Force-stop Flower Server by killing the process on port 8080.
    """
    import signal

    process_info = _get_flower_process_info()
    if process_info is None:
        return {"status": "not_running", "message": "Flower Server is not running."}

    pid = process_info.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            return {"status": "stopped", "message": f"Flower Server (PID {pid}) terminated."}
        except ProcessLookupError:
            return {"status": "stopped", "message": "Process already gone."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "unknown", "message": "Could not determine PID to kill."}


@app.post("/api/fl/start")
def start_fl_server(
    num_rounds: int = 2,
    num_epochs: int = 2,
    model_name: str = "efficientnet_b0",
    learning_rate: float = 0.001,
    optimizer: str = "adam",
    min_fit_clients: int = 2,
    min_available_clients: int = 2,
    # Aggregation strategy
    aggregation_strategy: str = "fedavg",
    proximal_mu: float = 0.01,
    server_momentum: float = 0.9,
    server_lr: float = 0.01,
    server_beta1: float = 0.9,
    server_beta2: float = 0.99,
    server_tau: float = 1e-3,
    # Experiment logging (NOU)
    run_id: Optional[str] = None,
    experiments_dir: str = "experiments",
    test_global_csv: Optional[str] = None,
):
    """
    Start Flower Server with the given training configuration.

    The server starts in a background subprocess and waits for clients to connect.
    Call this BEFORE triggering training on the nodes.

    Args:
        num_rounds: Number of FL rounds
        num_epochs: Epochs per round (sent to clients via configure_fit)
        model_name: Model architecture
        learning_rate: Learning rate (sent to clients)
        optimizer: Optimizer name (sent to clients)
        min_fit_clients: Minimum clients required to start a round
        min_available_clients: Minimum clients that must be available
        aggregation_strategy: One of fedavg, fedprox, fedavgm, fedopt, fedadam, fedyogi, fedmedian
        proximal_mu: FedProx proximal term (ignored for other strategies)
        server_momentum: FedAvgM/FedOpt server momentum
        server_lr: FedOpt/FedAdam/FedYogi server learning rate
        server_beta1: FedAdam/FedYogi beta1
        server_beta2: FedAdam/FedYogi beta2
        server_tau: FedAdam/FedYogi tau
    """
    if check_flower_server_running():
        return {
            "status": "already_running",
            "message": "Flower Server is already running. Stop it before starting a new session.",
        }

    import subprocess as _subprocess
    import sys

    # Rezolvă experiments_dir la cale absolută față de /experiments (volumul montat)
    # dacă e o cale relativă (ex. "experiments" → "/experiments")
    if not os.path.isabs(experiments_dir):
        experiments_dir = "/" + experiments_dir

    # Rezolvă test_global_csv la cale absolută dacă e relativ
    if test_global_csv and not os.path.isabs(test_global_csv):
        test_global_csv = "/" + test_global_csv

    # Generează run_id dacă nu e furnizat (NOU)
    effective_run_id = run_id or _generate_run_id(aggregation_strategy, model_name, experiments_dir)

    # Determină test_global_csv implicit dacă nu e furnizat (NOU)
    effective_test_global_csv = test_global_csv or os.path.join(experiments_dir, "splits", "test_global.csv")

    cmd = [
        sys.executable, "-m", "app.flower_server",
        "--num-rounds", str(num_rounds),
        "--num-epochs", str(num_epochs),
        "--model-name", model_name,
        "--learning-rate", str(learning_rate),
        "--optimizer", optimizer,
        "--min-fit-clients", str(min_fit_clients),
        "--min-available-clients", str(min_available_clients),
        "--aggregation-strategy", aggregation_strategy,
        "--proximal-mu", str(proximal_mu),
        "--server-momentum", str(server_momentum),
        "--server-lr", str(server_lr),
        "--server-beta1", str(server_beta1),
        "--server-beta2", str(server_beta2),
        "--server-tau", str(server_tau),
        "--enable-ssl", os.getenv("FLOWER_ENABLE_SSL", "true"),
        "--certificates-path", os.getenv("CERTIFICATES_PATH", "/certificates"),
        "--signature-policy", os.getenv("SIGNATURE_POLICY", "log"),
        "--storage-path", STORAGE_ROOT,
        # Experiment logging (NOU)
        "--run-id", effective_run_id,
        "--experiments-dir", experiments_dir,
        "--test-global-csv", effective_test_global_csv,
    ]

    log_path = os.path.join(experiments_dir, f"flower_server_{effective_run_id}.log")
    os.makedirs(experiments_dir, exist_ok=True)
    log_fh = open(log_path, "w")
    _subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=log_fh,
        close_fds=True,
    )

    return {
        "status": "started",
        "message": "Flower Server starting in background. Trigger training on nodes now.",
        "config": {
            "num_rounds": num_rounds,
            "num_epochs": num_epochs,
            "model_name": model_name,
            "learning_rate": learning_rate,
            "optimizer": optimizer,
            "min_fit_clients": min_fit_clients,
            "min_available_clients": min_available_clients,
            "aggregation_strategy": aggregation_strategy,
            "run_id": effective_run_id,
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    # Add node_core to path (already done above, but ensure it's available)
    sys.path.insert(0, '/app/shared/python/node_core')
    
    from node_core import configure_fastapi_ssl, get_uvicorn_config
    
    # Check if SSL should be enabled
    enable_ssl = os.getenv("ENABLE_SSL", "true").lower() == "true"
    certificates_path = os.getenv("CERTIFICATES_PATH", "/certificates")
    port = int(os.getenv("PORT", "8081"))  # Changed to 8081 (8080 for Flower gRPC)
    
    ssl_config = None
    if enable_ssl:
        print(f"\n{'='*70}")
        print(f"CONFIGURING HTTPS FOR CENTRAL API")
        print(f"{'='*70}")
        
        # Configure SSL
        ssl_config = configure_fastapi_ssl(
            app=app,
            node_id=None,
            is_central=True,
            certificates_path=certificates_path,
            require_client_cert=False,  # Optional: enable for mTLS
            enforce_client_cert=False
        )
        
        if ssl_config:
            print(f"✓ HTTPS enabled for Central API")
        else:
            print(f"⚠️  HTTPS configuration failed, falling back to HTTP")
        
        print(f"{'='*70}\n")
    
    # Get Uvicorn configuration
    uvicorn_config = get_uvicorn_config(
        ssl_config=ssl_config,
        host="0.0.0.0",
        port=port
    )
    
    # Start server
    uvicorn.run(app, **uvicorn_config)

