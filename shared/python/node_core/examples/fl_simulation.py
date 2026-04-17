"""
Example: Simulating a complete Federated Learning round.

This demonstrates:
1. Creating a FL round on central server
2. Nodes pulling global model
3. Nodes computing deltas after local training
4. Nodes pushing updates to central
5. Central aggregating with FedAvg
6. Creating new global model
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import torch
from node_core import (
    get_model,
    FedAvgAggregator,
    simulate_fl_round,
    compute_delta_statistics,
    compute_model_hash
)


def main():
    print("=" * 70)
    print("FEDERATED LEARNING SIMULATION")
    print("=" * 70)
    
    # Configuration
    NUM_NODES = 3
    MODEL_NAME = 'resnet18'
    ROUND_ID = 'R-1'
    
    print(f"\nConfiguration:")
    print(f"  - Number of nodes: {NUM_NODES}")
    print(f"  - Model: {MODEL_NAME}")
    print(f"  - Round ID: {ROUND_ID}")
    
    # ========================================
    # STEP 1: Initialize Central Aggregator
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 1: Initialize Central Aggregator")
    print("=" * 70)
    
    aggregator = FedAvgAggregator(
        storage_path='./demo_storage/central',
        min_nodes=2
    )
    
    # ========================================
    # STEP 2: Create Base Model
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 2: Create Base Global Model")
    print("=" * 70)
    
    base_model = get_model(MODEL_NAME, num_classes=2, pretrained=True)
    base_state = base_model.state_dict()
    base_hash = compute_model_hash(base_state)
    
    print(f"✓ Base model created")
    print(f"  - Parameters: {sum(p.numel() for p in base_model.parameters()):,}")
    print(f"  - Hash: {base_hash[:16]}...")
    
    # ========================================
    # STEP 3: Create FL Round
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 3: Create FL Round on Central")
    print("=" * 70)
    
    hyperparameters = {
        'learning_rate': 0.001,
        'num_epochs': 5,
        'batch_size': 32,
        'optimizer': 'adam'
    }
    
    round_info = aggregator.create_round(
        round_id=ROUND_ID,
        model_name=MODEL_NAME,
        base_model_state=base_state,
        hyperparameters=hyperparameters
    )
    
    # ========================================
    # STEP 4: Simulate Node Training
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 4: Simulate Local Training on Nodes")
    print("=" * 70)
    
    # Simulate FL round (creates dummy deltas)
    round_data = simulate_fl_round(
        num_nodes=NUM_NODES,
        samples_per_node=[150, 200, 180],
        model_name=MODEL_NAME
    )
    
    print(f"\n✓ Simulated training on {NUM_NODES} nodes:")
    
    for i, update in enumerate(round_data['updates']):
        node_id = update['node_id']
        n_samples = update['n_samples']
        metrics = update['metrics']
        delta = update['delta']
        
        # Compute delta statistics
        delta_stats = compute_delta_statistics(delta)
        
        print(f"\n  Node: {node_id}")
        print(f"    - Samples: {n_samples}")
        print(f"    - Accuracy: {metrics['accuracy']:.4f}")
        print(f"    - F1: {metrics['f1']:.4f}")
        print(f"    - Delta norm: {delta_stats['norm']:.4f}")
    
    # ========================================
    # STEP 5: Nodes Join Round and Push Updates
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 5: Nodes Push Updates to Central")
    print("=" * 70)
    
    for update in round_data['updates']:
        # Register participant
        aggregator.register_participant(ROUND_ID, update['node_id'])
        
        # Push update
        result = aggregator.collect_update(
            round_id=ROUND_ID,
            node_id=update['node_id'],
            delta=update['delta'],
            base_model_hash=base_hash,
            n_samples=update['n_samples'],
            metrics=update['metrics']
        )
    
    # ========================================
    # STEP 6: Validate Updates
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 6: Validate Collected Updates")
    print("=" * 70)
    
    is_valid, issues = aggregator.validate_updates(ROUND_ID)
    
    if is_valid:
        print("✓ All updates validated successfully")
    else:
        print("✗ Validation issues found:")
        for issue in issues:
            print(f"  - {issue}")
    
    # ========================================
    # STEP 7: Aggregate with FedAvg
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 7: Aggregate Updates with FedAvg")
    print("=" * 70)
    
    aggregation_result = aggregator.aggregate_round(ROUND_ID, validate=True)
    
    print(f"\n✓ Aggregation complete:")
    print(f"  - Participants: {aggregation_result['num_participants']}")
    print(f"  - Total samples: {aggregation_result['total_samples']}")
    print(f"  - New model hash: {aggregation_result['new_model_hash'][:16]}...")
    print(f"\n  Aggregated metrics:")
    for metric, value in aggregation_result['aggregated_metrics'].items():
        print(f"    - {metric}: {value:.4f}")
    
    # ========================================
    # STEP 8: Load New Global Model
    # ========================================
    print("\n" + "=" * 70)
    print("STEP 8: Load New Global Model")
    print("=" * 70)
    
    new_global_state = torch.load(aggregation_result['new_model_path'])
    new_model = get_model(MODEL_NAME, num_classes=2, pretrained=False)
    new_model.load_state_dict(new_global_state)
    
    print(f"✓ New global model loaded")
    print(f"  - Path: {aggregation_result['new_model_path']}")
    
    # Compare with base model
    print(f"\n  Comparing with base model:")
    
    total_diff = 0
    for key in base_state.keys():
        diff = torch.norm(new_global_state[key] - base_state[key]).item()
        total_diff += diff ** 2
    
    total_diff = total_diff ** 0.5
    print(f"    - Total difference norm: {total_diff:.4f}")
    
    # ========================================
    # Summary
    # ========================================
    print("\n" + "=" * 70)
    print("SIMULATION COMPLETE")
    print("=" * 70)
    
    print(f"\nSummary:")
    print(f"  ✓ Round {ROUND_ID} completed successfully")
    print(f"  ✓ {NUM_NODES} nodes participated")
    print(f"  ✓ {aggregation_result['total_samples']} total samples")
    print(f"  ✓ New global model created and saved")
    print(f"\nNext steps:")
    print(f"  1. Nodes pull new global model for round R-2")
    print(f"  2. Repeat training with updated model")
    print(f"  3. Continue for 5+ rounds to see convergence")


if __name__ == "__main__":
    main()
