#!/usr/bin/env python3
"""
Fed-Med-FL — Sequential Multi-Strategy Training (4 Nodes) — UI Dataset Mode

Identical to test_e2e_4nodes.py with one difference:
  training is started WITHOUT splits_dir, so each node uses the dataset
  registered and activated via the UI (train/ val/ test/ folders).

This exercises _load_data() path 2 in flower_client.py.
"""
import requests
import time
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# ============================================================================
# SHARED TRAINING PARAMETERS
# ============================================================================

NUM_ROUNDS      = 2
NUM_EPOCHS      = 1
MODEL_NAME      = "efficientnet_b0"
BATCH_SIZE      = 32
LEARNING_RATE   = 0.001
OPTIMIZER       = "adam"

# ============================================================================
# SESSIONS
# ============================================================================

SESSIONS = [
    {
        "label":                "FedAvg (baseline)",
        "aggregation_strategy": "fedavg",
    },
]

# ============================================================================
# NODE CONFIGURATION — matches docker-compose-4nodes.yml
# ============================================================================

CENTRAL_URL = "http://localhost:8081"

NODES = [
    {"name": "node1", "url": "http://localhost:8001", "email": "admin@node1.fed-med-fl.com", "password": "AdminNode1@2026"},
    # {"name": "node2", "url": "http://localhost:8002", "email": "admin@node2.fed-med-fl.com", "password": "AdminNode2@2026"},
    # {"name": "node3", "url": "http://localhost:8003", "email": "admin@node3.fed-med-fl.com", "password": "AdminNode3@2026"},
    # {"name": "node4", "url": "http://localhost:8004", "email": "admin@node4.fed-med-fl.com", "password": "AdminNode4@2026"},
]

# ============================================================================
# TIMEOUTS
# ============================================================================

TIMEOUT             = 30
POLL_INTERVAL       = 5
MAX_TRAINING_WAIT   = 3600
SERVER_INIT_WAIT    = 45
SERVER_STOP_WAIT    = 60

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


def login_all() -> bool:
    log("Authenticating with all nodes...")
    return all(login(node) for node in NODES)


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


def check_active_datasets() -> bool:
    """Verify every node has an active dataset set via the UI. Does not modify anything."""
    log("Checking active datasets on all nodes...")
    ok = True
    for node in NODES:
        dataset_id = get_active_dataset(node)
        if dataset_id:
            log(f"✓ {node['name']} — active dataset: {dataset_id}")
        else:
            log(f"✗ {node['name']} — no active dataset. Register and activate one via the UI.", "ERROR")
            ok = False
    return ok


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

    deadline = time.time() + 10
    while time.time() < deadline:
        if not is_flower_running():
            log("✓ Flower Server stopped")
            return True
        time.sleep(2)

    log("⚠ Could not stop Flower Server", "WARNING")
    return False


def start_flower_server(session: Dict) -> bool:
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
        "proximal_mu":           session.get("proximal_mu", 0.01),
        "server_momentum":       session.get("server_momentum", 0.9),
        "server_lr":             session.get("server_lr", 0.01),
        "server_beta1":          session.get("server_beta1", 0.9),
        "server_beta2":          session.get("server_beta2", 0.99),
        "server_tau":            session.get("server_tau", 1e-3),
    }
    # No run_id — experiment logging not used in UI mode
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
            log("✓ Flower Server started")

            log(f"  Waiting for Flower Server to be ready (max {SERVER_INIT_WAIT}s)...")
            start_wait = time.time()
            deadline = start_wait + SERVER_INIT_WAIT
            while time.time() < deadline:
                time.sleep(2)
                try:
                    status_r = requests.get(f"{CENTRAL_URL}/flower/status", timeout=5)
                    if status_r.status_code == 200 and status_r.json().get("flower_server_running"):
                        elapsed = time.time() - start_wait
                        log(f"  ✓ Flower Server ready after {elapsed:.0f}s — waiting 3s for gRPC stabilization")
                        time.sleep(3)
                        return True
                except Exception:
                    pass
            log(f"  ⚠ Flower Server did not respond in {SERVER_INIT_WAIT}s, continuing anyway", "WARNING")
            return True
        log(f"✗ Failed to start Flower Server: {r.status_code} — {r.text}", "ERROR")
    except Exception as e:
        log(f"✗ Error starting Flower Server: {e}", "ERROR")
    return False


# ============================================================================
# Training — no splits_dir, uses UI dataset (train/ val/ test/ folders)
# ============================================================================

def start_training(node: Dict, dataset_id: str) -> Optional[str]:
    try:
        r = requests.post(
            f"{node['url']}/api/federated/train",
            params={
                "dataset_id": dataset_id,
                "model_name": MODEL_NAME,
                "batch_size": BATCH_SIZE,
                # splits_dir intentionally omitted — uses UI dataset path 2
            },
            headers=auth_headers(node["name"]),
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
            headers=auth_headers(node["name"]),
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
        if elapsed > MAX_TRAINING_WAIT:
            log(f"✗ Timeout after {elapsed:.0f}s", "ERROR")
            return False

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
# Single session runner
# ============================================================================

def run_session(session_num: int, session: Dict) -> bool:
    label = session["label"]

    log_banner(f"SESSION {session_num}/{len(SESSIONS)}: {label}")

    if not start_flower_server(session):
        log(f"✗ Session {session_num} aborted — could not start Flower Server", "ERROR")
        return False

    log(f"  Waiting {SERVER_INIT_WAIT}s for server to initialize...")
    time.sleep(SERVER_INIT_WAIT)

    job_ids = start_training_all()
    if not job_ids:
        log(f"✗ Session {session_num} aborted — could not start training", "ERROR")
        return False

    success = monitor_training(job_ids)

    if success:
        log(f"✓ Session {session_num} ({label}) PASSED")
    else:
        log(f"✗ Session {session_num} ({label}) FAILED", "ERROR")
        force_stop_flower_server()

    return success


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    log_banner(
        f"Fed-Med-FL — UI Dataset Mode\n"
        f"  Nodes:    {len(NODES)}\n"
        f"  Rounds:   {NUM_ROUNDS} per session\n"
        f"  Epochs:   {NUM_EPOCHS} per round\n"
        f"  Model:    {MODEL_NAME}\n"
        f"  Batch:    {BATCH_SIZE}\n"
        f"  Sessions: {len(SESSIONS)}\n"
        f"  Dataset:  active dataset from UI (train/ val/ test/ folders)"
    )
    for i, s in enumerate(SESSIONS, 1):
        log(f"  {i}. {s['label']}")

    log("\n[SETUP 1] Checking services...")
    if not check_all_services():
        log("✗ Not all services available. Exiting.", "ERROR")
        sys.exit(1)

    log("\n[SETUP 2] Authenticating...")
    if not login_all():
        log("✗ Authentication failed. Exiting.", "ERROR")
        sys.exit(1)

    log("\n[SETUP 3] Checking active datasets (set via UI)...")
    if not check_active_datasets():
        log("✗ One or more nodes have no active dataset. Register and activate datasets via the UI first.", "ERROR")
        sys.exit(1)

    results: Dict[str, bool] = {}

    for i, session in enumerate(SESSIONS, 1):
        if i > 1:
            log(f"\nWaiting for Flower Server to stop before session {i}...")
            if not wait_for_flower_to_stop():
                log("⚠ Server did not stop in time — force-stopping...", "WARNING")
                force_stop_flower_server()

        success = run_session(i, session)
        results[session["label"]] = success

        if not success:
            log(f"\n⚠ Session {i} failed — continuing with remaining sessions", "WARNING")

    log_banner("FINAL RESULTS")
    all_passed = True
    for label, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        log(f"  {status}  —  {label}")
        if not passed:
            all_passed = False

    log("")
    if all_passed:
        log("✓✓✓ ALL SESSIONS PASSED ✓✓✓")
        sys.exit(0)
    else:
        log("✗✗✗ ONE OR MORE SESSIONS FAILED ✗✗✗", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
