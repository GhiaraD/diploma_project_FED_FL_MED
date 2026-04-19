"""
Federated Learning Aggregator Module - Central server FL operations.

Handles:
- Collecting updates from nodes
- Validating updates (hash, format, outliers)
- FedAvg aggregation: ΔW_avg = Σ(n_i/Σn_i)*ΔW_i
- Applying aggregated delta: W_{t+1} = W_t + ΔW_avg
"""
import torch
import torch.nn as nn
from typing import Dict, List, Tuple, Optional
import numpy as np
from pathlib import Path

from .utils_hash import compute_model_hash


class FedAvgAggregator:
    """
    Federated Averaging (FedAvg) aggregator for central server.
    
    Implements the FedAvg algorithm:
    1. Collect delta updates from nodes
    2. Weight by number of samples: w_i = n_i / Σn_i
    3. Aggregate: ΔW_avg = Σ(w_i * ΔW_i)
    4. Update global model: W_{t+1} = W_t + ΔW_avg
    """
    
    def __init__(
        self,
        storage_path: str = "./storage/central",
        min_nodes: int = 2,
        outlier_threshold: float = 3.0
    ):
        """
        Initialize FedAvg aggregator.
        
        Args:
            storage_path: Path to store global models
            min_nodes: Minimum number of nodes required for aggregation
            outlier_threshold: Z-score threshold for outlier detection
        """
        self.storage_path = Path(storage_path)
        self.min_nodes = min_nodes
        self.outlier_threshold = outlier_threshold
        
        # Create storage directories
        self.models_dir = self.storage_path / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Track rounds
        self.rounds = {}  # round_id -> round_data
    
    def create_round(
        self,
        round_id: str,
        model_name: str,
        base_model_state: Dict[str, torch.Tensor],
        hyperparameters: Dict
    ) -> Dict:
        """
        Create a new FL round.
        
        Args:
            round_id: Unique round identifier (e.g., 'R-1')
            model_name: Model architecture name
            base_model_state: Initial global model state dict
            hyperparameters: Training hyperparameters for nodes
            
        Returns:
            Round metadata
        """
        # Compute base model hash
        base_hash = compute_model_hash(base_model_state)
        
        # Save base model
        model_path = self.models_dir / f"global_{round_id}.pt"
        torch.save(base_model_state, model_path)
        
        # Initialize round data
        self.rounds[round_id] = {
            'round_id': round_id,
            'model_name': model_name,
            'base_model_hash': base_hash,
            'base_model_path': str(model_path),
            'hyperparameters': hyperparameters,
            'participants': [],
            'updates': [],
            'status': 'created',
            'aggregated_model_path': None,
            'aggregated_metrics': None
        }
        
        print(f"[Central] Round {round_id} created")
        print(f"[Central]   - Model: {model_name}")
        print(f"[Central]   - Base hash: {base_hash[:16]}...")
        print(f"[Central]   - Hyperparameters: {hyperparameters}")
        
        return self.rounds[round_id]
    
    def register_participant(self, round_id: str, node_id: str):
        """
        Register a node as participant in a round.
        
        Args:
            round_id: Round identifier
            node_id: Node identifier
        """
        if round_id not in self.rounds:
            raise ValueError(f"Round {round_id} not found")
        
        if node_id not in self.rounds[round_id]['participants']:
            self.rounds[round_id]['participants'].append(node_id)
            print(f"[Central] Node {node_id} joined round {round_id}")
    
    def collect_update(
        self,
        round_id: str,
        node_id: str,
        delta: Dict[str, torch.Tensor],
        base_model_hash: str,
        n_samples: int,
        metrics: Dict
    ) -> Dict:
        """
        Collect delta update from a node.
        
        Args:
            round_id: Round identifier
            node_id: Node identifier
            delta: Delta weights from node
            base_model_hash: Hash of base model used by node
            n_samples: Number of training samples
            metrics: Training metrics from node
            
        Returns:
            Confirmation dict
            
        Raises:
            ValueError: If validation fails
        """
        if round_id not in self.rounds:
            raise ValueError(f"Round {round_id} not found")
        
        round_data = self.rounds[round_id]
        
        # Validate base model hash
        if base_model_hash != round_data['base_model_hash']:
            raise ValueError(
                f"Base model hash mismatch for {node_id}! "
                f"Expected {round_data['base_model_hash'][:16]}..., "
                f"got {base_model_hash[:16]}..."
            )
        
        # Store update
        update = {
            'node_id': node_id,
            'delta': delta,
            'n_samples': n_samples,
            'metrics': metrics
        }
        
        round_data['updates'].append(update)
        
        print(f"[Central] Update received from {node_id}")
        print(f"[Central]   - Samples: {n_samples}")
        print(f"[Central]   - Metrics: {metrics}")
        print(f"[Central]   - Total updates: {len(round_data['updates'])}/{len(round_data['participants'])}")
        
        return {
            'status': 'accepted',
            'round_id': round_id,
            'updates_received': len(round_data['updates']),
            'total_participants': len(round_data['participants'])
        }
    
    def validate_updates(self, round_id: str) -> Tuple[bool, List[str]]:
        """
        Validate collected updates for outliers.
        
        Args:
            round_id: Round identifier
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        if round_id not in self.rounds:
            return False, [f"Round {round_id} not found"]
        
        round_data = self.rounds[round_id]
        updates = round_data['updates']
        issues = []
        
        if len(updates) < self.min_nodes:
            issues.append(f"Insufficient updates: {len(updates)} < {self.min_nodes}")
            return False, issues
        
        # Check for outliers based on delta norms (only float tensors)
        delta_norms = []
        for update in updates:
            delta = update['delta']
            norm = sum(
                torch.norm(d.float()).item() ** 2 
                for d in delta.values() 
                if d.dtype in [torch.float32, torch.float64, torch.float16]
            ) ** 0.5
            delta_norms.append(norm)
        
        # Z-score outlier detection
        if len(delta_norms) > 2:
            mean_norm = np.mean(delta_norms)
            std_norm = np.std(delta_norms)
            
            if std_norm > 0:
                z_scores = [(n - mean_norm) / std_norm for n in delta_norms]
                
                for i, (update, z_score) in enumerate(zip(updates, z_scores)):
                    if abs(z_score) > self.outlier_threshold:
                        issues.append(
                            f"Outlier detected: {update['node_id']} "
                            f"(z-score={z_score:.2f}, norm={delta_norms[i]:.4f})"
                        )
        
        is_valid = len(issues) == 0
        
        if is_valid:
            print(f"[Central] ✓ All updates validated for round {round_id}")
        else:
            print(f"[Central] ✗ Validation issues for round {round_id}:")
            for issue in issues:
                print(f"[Central]     - {issue}")
        
        return is_valid, issues
    
    def aggregate_deltas(
        self,
        round_id: str,
        remove_outliers: bool = False
    ) -> Dict[str, torch.Tensor]:
        """
        Aggregate delta updates using FedAvg.
        
        Formula: ΔW_avg = Σ(n_i/Σn_i) * ΔW_i
        
        Args:
            round_id: Round identifier
            remove_outliers: Whether to remove outlier updates (not implemented yet)
            
        Returns:
            Aggregated delta state dict
        """
        if round_id not in self.rounds:
            raise ValueError(f"Round {round_id} not found")
        
        round_data = self.rounds[round_id]
        updates = round_data['updates']
        
        if len(updates) == 0:
            raise ValueError(f"No updates to aggregate for round {round_id}")
        
        print(f"[Central] Aggregating {len(updates)} updates for round {round_id}...")
        
        # Calculate total samples
        total_samples = sum(u['n_samples'] for u in updates)
        
        # Validate consistency
        first_delta = updates[0]['delta']
        for update in updates:
            if update['delta'].keys() != first_delta.keys():
                raise ValueError("Inconsistent model structure across clients")
        
        # Initialize aggregated delta (preserve dtype for non-float tensors)
        aggregated_delta = {}
        for key in first_delta.keys():
            original_dtype = first_delta[key].dtype
            # Use float32 for float tensors (stability), preserve dtype for others
            if original_dtype in [torch.float32, torch.float64, torch.float16]:
                aggregated_delta[key] = torch.zeros_like(first_delta[key], dtype=torch.float32)
            else:
                # Keep original dtype for integer/long tensors (e.g., num_batches_tracked)
                aggregated_delta[key] = torch.zeros_like(first_delta[key], dtype=original_dtype)
        
        # Weighted aggregation
        if total_samples > 0:
            print(f"[Central] Using weighted average (total_samples={total_samples})")
        else:
            print(f"[Central] Using simple average (total_samples=0)")
        
        for update in updates:
            weight = (update['n_samples'] / total_samples 
                     if total_samples > 0 
                     else 1.0 / len(updates))
            delta = update['delta']
            
            for key in aggregated_delta.keys():
                if key in delta:
                    agg_tensor = aggregated_delta[key]
                    delta_tensor = delta[key]
                    
                    # Only aggregate float tensors (skip integer buffers like num_batches_tracked)
                    if agg_tensor.dtype in [torch.float32, torch.float64, torch.float16]:
                        # Align device + dtype (CRITICAL FIX)
                        delta_tensor = delta_tensor.to(
                            device=agg_tensor.device,
                            dtype=agg_tensor.dtype
                        )
                        aggregated_delta[key] += weight * delta_tensor
                    else:
                        # For integer tensors, just take the first value (no averaging)
                        if update == updates[0]:
                            aggregated_delta[key] = delta_tensor.to(device=agg_tensor.device)
        
        # Convert back to original dtype for float tensors that were promoted to float32
        for key in aggregated_delta.keys():
            original_dtype = first_delta[key].dtype
            current_dtype = aggregated_delta[key].dtype
            # Only convert if we promoted to float32 for aggregation
            if (original_dtype in [torch.float64, torch.float16] and 
                current_dtype == torch.float32):
                aggregated_delta[key] = aggregated_delta[key].to(original_dtype)
        
        # Calculate aggregation statistics (stable version)
        agg_norm = torch.sqrt(
            sum(torch.norm(d.float()) ** 2 
                for d in aggregated_delta.values() 
                if d.dtype in [torch.float32, torch.float64, torch.float16])
        ).item()
        
        print(f"[Central] ✓ Aggregation complete")
        print(f"[Central]   - Total samples: {total_samples}")
        print(f"[Central]   - Aggregated delta norm: {agg_norm:.4f}")
        
        return aggregated_delta
    
    def apply_delta(
        self,
        base_model_state: Dict[str, torch.Tensor],
        aggregated_delta: Dict[str, torch.Tensor]
    ) -> Dict[str, torch.Tensor]:
        """
        Apply aggregated delta to base model.
        
        Formula: W_{t+1} = W_t + ΔW_avg
        
        Args:
            base_model_state: Current global model state dict
            aggregated_delta: Aggregated delta from nodes
            
        Returns:
            New global model state dict
        """
        print(f"[Central] Applying aggregated delta to global model...")
        
        new_state = {}
        
        for key in base_model_state.keys():
            base_tensor = base_model_state[key]
            
            if key in aggregated_delta:
                delta_tensor = aggregated_delta[key]
                
                # Verificare shape
                if base_tensor.shape != delta_tensor.shape:
                    raise ValueError(
                        f"Shape mismatch for key '{key}': "
                        f"{base_tensor.shape} vs {delta_tensor.shape}"
                    )
                
                # Aplicăm delta DOAR pe tensori float
                if base_tensor.dtype in [torch.float32, torch.float64, torch.float16]:
                    delta_tensor = delta_tensor.to(
                        device=base_tensor.device,
                        dtype=base_tensor.dtype
                    )
                    new_state[key] = base_tensor + delta_tensor
                else:
                    # Nu modificăm tensori non-float (ex: buffers, embeddings index)
                    new_state[key] = base_tensor
            else:
                # Fallback (nu ar trebui să se întâmple)
                new_state[key] = base_tensor
        
        print(f"[Central] ✓ New global model created")
        
        return new_state
    
    def aggregate_round(
        self,
        round_id: str,
        validate: bool = True
    ) -> Dict:
        """
        Complete aggregation for a round.
        
        Steps:
        1. Validate updates
        2. Aggregate deltas
        3. Apply to base model
        4. Save new global model
        5. Aggregate metrics
        
        Args:
            round_id: Round identifier
            validate: Whether to validate updates first
            
        Returns:
            Dict with aggregation results
        """
        if round_id not in self.rounds:
            raise ValueError(f"Round {round_id} not found")
        
        round_data = self.rounds[round_id]
        
        print(f"[Central] ═══════════════════════════════════════")
        print(f"[Central] Starting aggregation for round {round_id}")
        print(f"[Central] ═══════════════════════════════════════")
        
        # Validate
        if validate:
            is_valid, issues = self.validate_updates(round_id)
            if not is_valid:
                raise ValueError(f"Validation failed: {issues}")
        
        # Detect device (prefer GPU if available)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[Central] Using device: {device}")
        
        # Load base model on detected device
        base_model_state = torch.load(
            round_data['base_model_path'],
            map_location=device  # Load directly on GPU if available
        )
        
        # Aggregate deltas
        aggregated_delta = self.aggregate_deltas(round_id)
        
        # Apply delta
        new_global_state = self.apply_delta(base_model_state, aggregated_delta)
        
        # Save new global model
        new_model_path = self.models_dir / f"global_{round_id}_aggregated.pt"
        try:
            torch.save(new_global_state, new_model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to save model: {e}")
        
        # Compute new model hash
        new_hash = compute_model_hash(new_global_state)
        
        # Aggregate metrics (fără bias din valori lipsă)
        updates = round_data['updates']
        total_samples = sum(u['n_samples'] for u in updates)
        
        aggregated_metrics = {}
        
        for metric_name in ['accuracy', 'f1', 'auc', 'precision', 'recall']:
            pairs = [
                (u['metrics'][metric_name], u['n_samples'])
                for u in updates
                if metric_name in u['metrics']
            ]
            
            if not pairs:
                continue
            
            if total_samples > 0:
                aggregated_metrics[metric_name] = sum(
                    v * (n / total_samples) for v, n in pairs
                )
            else:
                aggregated_metrics[metric_name] = sum(v for v, _ in pairs) / len(pairs)
        
        # Update round data
        round_data['status'] = 'aggregated'
        round_data['aggregated_model_path'] = str(new_model_path)
        round_data['aggregated_model_hash'] = new_hash
        round_data['aggregated_metrics'] = aggregated_metrics
        
        print(f"[Central] ✓ Round {round_id} aggregation complete")
        print(f"[Central]   - New model hash: {new_hash[:16]}...")
        print(f"[Central]   - Aggregated metrics: {aggregated_metrics}")
        print(f"[Central]   - Model saved to: {new_model_path}")
        
        return {
            'round_id': round_id,
            'status': 'success',
            'new_model_hash': new_hash,
            'new_model_path': str(new_model_path),
            'aggregated_metrics': aggregated_metrics,
            'total_samples': total_samples,
            'num_participants': len(updates)
        }
    
    def get_round_results(self, round_id: str) -> Dict:
        """
        Get aggregation results for a round.
        
        Args:
            round_id: Round identifier
            
        Returns:
            Dict with round results
        """
        if round_id not in self.rounds:
            raise ValueError(f"Round {round_id} not found")
        
        round_data = self.rounds[round_id]
        
        return {
            'round_id': round_id,
            'status': round_data['status'],
            'participants': round_data['participants'],
            'num_updates': len(round_data['updates']),
            'aggregated_metrics': round_data.get('aggregated_metrics'),
            'aggregated_model_hash': round_data.get('aggregated_model_hash'),
            'aggregated_model_path': round_data.get('aggregated_model_path')
        }
