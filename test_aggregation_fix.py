#!/usr/bin/env python3
"""
Test script to verify aggregation fix for n_samples=0 case.
"""
import requests
import json
import torch
from pathlib import Path

# Simulated metrics from the logs
node_metrics = {
    'node1': {
        'accuracy': 0.9770114942528736,
        'f1': 0.985239852398524,
        'precision': 0.9744525547445255,
        'recall': 0.996268656716418,
        'auc': 0.9925373134328358
    },
    'node2': {
        'accuracy': 0.985632183908046,
        'f1': 0.9905123339658444,
        'precision': 0.9886363636363636,
        'recall': 0.9923954372623575,
        'auc': 0.9986132856184299
    },
    'node3': {
        'accuracy': 0.9655172413793104,
        'f1': 0.9766536964980544,
        'precision': 0.9580152671755725,
        'recall': 0.996031746031746,
        'auc': 0.9962384259259259
    }
}

# Load actual delta from disk
delta_paths = {
    'node1': 'storage/node1/deltas/delta_node1_R-SUCCESS-1.pt',
    'node2': 'storage/node2/deltas/delta_node2_R-SUCCESS-1.pt',
    'node3': 'storage/node3/deltas/delta_node3_R-SUCCESS-1.pt'
}

CENTRAL_URL = 'http://localhost:8080'
ROUND_ID = 'R-FIX-TEST'

print("=" * 60)
print("Testing Aggregation Fix for n_samples=0")
print("=" * 60)

# Submit updates for each node
for node_id in ['node1', 'node2', 'node3']:
    print(f"\n▶ Submitting update from {node_id}...")
    
    # Load delta
    delta_path = Path(delta_paths[node_id])
    if not delta_path.exists():
        print(f"  ✗ Delta file not found: {delta_path}")
        continue
    
    delta = torch.load(delta_path)
    
    # Prepare update payload
    update_data = {
        'round_id': ROUND_ID,
        'node_id': node_id,
        'n_samples': 0,  # This is the problematic case!
        'metrics': node_metrics[node_id],
        'delta': {k: v.tolist() for k, v in delta.items()},
        'model_hash': 'test_hash_' + node_id
    }
    
    # Submit update
    try:
        response = requests.post(
            f'{CENTRAL_URL}/update/submit',
            json=update_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Update accepted")
            print(f"    - Updates received: {result.get('updates_received', '?')}/{result.get('total_participants', '?')}")
        else:
            print(f"  ✗ Failed: {response.status_code}")
            print(f"    {response.text}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

# Trigger aggregation
print(f"\n▶ Triggering FedAvg aggregation...")
try:
    response = requests.post(
        f'{CENTRAL_URL}/round/{ROUND_ID}/aggregate',
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"  ✓ Aggregation successful!")
        print(f"\n{'=' * 60}")
        print("AGGREGATED METRICS:")
        print(f"{'=' * 60}")
        
        metrics = result.get('aggregated_metrics', {})
        for metric, value in metrics.items():
            print(f"  {metric:12s}: {value:.6f}")
        
        print(f"\nTotal samples: {result.get('total_samples', 0)}")
        print(f"Participants: {result.get('num_participants', 0)}")
        print(f"{'=' * 60}")
        
        # Calculate expected values (simple average since n_samples=0)
        print(f"\nEXPECTED (simple average):")
        print(f"{'=' * 60}")
        for metric in ['accuracy', 'f1', 'precision', 'recall', 'auc']:
            values = [node_metrics[node][metric] for node in ['node1', 'node2', 'node3']]
            expected = sum(values) / len(values)
            actual = metrics.get(metric, 0)
            diff = abs(actual - expected)
            status = "✓" if diff < 0.0001 else "✗"
            print(f"  {status} {metric:12s}: {expected:.6f} (diff: {diff:.6f})")
        
    else:
        print(f"  ✗ Aggregation failed: {response.status_code}")
        print(f"    {response.text}")
except Exception as e:
    print(f"  ✗ Error: {e}")

print(f"\n{'=' * 60}")
print("Test complete!")
print(f"{'=' * 60}")
