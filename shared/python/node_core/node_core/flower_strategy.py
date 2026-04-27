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
from .crypto_utils import create_payload_signer, verify_model_parameters, sign_model_parameters


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
        num_epochs: int = 2,
        learning_rate: float = 0.001,
        optimizer: str = "adam",
        enable_signing: bool = True,
        certificates_path: str = "/certificates",
        signature_policy: str = "log",  # "log", "warn", "reject"
        min_valid_signatures: float = 0.8,  # Minimum 80% must be valid
        **kwargs
    ):
        """
        Initialize FedMed Strategy.
        
        Args:
            model_name: Model architecture (resnet18, densenet121, efficientnet_b0)
            num_classes: Number of output classes
            storage_path: Path to storage directory
            save_models: Whether to save models after each round
            num_epochs: Number of epochs per round
            learning_rate: Learning rate for training
            optimizer: Optimizer name
            enable_signing: Enable payload signing and verification
            certificates_path: Path to certificates
            **kwargs: Additional arguments for FedAvg
        """
        super().__init__(**kwargs)
        
        self.model_name = model_name
        self.num_classes = num_classes
        self.storage_path = Path(storage_path)
        self.save_models = save_models
        self.num_epochs = num_epochs
        self.learning_rate = learning_rate
        self.optimizer = optimizer
        self.enable_signing = enable_signing
        self.signature_policy = signature_policy
        self.min_valid_signatures = min_valid_signatures
        
        # Create storage directories
        self.models_dir = self.storage_path / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize global model
        self.model = get_model(model_name, num_classes=num_classes, pretrained=True)
        
        # Initialize payload signer/verifier
        self.signer = None
        if enable_signing:
            try:
                self.signer = create_payload_signer(
                    node_id="central",
                    certificates_path=certificates_path,
                    is_central=True
                )
                if self.signer.is_ready():
                    print(f"[FedMedStrategy] 🔐 Payload signing/verification enabled")
                else:
                    print(f"[FedMedStrategy] ⚠️  Payload signing disabled (certificates not ready)")
                    self.enable_signing = False
            except Exception as e:
                print(f"[FedMedStrategy] ⚠️  Failed to initialize signer: {e}")
                self.enable_signing = False
        
        # Track rounds
        self.current_round = 0
        self.round_history = []
        
        # Track signature verification stats
        self.signature_stats = {
            'total_verifications': 0,
            'successful_verifications': 0,
            'failed_verifications': 0,
            'unsigned_parameters': 0
        }
        
        print(f"[FedMedStrategy] Initialized with {model_name}")
        print(f"[FedMedStrategy] Storage: {self.storage_path}")
        print(f"[FedMedStrategy] Save models: {save_models}")
        print(f"[FedMedStrategy] Training config: {num_epochs} epochs, lr={learning_rate}, optimizer={optimizer}")
        print(f"[FedMedStrategy] Signing: {'Enabled' if self.enable_signing else 'Disabled'}")
        if self.enable_signing:
            print(f"[FedMedStrategy] Signature Policy: {self.signature_policy}")
            print(f"[FedMedStrategy] Min Valid Signatures: {self.min_valid_signatures * 100:.0f}%")
    
    def configure_fit(
        self, 
        server_round: int, 
        parameters, 
        client_manager
    ):
        """
        Configure the next round of training.
        
        Uses default FedAvg client selection but adds training hyperparameters.
        """
        # Call parent to get default client selection
        config_list = super().configure_fit(server_round, parameters, client_manager)
        
        # Add hyperparameters to config
        if config_list:
            updated_config_list = []
            for client, fit_ins in config_list:
                # Merge existing config with hyperparameters and server_round
                new_config = {
                    **fit_ins.config,
                    "server_round": server_round,  # Add round number
                    "num_epochs": self.num_epochs,
                    "learning_rate": self.learning_rate,
                    "optimizer": self.optimizer,
                }
                new_fit_ins = fl.common.FitIns(fit_ins.parameters, new_config)
                updated_config_list.append((client, new_fit_ins))
            
            print(f"[FedMedStrategy] Round {server_round}: Configured {len(updated_config_list)} clients")
            print(f"[FedMedStrategy]   Hyperparameters: {self.num_epochs} epochs, lr={self.learning_rate}")
            
            return updated_config_list
        
        return config_list
    
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
        print(f"🔄 FEDERATED ROUND {server_round} - AGGREGATION")
        print(f"{'='*70}")
        print(f"  📥 Received results from {len(results)} client(s)")
        
        if failures:
            print(f"  ⚠️  {len(failures)} client(s) failed")
        
        if not results:
            print("  ✗ No results to aggregate")
            print(f"{'='*70}\n")
            return None, {}
        
        # Log client metrics and verify signatures
        print(f"\n  📊 Client Results:")
        clients_to_reject = []  # Track clients to reject based on policy
        
        for i, (client, fit_res) in enumerate(results, 1):
            metrics = fit_res.metrics
            num_samples = fit_res.num_examples
            acc = metrics.get('accuracy', 0)
            print(f"    {i}. Client {client.cid}:")
            print(f"       • Samples: {num_samples}")
            print(f"       • Accuracy: {acc:.2%}")
            print(f"       • Train Loss: {metrics.get('train_loss', 0):.4f}")
            print(f"       • Val Loss: {metrics.get('val_loss', 0):.4f}")
            
            # Verify signature if present
            if self.enable_signing and self.signer:
                signature_package_json = metrics.get('_signature_package')
                if signature_package_json:
                    # Deserialize JSON string to dict
                    import json
                    try:
                        signature_package = json.loads(signature_package_json)
                    except:
                        signature_package = None
                    
                    if signature_package and signature_package.get('signed'):
                        # Get parameters from fit_res
                        parameters = fl.common.parameters_to_ndarrays(fit_res.parameters)
                        
                        # Verify signature
                        is_valid, message = verify_model_parameters(
                            parameters=parameters,
                            signature_package=signature_package,
                            verifier=self.signer,
                            use_cache=True
                        )
                        
                        self.signature_stats['total_verifications'] += 1
                        
                        if is_valid:
                            print(f"       🔐 Signature: ✓ Valid")
                            self.signature_stats['successful_verifications'] += 1
                        else:
                            print(f"       🔐 Signature: ✗ Invalid - {message}")
                            self.signature_stats['failed_verifications'] += 1
                            
                            # Apply signature policy
                            if self.signature_policy == "reject":
                                print(f"       ⚠️  Policy: REJECT - Client will be excluded from aggregation")
                                clients_to_reject.append(client.cid)
                            elif self.signature_policy == "warn":
                                print(f"       ⚠️  Policy: WARN - Invalid signature detected but continuing")
                            else:  # "log"
                                print(f"       ℹ️  Policy: LOG - Invalid signature logged")
                    else:
                        print(f"       🔐 Signature: Not signed")
                        self.signature_stats['unsigned_parameters'] += 1
                else:
                    print(f"       🔐 Signature: Not signed")
                    self.signature_stats['unsigned_parameters'] += 1
        
        # Apply signature policy - filter out rejected clients
        if clients_to_reject:
            print(f"\n  🚫 Rejecting {len(clients_to_reject)} client(s) due to invalid signatures")
            results = [(c, r) for c, r in results if c.cid not in clients_to_reject]
            
            if not results:
                print("  ✗ No valid results remaining after signature policy enforcement")
                print(f"{'='*70}\n")
                return None, {}
        
        # Check if we meet minimum valid signatures threshold (for "warn" policy)
        if self.signature_policy == "warn" and self.signature_stats['total_verifications'] > 0:
            valid_ratio = self.signature_stats['successful_verifications'] / self.signature_stats['total_verifications']
            if valid_ratio < self.min_valid_signatures:
                print(f"\n  ⚠️  WARNING: Only {valid_ratio:.1%} signatures are valid (threshold: {self.min_valid_signatures:.1%})")
                print(f"  ⚠️  Consider investigating signature failures or switching to 'reject' policy")
        
        # Call parent FedAvg aggregation
        print(f"\n  🔄 Aggregating parameters...")
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, results, failures
        )
        
        if aggregated_parameters is not None:
            # Save aggregated model
            if self.save_models:
                parameters_list = fl.common.parameters_to_ndarrays(aggregated_parameters)
                self._save_global_model(parameters_list, server_round)
            
            # Log aggregated metrics
            print(f"\n{'='*70}")
            print(f"✅ ROUND {server_round} COMPLETE")
            print(f"{'='*70}")
            if aggregated_metrics:
                print(f"  📈 Aggregated Metrics:")
                for key, value in aggregated_metrics.items():
                    if isinstance(value, float):
                        if 'acc' in key.lower():
                            print(f"    • {key}: {value:.2%}")
                        else:
                            print(f"    • {key}: {value:.4f}")
                    else:
                        print(f"    • {key}: {value}")
            
            # Log signature verification stats
            if self.enable_signing:
                print(f"  🔐 Signature Verification Stats:")
                print(f"    • Total verifications: {self.signature_stats['total_verifications']}")
                print(f"    • Successful: {self.signature_stats['successful_verifications']}")
                print(f"    • Failed: {self.signature_stats['failed_verifications']}")
                print(f"    • Unsigned: {self.signature_stats['unsigned_parameters']}")
            
            print(f"{'='*70}\n")
            
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
    min_fit_clients: int = 1,  # Train 1 client at a time by default
    min_available_clients: int = 3,  # Wait for all clients to be available
    fraction_fit: float = 1.0,
    fraction_evaluate: float = 1.0,
    num_epochs: int = 5,
    learning_rate: float = 0.001,
    optimizer: str = "adam",
    enable_signing: bool = True,
    certificates_path: str = "/certificates",
    signature_policy: str = "log",  # "log", "warn", "reject"
    min_valid_signatures: float = 0.8,  # Minimum 80% must be valid
    **kwargs
) -> FedMedStrategy:
    """
    Create FedMed strategy with common defaults.
    
    Args:
        model_name: Model architecture
        num_classes: Number of classes
        storage_path: Storage directory
        min_clients: Minimum number of clients
        min_fit_clients: Minimum clients to train per round (1 = sequential)
        min_available_clients: Minimum clients that must be available
        fraction_fit: Fraction of clients for training
        fraction_evaluate: Fraction of clients for evaluation
        num_epochs: Number of epochs per round
        learning_rate: Learning rate for training
        optimizer: Optimizer name
        enable_signing: Enable payload signing and verification
        certificates_path: Path to certificates
        signature_policy: Policy for invalid signatures ("log", "warn", "reject")
        min_valid_signatures: Minimum fraction of valid signatures (for "warn" policy)
        **kwargs: Additional strategy arguments
    
    Returns:
        Configured FedMedStrategy instance
    """
    strategy = FedMedStrategy(
        model_name=model_name,
        num_classes=num_classes,
        storage_path=storage_path,
        num_epochs=num_epochs,
        learning_rate=learning_rate,
        optimizer=optimizer,
        enable_signing=enable_signing,
        certificates_path=certificates_path,
        signature_policy=signature_policy,
        min_valid_signatures=min_valid_signatures,
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_evaluate,
        min_fit_clients=min_fit_clients,
        min_evaluate_clients=min_clients,
        min_available_clients=min_available_clients,
        **kwargs
    )
    
    return strategy
