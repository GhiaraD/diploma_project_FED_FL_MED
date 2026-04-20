"""
Flower Strategy for Fed-Med-FL

Custom FedAvg strategy with:
- Model persistence (save global model after each round)
- Medical imaging metrics aggregation
- Integration with existing node_core utilities
"""
import torch
import torch.nn as nn
import flwr as fl
from typing import Dict, List, Tuple, Optional, Union
from pathlib import Path
import os

from .ml_models import get_model, save_model
from .utils_hash import compute_model_hash


class FedMedStrategy(fl.server.strategy.FedAvg):
    """
    Custom Flower Strategy for Fed-Med-FL.
    
    Extends FedAvg with:
    - Automatic model persistence after each round
    - Medical imaging specific metrics aggregation
    - Model hash tracking for integrity
    - Integration with existing storage structure
    """
    
    def __init__(
        self,
        model_name: str = "resnet18",
        num_classes: int = 2,
        storage_path: str = "/storage",
        save_models: bool = True,
        **kwargs
    ):
        """
        Initialize FedMed Strategy.
        
        Args:
            model_name: Model architecture (resnet18, densenet121, efficientnet_b0)
            num_classes: Number of output classes
            storage_path: Path to storage directory
            save_models: Whether to save models after each round
            **kwargs: Additional arguments for FedAvg
        """
        super().__init__(**kwargs)
        
        self.model_name = model_name
        self.num_classes = num_classes
        self.storage_path = Path(storage_path)
        self.save_models = save_models
        
        # Create storage directories
        self.models_dir = self.storage_path / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize global model
        self.model = get_model(model_name, num_classes=num_classes, pretrained=True)
        
        # Track rounds
        self.current_round = 0
        self.round_history = []
        
        print(f"[FedMedStrategy] Initialized with {model_name}")
        print(f"[FedMedStrategy] Storage: {self.storage_path}")
        print(f"[FedMedStrategy] Save models: {save_models}")
    
    def initialize_parameters(self, client_manager):
        """
        Return initial global model parameters.
        
        Called once at the start of FL to initialize the global model.
        """
        print("[FedMedStrategy] Initializing global model parameters...")
        
        # Get model parameters as numpy arrays
        parameters = [val.cpu().numpy() for val in self.model.state_dict().values()]
        
        # Save initial model
        if self.save_models:
            self._save_global_model(parameters, round_num=0)
        
        return fl.common.ndarrays_to_parameters(parameters)
    
    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[fl.server.client_proxy.ClientProxy, fl.common.FitRes]],
        failures: List[Union[Tuple[fl.server.client_proxy.ClientProxy, fl.common.FitRes], BaseException]],
    ):
        """
        Aggregate training results from clients.
        
        Args:
            server_round: Current round number
            results: List of (client, fit_result) tuples
            failures: List of failed clients
        
        Returns:
            - Aggregated parameters
            - Aggregated metrics
        """
        self.current_round = server_round
        
        print(f"\n{'='*70}")
        print(f"[FedMedStrategy] Round {server_round}: Aggregating {len(results)} clients")
        print(f"{'='*70}")
        
        if not results:
            print("[FedMedStrategy] ✗ No results to aggregate")
            return None, {}
        
        # Log client metrics before aggregation
        for client, fit_res in results:
            metrics = fit_res.metrics
            num_samples = fit_res.num_examples
            print(f"[FedMedStrategy] Client {client.cid}:")
            print(f"  - Samples: {num_samples}")
            print(f"  - Metrics: {metrics}")
        
        # Call parent FedAvg aggregation
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, results, failures
        )
        
        if aggregated_parameters is not None:
            # Save aggregated model
            if self.save_models:
                parameters_list = fl.common.parameters_to_ndarrays(aggregated_parameters)
                self._save_global_model(parameters_list, server_round)
            
            # Log aggregated metrics
            print(f"\n[FedMedStrategy] ✓ Round {server_round} aggregation complete")
            if aggregated_metrics:
                print(f"[FedMedStrategy] Aggregated metrics: {aggregated_metrics}")
            
            # Store round history
            self.round_history.append({
                'round': server_round,
                'num_clients': len(results),
                'metrics': aggregated_metrics
            })
        
        return aggregated_parameters, aggregated_metrics
    
    def aggregate_evaluate(
        self,
        server_round: int,
        results: List[Tuple[fl.server.client_proxy.ClientProxy, fl.common.EvaluateRes]],
        failures: List[Union[Tuple[fl.server.client_proxy.ClientProxy, fl.common.EvaluateRes], BaseException]],
    ):
        """
        Aggregate evaluation results from clients.
        
        Args:
            server_round: Current round number
            results: List of (client, evaluate_result) tuples
            failures: List of failed clients
        
        Returns:
            - Aggregated loss
            - Aggregated metrics
        """
        if not results:
            return None, {}
        
        # Call parent aggregation
        aggregated_loss, aggregated_metrics = super().aggregate_evaluate(
            server_round, results, failures
        )
        
        print(f"\n[FedMedStrategy] Round {server_round} evaluation:")
        print(f"  - Aggregated loss: {aggregated_loss:.4f}")
        if aggregated_metrics:
            print(f"  - Aggregated metrics: {aggregated_metrics}")
        
        return aggregated_loss, aggregated_metrics
    
    def _save_global_model(self, parameters: List, round_num: int):
        """
        Save global model to disk.
        
        Args:
            parameters: Model parameters as list of numpy arrays
            round_num: Round number
        """
        try:
            # Convert parameters to state dict
            params_dict = zip(self.model.state_dict().keys(), parameters)
            state_dict = {k: torch.tensor(v) for k, v in params_dict}
            
            # Update model with new parameters
            self.model.load_state_dict(state_dict)
            
            # Compute hash
            model_hash = compute_model_hash(state_dict)
            
            # Save model
            model_path = self.models_dir / f"global_R-{round_num}.pt"
            
            metadata = {
                'round': round_num,
                'model_name': self.model_name,
                'num_classes': self.num_classes,
                'hash': model_hash,
                'history': self.round_history
            }
            
            save_model(self.model, str(model_path), metadata)
            
            print(f"[FedMedStrategy] ✓ Model saved: {model_path}")
            print(f"[FedMedStrategy]   Hash: {model_hash[:16]}...")
            
        except Exception as e:
            print(f"[FedMedStrategy] ✗ Failed to save model: {e}")
    
    def get_round_history(self) -> List[Dict]:
        """
        Get history of all rounds.
        
        Returns:
            List of round metadata dicts
        """
        return self.round_history
    
    def get_current_model_path(self) -> Optional[str]:
        """
        Get path to current global model.
        
        Returns:
            Path to model file or None
        """
        if self.current_round == 0:
            return None
        
        model_path = self.models_dir / f"global_R-{self.current_round}.pt"
        
        if model_path.exists():
            return str(model_path)
        
        return None


# ============================================================================
# Helper Functions
# ============================================================================

def create_fedmed_strategy(
    model_name: str = "resnet18",
    num_classes: int = 2,
    storage_path: str = "/storage",
    min_clients: int = 2,
    fraction_fit: float = 1.0,
    fraction_evaluate: float = 1.0,
    **kwargs
) -> FedMedStrategy:
    """
    Create FedMed strategy with common defaults.
    
    Args:
        model_name: Model architecture
        num_classes: Number of classes
        storage_path: Storage directory
        min_clients: Minimum number of clients
        fraction_fit: Fraction of clients for training
        fraction_evaluate: Fraction of clients for evaluation
        **kwargs: Additional strategy arguments
    
    Returns:
        Configured FedMedStrategy instance
    """
    strategy = FedMedStrategy(
        model_name=model_name,
        num_classes=num_classes,
        storage_path=storage_path,
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_evaluate,
        min_fit_clients=min_clients,
        min_evaluate_clients=min_clients,
        min_available_clients=min_clients,
        **kwargs
    )
    
    return strategy
