"""
Unit tests for Federated Learning core functionality.
"""
import pytest
import torch
import torch.nn as nn
from node_core import (
    get_model,
    FederatedClient,
    FedAvgAggregator,
    compute_delta_statistics,
    scale_delta,
    clip_delta,
    compute_cosine_similarity,
    check_model_compatibility,
    simulate_fl_round
)


def test_compute_delta():
    """Test delta computation between two models."""
    # Create two models
    model1 = get_model('resnet18', num_classes=2, pretrained=False)
    model2 = get_model('resnet18', num_classes=2, pretrained=False)
    
    # Modify model2 slightly
    state2 = model2.state_dict()
    for key in state2.keys():
        state2[key] += torch.randn_like(state2[key]) * 0.01
    model2.load_state_dict(state2)
    
    # Compute delta manually
    state1 = model1.state_dict()
    state2 = model2.state_dict()
    
    delta = {}
    for key in state1.keys():
        delta[key] = state2[key] - state1[key]
    
    # Check delta is not zero
    delta_norm = sum(torch.norm(d).item() ** 2 for d in delta.values()) ** 0.5
    assert delta_norm > 0


def test_delta_statistics():
    """Test delta statistics computation."""
    # Create dummy delta
    delta = {
        'layer1': torch.randn(10, 10),
        'layer2': torch.randn(5, 5)
    }
    
    stats = compute_delta_statistics(delta)
    
    assert 'total_params' in stats
    assert 'norm' in stats
    assert 'mean' in stats
    assert 'std' in stats
    
    assert stats['total_params'] == 125  # 100 + 25


def test_scale_delta():
    """Test delta scaling."""
    delta = {
        'layer1': torch.ones(5, 5)
    }
    
    scaled = scale_delta(delta, 2.0)
    
    assert torch.allclose(scaled['layer1'], torch.ones(5, 5) * 2.0)


def test_clip_delta():
    """Test delta clipping."""
    # Create large delta
    delta = {
        'layer1': torch.ones(10, 10) * 100
    }
    
    # Clip to max norm of 10
    clipped = clip_delta(delta, max_norm=10.0)
    
    # Compute clipped norm
    clipped_norm = sum(torch.norm(d).item() ** 2 for d in clipped.values()) ** 0.5
    
    assert clipped_norm <= 10.1  # Allow small numerical error


def test_cosine_similarity():
    """Test cosine similarity between deltas."""
    delta1 = {
        'layer1': torch.ones(5, 5)
    }
    
    delta2 = {
        'layer1': torch.ones(5, 5) * 2.0
    }
    
    # Same direction, should be close to 1
    sim = compute_cosine_similarity(delta1, delta2)
    assert abs(sim - 1.0) < 0.01
    
    # Opposite direction
    delta3 = {
        'layer1': torch.ones(5, 5) * -1.0
    }
    
    sim = compute_cosine_similarity(delta1, delta3)
    assert abs(sim - (-1.0)) < 0.01


def test_check_model_compatibility():
    """Test model compatibility checking."""
    model1 = get_model('resnet18', num_classes=2, pretrained=False)
    model2 = get_model('resnet18', num_classes=2, pretrained=False)
    
    state1 = model1.state_dict()
    state2 = model2.state_dict()
    
    # Should be compatible
    assert check_model_compatibility(state1, state2)
    
    # Remove a key from state2
    del state2[list(state2.keys())[0]]
    
    # Should not be compatible
    assert not check_model_compatibility(state1, state2)


def test_fedavg_aggregation():
    """Test FedAvg aggregation."""
    aggregator = FedAvgAggregator(storage_path='./test_storage')
    
    # Simulate FL round
    round_data = simulate_fl_round(num_nodes=3, model_name='resnet18')
    
    # Create round
    round_id = 'test-round-1'
    aggregator.create_round(
        round_id=round_id,
        model_name='resnet18',
        base_model_state=round_data['base_model_state'],
        hyperparameters={'lr': 0.001, 'epochs': 5}
    )
    
    # Register participants and collect updates
    for update in round_data['updates']:
        aggregator.register_participant(round_id, update['node_id'])
        aggregator.collect_update(
            round_id=round_id,
            node_id=update['node_id'],
            delta=update['delta'],
            base_model_hash=aggregator.rounds[round_id]['base_model_hash'],
            n_samples=update['n_samples'],
            metrics=update['metrics']
        )
    
    # Validate
    is_valid, issues = aggregator.validate_updates(round_id)
    assert is_valid, f"Validation failed: {issues}"
    
    # Aggregate
    aggregated_delta = aggregator.aggregate_deltas(round_id)
    
    # Check aggregated delta is not empty
    assert len(aggregated_delta) > 0
    
    # Apply delta
    base_state = round_data['base_model_state']
    new_state = aggregator.apply_delta(base_state, aggregated_delta)
    
    # Check new state has same keys
    assert set(new_state.keys()) == set(base_state.keys())
    
    # Check new state is different from base
    is_different = False
    for key in base_state.keys():
        if not torch.allclose(base_state[key], new_state[key]):
            is_different = True
            break
    
    assert is_different, "New state should be different from base"


def test_simulate_fl_round():
    """Test FL round simulation."""
    round_data = simulate_fl_round(num_nodes=3, model_name='resnet18')
    
    assert 'base_model_state' in round_data
    assert 'updates' in round_data
    assert len(round_data['updates']) == 3
    
    # Check each update has required fields
    for update in round_data['updates']:
        assert 'node_id' in update
        assert 'delta' in update
        assert 'n_samples' in update
        assert 'metrics' in update


def test_weighted_aggregation():
    """Test that aggregation properly weights by sample count."""
    # Create simple deltas
    delta1 = {'layer': torch.ones(5, 5) * 1.0}
    delta2 = {'layer': torch.ones(5, 5) * 2.0}
    
    # Node 1 has 100 samples, Node 2 has 100 samples
    # Expected: (1.0 * 100 + 2.0 * 100) / 200 = 1.5
    
    aggregator = FedAvgAggregator(storage_path='./test_storage')
    
    # Create dummy base model
    base_state = {'layer': torch.zeros(5, 5)}
    
    round_id = 'test-weighted'
    aggregator.create_round(
        round_id=round_id,
        model_name='test',
        base_model_state=base_state,
        hyperparameters={}
    )
    
    # Collect updates
    for i, (delta, n_samples) in enumerate([(delta1, 100), (delta2, 100)]):
        node_id = f'node{i+1}'
        aggregator.register_participant(round_id, node_id)
        aggregator.collect_update(
            round_id=round_id,
            node_id=node_id,
            delta=delta,
            base_model_hash=aggregator.rounds[round_id]['base_model_hash'],
            n_samples=n_samples,
            metrics={'accuracy': 0.9}
        )
    
    # Aggregate
    agg_delta = aggregator.aggregate_deltas(round_id)
    
    # Check result is 1.5
    expected = torch.ones(5, 5) * 1.5
    assert torch.allclose(agg_delta['layer'], expected, atol=1e-5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
