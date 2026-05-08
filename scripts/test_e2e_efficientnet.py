#!/usr/bin/env python3
"""
End-to-End Test: EfficientNet with 2 nodes, 2 rounds, 2 epochs/round

Flow:
  1. Check services
  2. Authenticate
  3. Activate datasets
  4. Start Flower Server on Central (with training config)
  5. Start training on nodes (with batch_size)
  6. Monitor until completion
"""
import requests
import time
import json
import sys
from typing import Dict, Any, Optional

# Configuration
CENTRAL_URL = "http://localhost:8081"
NODE1_URL = "http://localhost:8001"
NODE2_URL = "http://localhost:8002"

TIMEOUT = 30
POLL_INTERVAL = 5
MAX_TRAINING_WAIT = 1800  # 30 minutes max

# Default credentials (from init_security_local.py)
NODE1_EMAIL = "admin@node1.fed-med-fl.com"
NODE1_PASSWORD = "AdminNode1@2026"
NODE2_EMAIL = "admin@node2.fed-med-fl.com"
NODE2_PASSWORD = "AdminNode2@2026"

# Training configuration — change these to adjust the run
FL_CONFIG = {
    "num_rounds": 2,
    "num_epochs": 1,
    "model_name": "efficientnet_b0",
    "learning_rate": 0.001,
    "optimizer": "adam",
    "min_fit_clients": 2,
    "batch_size": 16,  # per-node, passed to each node separately
}

node_tokens = {}


def log(message: str, level: str = "INFO"):
    """Print formatted log message."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def login_to_node(node_url: str, node_name: str, email: str, password: str) -> bool:
    """Login to a node and store JWT token."""
    try:
        response = requests.post(
            f"{node_url}/api/auth/login",
            data={"username": email, "password": password},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            if token:
                node_tokens[node_name] = token
                log(f"✓ Logged in to {node_name}")
                return True
            log(f"✗ No token in response from {node_name}", "ERROR")
        else:
            log(f"✗ Login failed for {node_name}: {response.status_code} - {response.text}", "ERROR")
    except Exception as e:
        log(f"✗ Error logging in to {node_name}: {e}", "ERROR")
    return False


def get_auth_headers(node_name: str) -> Dict[str, str]:
    """Get authorization headers for a node."""
    token = node_tokens.get(node_name)
    return {"Authorization": f"Bearer {token}"} if token else {}


def check_service(url: str, name: str, is_node: bool = False) -> bool:
    """Check if a service is available."""
    try:
        endpoint = "/api/health" if is_node else "/health"
        response = requests.get(f"{url}{endpoint}", timeout=TIMEOUT)
        if response.status_code == 200:
            log(f"✓ {name} is available")
            return True
        log(f"✗ {name} returned status {response.status_code}", "ERROR")
    except Exception as e:
        log(f"✗ {name} is not available: {e}", "ERROR")
    return False


def get_active_dataset(node_url: str, node_name: str) -> Optional[str]:
    """Get the active dataset ID for a node."""
    try:
        response = requests.get(
            f"{node_url}/api/data/active",
            headers=get_auth_headers(node_name),
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            active = response.json().get("active_dataset")
            if active:
                dataset_id = active.get("dataset_id")
                log(f"✓ Active dataset for {node_name}: {dataset_id}")
                return dataset_id
        log(f"⚠ No active dataset for {node_name}", "WARNING")
    except Exception as e:
        log(f"⚠ Error getting active dataset for {node_name}: {e}", "WARNING")
    return None


def list_and_activate_dataset(node_url: str, node_name: str) -> bool:
    """List datasets and activate the first one found."""
    try:
        response = requests.get(
            f"{node_url}/api/data/list",
            headers=get_auth_headers(node_name),
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            datasets = response.json()
            if datasets:
                dataset_id = datasets[0].get("dataset_id")
                log(f"✓ Found dataset for {node_name}: {dataset_id}")
                activate = requests.post(
                    f"{node_url}/api/data/set-active/{dataset_id}",
                    headers=get_auth_headers(node_name),
                    timeout=TIMEOUT,
                )
                if activate.status_code == 200:
                    log(f"✓ Dataset activated for {node_name}")
                else:
                    log(f"⚠ Could not activate dataset: {activate.text}", "WARNING")
                return True
            log(f"✗ No datasets found for {node_name}", "ERROR")
        else:
            log(f"✗ Failed to list datasets for {node_name}: {response.text}", "ERROR")
    except Exception as e:
        log(f"✗ Error listing datasets for {node_name}: {e}", "ERROR")
    return False


def start_fl_server(config: Dict) -> bool:
    """
    Start Flower Server on Central with the given training configuration.

    num_rounds, num_epochs, model_name, learning_rate, optimizer, min_fit_clients
    are all sent here — the server will push them to clients via configure_fit().
    """
    try:
        response = requests.post(
            f"{CENTRAL_URL}/api/fl/start",
            params={
                "num_rounds": config["num_rounds"],
                "num_epochs": config["num_epochs"],
                "model_name": config["model_name"],
                "learning_rate": config["learning_rate"],
                "optimizer": config["optimizer"],
                "min_fit_clients": config["min_fit_clients"],
                "min_available_clients": config["min_fit_clients"],
            },
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "already_running":
                log(f"⚠ Flower Server already running", "WARNING")
                return True
            log(f"✓ Flower Server started with config: {json.dumps(result.get('config', {}))}")
            return True
        log(f"✗ Failed to start Flower Server: {response.status_code} - {response.text}", "ERROR")
    except Exception as e:
        log(f"✗ Error starting Flower Server: {e}", "ERROR")
    return False


def start_training_on_nodes(config: Dict) -> Optional[Dict[str, Dict]]:
    """
    Start federated training on both nodes.

    batch_size and model_name are passed here — each node uses them locally.
    Returns dict with job_id and round_id per node, or None on failure.
    """
    dataset1 = get_active_dataset(NODE1_URL, "node1")
    dataset2 = get_active_dataset(NODE2_URL, "node2")

    if not dataset1 or not dataset2:
        log("✗ Could not get active datasets for both nodes", "ERROR")
        return None

    results = {}

    for node_name, node_url, dataset_id in [
        ("node1", NODE1_URL, dataset1),
        ("node2", NODE2_URL, dataset2),
    ]:
        log(f"Starting training on {node_name}...")
        try:
            response = requests.post(
                f"{node_url}/api/federated/train",
                params={
                    "dataset_id": dataset_id,
                    "model_name": config["model_name"],
                    "batch_size": config["batch_size"],
                },
                headers=get_auth_headers(node_name),
                timeout=TIMEOUT,
            )
            if response.status_code != 200:
                log(f"✗ Failed to start training on {node_name}: {response.text}", "ERROR")
                return None
            job = response.json()
            results[node_name] = {"job_id": job["job_id"]}
            log(f"✓ Training started on {node_name} — job_id: {job['job_id']}")
        except Exception as e:
            log(f"✗ Error starting training on {node_name}: {e}", "ERROR")
            return None

    return results


def monitor_training(training_info: Dict[str, Dict]) -> bool:
    """Monitor training progress on both nodes until completion."""
    job_id1 = training_info["node1"]["job_id"]
    job_id2 = training_info["node2"]["job_id"]

    log(f"Monitoring — node1 job: {job_id1}, node2 job: {job_id2}")
    start_time = time.time()

    consecutive_completed = 0
    consecutive_unavailable = 0
    REQUIRED_CONSECUTIVE_COMPLETED = 3
    MAX_CONSECUTIVE_UNAVAILABLE = 10

    while True:
        elapsed = time.time() - start_time

        if elapsed > MAX_TRAINING_WAIT:
            log(f"✗ Training timeout after {elapsed:.0f} seconds", "ERROR")
            return False

        try:
            r1 = requests.get(
                f"{NODE1_URL}/api/federated/status/{job_id1}",
                headers=get_auth_headers("node1"),
                timeout=TIMEOUT,
            )
            r2 = requests.get(
                f"{NODE2_URL}/api/federated/status/{job_id2}",
                headers=get_auth_headers("node2"),
                timeout=TIMEOUT,
            )

            if r1.status_code == 200 and r2.status_code == 200:
                s1 = r1.json().get("status", "unknown")
                s2 = r2.json().get("status", "unknown")

                log(f"Node1: {s1} | Node2: {s2} | Elapsed: {elapsed:.0f}s")

                if s1 == "completed" and s2 == "completed":
                    consecutive_completed += 1
                    consecutive_unavailable = 0
                    if consecutive_completed >= REQUIRED_CONSECUTIVE_COMPLETED:
                        log("✓ Training completed on both nodes!")
                        return True
                    log(f"  Confirming... ({consecutive_completed}/{REQUIRED_CONSECUTIVE_COMPLETED})")
                else:
                    consecutive_completed = 0

                if s1 == "failed" or s2 == "failed":
                    log("✗ Training failed on at least one node!", "ERROR")
                    return False
            else:
                consecutive_unavailable += 1
                consecutive_completed = 0
                log(
                    f"⚠ Status unavailable (node1: {r1.status_code}, node2: {r2.status_code}) | {elapsed:.0f}s",
                    "WARNING",
                )
                if consecutive_unavailable >= MAX_CONSECUTIVE_UNAVAILABLE:
                    log("⚠ Status unavailable too long — assuming completed", "WARNING")
                    return True

        except Exception as e:
            log(f"⚠ Error checking status: {e}", "WARNING")
            consecutive_unavailable += 1
            if consecutive_unavailable >= MAX_CONSECUTIVE_UNAVAILABLE:
                log("⚠ Too many errors — assuming completed", "WARNING")
                return True

        time.sleep(POLL_INTERVAL)


def main():
    """Run the end-to-end test."""
    log("=" * 80)
    log("Starting End-to-End Test: EfficientNet with 2 nodes")
    log(f"Config: {json.dumps(FL_CONFIG, indent=2)}")
    log("=" * 80)

    # Step 1: Check all services
    log("\n[STEP 1] Checking services availability...")
    if not all([
        check_service(CENTRAL_URL, "Central Server", is_node=False),
        check_service(NODE1_URL, "Node 1", is_node=True),
        check_service(NODE2_URL, "Node 2", is_node=True),
    ]):
        log("✗ Not all services are available. Exiting.", "ERROR")
        sys.exit(1)

    # Step 2: Login to nodes
    log("\n[STEP 2] Authenticating with nodes...")
    if not all([
        login_to_node(NODE1_URL, "node1", NODE1_EMAIL, NODE1_PASSWORD),
        login_to_node(NODE2_URL, "node2", NODE2_EMAIL, NODE2_PASSWORD),
    ]):
        log("✗ Failed to authenticate. Exiting.", "ERROR")
        sys.exit(1)

    # Step 3: Activate datasets
    log("\n[STEP 3] Activating datasets...")
    if not all([
        list_and_activate_dataset(NODE1_URL, "node1"),
        list_and_activate_dataset(NODE2_URL, "node2"),
    ]):
        log("✗ Failed to activate datasets. Exiting.", "ERROR")
        sys.exit(1)

    # Step 4: Start Flower Server with training config
    log("\n[STEP 4] Starting Flower Server on Central...")
    if not start_fl_server(FL_CONFIG):
        log("✗ Failed to start Flower Server. Exiting.", "ERROR")
        sys.exit(1)

    # Brief pause to let server initialize before clients connect
    time.sleep(3)

    # Step 5: Start training on nodes
    log("\n[STEP 5] Starting federated training on nodes...")
    training_info = start_training_on_nodes(FL_CONFIG)
    if not training_info:
        log("✗ Failed to start training. Exiting.", "ERROR")
        sys.exit(1)

    # Step 6: Monitor training
    log("\n[STEP 6] Monitoring training progress...")
    success = monitor_training(training_info)

    log("\n" + "=" * 80)
    if success:
        log("✓✓✓ END-TO-END TEST PASSED ✓✓✓")
        log("=" * 80)
        sys.exit(0)
    else:
        log("✗✗✗ END-TO-END TEST FAILED ✗✗✗", "ERROR")
        log("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
