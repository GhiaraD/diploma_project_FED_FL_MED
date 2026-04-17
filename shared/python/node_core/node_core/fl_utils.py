"""
Federated Learning Utilities - Helper functions for FL operations.
"""
import torch
import torch.nn as nn
from typing import Dict, List
import numpy as np


def compute_delta_statistics(delta: Dict[str, torch.Tensor]) -> Dict:
    """
    Compute statistics about a delta update.
    
    Args:
        delta: Delta state dict
        
    Returns:
        Dict with statistics (norm, mean, std, etc.)
    """
    # Flatten all delta values
    all_values = torch.cat([d.flatten() for d in delta.values()])
    
    # Compute statistics
    stats = {
        'total_params': all_values.numel(),
        'norm': torch.norm(all_values).item(),
        'mean': all_values.mean().item(),
        'std': all_values.std().item(),
        'min': all_values.min().item(),
        'max': all_values.max().item(),
        'abs_mean': all_values.abs().mean().item()
    }
    
    return stats


def compare_models(
    model1: nn.Module,
    model2: nn.Module
) -> Dict:
    """
    Compare two models and compute difference statistics.
    
    Args:
        model1: First model
        model2: Second model
        
    Returns:
        Dict with comparison statistics
    """
    state1 = model1.state_dict()
    state2 = model2.state_dict()
    
    # Compute differences
    differences = {}
    for key in state1.keys():
        if key in state2:
            differences[key] = state1[key] - state2[key]
    
    # Get statistics
    stats = compute_delta_statistics(differences)
    
    return stats


def scale_delta(
    delta: Dict[str, torch.Tensor],
    scale_factor: float
) -> Dict[str, torch.Tensor]:
    """
    Scale a delta by a constant factor.
    
    Args:
        delta: Delta state dict
        scale_factor: Scaling factor
        
    Returns:
        Scaled delta
    """
    scaled_delta = {}
    
    for key, value in delta.items():
        scaled_delta[key] = value * scale_factor
    
    return scaled_delta


def clip_delta(
    delta: Dict[str, torch.Tensor],
    max_norm: float
) -> Dict[str, torch.Tensor]:
    """
    Clip delta to maximum norm (for privacy/stability).
    
    Args:
        delta: Delta state dict
        max_norm: Maximum allowed norm
        
    Returns:
        Clipped delta
    """
    # Compute current norm
    current_norm = sum(torch.norm(d).item() ** 2 for d in delta.values()) ** 0.5
    
    if current_norm > max_norm:
        # Scale down to max_norm
        scale_factor = max_norm / current_norm
        return scale_delta(delta, scale_factor)
    
    return delta


def add_noise_to_delta(
    delta: Dict[str, torch.Tensor],
    noise_scale: float,
    device: str = 'cpu'
) -> Dict[str, torch.Tensor]:
    """
    Add Gaussian noise to delta (for differential privacy).
    
    Args:
        delta: Delta state dict
        noise_scale: Standard deviation of noise
        device: Device to create noise on
        
    Returns:
        Noisy delta
    """
    noisy_delta = {}
    
    for key, value in delta.items():
        noise = torch.randn_like(value, device=device) * noise_scale
        noisy_delta[key] = value + noise
    
    return noisy_delta


def compute_cosine_similarity(
    delta1: Dict[str, torch.Tensor],
    delta2: Dict[str, torch.Tensor]
) -> float:
    """
    Compute cosine similarity between two deltas.
    
    Args:
        delta1: First delta
        delta2: Second delta
        
    Returns:
        Cosine similarity in [-1, 1]
    """
    # Flatten deltas
    vec1 = torch.cat([d.flatten() for d in delta1.values()])
    vec2 = torch.cat([d.flatten() for d in delta2.values()])
    
    # Compute cosine similarity
    cos_sim = torch.nn.functional.cosine_similarity(
        vec1.unsqueeze(0),
        vec2.unsqueeze(0)
    ).item()
    
    return cos_sim


def aggregate_metrics(
    metrics_list: List[Dict],
    sample_counts: List[int]
) -> Dict:
    """
    Aggregate metrics from multiple nodes using weighted average.
    
    Args:
        metrics_list: List of metric dicts from nodes
        sample_counts: Number of samples per node
        
    Returns:
        Aggregated metrics dict
    """
    if not metrics_list or not sample_counts:
        return {}
    
    total_samples = sum(sample_counts)
    weights = [n / total_samples for n in sample_counts]
    
    aggregated = {}
    
    # Get all metric keys
    all_keys = set()
    for metrics in metrics_list:
        all_keys.update(metrics.keys())
    
    # Aggregate each metric
    for key in all_keys:
        values = [m.get(key, 0) for m in metrics_list]
        
        # Skip non-numeric values
        if not all(isinstance(v, (int, float)) for v in values):
            continue
        
        # Weighted average
        aggregated[key] = sum(v * w for v, w in zip(values, weights))
    
    return aggregated


def check_model_compatibility(
    state_dict1: Dict[str, torch.Tensor],
    state_dict2: Dict[str, torch.Tensor]
) -> bool:
    """
    Check if two state dicts are compatible (same keys and shapes).
    
    Args:
        state_dict1: First state dict
        state_dict2: Second state dict
        
    Returns:
        True if compatible, False otherwise
    """
    # Check keys
    if set(state_dict1.keys()) != set(state_dict2.keys()):
        return False
    
    # Check shapes
    for key in state_dict1.keys():
        if state_dict1[key].shape != state_dict2[key].shape:
            return False
    
    return True


def compute_update_quality_score(
    delta: Dict[str, torch.Tensor],
    metrics: Dict,
    n_samples: int
) -> float:
    """
    Compute a quality score for an update (for filtering/weighting).
    
    Args:
        delta: Delta update
        metrics: Training metrics
        n_samples: Number of samples
        
    Returns:
        Quality score (higher is better)
    """
    # Base score from metrics
    accuracy = metrics.get('accuracy', 0)
    f1 = metrics.get('f1', 0)
    
    metric_score = (accuracy + f1) / 2
    
    # Penalize very large deltas (potential outliers)
    delta_norm = sum(torch.norm(d).item() ** 2 for d in delta.values()) ** 0.5
    norm_penalty = 1.0 / (1.0 + delta_norm / 100.0)
    
    # Reward more samples
    sample_bonus = np.log(n_samples + 1) / 10.0
    
    quality_score = metric_score * norm_penalty + sample_bonus
    
    return quality_score


def simulate_fl_round(
    num_nodes: int = 3,
    samples_per_node: List[int] = None,
    model_name: str = 'resnet18'
) -> Dict:
    """
    Simulate a FL round for testing (creates dummy deltas).
    
    Args:
        num_nodes: Number of nodes to simulate
        samples_per_node: Samples per node (random if None)
        model_name: Model architecture
        
    Returns:
        Dict with simulated round data
    """
    from .ml_models import get_model
    
    if samples_per_node is None:
        samples_per_node = [100 + i * 50 for i in range(num_nodes)]
    
    # Create base model
    base_model = get_model(model_name, num_classes=2, pretrained=False)
    base_state = base_model.state_dict()
    
    # Simulate updates
    updates = []
    
    for i in range(num_nodes):
        # Create slightly different model
        node_model = get_model(model_name, num_classes=2, pretrained=False)
        
        # Add small random changes
        node_state = node_model.state_dict()
        for key in node_state.keys():
            noise = torch.randn_like(node_state[key]) * 0.01
            node_state[key] = base_state[key] + noise
        
        # Compute delta
        delta = {}
        for key in base_state.keys():
            delta[key] = node_state[key] - base_state[key]
        
        # Simulate metrics
        metrics = {
            'accuracy': 0.85 + np.random.rand() * 0.1,
            'f1': 0.83 + np.random.rand() * 0.1,
            'auc': 0.90 + np.random.rand() * 0.05
        }
        
        updates.append({
            'node_id': f'node{i+1}',
            'delta': delta,
            'n_samples': samples_per_node[i],
            'metrics': metrics
        })
    
    return {
        'base_model_state': base_state,
        'updates': updates,
        'num_nodes': num_nodes
    }
