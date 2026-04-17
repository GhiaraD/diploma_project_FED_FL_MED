#!/usr/bin/env python3
"""
Automated End-to-End FL Workflow Test

Fully automated test that:
1. Creates synthetic datasets
2. Uploads them to nodes via API
3. Creates FL round
4. Starts training on all nodes
5. Monitors progress
6. Triggers aggregation
7. Displays results
"""
import requests
import time
import sys
import os
from pathlib import Path

# Colors for terminal output
class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

def print_step(msg):
    print(f"{Colors.YELLOW}▶ {msg}{Colors.NC}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.NC}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.NC}")
    sys.exit(1)

def print_header(msg):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}{msg}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}\n")

# Configuration
CENTRAL_URL = "http://localhost:8080"
NODES = [
    {"id": "node1", "url": "http://localhost:8001"},
    {"id": "node2", "url": "http://localhost:8002"},
    {"id": "node3", "url": "http://localhost:8003"},
]
ROUND_ID = f"R-AUTO-{int(time.time())}"

def check_services():
    """Check if all services are running."""
    print_step("Checking services...")
    
    # Check central
    try:
        r = requests.get(f"{CENTRAL_URL}/health", timeout=5)
        r.raise_for_status()
        print_success("Central server OK")
    except Exception as e:
        print_error(f"Central server not responding: {e}")
    
    # Check nodes
    for node in NODES:
        try:
            r = requests.get(f"{node['url']}/api/health", timeout=5)
            r.raise_for_status()
            print_success(f"{node['id']} OK")
        except Exception as e:
            print_error(f"{node['id']} not responding: {e}")
    
    print()

def create_datasets():
    """Create synthetic test datasets."""
    print_step("Creating synthetic datasets...")
    
    # Check if datasets already exist
    datasets = [
        "test_dataset_node1.zip",
        "test_dataset_node2.zip",
        "test_dataset_node3.zip"
    ]
    
    if all(os.path.exists(d) for d in datasets):
        print("Datasets already exist, skipping creation")
        print_success("Test datasets ready")
        return
    
    # Create datasets
    import subprocess
    result = subprocess.run(
        ["python3", "scripts/create_test_dataset.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print_error(f"Failed to create datasets: {result.stderr}")
    
    print_success("Test datasets created")
    print()

def upload_datasets():
    """Upload datasets to nodes via API."""
    print_step("Uploading datasets to nodes...")
    
    dataset_ids = []
    
    for i, node in enumerate(NODES, 1):
        dataset_file = f"test_dataset_node{i}.zip"
        
        if not os.path.exists(dataset_file):
            print_error(f"Dataset file not found: {dataset_file}")
        
        print(f"Uploading {dataset_file} to {node['id']}...")
        
        try:
            with open(dataset_file, 'rb') as f:
                files = {'file': (dataset_file, f, 'application/zip')}
                data = {'split': 'train'}
                
                r = requests.post(
                    f"{node['url']}/api/data/upload",
                    files=files,
                    data=data,
                    timeout=60
                )
                r.raise_for_status()
                
                result = r.json()
                dataset_id = result['dataset_id']
                dataset_ids.append(dataset_id)
                
                print_success(f"{node['id']}: {dataset_id} ({result['num_samples']} samples)")
        
        except Exception as e:
            print_error(f"Failed to upload to {node['id']}: {e}")
    
    print()
    return dataset_ids

def create_round():
    """Create FL round on central server."""
    print_step(f"Creating FL round {ROUND_ID}...")
    
    payload = {
        "round_id": ROUND_ID,
        "model_name": "resnet18",
        "num_classes": 2,
        "pretrained": True,
        "hyperparameters": {
            "num_epochs": 2,
            "batch_size": 16,
            "learning_rate": 0.001,
            "optimizer": "adam"
        }
    }
    
    try:
        r = requests.post(f"{CENTRAL_URL}/round/create", json=payload, timeout=30)
        r.raise_for_status()
        result = r.json()
        
        if result.get('status') == 'success':
            print_success(f"Round created: {ROUND_ID}")
            print(f"  Model: {result['model_name']}")
            print(f"  Hash: {result['base_model_hash'][:16]}...")
        else:
            print_error("Failed to create round")
    
    except Exception as e:
        print_error(f"Failed to create round: {e}")
    
    print()

def join_round():
    """All nodes join the round."""
    print_step("Nodes joining round...")
    
    for node in NODES:
        try:
            r = requests.post(
                f"{CENTRAL_URL}/round/{ROUND_ID}/join",
                json={"node_id": node['id']},
                timeout=10
            )
            r.raise_for_status()
            result = r.json()
            
            if result.get('status') == 'success':
                print_success(f"{node['id']} joined")
            else:
                print_error(f"{node['id']} failed to join")
        
        except Exception as e:
            print_error(f"{node['id']} failed to join: {e}")
    
    print()

def check_round_status():
    """Check round status."""
    print_step("Checking round status...")
    
    try:
        r = requests.get(f"{CENTRAL_URL}/round/{ROUND_ID}/status", timeout=10)
        r.raise_for_status()
        result = r.json()
        
        print(f"  Status: {result['status']}")
        print(f"  Participants: {result['num_participants']}")
        print(f"  Updates received: {result['updates_received']}")
        
        if result['num_participants'] == 3:
            print_success("All 3 nodes registered")
        else:
            print_error(f"Expected 3 participants, got {result['num_participants']}")
    
    except Exception as e:
        print_error(f"Failed to check status: {e}")
    
    print()

def start_training(dataset_ids):
    """Start federated training on all nodes."""
    print_step("Starting federated training...")
    
    job_ids = []
    
    for node, dataset_id in zip(NODES, dataset_ids):
        try:
            r = requests.post(
                f"{node['url']}/api/federated/train/{ROUND_ID}",
                params={"dataset_id": dataset_id},
                timeout=10
            )
            r.raise_for_status()
            result = r.json()
            
            job_id = result['job_id']
            job_ids.append((node, job_id))
            
            print_success(f"{node['id']} training started: {job_id}")
        
        except Exception as e:
            print_error(f"Failed to start training on {node['id']}: {e}")
    
    print()
    return job_ids

def monitor_training(job_ids):
    """Monitor training progress."""
    print_step("Monitoring training progress...")
    print("(This may take 5-15 minutes depending on hardware)\n")
    
    start_time = time.time()
    max_wait = 1800  # 30 minutes max
    
    while True:
        statuses = []
        
        for node, job_id in job_ids:
            try:
                r = requests.get(f"{node['url']}/api/train/status/{job_id}", timeout=5)
                r.raise_for_status()
                result = r.json()
                status = result['status']
                statuses.append((node['id'], status))
            except:
                statuses.append((node['id'], 'unknown'))
        
        # Print status line
        status_str = " | ".join([f"{nid}: {st}" for nid, st in statuses])
        print(f"\r{status_str}    ", end='', flush=True)
        
        # Check if all completed
        all_completed = all(st == 'completed' for _, st in statuses)
        any_failed = any(st == 'failed' for _, st in statuses)
        
        if all_completed:
            print()
            print_success("All nodes completed training!")
            break
        
        if any_failed:
            print()
            print_error("One or more nodes failed training")
        
        # Check timeout
        if time.time() - start_time > max_wait:
            print()
            print_error("Training timeout (30 minutes)")
        
        time.sleep(5)
    
    print()

def check_updates():
    """Check if all updates were received."""
    print_step("Checking updates received by central...")
    
    try:
        r = requests.get(f"{CENTRAL_URL}/round/{ROUND_ID}/status", timeout=10)
        r.raise_for_status()
        result = r.json()
        
        updates = result['updates_received']
        print(f"  Updates received: {updates}/3")
        
        if updates == 3:
            print_success("All 3 updates received")
        else:
            print("⚠️  Waiting 10 more seconds for updates...")
            time.sleep(10)
            
            r = requests.get(f"{CENTRAL_URL}/round/{ROUND_ID}/status", timeout=10)
            r.raise_for_status()
            result = r.json()
            updates = result['updates_received']
            
            if updates == 3:
                print_success("All 3 updates received")
            else:
                print_error(f"Still missing updates: {updates}/3")
    
    except Exception as e:
        print_error(f"Failed to check updates: {e}")
    
    print()

def trigger_aggregation():
    """Trigger FedAvg aggregation."""
    print_step("Triggering FedAvg aggregation...")
    
    try:
        r = requests.post(f"{CENTRAL_URL}/round/{ROUND_ID}/aggregate", timeout=60)
        r.raise_for_status()
        result = r.json()
        
        if result.get('status') == 'success':
            print_success("Aggregation completed!")
            print(f"  Aggregated model hash: {result.get('aggregated_model_hash', 'N/A')[:16]}...")
        else:
            print_error("Aggregation failed")
    
    except Exception as e:
        print_error(f"Failed to aggregate: {e}")
    
    print()

def get_results():
    """Get final results."""
    print_step("Getting final results...")
    
    try:
        r = requests.get(f"{CENTRAL_URL}/round/{ROUND_ID}/results", timeout=10)
        r.raise_for_status()
        result = r.json()
        
        print("\n" + "="*60)
        print("FINAL RESULTS")
        print("="*60)
        print(f"Round ID: {result['round_id']}")
        print(f"Status: {result['status']}")
        print(f"Participants: {result['num_participants']}")
        print(f"Total samples: {result['total_samples']}")
        print("\nAggregated Metrics:")
        
        metrics = result.get('aggregated_metrics', {})
        for key, value in metrics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
        
        print("="*60 + "\n")
        
        print_success("Results retrieved")
    
    except Exception as e:
        print_error(f"Failed to get results: {e}")
    
    print()

def main():
    """Main test workflow."""
    print_header("Fed-Med-FL Automated End-to-End Test")
    
    # Step 0: Check services
    check_services()
    
    # Step 1: Create datasets
    create_datasets()
    
    # Step 2: Upload datasets
    dataset_ids = upload_datasets()
    
    # Step 3: Create round
    create_round()
    
    # Step 4: Join round
    join_round()
    
    # Step 5: Check status
    check_round_status()
    
    # Step 6: Start training
    job_ids = start_training(dataset_ids)
    
    # Step 7: Monitor training
    monitor_training(job_ids)
    
    # Step 8: Check updates
    check_updates()
    
    # Step 9: Trigger aggregation
    trigger_aggregation()
    
    # Step 10: Get results
    get_results()
    
    # Success
    print_header("✓ End-to-End Test PASSED!")
    print(f"Round ID: {ROUND_ID}")
    print(f"View results at: {CENTRAL_URL}/round/{ROUND_ID}/results\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
