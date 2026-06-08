#!/usr/bin/env python3
"""
Fed-Med-FL — Sequential Multi-Strategy Training (4 Nodes)

Runs 3 consecutive FL sessions, one per aggregation strategy:
  1. FedAvg   — weighted average (baseline)
  2. FedAvgM  — FedAvg with server-side momentum  
  3. FedProx  — FedAvg with proximal regularization

All sessions share the same base parameters below.
Edit the constants to adjust the run.
"""
import requests
import time
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================================
# SHARED TRAINING PARAMETERS — same for all 3 sessions
# ============================================================================

NUM_ROUNDS      = 30                 # FL rounds per session
NUM_EPOCHS      = 3                  # Epochs per round (server pushes to clients)
MODEL_NAME      = "efficientnet_b0"  # resnet18 | densenet121 | efficientnet_b0
BATCH_SIZE      = 16                 # Per-node batch size
LEARNING_RATE   = 0.0005
OPTIMIZER       = "adam"

# ============================================================================
# SESSIONS — each defines only what differs between runs
# ============================================================================

SESSIONS = [
    {
        "label":                "FedMedian (robust)",
        "aggregation_strategy": "fedmedian",
    },
    {
        "label":                "FedAvg (baseline)",
        "aggregation_strategy": "fedavg",
    },
    {
        "label":                "FedAvgM (momentum=0.9)",
        "aggregation_strategy": "fedavgm",
        "server_momentum":      0.7,
    },
    {
        "label":                "FedProx (mu=0.01)",
        "aggregation_strategy": "fedprox",
        "proximal_mu":          0.05,
    },
]

# ============================================================================
# NODE CONFIGURATION — matches docker-compose-4nodes.yml
# ============================================================================

CENTRAL_URL = "http://localhost:8081"

NODES = [
    {"name": "node1", "url": "http://localhost:8001", "email": "admin@node1.fed-med-fl.com", "password": "AdminNode1@2026"},
    {"name": "node2", "url": "http://localhost:8002", "email": "admin@node2.fed-med-fl.com", "password": "AdminNode2@2026"},
    {"name": "node3", "url": "http://localhost:8003", "email": "admin@node3.fed-med-fl.com", "password": "AdminNode3@2026"},
    {"name": "node4", "url": "http://localhost:8004", "email": "admin@node4.fed-med-fl.com", "password": "AdminNode4@2026"},
]

# admin_central credentials — same account registered on every node
# Used exclusively for POST /api/federated/train and GET /api/federated/status
ADMIN_CENTRAL = {
    "email": "admin@central.fed-med-fl.com",
    "password": "AdminCentral@2026",
}
# ============================================================================
# TIMEOUTS
# ============================================================================

TIMEOUT             = 30    # HTTP request timeout (seconds)
POLL_INTERVAL       = 5     # Status polling interval (seconds)
SERVER_INIT_WAIT    = 45    # Seconds after starting Flower Server before triggering nodes
SERVER_STOP_WAIT    = 60    # Max seconds to wait for Flower Server to stop between sessions

# Experiment logging (NOU)
EXPERIMENTS_DIR = "experiments"
SPLITS_DIR = "/experiments/splits"

# ============================================================================
# Internal state
# ============================================================================

_tokens: Dict[str, str] = {}


# ============================================================================
# Logging
# ============================================================================

def log(message: str, level: str = "INFO") -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {message}")


def log_banner(text: str) -> None:
    log("=" * 80)
    log(text)
    log("=" * 80)


# ============================================================================
# Service checks
# ============================================================================

def check_service(url: str, name: str, is_node: bool = False) -> bool:
    endpoint = "/api/health" if is_node else "/health"
    try:
        r = requests.get(f"{url}{endpoint}", timeout=TIMEOUT)
        if r.status_code == 200:
            log(f"✓ {name} is available")
            return True
        log(f"✗ {name} returned {r.status_code}", "ERROR")
    except Exception as e:
        log(f"✗ {name} unreachable: {e}", "ERROR")
    return False


def check_all_services() -> bool:
    results = [check_service(CENTRAL_URL, "Central", is_node=False)]
    for node in NODES:
        results.append(check_service(node["url"], node["name"], is_node=True))
    return all(results)


# ============================================================================
# Authentication
# ============================================================================

def login(node: Dict) -> bool:
    try:
        r = requests.post(
            f"{node['url']}/api/auth/login",
            data={"username": node["email"], "password": node["password"]},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            token = r.json().get("access_token")
            if token:
                _tokens[node["name"]] = token
                log(f"✓ Logged in to {node['name']}")
                return True
        log(f"✗ Login failed for {node['name']}: {r.status_code}", "ERROR")
    except Exception as e:
        log(f"✗ Login error for {node['name']}: {e}", "ERROR")
    return False


def auth_headers(node_name: str) -> Dict[str, str]:
    token = _tokens.get(node_name)
    return {"Authorization": f"Bearer {token}"} if token else {}


def auth_headers_central(node_url_name: str) -> Dict[str, str]:
    """Headers using admin_central token for the given node."""
    token = _tokens.get(f"central_{node_url_name}")
    return {"Authorization": f"Bearer {token}"} if token else {}


def login_central_on_node(node: Dict) -> bool:
    """Login as admin_central on a specific node."""
    try:
        r = requests.post(
            f"{node['url']}/api/auth/login",
            data={"username": ADMIN_CENTRAL["email"], "password": ADMIN_CENTRAL["password"]},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            token = r.json().get("access_token")
            if token:
                _tokens[f"central_{node['name']}"] = token
                log(f"✓ Logged in as admin_central on {node['name']}")
                return True
        log(f"✗ admin_central login failed on {node['name']}: {r.status_code}", "ERROR")
    except Exception as e:
        log(f"✗ admin_central login error on {node['name']}: {e}", "ERROR")
    return False


def login_all() -> bool:
    log("Authenticating with all nodes...")
    node_logins = all(login(node) for node in NODES)
    central_logins = all(login_central_on_node(node) for node in NODES)
    return node_logins and central_logins


# ============================================================================
# Dataset management
# ============================================================================

def get_active_dataset(node: Dict) -> Optional[str]:
    try:
        r = requests.get(
            f"{node['url']}/api/data/active",
            headers=auth_headers(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            active = r.json().get("active_dataset")
            if active:
                return active.get("dataset_id")
    except Exception:
        pass
    return None


def activate_first_dataset(node: Dict) -> bool:
    try:
        r = requests.get(
            f"{node['url']}/api/data/list",
            headers=auth_headers(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code != 200 or not r.json():
            log(f"✗ No datasets found for {node['name']}", "ERROR")
            return False

        dataset_id = r.json()[0].get("dataset_id")
        activate = requests.post(
            f"{node['url']}/api/data/set-active/{dataset_id}",
            headers=auth_headers(node["name"]),
            timeout=TIMEOUT,
        )
        if activate.status_code == 200:
            log(f"✓ Dataset activated for {node['name']}: {dataset_id}")
        else:
            log(f"⚠ Could not activate dataset for {node['name']}", "WARNING")
        return True
    except Exception as e:
        log(f"✗ Error activating dataset for {node['name']}: {e}", "ERROR")
        return False


def activate_all_datasets() -> bool:
    log("Activating datasets on all nodes...")
    return all(activate_first_dataset(node) for node in NODES)


# ============================================================================
# Flower Server lifecycle
# ============================================================================

def is_flower_running() -> bool:
    try:
        r = requests.get(f"{CENTRAL_URL}/flower/status", timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json().get("flower_server_running", False)
    except Exception:
        pass
    return False


def wait_for_flower_to_stop(max_wait: int = SERVER_STOP_WAIT) -> bool:
    """Wait until Flower Server stops (it stops automatically after all rounds complete)."""
    log(f"Waiting for Flower Server to stop (max {max_wait}s)...")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if not is_flower_running():
            log("✓ Flower Server stopped")
            return True
        time.sleep(5)
    log("⚠ Flower Server did not stop within timeout", "WARNING")
    return False


def force_stop_flower_server() -> bool:
    """Force-kill Flower Server via the central API kill endpoint, then verify."""
    if not is_flower_running():
        return True

    log("Force-stopping Flower Server...")
    try:
        r = requests.post(f"{CENTRAL_URL}/api/fl/stop", timeout=TIMEOUT)
        if r.status_code == 200:
            log("✓ Flower Server force-stopped via API")
            time.sleep(2)
            return not is_flower_running()
    except Exception:
        pass

    # Fallback: poll until it stops on its own (max 10s)
    deadline = time.time() + 10
    while time.time() < deadline:
        if not is_flower_running():
            log("✓ Flower Server stopped")
            return True
        time.sleep(2)

    log("⚠ Could not stop Flower Server", "WARNING")
    return False


def start_flower_server(session: Dict, run_id: str = None) -> bool:
    """Start Flower Server with the given session config merged with shared params."""
    strategy = session["aggregation_strategy"]
    log(f"Starting Flower Server — strategy: {strategy.upper()}")

    params = {
        "num_rounds":            NUM_ROUNDS,
        "num_epochs":            NUM_EPOCHS,
        "model_name":            MODEL_NAME,
        "learning_rate":         LEARNING_RATE,
        "optimizer":             OPTIMIZER,
        "min_fit_clients":       len(NODES),
        "min_available_clients": len(NODES),
        "aggregation_strategy":  strategy,
        # Strategy-specific overrides from session dict (defaults if not present)
        "proximal_mu":           session.get("proximal_mu", 0.01),
        "server_momentum":       session.get("server_momentum", 0.9),
        "server_lr":             session.get("server_lr", 0.01),
        "server_beta1":          session.get("server_beta1", 0.9),
        "server_beta2":          session.get("server_beta2", 0.99),
        "server_tau":            session.get("server_tau", 1e-3),
    }
    # Adaugă run_id dacă e furnizat (NOU)
    if run_id:
        params["run_id"] = run_id
        params["experiments_dir"] = EXPERIMENTS_DIR
    try:
        r = requests.post(
            f"{CENTRAL_URL}/api/fl/start",
            params=params,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            result = r.json()
            if result.get("status") == "already_running":
                log("⚠ Flower Server already running — cannot start new session", "WARNING")
                return False
            log(f"✓ Flower Server started")

            # Așteptăm activ până când serverul e gata să accepte conexiuni gRPC
            log(f"  Așteptăm ca Flower Server să fie gata (max {SERVER_INIT_WAIT}s)...")
            start_wait = time.time()
            deadline = start_wait + SERVER_INIT_WAIT
            while time.time() < deadline:
                time.sleep(2)
                try:
                    status_r = requests.get(f"{CENTRAL_URL}/flower/status", timeout=5)
                    if status_r.status_code == 200 and status_r.json().get("flower_server_running"):
                        elapsed = time.time() - start_wait
                        log(f"  ✓ Flower Server gata după {elapsed:.0f}s — așteptăm 3s pentru stabilizare gRPC")
                        time.sleep(3)
                        return True
                except Exception:
                    pass
            log(f"  ⚠ Flower Server nu a răspuns în {SERVER_INIT_WAIT}s, continuăm oricum", "WARNING")
            return True
        log(f"✗ Failed to start Flower Server: {r.status_code} — {r.text}", "ERROR")
    except Exception as e:
        log(f"✗ Error starting Flower Server: {e}", "ERROR")
    return False


# ============================================================================
# Training
# ============================================================================

def start_training(node: Dict, dataset_id: str) -> Optional[str]:
    try:
        r = requests.post(
            f"{node['url']}/api/federated/train",
            params={
                "dataset_id": dataset_id,
                "model_name": MODEL_NAME,
                "batch_size": BATCH_SIZE,
                "splits_dir": SPLITS_DIR,
            },
            headers=auth_headers_central(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            job_id = r.json().get("job_id")
            log(f"✓ Training started on {node['name']} — job_id: {job_id}")
            return job_id
        log(f"✗ Failed to start training on {node['name']}: {r.text}", "ERROR")
    except Exception as e:
        log(f"✗ Error starting training on {node['name']}: {e}", "ERROR")
    return None


def start_training_all() -> Optional[Dict[str, str]]:
    log("Starting federated training on all nodes...")
    job_ids: Dict[str, str] = {}
    for node in NODES:
        dataset_id = get_active_dataset(node)
        if not dataset_id:
            log(f"✗ No active dataset for {node['name']}", "ERROR")
            return None
        job_id = start_training(node, dataset_id)
        if not job_id:
            return None
        job_ids[node["name"]] = job_id
    return job_ids


# ============================================================================
# Monitoring
# ============================================================================

def get_job_status(node: Dict, job_id: str) -> Optional[str]:
    try:
        r = requests.get(
            f"{node['url']}/api/federated/status/{job_id}",
            headers=auth_headers_central(node["name"]),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json().get("status", "unknown")
    except Exception:
        pass
    return None


def monitor_training(job_ids: Dict[str, str]) -> bool:
    node_map = {node["name"]: node for node in NODES}
    start_time = time.time()
    consecutive_completed = 0
    consecutive_errors = 0
    REQUIRED_CONFIRMATIONS = 3
    MAX_ERRORS = 10

    while True:
        elapsed = time.time() - start_time

        statuses: Dict[str, str] = {}
        all_reachable = True

        for name, job_id in job_ids.items():
            status = get_job_status(node_map[name], job_id)
            if status is None:
                all_reachable = False
                statuses[name] = "?"
            else:
                statuses[name] = status

        status_str = " | ".join(f"{n}: {s}" for n, s in statuses.items())
        log(f"{status_str} | {elapsed:.0f}s")

        if not all_reachable:
            consecutive_errors += 1
            consecutive_completed = 0
            if consecutive_errors >= MAX_ERRORS:
                log("⚠ Too many unreachable responses — assuming completed", "WARNING")
                return True
            time.sleep(POLL_INTERVAL)
            continue

        consecutive_errors = 0

        failed = [n for n, s in statuses.items() if s == "failed"]
        if failed:
            log(f"✗ Training failed on: {', '.join(failed)}", "ERROR")
            return False

        if all(s == "completed" for s in statuses.values()):
            consecutive_completed += 1
            if consecutive_completed >= REQUIRED_CONFIRMATIONS:
                log(f"✓ All {len(job_ids)} nodes completed!")
                return True
            log(f"  Confirming... ({consecutive_completed}/{REQUIRED_CONFIRMATIONS})")
        else:
            consecutive_completed = 0

        time.sleep(POLL_INTERVAL)


# ============================================================================
# Experiment output verification (NOU)
# ============================================================================

def _generate_run_id(strategy: str, model_name: str) -> str:
    """
    Generează run_id cu format: fl_{strategy}_{model}_run{NN}
    NN = numărul de directoare existente cu același prefix + 1.
    """
    model_clean = model_name.replace("-", "_").replace(".", "_")
    prefix = f"fl_{strategy}_{model_clean}_run"

    exp_dir = Path(EXPERIMENTS_DIR)
    existing = []
    if exp_dir.exists():
        for d in exp_dir.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                existing.append(d.name)

    nn = len(existing) + 1
    return f"{prefix}{nn:02d}"


def verify_experiment_outputs(run_id: str) -> bool:
    """
    Verifică existența fișierelor obligatorii pentru un experiment FL.

    Returns:
        True dacă toate fișierele obligatorii există.
    """
    exp_dir = Path(EXPERIMENTS_DIR) / run_id
    required_files = (
        [exp_dir / "run_config.json", exp_dir / "central" / "metrics_by_round.csv"]
        + [exp_dir / "nodes" / f"node{i}_metrics_by_round.csv" for i in range(1, len(NODES) + 1)]
    )

    missing = [str(f) for f in required_files if not f.exists()]
    if missing:
        for m in missing:
            log(f"  ⚠ Lipsă: {m}", "WARNING")
        return False
    return True


# ============================================================================
# Single session runner
# ============================================================================

def run_session(session_num: int, session: Dict) -> Tuple[bool, str]:
    """Run one complete FL session. Returns (success, run_id)."""
    label = session["label"]
    strategy = session["aggregation_strategy"]

    # NOU: generează run_id unic pentru această sesiune
    run_id = _generate_run_id(strategy, MODEL_NAME)

    log_banner(f"SESSION {session_num}/{len(SESSIONS)}: {label} (run_id: {run_id})")

    # Start Flower Server for this session
    if not start_flower_server(session, run_id=run_id):
        log(f"✗ Session {session_num} aborted — could not start Flower Server", "ERROR")
        return False, run_id

    log(f"  Waiting {SERVER_INIT_WAIT}s for server to initialize...")
    time.sleep(SERVER_INIT_WAIT)

    # Start training on all nodes
    job_ids = start_training_all()
    if not job_ids:
        log(f"✗ Session {session_num} aborted — could not start training", "ERROR")
        return False, run_id

    # Monitor until completion
    success = monitor_training(job_ids)

    if success:
        log(f"✓ Session {session_num} ({label}) PASSED")
    else:
        log(f"✗ Session {session_num} ({label}) FAILED", "ERROR")
        force_stop_flower_server()

    return success, run_id


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    log_banner(
        f"Fed-Med-FL — Sequential Multi-Strategy Training\n"
        f"  Nodes:    {len(NODES)}\n"
        f"  Rounds:   {NUM_ROUNDS} per session\n"
        f"  Epochs:   {NUM_EPOCHS} per round\n"
        f"  Model:    {MODEL_NAME}\n"
        f"  Batch:    {BATCH_SIZE}\n"
        f"  Sessions: {len(SESSIONS)}"
    )
    for i, s in enumerate(SESSIONS, 1):
        log(f"  {i}. {s['label']}")

    # ── One-time setup ──────────────────────────────────────────────────────

    log("\n[SETUP 1] Checking services...")
    if not check_all_services():
        log("✗ Not all services available. Exiting.", "ERROR")
        sys.exit(1)

    log("\n[SETUP 2] Authenticating...")
    if not login_all():
        log("✗ Authentication failed. Exiting.", "ERROR")
        sys.exit(1)

    log("\n[SETUP 3] Activating datasets...")
    if not activate_all_datasets():
        log("✗ Dataset activation failed. Exiting.", "ERROR")
        sys.exit(1)

    # ── Run sessions sequentially ───────────────────────────────────────────

    results: Dict[str, Tuple[bool, str]] = {}

    for i, session in enumerate(SESSIONS, 1):
        # Ensure Flower Server is not running before starting a new session
        if i > 1:
            log(f"\nWaiting for Flower Server to stop before session {i}...")
            if not wait_for_flower_to_stop():
                log("⚠ Server did not stop in time — force-stopping...", "WARNING")
                force_stop_flower_server()

        success, run_id = run_session(i, session)
        results[session["label"]] = (success, run_id)

        if not success:
            log(f"\n⚠ Session {i} failed — continuing with remaining sessions", "WARNING")

    # ── Final summary ───────────────────────────────────────────────────────

    log_banner("FINAL RESULTS")
    all_passed = True
    for label, (passed, run_id) in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        log(f"  {status}  —  {label} ({run_id})")
        if not passed:
            all_passed = False

    # NOU: Verificare fișiere output
    log_banner("VERIFICARE FIȘIERE OUTPUT")
    for label, (passed, run_id) in results.items():
        if passed:
            files_ok = verify_experiment_outputs(run_id)
            file_status = "✓ FIȘIERE OK" if files_ok else "⚠ FIȘIERE LIPSĂ"
            log(f"  {file_status}  —  {label} ({run_id})")

    log("")
    if all_passed:
        log("✓✓✓ ALL SESSIONS PASSED ✓✓✓")
        sys.exit(0)
    else:
        log("✗✗✗ ONE OR MORE SESSIONS FAILED ✗✗✗", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
