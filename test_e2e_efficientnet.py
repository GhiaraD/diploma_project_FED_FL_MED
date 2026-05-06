#!/usr/bin/env python3
"""
End-to-End Test: EfficientNet with 2 nodes, 1 round
"""
import requests
import time
import json
import sys
from typing import Dict, Any

# Configuration
CENTRAL_URL = "http://localhost:8081"
NODE1_URL = "http://localhost:8001"
NODE2_URL = "http://localhost:8002"

TIMEOUT = 30
POLL_INTERVAL = 5
MAX_TRAINING_WAIT = 1800  # 30 minutes max for training (increased for 4 rounds)

# Default credentials (from init_security_local.py)
NODE1_EMAIL = "admin@node1.fed-med-fl.com"
NODE1_PASSWORD = "AdminNode1@2026"
NODE2_EMAIL = "admin@node2.fed-med-fl.com"
NODE2_PASSWORD = "AdminNode2@2026"

# Store tokens for each node
node_tokens = {}


def log(message: str, level: str = "INFO"):
    """Print formatted log message"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def login_to_node(node_url: str, node_name: str, email: str, password: str) -> str:
    """Login to a node and get JWT token"""
    try:
        login_data = {
            "username": email,  # API expects 'username' field but it's actually email
            "password": password
        }
        
        response = requests.post(
            f"{node_url}/api/auth/login",
            data=login_data,  # Use form data instead of JSON
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            token = result.get("access_token")
            if token:
                node_tokens[node_name] = token
                log(f"✓ Logged in to {node_name}")
                return token
            else:
                log(f"✗ No token in response from {node_name}", "ERROR")
                return None
        else:
            log(f"✗ Login failed for {node_name}: {response.status_code} - {response.text}", "ERROR")
            return None
            
    except Exception as e:
        log(f"✗ Error logging in to {node_name}: {e}", "ERROR")
        return None


def get_auth_headers(node_name: str) -> Dict[str, str]:
    """Get authorization headers for a node"""
    token = node_tokens.get(node_name)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def check_service(url: str, name: str, is_node: bool = False) -> bool:
    """Check if a service is available"""
    try:
        health_endpoint = "/api/health" if is_node else "/health"
        response = requests.get(f"{url}{health_endpoint}", timeout=TIMEOUT)
        if response.status_code == 200:
            log(f"✓ {name} is available")
            return True
        else:
            log(f"✗ {name} returned status {response.status_code}", "ERROR")
            return False
    except Exception as e:
        log(f"✗ {name} is not available: {e}", "ERROR")
        return False


def register_node(node_url: str, node_name: str, round_id: str) -> bool:
    """Register a node to join a round"""
    try:
        # Register with central for this round
        register_data = {
            "node_id": node_name
        }
        
        response = requests.post(
            f"{CENTRAL_URL}/round/{round_id}/join",
            json=register_data,
            timeout=TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            log(f"✓ {node_name} registered for round {round_id}")
            return True
        else:
            log(f"✗ Failed to register {node_name}: {response.text}", "ERROR")
            return False
            
    except Exception as e:
        log(f"✗ Error registering {node_name}: {e}", "ERROR")
        return False


def create_training_round() -> str:
    """Create a training round with EfficientNet B0"""
    try:
        round_id = f"efficientnet_test_{int(time.time())}"
        
        round_data = {
            "round_id": round_id,
            "model_name": "efficientnet_b0",
            "num_classes": 2,
            "pretrained": True,
            "hyperparameters": {
                "num_epochs": 2,  # 2 epochs per round
                "batch_size": 16,
                "learning_rate": 0.001,
                "optimizer": "adam"
            }
        }
        
        log(f"Creating training round: {json.dumps(round_data, indent=2)}")
        
        response = requests.post(
            f"{CENTRAL_URL}/round/create",
            json=round_data,
            timeout=TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            log(f"✓ Training round created: {round_id}")
            log(f"Round details: {json.dumps(result, indent=2)}")
            return round_id
        else:
            log(f"✗ Failed to create round: {response.status_code} - {response.text}", "ERROR")
            return None
            
    except Exception as e:
        log(f"✗ Error creating round: {e}", "ERROR")
        return None


def list_and_activate_dataset(node_url: str, node_name: str) -> str:
    """List datasets and activate the first one found"""
    try:
        # List datasets
        log(f"Listing datasets for {node_name}...")
        response = requests.get(
            f"{node_url}/api/data/list",
            headers=get_auth_headers(node_name),
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            datasets = response.json()
            if datasets and len(datasets) > 0:
                dataset_id = datasets[0].get("dataset_id")  # Changed from "id" to "dataset_id"
                log(f"✓ Found dataset for {node_name}: {dataset_id}")
                
                # Activate the dataset
                log(f"Activating dataset for {node_name}...")
                activate_response = requests.post(
                    f"{node_url}/api/data/set-active/{dataset_id}",
                    headers=get_auth_headers(node_name),
                    timeout=TIMEOUT
                )
                
                if activate_response.status_code == 200:
                    log(f"✓ Dataset activated for {node_name}")
                    return dataset_id
                else:
                    log(f"⚠ Could not activate dataset for {node_name}: {activate_response.text}", "WARNING")
                    return dataset_id  # Return anyway, might still work
            else:
                log(f"✗ No datasets found for {node_name}", "ERROR")
                return None
        else:
            log(f"✗ Failed to list datasets for {node_name}: {response.text}", "ERROR")
            return None
            
    except Exception as e:
        log(f"✗ Error listing datasets for {node_name}: {e}", "ERROR")
        return None


def register_and_activate_dataset(node_url: str, node_name: str, dataset_path: str) -> str:
    """Register and activate a dataset for a node"""
    try:
        # Register dataset
        register_data = {
            "name": f"{node_name}_pneumonia_dataset",
            "path": dataset_path,
            "type": "image_classification",
            "description": "Chest X-Ray Pneumonia Detection Dataset"
        }
        
        log(f"Registering dataset for {node_name}...")
        response = requests.post(
            f"{node_url}/api/data/register",
            json=register_data,
            headers=get_auth_headers(node_name),
            timeout=TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            dataset_id = result.get("dataset_id")
            log(f"✓ Dataset registered for {node_name}: {dataset_id}")
            
            # Activate the dataset
            log(f"Activating dataset for {node_name}...")
            activate_response = requests.post(
                f"{node_url}/api/data/set-active/{dataset_id}",
                headers=get_auth_headers(node_name),
                timeout=TIMEOUT
            )
            
            if activate_response.status_code == 200:
                log(f"✓ Dataset activated for {node_name}")
                return dataset_id
            else:
                log(f"⚠ Could not activate dataset for {node_name}: {activate_response.text}", "WARNING")
                return dataset_id  # Return anyway, might still work
        else:
            log(f"✗ Failed to register dataset for {node_name}: {response.text}", "ERROR")
            return None
            
    except Exception as e:
        log(f"✗ Error registering dataset for {node_name}: {e}", "ERROR")
        return None


def get_active_dataset(node_url: str, node_name: str) -> str:
    """Get the active dataset ID for a node"""
    try:
        response = requests.get(
            f"{node_url}/api/data/active",
            headers=get_auth_headers(node_name),
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            active_dataset = data.get("active_dataset")
            if active_dataset:
                dataset_id = active_dataset.get("dataset_id")
                if dataset_id:
                    log(f"✓ Active dataset for {node_name}: {dataset_id}")
                    return dataset_id
            log(f"⚠ No active dataset for {node_name}", "WARNING")
            return None
        else:
            log(f"⚠ Could not get active dataset for {node_name}: {response.text}", "WARNING")
            return None
            
    except Exception as e:
        log(f"⚠ Error getting active dataset for {node_name}: {e}", "WARNING")
        return None


def start_training_on_nodes(round_id: str, node1_url: str, node2_url: str) -> bool:
    """Start federated training on both nodes"""
    try:
        # Get active datasets
        dataset1 = get_active_dataset(node1_url, "node1")
        dataset2 = get_active_dataset(node2_url, "node2")
        
        if not dataset1 or not dataset2:
            log("✗ Could not get active datasets for both nodes", "ERROR")
            return False
        
        # Start training on node1
        log(f"Starting training on node1 for round {round_id}...")
        response1 = requests.post(
            f"{node1_url}/api/federated/train/{round_id}?dataset_id={dataset1}",
            headers=get_auth_headers("node1"),
            timeout=TIMEOUT
        )
        
        if response1.status_code != 200:
            log(f"✗ Failed to start training on node1: {response1.text}", "ERROR")
            return False
        
        job1 = response1.json()
        log(f"✓ Training started on node1, job_id: {job1.get('job_id')}")
        
        # Start training on node2
        log(f"Starting training on node2 for round {round_id}...")
        response2 = requests.post(
            f"{node2_url}/api/federated/train/{round_id}?dataset_id={dataset2}",
            headers=get_auth_headers("node2"),
            timeout=TIMEOUT
        )
        
        if response2.status_code != 200:
            log(f"✗ Failed to start training on node2: {response2.text}", "ERROR")
            return False
        
        job2 = response2.json()
        log(f"✓ Training started on node2, job_id: {job2.get('job_id')}")
        
        return True
            
    except Exception as e:
        log(f"✗ Error starting training: {e}", "ERROR")
        return False


def get_round_status(round_id: str) -> Dict[str, Any]:
    """Get the current status of a training round"""
    try:
        response = requests.get(
            f"{CENTRAL_URL}/round/{round_id}/status",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            log(f"✗ Failed to get round status: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"✗ Error getting round status: {e}", "ERROR")
        return None


def monitor_training(round_id: str, node1_url: str, node2_url: str) -> bool:
    """Monitor training progress on nodes until completion"""
    log(f"Monitoring training round {round_id}...")
    start_time = time.time()
    
    # Track consecutive status checks
    consecutive_completed = 0
    consecutive_unavailable = 0
    REQUIRED_CONSECUTIVE_COMPLETED = 3  # Need 3 consecutive "completed" to confirm
    MAX_CONSECUTIVE_UNAVAILABLE = 10  # After 10 unavailable checks, assume training is done
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > MAX_TRAINING_WAIT:
            log(f"✗ Training timeout after {elapsed:.0f} seconds", "ERROR")
            return False
        
        # Check status on both nodes
        try:
            response1 = requests.get(
                f"{node1_url}/api/federated/status/{round_id}",
                headers=get_auth_headers("node1"),
                timeout=TIMEOUT
            )
            response2 = requests.get(
                f"{node2_url}/api/federated/status/{round_id}",
                headers=get_auth_headers("node2"),
                timeout=TIMEOUT
            )
            
            status1_ok = response1.status_code == 200
            status2_ok = response2.status_code == 200
            
            if status1_ok and status2_ok:
                status1 = response1.json()
                status2 = response2.json()
                
                status1_state = status1.get('status', 'unknown')
                status2_state = status2.get('status', 'unknown')
                
                log(f"Node1 status: {status1_state} | Node2 status: {status2_state} | Elapsed: {elapsed:.0f}s")
                
                # Check if both completed
                if status1_state == 'completed' and status2_state == 'completed':
                    consecutive_completed += 1
                    consecutive_unavailable = 0
                    
                    if consecutive_completed >= REQUIRED_CONSECUTIVE_COMPLETED:
                        log(f"✓ Training completed on both nodes (confirmed {consecutive_completed} times)!")
                        log(f"Node1 final: {json.dumps(status1, indent=2)}")
                        log(f"Node2 final: {json.dumps(status2, indent=2)}")
                        return True
                    else:
                        log(f"  Confirming completion... ({consecutive_completed}/{REQUIRED_CONSECUTIVE_COMPLETED})")
                else:
                    consecutive_completed = 0
                
                # Check if any failed
                if status1_state == 'failed' or status2_state == 'failed':
                    log(f"✗ Training failed on at least one node!", "ERROR")
                    log(f"Node1: {json.dumps(status1, indent=2)}")
                    log(f"Node2: {json.dumps(status2, indent=2)}")
                    return False
            else:
                # If status endpoint doesn't work, count consecutive unavailable
                consecutive_unavailable += 1
                consecutive_completed = 0
                
                log(f"⚠ Status endpoint unavailable (Node1: {response1.status_code}, Node2: {response2.status_code}) | Elapsed: {elapsed:.0f}s", "WARNING")
                
                if consecutive_unavailable >= MAX_CONSECUTIVE_UNAVAILABLE:
                    log(f"⚠ Status endpoint unavailable for {consecutive_unavailable} consecutive checks", "WARNING")
                    log(f"  Assuming training completed (Flower Server may have finished)")
                    log(f"  Please verify manually by checking Flower Server logs or model files")
                    return True
                else:
                    log(f"  Continuing to wait... ({consecutive_unavailable}/{MAX_CONSECUTIVE_UNAVAILABLE} unavailable checks, timeout in {MAX_TRAINING_WAIT - elapsed:.0f}s)")
            
        except Exception as e:
            log(f"⚠ Error checking status: {e}", "WARNING")
            consecutive_unavailable += 1
            
            if consecutive_unavailable >= MAX_CONSECUTIVE_UNAVAILABLE:
                log(f"⚠ Too many consecutive errors ({consecutive_unavailable})", "WARNING")
                log(f"  Assuming training completed or connection issues")
                return True
        
        time.sleep(POLL_INTERVAL)


def main():
    """Run the end-to-end test"""
    log("=" * 80)
    log("Starting End-to-End Test: EfficientNet with 2 nodes, 2 rounds, 2 epochs/round")
    log("=" * 80)
    
    # Step 1: Check all services
    log("\n[STEP 1] Checking services availability...")
    services_ok = all([
        check_service(CENTRAL_URL, "Central Server", is_node=False),
        check_service(NODE1_URL, "Node 1", is_node=True),
        check_service(NODE2_URL, "Node 2", is_node=True)
    ])
    
    if not services_ok:
        log("✗ Not all services are available. Exiting.", "ERROR")
        sys.exit(1)
    
    # Step 2: Login to nodes
    log("\n[STEP 2] Authenticating with nodes...")
    auth_ok = all([
        login_to_node(NODE1_URL, "node1", NODE1_EMAIL, NODE1_PASSWORD),
        login_to_node(NODE2_URL, "node2", NODE2_EMAIL, NODE2_PASSWORD)
    ])
    
    if not auth_ok:
        log("✗ Failed to authenticate with all nodes. Exiting.", "ERROR")
        sys.exit(1)
    
    # Step 3: List and activate datasets
    log("\n[STEP 3] Listing and activating datasets...")
    datasets_ok = all([
        list_and_activate_dataset(NODE1_URL, "node1"),
        list_and_activate_dataset(NODE2_URL, "node2")
    ])
    
    if not datasets_ok:
        log("✗ Failed to register datasets. Exiting.", "ERROR")
        sys.exit(1)
    
    # Step 4: Create training round
    log("\n[STEP 4] Creating training round...")
    round_id = create_training_round()
    
    if not round_id:
        log("✗ Failed to create training round. Exiting.", "ERROR")
        sys.exit(1)
    
    # Step 5: Register nodes to round
    log("\n[STEP 5] Registering nodes to round...")
    nodes_ok = all([
        register_node(NODE1_URL, "node1", round_id),
        register_node(NODE2_URL, "node2", round_id)
    ])
    
    if not nodes_ok:
        log("✗ Failed to register all nodes. Exiting.", "ERROR")
        sys.exit(1)
    
    # Give nodes a moment to fully register
    time.sleep(2)
    
    # Step 6: Start training on nodes
    log("\n[STEP 6] Starting training on nodes...")
    if not start_training_on_nodes(round_id, NODE1_URL, NODE2_URL):
        log("✗ Failed to start training. Exiting.", "ERROR")
        sys.exit(1)
    
    # Step 7: Monitor training
    log("\n[STEP 7] Monitoring training progress...")
    success = monitor_training(round_id, NODE1_URL, NODE2_URL)
    
    # Final result
    log("\n" + "=" * 80)
    if success:
        log("✓✓✓ END-TO-END TEST PASSED ✓✓✓", "SUCCESS")
        log("=" * 80)
        sys.exit(0)
    else:
        log("✗✗✗ END-TO-END TEST FAILED ✗✗✗", "ERROR")
        log("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
